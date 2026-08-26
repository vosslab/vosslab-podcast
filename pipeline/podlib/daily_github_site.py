import hashlib
import html
import ipaddress
import json
import os
import re
import shutil
import socket
import stat


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SITE_DIRECTORY_NAME = "daily_site"
POSTS_DIRECTORY_NAME = "posts"
DATE_DIRECTORY_NAME = "date"
NO_ACTIVITY_PARAGRAPH = "No confirmed vosslab GitHub commits were recorded for this complete day."
PRIVATE_LAN_NETWORKS = (
	ipaddress.ip_network("10.0.0.0/8"),
	ipaddress.ip_network("172.16.0.0/12"),
	ipaddress.ip_network("192.168.0.0/16"),
)
STATUS_LABELS = {
	"published": "Complete and published",
	"validation-failed": "Validation failed",
	"incomplete": "Incomplete run",
	"complete-unpublished": "Complete, not published",
}
PROMOTION_RECEIPT_NAME = "validated_promotion_receipt.json"
RECEIPT_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_RECEIPT_ARTIFACTS = {
	"raw_commits.json",
	"claims.json",
	"run_manifest.json",
	"post_draft.md",
	"agent_generation_manifest.json",
}


#============================================
def is_regular_nonsymlink(path: str) -> bool:
	"""
	Return whether a path is one regular file without following a symlink.
	"""
	try:
		file_stat = os.lstat(path)
	except OSError:
		return False
	return stat.S_ISREG(file_stat.st_mode)


#============================================
def is_directory_nonsymlink(path: str) -> bool:
	"""
	Return whether a path is one directory without following a symlink.
	"""
	try:
		file_stat = os.lstat(path)
	except OSError:
		return False
	return stat.S_ISDIR(file_stat.st_mode)


#============================================
def read_regular_text(path: str) -> str:
	"""
	Read one regular, non-symlinked UTF-8 artifact without following a source link.
	"""
	if not is_regular_nonsymlink(path):
		raise RuntimeError(f"Expected a regular non-symlinked artifact: {path}")
	flags = os.O_RDONLY
	if hasattr(os, "O_NOFOLLOW"):
		flags |= os.O_NOFOLLOW
	file_descriptor = os.open(path, flags)
	try:
		file_stat = os.fstat(file_descriptor)
		if not stat.S_ISREG(file_stat.st_mode):
			raise RuntimeError(f"Expected a regular artifact: {path}")
		with os.fdopen(file_descriptor, "r", encoding="utf-8") as handle:
			content = handle.read()
		file_descriptor = -1
	except Exception:
		if file_descriptor >= 0:
			os.close(file_descriptor)
		raise
	return content


#============================================
def read_json_object(path: str) -> dict:
	"""
	Read one JSON object artifact.
	"""
	payload = json.loads(read_regular_text(path))
	if not isinstance(payload, dict):
		raise RuntimeError(f"Expected a JSON object: {path}")
	return payload


#============================================
def read_optional_json_object(path: str) -> dict:
	"""
	Read one optional JSON object artifact or return an empty mapping.
	"""
	if not os.path.lexists(path):
		return {}
	payload = read_json_object(path)
	return payload


#============================================
def get_validation_errors(run_dir: str) -> list[str]:
	"""
	Read retained M3 validation errors without failing presentation.
	"""
	report_path = os.path.join(run_dir, "validation_failures", "validation_report.json")
	try:
		report = read_optional_json_object(report_path)
	except (OSError, ValueError, json.JSONDecodeError) as error:
		return [f"Could not read validation report: {error}"]
	errors = report.get("errors", [])
	if not isinstance(errors, list):
		return ["Validation report has an invalid errors field."]
	result = [str(error) for error in errors if str(error).strip()]
	return result


#============================================
def get_claim_summary(run_dir: str) -> tuple[int, list[str]]:
	"""
	Return confirmed claim count and sorted repository names for one daily run.
	"""
	claims_path = os.path.join(run_dir, "claims.json")
	try:
		claim_packet = read_optional_json_object(claims_path)
	except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
		return 0, []
	claims = claim_packet.get("claims", [])
	if not isinstance(claims, list):
		return 0, []
	repositories = set()
	for claim in claims:
		if isinstance(claim, dict):
			repository = str(claim.get("repository") or "").strip()
			if repository:
				repositories.add(repository)
	ordered_repositories = sorted(repositories, key=str.casefold)
	return len(claims), ordered_repositories


