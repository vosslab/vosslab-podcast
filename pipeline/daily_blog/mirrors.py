"""Refresh and inspect durable Git repository evidence caches."""

# Standard Library
import os
import re
import subprocess

# local repo modules
import daily_blog.locks
import daily_blog.schema
import daily_blog.io_utils


GITHUB_URL_RE = re.compile(
	r"^https://github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9._-]+?)(?:\.git)?$"
)


#============================================
def repository_from_url(url: str) -> str:
	"""Return the canonical owner/repository name from one HTTPS GitHub URL."""
	match = GITHUB_URL_RE.fullmatch(url.strip())
	if not match:
		raise RuntimeError(f"Mirror origin must be one HTTPS GitHub repository URL: {url}")
	repository = f"{match.group(1)}/{match.group(2)}"
	return repository


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
def discover_cache_paths(root: str) -> list[str]:
	"""Discover direct physical Git working trees below the cache root."""
	if not os.path.isdir(root):
		return []
	paths = []
	for name in sorted(os.listdir(root), key=str.casefold):
		path = os.path.join(root, name)
		if is_git_cache(path):
			paths.append(path)
	return paths


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
	"""Refresh all configured/discovered caches under per-cache locks."""

	#============================================
	def __init__(self, cache_root: str, repository_urls: tuple[str, ...]) -> None:
		"""Configure the durable cache root and optional clone sources."""
		self.cache_root = os.path.abspath(cache_root)
		self.repository_urls = repository_urls

	#============================================
	def _ensure_configured_clones(self) -> list[str]:
		"""Clone configured repositories that have no durable cache yet."""
		os.makedirs(self.cache_root, exist_ok=True)
		paths = []
		for url in self.repository_urls:
			repository = repository_from_url(url)
			name = repository.split("/", 1)[1]
			path = os.path.join(self.cache_root, name)
			lock_path = os.path.join(self.cache_root, ".locks", f"{name}.lock")
			with daily_blog.locks.FileLock(lock_path):
				if not os.path.exists(path):
					result = subprocess.run(
						["git", "clone", "--no-tags", url, path],
						check=False,
						text=True,
						stdout=subprocess.PIPE,
						stderr=subprocess.PIPE,
						timeout=600,
					)
					if result.returncode:
						message = result.stderr.strip() or result.stdout.strip()
						raise RuntimeError(f"Git mirror clone failed for {url}: {message}")
			if not is_git_cache(path):
				raise RuntimeError(f"Configured mirror is not a Git working tree: {path}")
			paths.append(path)
		return paths

	#============================================
	def _refresh_one(self, cache_path: str, refresh: bool) -> dict:
		"""Refresh one cache and return a complete inspectable manifest entry."""
		name = os.path.basename(cache_path)
		lock_path = os.path.join(self.cache_root, ".locks", f"{name}.lock")
		refresh_result = "skipped"
		refresh_error = ""
		with daily_blog.locks.FileLock(lock_path):
			origin_result = _run_git(cache_path, ["remote", "get-url", "origin"], check=False)
			if origin_result.returncode:
				raise RuntimeError(f"Mirror has no readable origin URL: {cache_path}")
			origin_url = origin_result.stdout.strip()
			repository = repository_from_url(origin_url)
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
			"repository": repository,
			"repository_url": origin_url,
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
		"""Refresh every configured and discovered cache in repository order."""
		configured = self._ensure_configured_clones() if self.repository_urls else []
		paths = set(discover_cache_paths(self.cache_root))
		paths.update(configured)
		if not paths:
			raise RuntimeError(f"No Git repository caches found under {self.cache_root}")
		entries = [self._refresh_one(path, refresh) for path in sorted(paths, key=str.casefold)]
		entries.sort(key=lambda item: item["repository"].casefold())
		return entries
