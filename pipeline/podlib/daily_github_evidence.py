import json
import os
import re
import shutil
import uuid
from datetime import date
from datetime import datetime
from datetime import timezone
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError


CO_AUTHOR_RE = re.compile(r"^Co-authored-by:\s*(.+?)\s*<([^>]+)>\s*$", re.IGNORECASE | re.MULTILINE)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
GITHUB_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
GITHUB_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9])?$")
GIT_OBJECT_ID_RE = re.compile(r"^(?:[0-9A-Fa-f]{40}|[0-9A-Fa-f]{64})$")


#============================================
def parse_iso_timestamp(value: str) -> datetime:
	"""
	Parse one API timestamp into a timezone-aware datetime.
	"""
	text = (value or "").strip()
	if not text:
		raise RuntimeError("Commit timestamp is required.")
	parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
	if parsed.tzinfo is None:
		parsed = parsed.replace(tzinfo=timezone.utc)
	return parsed


#============================================
def build_local_date_window(date_text: str, timezone_name: str) -> tuple[datetime, datetime]:
	"""
	Return [local midnight, next local midnight) for one IANA calendar date.
	"""
	if not DATE_RE.fullmatch(date_text):
		raise RuntimeError(f"Invalid --date value: {date_text}. Use YYYY-MM-DD.")
	try:
		selected_date = date.fromisoformat(date_text)
	except ValueError as error:
		raise RuntimeError(f"Invalid --date value: {date_text}. Use YYYY-MM-DD.") from error
	try:
		local_timezone = ZoneInfo(timezone_name)
	except ZoneInfoNotFoundError as error:
		raise RuntimeError(f"Invalid IANA timezone: {timezone_name}") from error
	start = datetime.combine(selected_date, datetime.min.time(), tzinfo=local_timezone)
	end = datetime.combine(selected_date.fromordinal(selected_date.toordinal() + 1), datetime.min.time(), tzinfo=local_timezone)
	return start, end


#============================================
def get_nested_mapping(record: dict, first_key: str, second_key: str) -> dict:
	"""
	Read one nested GitHub mapping or return an empty mapping.
	"""
	outer = record.get(first_key)
	if not isinstance(outer, dict):
		return {}
	inner = outer.get(second_key)
	if not isinstance(inner, dict):
		return {}
	return inner


#============================================
def get_top_mapping(record: dict, key: str) -> dict:
	"""
	Read one top-level GitHub mapping or return an empty mapping.
	"""
	value = record.get(key)
	if not isinstance(value, dict):
		return {}
	return value


#============================================
def normalized_text(value) -> str:
	"""
	Normalize an identity value for exact case-insensitive comparison.
	"""
	text = str(value or "").strip().casefold()
	return text


#============================================
def extract_coauthors(message: str) -> list[dict]:
	"""
	Return signed co-author trailers from a commit message.
	"""
	trailers = []
	for name, email in CO_AUTHOR_RE.findall(message or ""):
		trailers.append({"name": name.strip(), "email": email.strip()})
	return trailers


