"""Exact-revision evidence providers and authority-aware packet assembly."""

# Standard Library
import os
import re
import subprocess

# local repo modules
import daily_blog.schema
import daily_blog.io_utils


IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp")
DOCUMENT_SUFFIXES = (".md", ".rst", ".txt")
LEVEL_TWO_HEADING_RE = re.compile(r"^##\s+([^\n]+)$", re.MULTILINE)


#============================================
def _run_git_text(cache_path: str, arguments: list[str], check: bool = True) -> str:
	"""Run one exact-object Git query and return decoded text."""
	result = subprocess.run(
		["git", "-C", cache_path, *arguments],
		check=False,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		timeout=300,
	)
	if check and result.returncode:
		message = result.stderr.decode("utf-8", errors="replace").strip()
		raise RuntimeError(f"Git evidence query failed in {cache_path}: {message}")
	text = result.stdout.decode("utf-8", errors="replace")
	return text


#============================================
def _run_git_bytes(cache_path: str, arguments: list[str], check: bool = True) -> bytes:
	"""Run one exact-object Git query and return raw bytes."""
	result = subprocess.run(
		["git", "-C", cache_path, *arguments],
		check=False,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		timeout=300,
	)
	if check and result.returncode:
		message = result.stderr.decode("utf-8", errors="replace").strip()
		raise RuntimeError(f"Git evidence query failed in {cache_path}: {message}")
	return result.stdout


#============================================
def extract_dated_sections(changelog: str, report_date: str) -> str:
	"""Extract every complete matching level-two dated changelog section."""
	matches = list(LEVEL_TWO_HEADING_RE.finditer(changelog))
	sections = []
	for index, match in enumerate(matches):
		heading = match.group(1).strip()
		if heading != report_date and not heading.startswith(report_date + " "):
			continue
		end = matches[index + 1].start() if index + 1 < len(matches) else len(changelog)
		section = changelog[match.start():end].rstrip()
		sections.append(section)
	text = "\n\n".join(sections)
	if text:
		text += "\n"
	return text


#============================================
def _safe_asset_name(path: str) -> str:
	"""Return a portable ASCII basename for one commit-selected image."""
	name = os.path.basename(path)
	stem, suffix = os.path.splitext(name)
	clean_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_").lower()
	clean_suffix = suffix.lower()
	if not clean_stem:
		clean_stem = "image"
	name = clean_stem[:80] + clean_suffix
	return name


class GitSnapshot:
	"""Read evidence solely from one repository's exact Git objects."""

	#============================================
	def __init__(self, activity: daily_blog.schema.RepositoryActivity) -> None:
		"""Bind all reads to one typed activity range."""
		self.activity = activity

	#============================================
	def object_exists(self, commit: str, path: str) -> bool:
		"""Return whether one path exists as a blob at the exact commit."""
		result = subprocess.run(
			[
				"git",
				"-C",
				self.activity.cache_path,
				"cat-file",
				"-e",
				f"{commit}:{path}",
			],
			check=False,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			timeout=60,
		)
		return result.returncode == 0

	#============================================
	def blob_hash(self, commit: str, path: str) -> str:
		"""Resolve one commit-selected path to its exact Git blob hash."""
		text = _run_git_text(
			self.activity.cache_path,
			["rev-parse", "--verify", f"{commit}:{path}"],
		)
		return text.strip()

	#============================================
	def read_text(self, commit: str, path: str) -> str:
		"""Read one text blob from the exact commit."""
		text = _run_git_text(self.activity.cache_path, ["show", f"{commit}:{path}"])
		return text

	#============================================
	def read_bytes(self, commit: str, path: str) -> bytes:
		"""Read one binary blob from the exact commit."""
		contents = _run_git_bytes(self.activity.cache_path, ["show", f"{commit}:{path}"])
		return contents

	#============================================
	def changed_paths(self, revision: daily_blog.schema.RevisionRange) -> list[str]:
		"""Return paths changed across one exact parent boundary."""
		if revision.base_commit:
			arguments = [
				"diff",
				"--name-only",
				"-z",
				revision.base_commit,
				revision.final_commit,
			]
		else:
			arguments = [
				"diff-tree",
				"--root",
				"--no-commit-id",
				"--name-only",
				"-r",
				"-z",
				revision.final_commit,
			]
		contents = _run_git_bytes(self.activity.cache_path, arguments)
		paths = [
			item.decode("utf-8", errors="replace")
			for item in contents.split(b"\0")
			if item
		]
		return sorted(set(paths), key=str.casefold)

	#============================================
	def bounded_diff(
		self,
		revision: daily_blog.schema.RevisionRange,
		limit: int,
	) -> tuple[str, bool]:
		"""Return one exact parent patch bounded to its source allocation."""
		if revision.base_commit:
			arguments = [
				"diff",
				"--no-ext-diff",
				"--unified=3",
				revision.base_commit,
				revision.final_commit,
			]
		else:
			arguments = [
				"show",
				"--format=",
				"--no-ext-diff",
				"--unified=3",
				revision.final_commit,
			]
		text = _run_git_text(self.activity.cache_path, arguments)
		if len(text) <= limit:
			return text, False
		marker = "\n[Diff evidence reached its configured character budget.]\n"
		bounded = text[: max(0, limit - len(marker))].rstrip() + marker
		return bounded, True