#============================================
def get_prose_paragraphs(draft: str) -> list[str]:
	"""
	Return non-heading Markdown paragraph blocks in source order.
	"""
	paragraphs = []
	for block in re.split(r"\n\s*\n", draft.strip()):
		text = block.strip()
		if text and not text.startswith("#"):
			paragraphs.append(text)
	return paragraphs


#============================================
def validate_m3_generation(run_dir: str, date_text: str, manifest: dict) -> dict:
	"""
	Validate current regular M2 and M3 generation artifacts without mutating source state.
	"""
	errors = []
	paths = {
		"raw": os.path.join(run_dir, "raw_commits.json"),
		"claims": os.path.join(run_dir, "claims.json"),
		"draft": os.path.join(run_dir, "post_draft.md"),
		"generation": os.path.join(run_dir, "agent_generation_manifest.json"),
	}
	payloads = {}
	for label in ("raw", "claims", "generation"):
		try:
			payloads[label] = read_json_object(paths[label])
		except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
			errors.append(f"could not read current {label} artifact: {error}")
	try:
		draft = read_regular_text(paths["draft"])
	except OSError as error:
		errors.append(f"could not read current draft artifact: {error}")
		draft = ""
	except RuntimeError as error:
		errors.append(f"could not read current draft artifact: {error}")
		draft = ""
	timezone_name = str(manifest.get("timezone") or "")
	if manifest.get("date") != date_text or not timezone_name:
		errors.append("run manifest must declare the current date and timezone")
	if not manifest.get("complete"):
		errors.append("run manifest is incomplete")
	publication = manifest.get("publication")
	if not isinstance(publication, dict) or not publication.get("eligible"):
		errors.append("run manifest is not publication eligible")
	for label in ("raw", "claims"):
		payload = payloads.get(label, {})
		if payload.get("date") != date_text or payload.get("timezone") != timezone_name:
			errors.append(f"current {label} artifact does not match the M2 run")
	claim_packet = payloads.get("claims", {})
	if not claim_packet.get("complete"):
		errors.append("current claim packet is incomplete")
	claims = claim_packet.get("claims")
	if not isinstance(claims, list):
		errors.append("current claim packet must contain a claims list")
		claims = []
	claims_by_id = {}
	claims_by_sha = {}
	for claim in claims:
		if not isinstance(claim, dict):
			errors.append("current claim packet contains a non-object claim")
			continue
		claim_id = str(claim.get("claim_id") or "")
		sha = str(claim.get("sha") or "")
		identity = claim.get("identity")
		if not claim_id or not sha or not isinstance(identity, dict) or identity.get("status") != "confirmed":
			errors.append("current claim packet contains an invalid confirmed claim")
			continue
		if claim_id in claims_by_id or sha in claims_by_sha:
			errors.append("current claim packet contains duplicate claim IDs or SHAs")
			continue
		claims_by_id[claim_id] = claim
		claims_by_sha[sha] = claim
	generation = payloads.get("generation", {})
	if generation.get("date") != date_text or generation.get("timezone") != timezone_name:
		errors.append("generation manifest does not match the current M2 run")
	if generation.get("draft_path") != "post_draft.md":
		errors.append("generation manifest must declare post_draft.md")
	title = draft.splitlines()[0] if draft.splitlines() else ""
	if not title.startswith("# ") or date_text not in title or timezone_name not in title:
		errors.append("current draft H1 does not match the M2 run")
	paragraphs = get_prose_paragraphs(draft)
	entries = generation.get("paragraphs")
	if not isinstance(entries, list) or len(entries) != len(paragraphs):
		errors.append("generation manifest does not map every current draft paragraph")
		entries = []
	for index, paragraph in enumerate(paragraphs):
		if index >= len(entries) or not isinstance(entries[index], dict):
			continue
		entry = entries[index]
		claim_ids = entry.get("claim_ids")
		shas = entry.get("shas")
		if entry.get("paragraph") != paragraph or not isinstance(claim_ids, list) or not isinstance(shas, list):
			errors.append(f"generation manifest paragraph {index + 1} is invalid")
			continue
		if not claim_ids or not shas:
			is_complete_no_activity = (
				not claims_by_id
				and entry.get("no_activity") is True
				and paragraph == NO_ACTIVITY_PARAGRAPH
				and claim_ids == []
				and shas == []
			)
			if not is_complete_no_activity:
				errors.append(f"generation manifest paragraph {index + 1} lacks current claim support")
			continue
		for claim_id in claim_ids:
			claim = claims_by_id.get(str(claim_id))
			if claim is None or claim.get("sha") not in shas:
				errors.append(f"generation manifest claim ID/SHA does not match: {claim_id}")
				continue
			if "](" + str(claim.get("html_url") or "") + ")" not in paragraph:
				errors.append(f"generation manifest omits a current commit permalink: {claim_id}")
		for sha in shas:
			claim = claims_by_sha.get(str(sha))
			if claim is None or claim.get("claim_id") not in claim_ids:
				errors.append(f"generation manifest SHA/claim ID does not match: {sha}")
	result = {"valid": not errors, "errors": errors, "draft": draft}
	return result