#============================================
def classify_commit_identity(record: dict, configured_login: str, allowed_emails: list[str]) -> dict:
	"""
	Classify one commit identity as confirmed, ambiguous, or excluded.

	A configured GitHub login or an explicit allowed email confirms a direct author
	or committer identity. Any co-author trailer makes an otherwise matching commit
	ambiguous so it cannot become a personal daily claim without review.
	"""
	author = get_top_mapping(record, "author")
	committer = get_top_mapping(record, "committer")
	commit_author = get_nested_mapping(record, "commit", "author")
	commit_committer = get_nested_mapping(record, "commit", "committer")
	message = str(get_top_mapping(record, "commit").get("message") or "")
	login = normalized_text(configured_login)
	allowed = {normalized_text(email) for email in allowed_emails if normalized_text(email)}
	login_values = [
		normalized_text(author.get("login")),
		normalized_text(committer.get("login")),
	]
	email_values = [
		normalized_text(commit_author.get("email")),
		normalized_text(commit_committer.get("email")),
	]
	matching_logins = sorted({value for value in login_values if value and value == login})
	matching_emails = sorted({value for value in email_values if value and value in allowed})
	coauthors = extract_coauthors(message)
	target_coauthor = False
	for coauthor in coauthors:
		coauthor_email = normalized_text(coauthor.get("email"))
		if (coauthor_email in allowed) or (coauthor_email == login):
			target_coauthor = True
	direct_match = bool(matching_logins or matching_emails)
	if direct_match and coauthors:
		status = "ambiguous"
		reason = "direct identity match has co-author trailers"
	elif direct_match:
		status = "confirmed"
		reason = "configured GitHub login matched" if matching_logins else "allowed email matched"
	elif target_coauthor:
		status = "ambiguous"
		reason = "configured identity appears only in a co-author trailer"
	else:
		status = "excluded"
		reason = "no configured login or allowed email matched"
	evidence = {
		"status": status,
		"reason": reason,
		"configured_login": configured_login,
		"allowed_emails": sorted(allowed),
		"author_login": author.get("login") or "",
		"committer_login": committer.get("login") or "",
		"author_email": commit_author.get("email") or "",
		"committer_email": commit_committer.get("email") or "",
		"matching_logins": matching_logins,
		"matching_emails": matching_emails,
		"coauthors": coauthors,
	}
	return evidence


#============================================
def get_repository_name(record: dict) -> str:
	"""
	Resolve a repository full name from accepted raw commit record shapes.
	"""
	for key in ("repo_full_name", "repository", "repo"):
		value = record.get(key)
		if isinstance(value, dict):
			value = value.get("full_name") or value.get("name")
		text = str(value or "").strip()
		if text:
			return validate_repository_name(text)
	raise RuntimeError("Commit record must provide repo_full_name, repository.full_name, or repo.")


#============================================
def validate_repository_name(value) -> str:
	"""
	Require one canonical GitHub owner/repository name before using it in identifiers or URLs.
	"""
	text = str(value or "").strip()
	components = text.split("/")
	if len(components) != 2:
		raise RuntimeError("Commit repository must be exactly valid GitHub owner/repo components.")
	owner, repository = components
	if not GITHUB_OWNER_RE.fullmatch(owner) or not GITHUB_REPOSITORY_RE.fullmatch(repository):
		raise RuntimeError("Commit repository must be exactly valid GitHub owner/repo components.")
	return text


#============================================
def validate_git_object_id(value) -> str:
	"""
	Require a full SHA-1 or SHA-256 Git object identifier before using it in identifiers or URLs.
	"""
	sha = str(value or "").strip()
	if not GIT_OBJECT_ID_RE.fullmatch(sha):
		raise RuntimeError("Commit sha must be a full hexadecimal Git object identifier.")
	return sha


#============================================
def get_author_timestamp(record: dict) -> str:
	"""
	Return author timestamp, falling back to committer timestamp when necessary.
	"""
	commit_author = get_nested_mapping(record, "commit", "author")
	commit_committer = get_nested_mapping(record, "commit", "committer")
	value = commit_author.get("date") or commit_committer.get("date") or ""
	return str(value)


#============================================
def validate_commit_urls(record: dict, repository: str, sha: str) -> None:
	"""
	Require exact canonical GitHub API and HTML commit URLs for one repository SHA.
	"""
	repository = validate_repository_name(repository)
	sha = validate_git_object_id(sha)
	expected_api_url = f"https://api.github.com/repos/{repository}/commits/{sha}"
	expected_html_url = f"https://github.com/{repository}/commit/{sha}"
	api_url = str(record.get("url") or "").strip()
	html_url = str(record.get("html_url") or "").strip()
	if api_url != expected_api_url:
		raise RuntimeError("Commit API URL does not match its repository and SHA.")
	if html_url != expected_html_url:
		raise RuntimeError("Commit HTML URL does not match its repository and SHA.")


