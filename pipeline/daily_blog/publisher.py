"""Invoke the separately owned bundle importer in the daily-blog repository."""

# Standard Library
import os
import json
import subprocess

# local repo modules
import daily_blog.io_utils


#============================================
def import_bundle(
	daily_blog_repository: str,
	bundle_path: str,
	*,
	replace_existing: bool = False,
) -> dict:
	"""Run the publisher's one importer through its required Bash environment.

	Args:
		daily_blog_repository: Physical publisher repository root.
		bundle_path: Physical producer publication-bundle directory.
		replace_existing: Whether to replace the current post for the bundle's report date.

	Returns:
		The bounded publisher import result.

	Raises:
		RuntimeError: Replacement authorization, subprocess execution, or output validation fails.
	"""
	repository = os.path.abspath(daily_blog_repository)
	if not os.path.isfile(os.path.join(repository, "scripts", "import_publication_bundle.py")):
		raise RuntimeError(f"Daily-blog bundle importer is unavailable: {repository}")
	if type(replace_existing) is not bool:
		raise RuntimeError("Replace-existing state must be Boolean.")
	script = 'source source_me.sh && python3 scripts/import_publication_bundle.py --bundle "$1"'
	arguments = ["daily-blog-import", os.path.abspath(bundle_path)]
	if replace_existing:
		script += " --replace-existing"
	result = subprocess.run(
		["/bin/bash", "-lc", script, *arguments],
		cwd=repository,
		check=False,
		text=True,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		timeout=1200,
	)
	if result.returncode:
		message = result.stderr.strip() or result.stdout.strip()
		raise RuntimeError(f"Daily-blog bundle import failed: {message}")
	try:
		publisher_result = json.loads(result.stdout)
	except json.JSONDecodeError as error:
		raise RuntimeError("Daily-blog bundle importer returned invalid JSON.") from error
	if not isinstance(publisher_result, dict) or publisher_result.get("status") not in {
		"imported",
		"idempotent",
		"replaced",
	}:
		raise RuntimeError("Daily-blog bundle importer returned an unsupported status.")
	if publisher_result["status"] == "replaced":
		if not replace_existing:
			raise RuntimeError("Daily-blog bundle importer replaced an unapproved report date.")
	output = {
		"status": publisher_result["status"],
		"bundle_sha256": str(publisher_result.get("bundle_sha256") or ""),
		"report_date": str(publisher_result.get("report_date") or ""),
		"stdout_hash": daily_blog.io_utils.sha256_text(result.stdout),
	}
	return output
