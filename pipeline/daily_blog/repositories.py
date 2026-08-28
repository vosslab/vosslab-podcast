"""Authoritative GitHub owner-roster acquisition for daily publication."""

# Standard Library
import os
import re

# local repo modules
import daily_blog.schema
import daily_blog.repository_contracts
import podlib.github_client
import podlib.runtime_credentials


REPOSITORY_POLICY_VERSION = "public-owner-repositories-v1"
GITHUB_PAYLOAD_KEYS = {
	"archived",
	"clone_url",
	"created_at",
	"disabled",
	"fork",
	"full_name",
	"html_url",
	"owner",
	"private",
}


#============================================
def _validated_record(
	owner: str,
	value: object,
) -> daily_blog.repository_contracts.RepositoryRecord | None:
	"""Validate one GitHub response object and return it when publication-eligible."""
	# ASVS V2.2.1 and V16.5.1: positively validate every remote field and fail closed.
	if not isinstance(value, dict) or not GITHUB_PAYLOAD_KEYS.issubset(value):
		raise RuntimeError("GitHub repository roster entry is incomplete.")
	owner_value = value["owner"]
	if not isinstance(owner_value, dict) or "login" not in owner_value:
		raise RuntimeError("GitHub repository roster owner is incomplete.")
	owner_login = owner_value["login"]
	if not isinstance(owner_login, str):
		raise RuntimeError("GitHub repository roster owner is incomplete.")
	full_name = value["full_name"]
	if not isinstance(full_name, str):
		raise RuntimeError("GitHub repository roster identity must be text.")
	match = daily_blog.repository_contracts.REPOSITORY_NAME_RE.fullmatch(full_name)
	if match is None or ".." in match.group("name"):
		raise RuntimeError("GitHub repository roster identity is invalid.")
	if (
		match.group("owner").casefold() != owner.casefold()
		or owner_login.casefold() != owner.casefold()
	):
		raise RuntimeError("GitHub repository roster contains an owner mismatch.")
	for key in ("archived", "disabled", "fork", "private"):
		if type(value[key]) is not bool:
			raise RuntimeError(f"GitHub repository roster {key} state must be Boolean.")
	expected_page = f"https://github.com/{full_name}"
	expected_clone = expected_page + ".git"
	# ASVS V13.2.1: the remote service and clone target use an exact HTTPS allowlist.
	if value["html_url"] != expected_page or value["clone_url"] != expected_clone:
		raise RuntimeError("GitHub repository roster URL is outside canonical HTTPS GitHub scope.")
	created_at = daily_blog.repository_contracts.canonical_utc_timestamp(
		value["created_at"], "GitHub repository creation time"
	)
	if value["private"] or value["archived"] or value["disabled"]:
		return None
	record = daily_blog.repository_contracts.RepositoryRecord.from_dict(
		{
			"repository": full_name,
			"repository_url": expected_page,
			"clone_url": expected_clone,
			"created_at": created_at,
			"is_fork": value["fork"],
		}
	)
	return record


#============================================
def repository_payload_to_roster(
	owner: str,
	value: object,
) -> daily_blog.repository_contracts.RepositoryRoster:
	"""Convert one complete GitHub list response into the eligible typed roster."""
	if not re.fullmatch(r"[A-Za-z0-9-]+", owner):
		raise RuntimeError("GitHub repository roster owner is invalid.")
	if not isinstance(value, list):
		raise RuntimeError("GitHub repository roster response must be a list.")
	records = []
	seen = set()
	for item in value:
		record = _validated_record(owner, item)
		if record is None:
			continue
		identity = record.repository.casefold()
		if identity in seen:
			raise RuntimeError("GitHub repository roster contains duplicate identities.")
		seen.add(identity)
		records.append(record)
	return daily_blog.repository_contracts.RepositoryRoster.create(owner, records)


#============================================
def discover_owner_repositories(
	owner: str,
	output_root: str,
) -> daily_blog.repository_contracts.RepositoryRoster:
	"""Fetch a fresh owner roster without exposing credentials or remote payloads."""
	if not re.fullmatch(r"[A-Za-z0-9-]+", owner):
		raise RuntimeError("GitHub repository roster owner is invalid.")
	token = podlib.runtime_credentials.get_github_token()
	cache_dir = os.path.join(output_root, owner, "daily_blog_cache", "github_owner_roster_api")
	client = podlib.github_client.GitHubClient(token, cache_dir=cache_dir)
	# PyGithub owns the HTTPS transport; bypass its 24-hour data cache
	# so a repository created earlier in the report day cannot be hidden by a stale roster.
	payload = client.list_repos(owner, use_cache=False)
	return repository_payload_to_roster(owner, payload)
