"""Invoke the separately owned bundle importer in the daily-blog repository."""

# Standard Library
import os
import json
import subprocess

# local repo modules
import daily_blog.io_utils


#============================================
def import_bundle(daily_blog_repository: str, bundle_path: str) -> dict:
	"""Run the publisher's one importer through its required Bash environment."""
	repository = os.path.abspath(daily_blog_repository)
	if not os.path.isfile(os.path.join(repository, "scripts", "import_publication_bundle.py")):
		raise RuntimeError(f"Daily-blog bundle importer is unavailable: {repository}")
	script = 'source source_me.sh && python3 scripts/import_publication_bundle.py --bundle "$1"'
	result = subprocess.run(
		["/bin/bash", "-lc", script, "daily-blog-import", os.path.abspath(bundle_path)],
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
	}:
		raise RuntimeError("Daily-blog bundle importer returned an unsupported status.")
	output = {
		"status": publisher_result["status"],
		"bundle_id": str(publisher_result.get("bundle_id") or ""),
		"report_date": str(publisher_result.get("report_date") or ""),
		"stdout_hash": daily_blog.io_utils.sha256_text(result.stdout),
	}
	return output