#============================================
def normalize_claim(record: dict, identity: dict) -> dict:
	"""
	Normalize one confirmed raw record into an agent-ready commit claim.
	"""
	repository = get_repository_name(record)
	sha = validate_git_object_id(record.get("sha"))
	validate_commit_urls(record, repository, sha)
	commit = get_top_mapping(record, "commit")
	api_url = str(record.get("url") or "").strip()
	html_url = str(record.get("html_url") or "").strip()
	author_timestamp = get_author_timestamp(record)
	committer_timestamp = str(get_nested_mapping(record, "commit", "committer").get("date") or "")
	claim = {
		"claim_id": f"{repository}:{sha}",
		"repository": repository,
		"sha": sha,
		"api_url": api_url,
		"html_url": html_url,
		"message": str(commit.get("message") or ""),
		"author_timestamp": author_timestamp,
		"committer_timestamp": committer_timestamp,
		"identity": identity,
	}
	return claim


#============================================
def is_in_local_date(record: dict, start: datetime, end: datetime) -> bool:
	"""
	Return whether a raw record's author timestamp belongs to the selected local date.
	"""
	timestamp = get_author_timestamp(record)
	if not timestamp:
		raise RuntimeError("Commit record must provide an author or committer timestamp.")
	moment = parse_iso_timestamp(timestamp).astimezone(start.tzinfo)
	return start <= moment < end


#============================================
def sort_claims(claims: list[dict]) -> list[dict]:
	"""
	Sort claims by repository then chronological author time and SHA.
	"""
	ordered = sorted(
		claims,
		key=lambda claim: (
			claim["repository"].casefold(),
			parse_iso_timestamp(claim["author_timestamp"]).astimezone(timezone.utc),
			claim["sha"],
		),
	)
	return ordered


#============================================
def collect_counts(evaluated: list[dict], duplicate_records: int, outside_date_records: int) -> dict:
	"""
	Count identity outcomes and normalized-record exclusions.
	"""
	counts = {
		"raw_records": len(evaluated) + duplicate_records + outside_date_records,
		"date_scoped_records": len(evaluated) + duplicate_records,
		"duplicate_records": duplicate_records,
		"outside_date_records": outside_date_records,
		"confirmed": 0,
		"ambiguous": 0,
		"excluded": 0,
	}
	for item in evaluated:
		status = item["identity"]["status"]
		counts[status] += 1
	return counts


#============================================
def is_nonnegative_page_count(value) -> bool:
	"""
	Return whether a pagination count is a nonnegative integer but not a boolean.
	"""
	valid = type(value) is int and value >= 0
	return valid


#============================================
def validate_pagination_metadata(
	pagination: list,
	expected_pages: int,
	received_pages: int,
	observed_repositories: set[str],
) -> list[str]:
	"""
	Return structural errors when per-repository pagination disagrees with collection metadata.
	"""
	errors = []
	expected_total = 0
	received_total = 0
	pagination_repositories = set()
	for item in pagination:
		if not isinstance(item, dict):
			errors.append("Collection pagination entries must be mappings.")
			continue
		try:
			repository = validate_repository_name(item.get("repository"))
		except RuntimeError:
			errors.append("Collection pagination repositories must be valid GitHub owner/repo names.")
			repository = ""
		if repository in pagination_repositories:
			errors.append("Collection pagination must contain one entry per repository.")
		pagination_repositories.add(repository)
		expected_value = item.get("expected_pages")
		received_value = item.get("received_pages")
		if type(expected_value) is not int or expected_value < 0:
			errors.append("Collection pagination expected_pages must be a nonnegative integer.")
			continue
		if type(received_value) is not int or received_value < 0:
			errors.append("Collection pagination received_pages must be a nonnegative integer.")
			continue
		expected_total += expected_value
		received_total += received_value
		if received_value > expected_value:
			errors.append("Collection pagination received_pages cannot exceed expected_pages.")
		complete_value = item.get("complete")
		if type(complete_value) is not bool:
			errors.append("Collection pagination complete metadata must be a boolean.")
		elif complete_value != (received_value == expected_value):
			errors.append("Collection pagination complete metadata does not match page counts.")
	if expected_total != expected_pages or received_total != received_pages:
		errors.append("Collection pagination totals do not match collection page counts.")
	missing_repositories = observed_repositories - pagination_repositories
	if missing_repositories:
		errors.append("Collection pagination omits a repository present in the input records.")
	return errors