#============================================
def validate_receipt_artifact_digests(run_dir: str, date_text: str, manifest: dict) -> tuple[dict, list[str]]:
	"""
	Require a regular promotion receipt and verify every bound digest against current artifacts.
	"""
	errors = []
	receipt_path = os.path.join(run_dir, PROMOTION_RECEIPT_NAME)
	try:
		receipt = read_json_object(receipt_path)
	except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
		return {}, [f"could not read validated promotion receipt: {error}"]
	if receipt.get("schema_version") != 1:
		errors.append("promotion receipt schema version is invalid")
	if receipt.get("status") != "validated-promotion":
		errors.append("promotion receipt status is invalid")
	timezone_name = str(manifest.get("timezone") or "")
	if receipt.get("date") != date_text or receipt.get("timezone") != timezone_name:
		errors.append("promotion receipt date or timezone does not match the M2 run")
	post_name = f"post-{date_text}.md"
	if receipt.get("post_path") != post_name:
		errors.append("promotion receipt post path does not match the M2 run")
	artifact_digests = receipt.get("artifact_digests")
	if not isinstance(artifact_digests, dict):
		return receipt, errors + ["promotion receipt must contain artifact digests"]
	required_names = REQUIRED_RECEIPT_ARTIFACTS | {post_name}
	if not required_names.issubset(artifact_digests):
		errors.append("promotion receipt omits required artifact digests")
	for artifact_name, expected_digest in artifact_digests.items():
		if not isinstance(artifact_name, str) or os.path.basename(artifact_name) != artifact_name:
			errors.append("promotion receipt artifact path must be one direct filename")
			continue
		if not isinstance(expected_digest, str) or not RECEIPT_DIGEST_RE.fullmatch(expected_digest):
			errors.append(f"promotion receipt digest is invalid: {artifact_name}")
			continue
		artifact_path = os.path.join(run_dir, artifact_name)
		try:
			artifact_text = read_regular_text(artifact_path)
		except (OSError, RuntimeError) as error:
			errors.append(f"could not read receipt-bound artifact {artifact_name}: {error}")
			continue
		actual_digest = hashlib.sha256(artifact_text.encode("utf-8")).hexdigest()
		if actual_digest != expected_digest:
			errors.append(f"promotion receipt digest does not match current artifact: {artifact_name}")
	return receipt, errors


#============================================
def validate_m3_promotion_receipt(run_dir: str, date_text: str, manifest: dict) -> dict:
	"""
	Require exact current M2/M3 generation plus a regular promoted byte-for-byte receipt.
	"""
	generation = validate_m3_generation(run_dir, date_text, manifest)
	receipt, receipt_errors = validate_receipt_artifact_digests(run_dir, date_text, manifest)
	errors = list(generation["errors"])
	errors.extend(receipt_errors)
	post_path = os.path.join(run_dir, f"post-{date_text}.md")
	try:
		post_text = read_regular_text(post_path)
	except (OSError, RuntimeError) as error:
		errors.append(f"could not read regular promoted post: {error}")
		post_text = ""
	if post_text and post_text != generation["draft"]:
		errors.append("promoted post does not match the current M3 draft receipt")
	result = {
		"valid": not errors,
		"errors": errors,
		"post_text": post_text,
		"generation": generation,
		"receipt": receipt,
	}
	return result