class ChangelogEvidenceProvider:
	"""Extract complete report-date changelogs at attributed branch tips."""

	#============================================
	def collect(
		self,
		activity: daily_blog.schema.RepositoryActivity,
		snapshot: GitSnapshot,
	) -> list[daily_blog.schema.EvidenceItem]:
		"""Return primary narrative evidence from every distinct tip snapshot."""
		path = "docs/CHANGELOG.md"
		items = []
		seen_blobs = set()
		for commit in activity.snapshot_commits:
			if not snapshot.object_exists(commit, path):
				continue
			blob_hash = snapshot.blob_hash(commit, path)
			if blob_hash in seen_blobs:
				continue
			text = snapshot.read_text(commit, path)
			sections = extract_dated_sections(text, self.report_date)
			if not sections:
				continue
			seen_blobs.add(blob_hash)
			items.append(
				daily_blog.schema.EvidenceItem.create(
					"dated_changelog",
					activity.repository,
					commit,
					path,
					blob_hash,
					sections,
					f"git show {commit}:{path}",
				)
			)
		return items

	#============================================
	def __init__(self, report_date: str) -> None:
		"""Bind this provider to one changelog date."""
		self.report_date = report_date


class DiffEvidenceProvider:
	"""Capture bounded parent-to-final changed paths and patches."""

	#============================================
	def __init__(self, limit: int) -> None:
		"""Set the explicit per-repository diff budget."""
		self.limit = limit

	#============================================
	def collect(
		self,
		activity: daily_blog.schema.RepositoryActivity,
		snapshot: GitSnapshot,
	) -> list[daily_blog.schema.EvidenceItem]:
		"""Return one budgeted technical item for every exact revision range."""
		allocation = max(1, self.limit // len(activity.revision_ranges))
		items = []
		for revision in activity.revision_ranges:
			paths = snapshot.changed_paths(revision)
			patch, truncated = snapshot.bounded_diff(revision, allocation)
			path_text = "Changed paths:\n" + "\n".join(f"- {path}" for path in paths)
			content = path_text + "\n\nPatch:\n" + patch
			range_text = revision.base_commit or "empty-tree"
			item = daily_blog.schema.EvidenceItem.create(
				"diff",
				activity.repository,
				revision.final_commit,
				"",
				"",
				content,
				f"git diff {range_text} {revision.final_commit}",
				truncated=truncated,
			)
			items.append(_truncate_item(item, allocation))
		return items


class DocumentationEvidenceProvider:
	"""Capture changed documentation, release notes, and final README context."""

	#============================================
	def collect(
		self,
		activity: daily_blog.schema.RepositoryActivity,
		snapshot: GitSnapshot,
	) -> list[daily_blog.schema.EvidenceItem]:
		"""Return documentation from branch tips and every changed range."""
		items = []
		seen = set()
		readme_paths = ("README.md", "README.rst", "README.txt")
		for commit in activity.snapshot_commits:
			for readme_path in readme_paths:
				if not snapshot.object_exists(commit, readme_path):
					continue
				blob_hash = snapshot.blob_hash(commit, readme_path)
				identity = ("readme_context", readme_path, blob_hash)
				if identity not in seen:
					seen.add(identity)
					content = snapshot.read_text(commit, readme_path)
					items.append(
						daily_blog.schema.EvidenceItem.create(
							"readme_context",
							activity.repository,
							commit,
							readme_path,
							blob_hash,
							content,
							f"git show {commit}:{readme_path}",
						)
					)
				break
		for revision in activity.revision_ranges:
			for path in snapshot.changed_paths(revision):
				lower = path.casefold()
				basename = os.path.basename(lower)
				is_document = lower.endswith(DOCUMENT_SUFFIXES)
				is_relevant = lower.startswith("docs/") or basename.startswith(
					("readme", "news", "release")
				)
				if not is_document or not is_relevant:
					continue
				if lower == "docs/changelog.md" or basename.startswith("readme"):
					continue
				if not snapshot.object_exists(revision.final_commit, path):
					continue
				blob_hash = snapshot.blob_hash(revision.final_commit, path)
				identity = ("changed_documentation", path, blob_hash)
				if identity in seen:
					continue
				seen.add(identity)
				content = snapshot.read_text(revision.final_commit, path)
				items.append(
					daily_blog.schema.EvidenceItem.create(
						"changed_documentation",
						activity.repository,
						revision.final_commit,
						path,
						blob_hash,
						content,
						f"git show {revision.final_commit}:{path}",
					)
				)
		return items


class ScreenshotEvidenceProvider:
	"""Capture commit-selected image blobs and bundle publication paths."""

	#============================================
	def __init__(self, report_date: str) -> None:
		"""Bind publication asset paths to one report date."""
		self.report_date = report_date

	#============================================
	def collect(
		self,
		activity: daily_blog.schema.RepositoryActivity,
		snapshot: GitSnapshot,
	) -> tuple[list[daily_blog.schema.EvidenceItem], dict[str, bytes]]:
		"""Return exact image evidence items and their immutable bytes."""
		items = []
		assets = {}
		for revision in activity.revision_ranges:
			for path in snapshot.changed_paths(revision):
				if not path.casefold().endswith(IMAGE_SUFFIXES):
					continue
				if not snapshot.object_exists(revision.final_commit, path):
					continue
				contents = snapshot.read_bytes(revision.final_commit, path)
				content_hash = daily_blog.io_utils.sha256_bytes(contents)
				asset_name = content_hash[:12] + "-" + _safe_asset_name(path)
				asset_path = "assets/" + asset_name
				if asset_path in assets:
					continue
				publish_path = f"../../assets/publications/{self.report_date}/{asset_name}"
				content = (
					f"Commit-selected image {path} is available to the article at "
					+ f"{publish_path}."
				)
				item = daily_blog.schema.EvidenceItem.create(
					"screenshot",
					activity.repository,
					revision.final_commit,
					path,
					snapshot.blob_hash(revision.final_commit, path),
					content,
					f"git show {revision.final_commit}:{path}",
					asset_path=asset_path,
					publish_path=publish_path,
				)
				items.append(item)
				assets[asset_path] = contents
		return items, assets


class CommitMetadataEvidenceProvider:
	"""Represent commit messages as locators and supporting provenance."""

	#============================================
	def collect(
		self,
		activity: daily_blog.schema.RepositoryActivity,
		_snapshot: GitSnapshot,
	) -> list[daily_blog.schema.EvidenceItem]:
		"""Return one supporting evidence item per attributed commit."""
		items = []
		for commit in activity.commits:
			content = (
				f"Author: {commit.author_name} <{commit.author_email}>\n"
				+ f"Author time: {commit.author_timestamp}\n"
				+ f"Commit message:\n{commit.message}\n"
			)
			item = daily_blog.schema.EvidenceItem.create(
				"commit_metadata",
				activity.repository,
				commit.sha,
				"",
				"",
				content,
				f"git show --quiet {commit.sha}",
			)
			items.append(item)
		return items


#============================================
def _truncate_item(item: daily_blog.schema.EvidenceItem, limit: int) -> daily_blog.schema.EvidenceItem:
	"""Return one evidence item constrained to a positive character budget."""
	if len(item.content) <= limit:
		return item
	marker = "\n[Evidence reached its configured character budget.]\n"
	if limit <= len(marker):
		content = item.content[:limit]
	else:
		content = item.content[: limit - len(marker)].rstrip() + marker
	truncated = daily_blog.schema.EvidenceItem.create(
		item.kind,
		item.repository,
		item.commit,
		item.path,
		item.blob_hash,
		content,
		item.acquisition_source,
		truncated=True,
		asset_path=item.asset_path,
		publish_path=item.publish_path,
	)
	return truncated


class EvidenceAssembler:
	"""Order providers by authority and budget all supporting context explicitly."""

	#============================================
	def __init__(
		self,
		report_date: str,
		timezone_name: str,
		collection_limits: dict[str, int],
	) -> None:
		"""Configure the report identity and evidence collection limits."""
		self.report_date = report_date
		self.timezone_name = timezone_name
		self.collection_limits = collection_limits

	#============================================
	def _budget_items(
		self,
		items: list[daily_blog.schema.EvidenceItem],
		required_repositories: list[str],
	) -> list[daily_blog.schema.EvidenceItem]:
		"""Reserve repository coverage, then apply per-source and total limits."""
		ordered = sorted(
			items,
			key=lambda item: (
				-item.authority_rank,
				item.repository.casefold(),
				item.path.casefold(),
				item.evidence_id,
			),
		)
		remaining_by_kind = {
			"changed_documentation": self.collection_limits["changed_documentation_chars"],
			"diff": self.collection_limits["diff_chars"],
			"readme_context": self.collection_limits["readme_context_chars"],
			"commit_metadata": self.collection_limits["commit_metadata_chars"],
			"screenshot": self.collection_limits["supporting_total_chars"],
		}
		remaining_total = self.collection_limits["supporting_total_chars"]
		screenshot_remaining = self.collection_limits["screenshot_count"]
		selected = []
		selected_ids = set()
		selected_repositories = set()

		def select_budgeted(
			item: daily_blog.schema.EvidenceItem,
			limit_cap: int | None = None,
		) -> bool:
			"""Select one bounded item when its source and total budgets permit it."""
			nonlocal remaining_total, screenshot_remaining
			if item.evidence_id in selected_ids:
				return True
			if item.kind == "screenshot" and screenshot_remaining <= 0:
				return False
			kind_remaining = remaining_by_kind[item.kind]
			limit = min(
				self.collection_limits["per_item_chars"],
				kind_remaining,
				remaining_total,
			)
			if limit_cap is not None:
				limit = min(limit, limit_cap)
			if limit <= 0:
				return False
			bounded = _truncate_item(item, limit)
			selected.append(bounded)
			selected_ids.add(item.evidence_id)
			selected_repositories.add(item.repository)
			used = len(bounded.content)
			remaining_by_kind[item.kind] -= used
			remaining_total -= used
			if item.kind == "screenshot":
				screenshot_remaining -= 1
			return True

		# Changelogs are the primary narrative record and retain their existing
		# unmetered contract. They also satisfy repository coverage immediately.
		for item in ordered:
			if item.kind == "dated_changelog":
				selected.append(item)
				selected_ids.add(item.evidence_id)
				selected_repositories.add(item.repository)

		# Projection requires one citable source for every active repository. Reserve
		# that coverage before routine supporting material can consume the budget.
		missing_repositories = [
			repository
			for repository in required_repositories
			if repository not in selected_repositories
		]
		for index, repository in enumerate(missing_repositories):
			remaining_slots = len(missing_repositories) - index
			if remaining_total < remaining_slots:
				raise RuntimeError(
					"Evidence budget cannot retain one citable item for every active repository."
				)
			coverage_cap = max(1, remaining_total // remaining_slots)
			candidates = [
				item
				for item in ordered
				if item.repository == repository and item.kind != "dated_changelog"
			]
			if not any(select_budgeted(item, coverage_cap) for item in candidates):
				raise RuntimeError(
					f"Evidence assembly lacks citable source material for {repository}."
				)

		for item in ordered:
			if item.kind != "dated_changelog":
				select_budgeted(item)
		return selected

	#============================================
	def assemble(
		self,
		mirror_entries: list[dict],
		activities: list[daily_blog.schema.RepositoryActivity],
	) -> tuple[daily_blog.schema.EvidencePacket, dict[str, bytes]]:
		"""Run all providers and return one immutable packet plus selected assets."""
		items = []
		assets = {}
		for activity in activities:
			snapshot = GitSnapshot(activity)
			items.extend(ChangelogEvidenceProvider(self.report_date).collect(activity, snapshot))
			items.extend(DocumentationEvidenceProvider().collect(activity, snapshot))
			items.extend(
				DiffEvidenceProvider(self.collection_limits["diff_chars"]).collect(
					activity,
					snapshot,
				)
			)
			screenshot_items, screenshot_assets = ScreenshotEvidenceProvider(
				self.report_date
			).collect(activity, snapshot)
			items.extend(screenshot_items)
			assets.update(screenshot_assets)
			items.extend(CommitMetadataEvidenceProvider().collect(activity, snapshot))
		budgeted = self._budget_items(
			items,
			[activity.repository for activity in activities],
		)
		selected_asset_paths = {item.asset_path for item in budgeted if item.asset_path}
		selected_assets = {
			path: contents for path, contents in assets.items() if path in selected_asset_paths
		}
		complete = all(
			entry["object_available"] and entry["refresh_result"] != "failed"
			for entry in mirror_entries
		)
		packet = daily_blog.schema.EvidencePacket.create(
			self.report_date,
			self.timezone_name,
			complete,
			self.collection_limits,
			mirror_entries,
			activities,
			budgeted,
		)
		return packet, selected_assets
