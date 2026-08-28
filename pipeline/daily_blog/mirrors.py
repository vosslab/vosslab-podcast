"""Refresh and inspect durable Git repository evidence caches."""

# Standard Library
import os
import subprocess

# local repo modules
import daily_blog.locks
import daily_blog.schema
import daily_blog.repository_contracts
import daily_blog.io_utils


#============================================
def _run_git(
	cache_path: str,
	arguments: list[str],
	check: bool = True,
) -> subprocess.CompletedProcess:
	"""Run one bounded Git command against a repository cache."""
	command = ["git", "-C", cache_path, *arguments]
	result = subprocess.run(
		command,
		check=False,
		text=True,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		timeout=300,
	)
	if check and result.returncode:
		message = result.stderr.strip() or result.stdout.strip()
		raise RuntimeError(f"Git command failed in {cache_path}: {message}")
	return result


#============================================
def is_git_cache(path: str) -> bool:
	"""Return whether a path is a physical Git working tree."""
	if not os.path.isdir(path) or os.path.islink(path):
		return False
	result = _run_git(path, ["rev-parse", "--is-inside-work-tree"], check=False)
	valid = result.returncode == 0 and result.stdout.strip() == "true"
	return valid


#============================================
def _default_revision(cache_path: str) -> str:
	"""Resolve the fetched default revision to one exact Git object."""
	symbolic = _run_git(
		cache_path,
		["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"],
		check=False,
	)
	candidates = []
	if symbolic.returncode == 0 and symbolic.stdout.strip():
		candidates.append(symbolic.stdout.strip())
	candidates.extend(("refs/remotes/origin/main", "refs/remotes/origin/master", "HEAD"))
	for candidate in candidates:
		result = _run_git(cache_path, ["rev-parse", "--verify", f"{candidate}^{{commit}}"], check=False)
		if result.returncode == 0:
			return result.stdout.strip()
	return ""


#============================================
def _ref_fingerprint(cache_path: str) -> str:
	"""Hash all local and fetched branch refs that can locate date activity."""
	result = _run_git(
		cache_path,
		[
			"for-each-ref",
			"--format=%(refname) %(objectname)",
			"refs/heads",
			"refs/remotes/origin",
		],
	)
	lines = sorted(line.strip() for line in result.stdout.splitlines() if line.strip())
	fingerprint = daily_blog.io_utils.hash_value(lines)
	return fingerprint


#============================================
def _object_available(cache_path: str, revision: str) -> bool:
	"""Return whether one exact commit object is locally available."""
	if not revision:
		return False
	result = _run_git(cache_path, ["cat-file", "-e", f"{revision}^{{commit}}"], check=False)
	return result.returncode == 0