#============================================
def get_governing_validation_errors(run_dir: str, manifest: dict, receipt: dict) -> list[str]:
	"""
	Return a retained failure only when it exactly describes the current invalid M3 generation.
	"""
	if receipt["valid"]:
		return []
	report_path = os.path.join(run_dir, "validation_failures", "validation_report.json")
	try:
		report = read_optional_json_object(report_path)
	except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
		return []
	report_errors = report.get("errors")
	if (
		report.get("valid") is False
		and report.get("date") == manifest.get("date")
		and report.get("timezone") == manifest.get("timezone")
		and isinstance(report_errors, list)
		and report_errors == receipt["generation"]["errors"]
	):
		return [str(error) for error in report_errors if str(error).strip()]
	return []


#============================================
def collect_run_record(daily_root: str, date_text: str) -> dict:
	"""
	Build one presentation record from an M2/M3 daily artifact directory.
	"""
	run_dir = os.path.join(daily_root, date_text)
	manifest_path = os.path.join(run_dir, "run_manifest.json")
	manifest = {}
	manifest_error = ""
	try:
		manifest = read_optional_json_object(manifest_path)
	except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
		manifest_error = f"Could not read run manifest: {error}"
	post_name = f"post-{date_text}.md"
	post_path = os.path.join(run_dir, post_name)
	complete = bool(manifest.get("complete"))
	receipt = validate_m3_promotion_receipt(run_dir, date_text, manifest)
	published = receipt["valid"]
	validation_errors = get_governing_validation_errors(run_dir, manifest, receipt)
	if published:
		status = "published"
	elif validation_errors:
		status = "validation-failed"
	elif not complete:
		status = "incomplete"
	else:
		status = "complete-unpublished"
	failure_text = manifest_error
	if not failure_text:
		errors = manifest.get("errors", [])
		if isinstance(errors, list):
			failure_text = "; ".join(str(error) for error in errors if str(error).strip())
	if validation_errors:
		failure_text = "; ".join(validation_errors)
	claim_count, repositories = get_claim_summary(run_dir)
	counts = manifest.get("counts", {})
	if isinstance(counts, dict) and not claim_count:
		claim_count = int(counts.get("confirmed", 0) or 0)
	record = {
		"date": date_text,
		"run_dir": run_dir,
		"manifest": manifest,
		"complete": complete,
		"published": published,
		"status": status,
		"status_label": STATUS_LABELS[status],
		"failure_text": failure_text,
		"validation_errors": validation_errors,
		"claim_count": claim_count,
		"repositories": repositories,
		"repository_count": len(repositories),
		"collected_at": str(manifest.get("collected_at") or ""),
		"timezone": str(manifest.get("timezone") or ""),
		"post_path": post_path if published else "",
		"post_name": post_name,
		"post_text": receipt["post_text"] if published else "",
	}
	return record


#============================================
def collect_daily_run_records(daily_root: str) -> list[dict]:
	"""
	Discover date-scoped daily artifacts and return newest-first records.
	"""
	if not is_directory_nonsymlink(daily_root):
		return []
	dates = []
	for name in os.listdir(daily_root):
		path = os.path.join(daily_root, name)
		if DATE_RE.fullmatch(name) and is_directory_nonsymlink(path):
			dates.append(name)
	records = []
	for date_text in sorted(dates, reverse=True):
		records.append(collect_run_record(daily_root, date_text))
	return records


#============================================
def safe_url(value: str) -> str:
	"""
	Return an HTML-safe external URL only for HTTP(S) Markdown links.
	"""
	text = str(value or "").strip()
	if text.startswith("https://") or text.startswith("http://"):
		return html.escape(text, quote=True)
	return "#"