#============================================
def create_evidence_artifacts(
	date_text: str,
	timezone_name: str,
	configured_login: str,
	allowed_emails: list[str],
	raw_records: list[dict],
	collection_metadata: dict,
	collected_at: str,
) -> tuple[dict, dict, dict]:
	"""
	Build raw provenance, normalized claims, and a completeness-bearing manifest.
	"""
	start, end = build_local_date_window(date_text, timezone_name)
	if not configured_login.strip():
		raise RuntimeError("A configured GitHub login is required.")
	metadata_errors = []
	if not isinstance(collection_metadata, dict):
		collection_metadata = {}
		metadata_errors.append("Collection metadata must be a mapping.")
	evaluated = []
	claims = []
	seen = set()
	observed_repositories = set()
	duplicate_records = 0
	outside_date_records = 0
	record_errors = []
	for raw_record in raw_records:
		if not isinstance(raw_record, dict):
			record_errors.append("Malformed commit record: expected a JSON object.")
			continue
		try:
			if not is_in_local_date(raw_record, start, end):
				outside_date_records += 1
				continue
			repository = get_repository_name(raw_record)
			observed_repositories.add(repository)
			sha = validate_git_object_id(raw_record.get("sha"))
			dedup_key = f"{repository}:{sha}"
			if dedup_key in seen:
				duplicate_records += 1
				continue
			seen.add(dedup_key)
			identity = classify_commit_identity(raw_record, configured_login, allowed_emails)
			evaluated.append({"repository": repository, "sha": sha, "identity": identity})
			if identity["status"] == "confirmed":
				claims.append(normalize_claim(raw_record, identity))
		except (TypeError, ValueError, RuntimeError) as error:
			record_errors.append(f"Malformed commit record: {error}")
	ordered_claims = sort_claims(claims)
	counts = collect_counts(evaluated, duplicate_records, outside_date_records)
	expected_value = collection_metadata.get("expected_pages", 1)
	received_value = collection_metadata.get("received_pages", expected_value)
	if is_nonnegative_page_count(expected_value):
		expected_pages = expected_value
	else:
		expected_pages = 0
		metadata_errors.append("Collection expected_pages must be a nonnegative integer.")
	if is_nonnegative_page_count(received_value):
		received_pages = received_value
	else:
		received_pages = 0
		metadata_errors.append("Collection received_pages must be a nonnegative integer.")
	if received_pages > expected_pages:
		metadata_errors.append("Collection received_pages cannot exceed expected_pages.")
	pagination_supplied = "pagination" in collection_metadata
	pagination = collection_metadata.get("pagination", [])
	if not pagination_supplied:
		metadata_errors.append("Collection pagination metadata is required.")
	elif not isinstance(pagination, list):
		metadata_errors.append("Collection pagination metadata must be a list.")
		pagination = []
	if isinstance(pagination, list):
		metadata_errors.extend(
			validate_pagination_metadata(
				pagination,
				expected_pages,
				received_pages,
				observed_repositories,
			)
		)
	error_values = collection_metadata.get("errors", [])
	errors = []
	if not isinstance(error_values, list):
		metadata_errors.append("Collection errors metadata must be a list of strings.")
	else:
		for item in error_values:
			if not isinstance(item, str):
				metadata_errors.append("Collection errors metadata must be a list of strings.")
				continue
			if item.strip():
				errors.append(item)
	errors.extend(metadata_errors)
	explicit_complete = collection_metadata.get("complete")
	if "complete" in collection_metadata and type(explicit_complete) is not bool:
		errors.append("Collection complete metadata must be a boolean.")
		explicit_complete = False
	errors.extend(record_errors)
	complete = (received_pages >= expected_pages) and (not errors)
	if explicit_complete is not None:
		complete = complete and explicit_complete
	raw_snapshot = {
		"schema_version": 1,
		"date": date_text,
		"timezone": timezone_name,
		"window_start": start.isoformat(),
		"window_end": end.isoformat(),
		"collected_at": collected_at,
		"records": raw_records,
	}
	claim_packet = {
		"schema_version": 1,
		"date": date_text,
		"timezone": timezone_name,
		"window_start": start.isoformat(),
		"window_end": end.isoformat(),
		"complete": complete,
		"claims": ordered_claims,
	}
	manifest = {
		"schema_version": 1,
		"date": date_text,
		"timezone": timezone_name,
		"configured_login": configured_login,
		"allowed_emails": sorted({email.strip() for email in allowed_emails if email.strip()}),
		"window_start": start.isoformat(),
		"window_end": end.isoformat(),
		"collected_at": collected_at,
		"expected_pages": expected_pages,
		"received_pages": received_pages,
		"pagination": pagination,
		"rate_limit": collection_metadata.get("rate_limit", {"status": "not_reported"}),
		"errors": errors,
		"complete": complete,
		"counts": counts,
		"artifacts": {
			"raw_snapshot": "raw_commits.json",
			"claim_packet": "claims.json",
		},
	}
	publication = publication_prerequisites(manifest, claim_packet)
	manifest["publication"] = publication
	return raw_snapshot, claim_packet, manifest


