"""Deterministically own the reader-visible report-day repository footer."""

# Standard Library
import collections.abc
import re

# local repo modules
import daily_blog.artifacts
import daily_blog.schema


PROJECT_COVERAGE_RE = re.compile(
	r"(?ms)^## Project coverage[ \t]*\n.*?(?=^##[ \t]+|\Z)",
)
REPOSITORY_RE = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+\Z")


#============================================
def attach_project_coverage(
	post: daily_blog.artifacts.CompletePost,
	packets: collections.abc.Sequence[daily_blog.schema.EvidencePacket],
	activities: collections.abc.Sequence[daily_blog.schema.RepositoryActivity],
) -> daily_blog.artifacts.CompletePost:
	"""Replace authored coverage with exact machine-owned activity counts.

	ASVS 2.3.1: final coverage follows the acquisition's exact machine-observed
	activity while preserving the selected post's existing provenance identity.
	"""
	if type(post) is not daily_blog.artifacts.CompletePost:
		raise RuntimeError("Project coverage requires an exact CompletePost.")
	if not isinstance(packets, collections.abc.Sequence) or not packets:
		raise RuntimeError("Project coverage requires evidence packets.")
	if not isinstance(activities, collections.abc.Sequence) or not activities:
		raise RuntimeError("Project coverage requires exact report-day activity.")
	ordered = tuple(sorted(
		activities, key=lambda item: (-len(item.commits), item.repository.casefold()),
	))
	if (
		any(type(item) is not daily_blog.schema.RepositoryActivity for item in ordered)
		or len({item.repository.casefold() for item in ordered}) != len(ordered)
		or any(not item.commits for item in ordered)
		or any(REPOSITORY_RE.fullmatch(item.repository) is None for item in ordered)
	):
		raise RuntimeError("Project coverage activity is invalid.")
	body = PROJECT_COVERAGE_RE.sub("", post.content).rstrip()
	rows = []
	for item in ordered:
		count = len(item.commits)
		label = "commit" if count == 1 else "commits"
		rows.append(
			f"- [{item.repository}](https://github.com/{item.repository}) — {count} {label}"
		)
	# Preserve machine-owned provenance independently of any authored footer bytes
	# removed above; the reader-visible coverage rows do not depend on LLM citations.
	provenance = "<!-- evidence: " + ", ".join(post.evidence_ids) + " -->"
	content = body + "\n\n" + provenance + "\n\n## Project coverage\n\n" + "\n".join(rows) + "\n"
	return daily_blog.artifacts.CompletePost.create(
		post.report_date, packets, post.repositories, content, post.evidence_ids,
		post.publication_id, post.output_path, post.image_paths,
	)