#============================================
def render_inline_markdown(text: str) -> str:
	"""
	Escape prose and render simple HTTP(S) Markdown links safely.
	"""
	escaped = html.escape(text, quote=False)
	pattern = re.compile(r"\[([^\]]+)\]\(([^\s)]+)\)")

	def replace_link(match) -> str:
		label = match.group(1)
		url = safe_url(html.unescape(match.group(2)))
		return f'<a href="{url}" rel="noreferrer">{label}</a>'

	rendered = pattern.sub(replace_link, escaped)
	return rendered


#============================================
def render_post_markdown(markdown_text: str) -> str:
	"""
	Render a safe, intentionally small Markdown subset for promoted post presentation.
	"""
	blocks = []
	paragraph_lines = []
	list_items = []

	def flush_paragraph() -> None:
		if paragraph_lines:
			paragraph = " ".join(paragraph_lines)
			blocks.append("<p>" + render_inline_markdown(paragraph) + "</p>")
			paragraph_lines.clear()

	def flush_list() -> None:
		if list_items:
			items = "".join("<li>" + render_inline_markdown(item) + "</li>" for item in list_items)
			blocks.append("<ul>" + items + "</ul>")
			list_items.clear()

	for raw_line in markdown_text.splitlines():
		line = raw_line.strip()
		if not line:
			flush_paragraph()
			flush_list()
			continue
		if line.startswith("### "):
			flush_paragraph()
			flush_list()
			blocks.append("<h3>" + render_inline_markdown(line[4:]) + "</h3>")
			continue
		if line.startswith("## "):
			flush_paragraph()
			flush_list()
			blocks.append("<h2>" + render_inline_markdown(line[3:]) + "</h2>")
			continue
		if line.startswith("# "):
			flush_paragraph()
			flush_list()
			blocks.append("<h1>" + render_inline_markdown(line[2:]) + "</h1>")
			continue
		if line.startswith("- "):
			flush_paragraph()
			list_items.append(line[2:])
			continue
		flush_list()
		paragraph_lines.append(line)
	flush_paragraph()
	flush_list()
	result = "\n".join(blocks)
	return result


#============================================
def render_page(title: str, body: str) -> str:
	"""
	Wrap deterministic page content in the archive's shared private-site HTML shell.
	"""
	safe_title = html.escape(title)
	page = (
		"<!doctype html>\n"
		"<html lang=\"en\">\n"
		"<head>\n"
		"<meta charset=\"utf-8\">\n"
		"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
		f"<title>{safe_title}</title>\n"
		"<style>"
		"body{font-family:system-ui,sans-serif;line-height:1.55;margin:0 auto;max-width:960px;padding:2rem;}"
		"nav{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0;}"
		"table{border-collapse:collapse;width:100%;}th,td{border:1px solid #bbb;padding:.5rem;text-align:left;}"
		".state{font-weight:700;}.published{color:#176b2c;}.incomplete,.validation-failed{color:#9b1c1c;}"
		".complete-unpublished{color:#725500;}.notice{border-left:4px solid #777;padding:.5rem 1rem;}"
		"</style>\n"
		"</head>\n"
		"<body>\n"
		+ body
		+ "\n</body>\n</html>\n"
	)
	return page


#============================================
def render_navigation(records: list[dict], prefix: str) -> str:
	"""
	Render newest-first direct date navigation using a page-relative prefix.
	"""
	links = [f'<a href="{prefix}index.html">Archive</a>', f'<a href="{prefix}status.html">Run status</a>']
	for record in records:
		date_text = html.escape(record["date"])
		links.append(f'<a href="{prefix}date/{date_text}/index.html">{date_text}</a>')
	navigation = "<nav>" + " ".join(links) + "</nav>"
	return navigation