class MirrorManager:
	"""Reconcile one authoritative owner roster into durable Git caches."""

	#============================================
	def __init__(
		self,
		cache_root: str,
		roster: daily_blog.repository_contracts.RepositoryRoster,
	) -> None:
		"""Configure the owner-qualified cache root and exact repository roster."""
		self.cache_root = os.path.abspath(cache_root)
		self.roster = daily_blog.repository_contracts.RepositoryRoster.from_dict(roster.to_dict())
		self.resolved_cache_root = ""
		self._ensure_safe_cache_root()

	#============================================
	def _ensure_safe_cache_root(self) -> None:
		"""Create one physical cache root and resolve its durable filesystem identity."""
		if os.path.lexists(self.cache_root) and os.path.islink(self.cache_root):
			raise RuntimeError("Repository cache root must not be a symlink.")
		os.makedirs(self.cache_root, exist_ok=True)
		if not os.path.isdir(self.cache_root) or os.path.islink(self.cache_root):
			raise RuntimeError("Repository cache root must be a physical directory.")
		self.resolved_cache_root = os.path.realpath(self.cache_root)

	#============================================
	def _safe_child_path(self, *components: str) -> str:
		"""Return one non-symlink descendant whose resolved path remains under the cache root."""
		path = os.path.abspath(os.path.join(self.cache_root, *components))
		if os.path.commonpath((self.cache_root, path)) != self.cache_root:
			raise RuntimeError("Repository cache path escapes the configured mirror root.")
		current = self.cache_root
		for index, component in enumerate(components):
			current = os.path.join(current, component)
			if not os.path.lexists(current):
				continue
			if os.path.islink(current):
				raise RuntimeError("Repository cache paths must not contain symlinks.")
			if index < len(components) - 1 and not os.path.isdir(current):
				raise RuntimeError("Repository cache path has a non-directory parent.")
		resolved_path = os.path.realpath(path)
		if os.path.commonpath((self.resolved_cache_root, resolved_path)) != self.resolved_cache_root:
			raise RuntimeError("Repository cache path resolves outside the mirror root.")
		return path

	#============================================
	def _cache_path(self, record: daily_blog.repository_contracts.RepositoryRecord) -> str:
		"""Derive one owner-qualified path from a validated repository identity."""
		owner, name = record.repository.split("/", 1)
		return self._safe_child_path(owner, name)

	#============================================
	def _lock_path(self, record: daily_blog.repository_contracts.RepositoryRecord) -> str:
		"""Return one collision-free lock path for an owner-qualified repository."""
		owner, name = record.repository.split("/", 1)
		return self._safe_child_path(".locks", owner, f"{name}.lock")

	#============================================
	def _ensure_roster_clones(self) -> list[tuple[str, daily_blog.repository_contracts.RepositoryRecord]]:
		"""Clone every roster repository that has no durable cache yet."""
		self._ensure_safe_cache_root()
		paths = []
		for record in self.roster.repositories:
			path = self._cache_path(record)
			lock_path = self._lock_path(record)
			with daily_blog.locks.FileLock(lock_path):
				if not os.path.exists(path):
					result = subprocess.run(
						["git", "clone", "--no-tags", record.clone_url, path],
						check=False,
						text=True,
						stdout=subprocess.PIPE,
						stderr=subprocess.PIPE,
						timeout=600,
					)
					if result.returncode:
						message = result.stderr.strip() or result.stdout.strip()
						raise RuntimeError(
							f"Git mirror clone failed for {record.repository}: {message}"
						)
			if not is_git_cache(path):
				raise RuntimeError(f"Roster mirror is not a Git working tree: {path}")
			paths.append((path, record))
		return paths

	#============================================
	def _refresh_one(
		self,
		cache_path: str,
		record: daily_blog.repository_contracts.RepositoryRecord,
		refresh: bool,
	) -> dict:
		"""Refresh one cache and return a complete inspectable manifest entry."""
		expected_path = self._cache_path(record)
		if os.path.abspath(cache_path) != expected_path:
			raise RuntimeError("Repository cache path does not match its roster identity.")
		lock_path = self._lock_path(record)
		refresh_result = "skipped"
		refresh_error = ""
		with daily_blog.locks.FileLock(lock_path):
			origin_result = _run_git(cache_path, ["remote", "get-url", "origin"], check=False)
			if origin_result.returncode:
				raise RuntimeError(f"Mirror has no readable origin URL: {cache_path}")
			origin_url = origin_result.stdout.strip()
			if origin_url != record.clone_url:
				raise RuntimeError(
					f"Mirror origin does not exactly match owner roster clone URL: {record.repository}"
				)
			if refresh:
				shallow = _run_git(
					cache_path,
					["rev-parse", "--is-shallow-repository"],
					check=False,
				)
				fetch_arguments = [
					"fetch",
					"--prune",
					"--tags",
					"origin",
					"+refs/heads/*:refs/remotes/origin/*",
				]
				if shallow.returncode == 0 and shallow.stdout.strip() == "true":
					fetch_arguments.insert(1, "--unshallow")
				fetch = _run_git(cache_path, fetch_arguments, check=False)
				if fetch.returncode:
					refresh_result = "failed"
					refresh_error = fetch.stderr.strip() or fetch.stdout.strip()
				else:
					refresh_result = "refreshed"
			default_revision = _default_revision(cache_path)
			available = _object_available(cache_path, default_revision)
			ref_fingerprint = _ref_fingerprint(cache_path)
		entry = {
			"repository": record.repository,
			"repository_url": record.repository_url,
			"clone_url": record.clone_url,
			"created_at": record.created_at,
			"is_fork": record.is_fork,
			"roster_id": self.roster.roster_id,
			"cache_path": cache_path,
			"refresh_result": refresh_result,
			"refresh_error": refresh_error,
			"default_revision": default_revision,
			"object_available": available,
			"ref_fingerprint": ref_fingerprint,
			"refreshed_at": daily_blog.schema.utc_now(),
		}
		return entry

	#============================================
	def refresh_all(self, refresh: bool = True) -> list[dict]:
		"""Refresh exactly the repositories in the authoritative owner roster."""
		paths = self._ensure_roster_clones()
		entries = [self._refresh_one(path, record, refresh) for path, record in paths]
		entries.sort(key=lambda item: item["repository"].casefold())
		return entries