#============================================
def publication_prerequisites(manifest: dict, claim_packet: dict) -> dict:
	"""
	State whether evidence is safe for a later publication stage.
	"""
	reasons = []
	if not manifest.get("complete"):
		reasons.append("run manifest is incomplete")
	if not claim_packet.get("complete"):
		reasons.append("claim packet is incomplete")
	if manifest.get("date") != claim_packet.get("date"):
		reasons.append("claim packet date does not match run manifest")
	if manifest.get("timezone") != claim_packet.get("timezone"):
		reasons.append("claim packet timezone does not match run manifest")
	result = {"eligible": not reasons, "reasons": reasons}
	return result


#============================================
def write_json_file(path: str, payload: dict) -> None:
	"""
	Write one stable JSON artifact with a final newline.
	"""
	with open(path, "w", encoding="utf-8") as handle:
		json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
		handle.write("\n")


#============================================
def write_evidence_artifacts(output_root: str, output_user: str, date_text: str, raw_snapshot: dict, claim_packet: dict, manifest: dict) -> str:
	"""
	Atomically replace all daily evidence artifacts below one user-scoped date directory.
	"""
	base_dir = os.path.abspath(os.path.join(output_root, output_user, "daily", date_text))
	parent_dir = os.path.dirname(base_dir)
	generation_name = f".{date_text}.generation-{uuid.uuid4().hex}"
	staging_dir = os.path.join(parent_dir, generation_name)
	previous_dir = ""
	os.makedirs(parent_dir, exist_ok=True)
	os.makedirs(staging_dir)
	try:
		write_json_file(os.path.join(staging_dir, "raw_commits.json"), raw_snapshot)
		write_json_file(os.path.join(staging_dir, "claims.json"), claim_packet)
		write_json_file(os.path.join(staging_dir, "run_manifest.json"), manifest)
		if os.path.exists(base_dir):
			previous_dir = os.path.join(parent_dir, f".{date_text}.previous-{uuid.uuid4().hex}")
			os.replace(base_dir, previous_dir)
		try:
			os.replace(staging_dir, base_dir)
		except OSError:
			if previous_dir and os.path.exists(previous_dir):
				os.replace(previous_dir, base_dir)
			raise
		if previous_dir and os.path.exists(previous_dir):
			shutil.rmtree(previous_dir)
	except Exception:
		if os.path.exists(staging_dir):
			shutil.rmtree(staging_dir)
		raise
	return base_dir