#============================================
def render_run_rows(records: list[dict], prefix: str) -> str:
	"""
	Render one newest-first archive table from normalized run records.
	"""
	rows = []
	for record in records:
		date_text = html.escape(record["date"])
		status = html.escape(record["status"])
		status_label = html.escape(record["status_label"])
		failure_text = html.escape(record["failure_text"])
		repository_text = ", ".join(html.escape(name) for name in record["repositories"])
		if not repository_text:
			repository_text = "-"
		date_link = f'<a href="{prefix}date/{date_text}/index.html">{date_text}</a>'
		rows.append(
			"<tr>"
			+ f"<td>{date_link}</td>"
			+ f'<td class="state {status}">{status_label}</td>'
			+ f"<td>{record['claim_count']}</td>"
			+ f"<td>{repository_text}</td>"
			+ f"<td>{failure_text or '-'}</td>"
			+ "</tr>"
		)
	if not rows:
		rows.append("<tr><td colspan=\"5\">No daily run directories were found.</td></tr>")
	table = (
		"<table><thead><tr><th>Date</th><th>State</th><th>Confirmed commits</th>"
		"<th>Repositories</th><th>Failure detail</th></tr></thead><tbody>"
		+ "".join(rows)
		+ "</tbody></table>"
	)
	return table


#============================================
def render_index_page(records: list[dict]) -> str:
	"""
	Render the archive home page with current run visibility.
	"""
	navigation = render_navigation(records, "")
	if records:
		latest = records[0]
		latest_text = (
			"<p class=\"notice\"><strong>Latest source date:</strong> "
			+ html.escape(latest["date"])
			+ "; <strong>state:</strong> "
			+ html.escape(latest["status_label"])
			+ "; <strong>collected:</strong> "
			+ html.escape(latest["collected_at"] or "not recorded")
			+ "; <strong>confirmed commits:</strong> "
			+ str(latest["claim_count"])
			+ "; <strong>repositories:</strong> "
			+ str(latest["repository_count"])
			+ "</p>"
		)
	else:
		latest_text = "<p class=\"notice\">No daily evidence runs are available yet.</p>"
	body = "<h1>Private daily GitHub archive</h1>" + navigation + latest_text + render_run_rows(records, "")
	page = render_page("Private daily GitHub archive", body)
	return page


#============================================
def render_status_page(records: list[dict]) -> str:
	"""
	Render a detailed static status page for complete, incomplete, and failed runs.
	"""
	body = "<h1>Daily GitHub run status</h1>" + render_navigation(records, "") + render_run_rows(records, "")
	page = render_page("Daily GitHub run status", body)
	return page


#============================================
def render_date_page(record: dict, records: list[dict]) -> str:
	"""
	Render one date page from a promoted post or visible non-publication state.
	"""
	navigation = render_navigation(records, "../../")
	metadata = (
		"<p class=\"notice\"><strong>State:</strong> "
		+ html.escape(record["status_label"])
		+ "; <strong>Completeness:</strong> "
		+ ("complete" if record["complete"] else "incomplete")
		+ "; <strong>Confirmed commits:</strong> "
		+ str(record["claim_count"])
		+ "; <strong>Repositories:</strong> "
		+ str(record["repository_count"])
		+ "</p>"
	)
	if record["published"]:
		post_html = render_post_markdown(record["post_text"])
		raw_link = f'../../{POSTS_DIRECTORY_NAME}/{html.escape(record["post_name"])}'
		content = post_html + f'<p><a href="{raw_link}">Promoted Markdown source</a></p>'
	else:
		detail = html.escape(record["failure_text"] or "No promoted post is available for this run.")
		content = "<p class=\"notice\">" + detail + "</p>"
	body = "<h1>Daily GitHub archive: " + html.escape(record["date"]) + "</h1>" + navigation + metadata + content
	page = render_page(f"Daily GitHub archive {record['date']}", body)
	return page


#============================================
def write_text_file(path: str, content: str) -> None:
	"""
	Write one UTF-8 static artifact with its deterministic supplied content.
	"""
	parent = os.path.dirname(path)
	os.makedirs(parent, exist_ok=True)
	with open(path, "w", encoding="utf-8") as handle:
		handle.write(content)


#============================================
def resolve_approved_site_root(output_root: str, output_user: str, site_root: str = "") -> tuple[str, str]:
	"""
	Resolve the one approved user-scoped source and rebuild destination pair.
	"""
	user_name = str(output_user or "").strip()
	if not user_name or os.path.basename(user_name) != user_name or user_name in (".", ".."):
		raise RuntimeError("Static-site output user must be one safe user-scoped path component.")
	resolved_output_root = os.path.abspath(output_root)
	if os.path.lexists(resolved_output_root) and not is_directory_nonsymlink(resolved_output_root):
		raise RuntimeError("Static-site output root must be a regular directory, not a symlink.")
	approved_user_root = os.path.abspath(os.path.join(resolved_output_root, user_name))
	if os.path.lexists(approved_user_root) and not is_directory_nonsymlink(approved_user_root):
		raise RuntimeError("Static-site user root must be a regular directory, not a symlink.")
	if os.path.commonpath([resolved_output_root, approved_user_root]) != resolved_output_root:
		raise RuntimeError("Static-site output user escapes the configured output root.")
	daily_root = os.path.join(approved_user_root, "daily")
	approved_site_root = os.path.join(approved_user_root, SITE_DIRECTORY_NAME)
	resolved_site_root = os.path.abspath(site_root) if site_root else approved_site_root
	if resolved_site_root != approved_site_root:
		raise RuntimeError("Static-site destination must be the approved user-scoped daily_site root.")
	return daily_root, approved_site_root


#============================================
def build_static_site(output_root: str, output_user: str, site_root: str = "") -> dict:
	"""
	Build a deterministic static archive from promoted posts and visible daily run state.
	"""
	daily_root, resolved_site_root = resolve_approved_site_root(output_root, output_user, site_root)
	records = collect_daily_run_records(daily_root)
	if os.path.lexists(resolved_site_root):
		if not is_directory_nonsymlink(resolved_site_root):
			raise RuntimeError("Static-site destination must be a regular directory, not a file or symlink.")
		shutil.rmtree(resolved_site_root)
	os.makedirs(resolved_site_root, exist_ok=True)
	write_text_file(os.path.join(resolved_site_root, "index.html"), render_index_page(records))
	write_text_file(os.path.join(resolved_site_root, "status.html"), render_status_page(records))
	for record in records:
		date_page = render_date_page(record, records)
		date_path = os.path.join(resolved_site_root, DATE_DIRECTORY_NAME, record["date"], "index.html")
		write_text_file(date_path, date_page)
		if record["published"]:
			post_path = os.path.join(resolved_site_root, POSTS_DIRECTORY_NAME, record["post_name"])
			write_text_file(post_path, record["post_text"])
	site_manifest = {
		"schema_version": 1,
		"daily_root": daily_root,
		"runs": [
			{
				"date": record["date"],
				"complete": record["complete"],
				"published": record["published"],
				"status": record["status"],
				"claim_count": record["claim_count"],
				"repositories": record["repositories"],
			}
			for record in records
		],
	}
	manifest_text = json.dumps(site_manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
	write_text_file(os.path.join(resolved_site_root, "site_manifest.json"), manifest_text)
	result = {"site_root": resolved_site_root, "daily_root": daily_root, "runs": records}
	return result


#============================================
def validate_private_bind_address(address: str) -> str:
	"""
	Require one locally assigned RFC1918 IPv4 address before the server may listen.
	"""
	text = str(address or "").strip()
	if not text:
		raise RuntimeError("daily_site.bind_address must name one private LAN IPv4 address.")
	try:
		parsed = ipaddress.ip_address(text)
	except ValueError as error:
		raise RuntimeError(f"Invalid daily site bind address: {text}") from error
	is_private_lan = any(parsed in network for network in PRIVATE_LAN_NETWORKS)
	if parsed.version != 4 or not is_private_lan or parsed.is_loopback or parsed.is_unspecified:
		raise RuntimeError("Daily site bind address must be one non-loopback private IPv4 address.")
	probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	try:
		probe.bind((text, 0))
	except OSError as error:
		raise RuntimeError(f"Daily site bind address is not assigned locally: {text}") from error
	finally:
		probe.close()
	return text


#============================================
def validate_private_server_configuration(address: str, port: int) -> tuple[str, int]:
	"""
	Validate a configured private LAN address and non-privileged TCP port before listen.
	"""
	validated_address = validate_private_bind_address(address)
	try:
		validated_port = int(port)
	except (TypeError, ValueError) as error:
		raise RuntimeError(f"Invalid daily site port: {port}") from error
	if validated_port < 1024 or validated_port > 65535:
		raise RuntimeError("Daily site port must be between 1024 and 65535.")
	return validated_address, validated_port
