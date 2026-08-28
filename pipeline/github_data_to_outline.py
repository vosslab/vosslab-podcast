#!/usr/bin/env python3
import argparse
import glob
import json
import os
import random
import re
import sys
from datetime import datetime

import local_llm_wrapper.llm_client

from podlib import depth_orchestrator
from podlib import github_outline_io
from podlib import pipeline_settings
from podlib import outline_llm

from podlib import prompt_loader


WORD_RE = re.compile(r"[A-Za-z0-9']+")
DEFAULT_INPUT_PATH = "out/github_data.jsonl"
DEFAULT_OUTLINE_JSON = "out/outline.json"
DEFAULT_OUTLINE_TXT = "out/outline.md"
DEFAULT_REPO_SHARDS_DIR = "out/outline_repos"
DEFAULT_DAILY_OUTLINES_DIR = "out/daily_outlines"
DAILY_GLOBAL_TARGET_WORDS = 2000
MIN_REPO_TARGET_WORDS = 750


#============================================
def log_step(message: str) -> None:
	"""
	Print one timestamped progress line.
	"""
	now_text = datetime.now().strftime("%H:%M:%S")
	print(f"[github_data_to_outline {now_text}] {message}", flush=True)


#============================================
def parse_args() -> argparse.Namespace:
	"""
	Parse command-line arguments.
	"""
	parser = argparse.ArgumentParser(
		description="Parse GitHub JSONL data and build summary outline outputs."
	)
	parser.add_argument(
		"--input",
		default=DEFAULT_INPUT_PATH,
		help="Path to input JSONL data from fetch_github_data.py.",
	)
	parser.add_argument(
		"--outline-json",
		default=DEFAULT_OUTLINE_JSON,
		help="Path to structured outline JSON output.",
	)
	parser.add_argument(
		"--outline-txt",
		default=DEFAULT_OUTLINE_TXT,
		help="Path to plain-text outline output.",
	)
	parser.add_argument(
		"--repo-shards-dir",
		default=DEFAULT_REPO_SHARDS_DIR,
		help="Directory for per-repo outline shard files.",
	)
	parser.add_argument(
		"--daily-outlines-dir",
		default=DEFAULT_DAILY_OUTLINES_DIR,
		help="Directory for dated daily outline snapshots (JSON + Markdown).",
	)
	parser.add_argument(
		"--skip-repo-shards",
		action="store_true",
		help="Skip writing per-repo outline shard outputs.",
	)
	parser.add_argument(
		"--continue",
		dest="continue_mode",
		action="store_true",
		help="Reuse existing repo outline shards when available (default: enabled).",
	)
	parser.add_argument(
		"--no-continue",
		dest="continue_mode",
		action="store_false",
		help="Disable reuse of existing repo outline shards.",
	)
	parser.set_defaults(continue_mode=True)
	parser.add_argument(
		"--settings",
		default="settings.yaml",
		help="YAML settings path for LLM defaults.",
	)
	parser.add_argument(
		"--llm-transport",
		choices=["ollama", "apple", "auto"],
		default=None,
		help="local-llm-wrapper transport selection (defaults from settings.yaml).",
	)
	parser.add_argument(
		"--llm-model",
		default=None,
		help="Optional model override (defaults from settings.yaml).",
	)
	parser.add_argument(
		"--llm-max-tokens",
		type=int,
		default=None,
		help="Maximum generation tokens per call (defaults from settings.yaml).",
	)
	parser.add_argument(
		"--llm-repo-limit",
		type=int,
		default=None,
		help="Optional cap for number of repos summarized (defaults from settings.yaml).",
	)
	parser.add_argument(
		'-d', '--depth', dest='depth', type=int, default=None,
		help="LLM generation depth 1-4 (higher = more candidates, better quality).",
	)
	args = parser.parse_args()
	return args


#============================================
def add_local_llm_wrapper_to_path() -> None:
	"""
	Add local-llm-wrapper path to sys.path when present.
	"""
	script_dir = os.path.dirname(os.path.abspath(__file__))
	repo_root = os.path.dirname(script_dir)
	candidates = [
		os.path.join(repo_root, "local-llm-wrapper"),
		os.path.join(repo_root, "pipeline", "local-llm-wrapper"),
	]
	for wrapper_repo in candidates:
		if not os.path.isdir(wrapper_repo):
			continue
		if wrapper_repo not in sys.path:
			sys.path.insert(0, wrapper_repo)
		return

#============================================
def build_repo_llm_prompt(outline: dict, bucket: dict, rank: int, repo_total: int) -> str:
	"""
	Build one repo-specific LLM prompt.
	"""
	context = github_outline_io.build_repo_context(bucket)
	context_json = json.dumps(context, ensure_ascii=True, indent=2)
	template = prompt_loader.load_prompt("outline_repo.txt")
	prompt = prompt_loader.render_prompt(template, {
		"user": outline.get("user", "unknown"),
		"window_start": outline.get("window_start", ""),
		"window_end": outline.get("window_end", ""),
		"context_json": context_json,
	})
	return prompt


#============================================
def build_repo_llm_prompt_with_target(
	outline: dict,
	bucket: dict,
	target_words: int,
	changelog_char_budget: int = 8000,
) -> str:
	"""
	Build one repo-specific LLM prompt with target word guidance.

	Args:
		outline: full outline dict.
		bucket: repo activity bucket.
		target_words: target word count for the outline.
		changelog_char_budget: max chars for changelog entries (default 8000).
	"""
	context = github_outline_io.build_repo_context(
		bucket,
		changelog_char_budget=changelog_char_budget,
	)
	context_json = json.dumps(context, ensure_ascii=True, indent=2)
	template = prompt_loader.load_prompt("outline_repo_targeted.txt")
	prompt = prompt_loader.render_prompt_with_target(template, {
		"user": outline.get("user", "unknown"),
		"window_start": outline.get("window_start", ""),
		"window_end": outline.get("window_end", ""),
		"target_words": str(target_words),
		"context_json": context_json,
	}, target_value=str(target_words), unit="words", document_name="repo outline")
	return prompt


#============================================
def count_words(text: str) -> int:
	"""
	Count words in a text block.
	"""
	return len(WORD_RE.findall(text or ""))


#============================================
def build_global_llm_prompt(
	outline: dict,
	repo_summaries: list[dict],
	repo_limit: int = 12,
	excerpt_chars: int = 700,
	target_words: int = DAILY_GLOBAL_TARGET_WORDS,
) -> str:
	"""
	Build one global compilation LLM prompt from repo-level summaries.
	"""
	compact_repos = []
	ordered = sorted(
		repo_summaries,
		key=lambda item: int(item.get("total_activity", 0)),
		reverse=True,
	)
	for item in ordered[:repo_limit]:
		compact_repos.append(
			{
				"repo_full_name": item.get("repo_full_name", ""),
				"total_activity": item.get("total_activity", 0),
				"repo_outline_excerpt": item.get("repo_outline", "")[:excerpt_chars],
			}
		)
	context = {
		"user": outline.get("user", "unknown"),
		"window_start": outline.get("window_start", ""),
		"window_end": outline.get("window_end", ""),
		"totals": outline.get("totals", {}),
		"repos": compact_repos,
		"notable_commit_messages": list(outline.get("notable_commit_messages", []))[:40],
	}
	context_json = json.dumps(context, ensure_ascii=True, indent=2)
	template = prompt_loader.load_prompt("outline_global.txt")
	prompt = prompt_loader.render_prompt_with_target(template, {
		"target_words": str(target_words),
		"context_json": context_json,
	}, target_value=str(target_words), unit="words", document_name="daily outline")
	return prompt


#============================================
def outline_quality_issue(text: str) -> str:
	"""
	Return a validation issue string when outline text is unusable.
	"""
	clean = (text or "").strip()
	if not clean:
		return "empty output"
	lower = clean.lower()
	if ("error_code" in lower) or ("generationerror" in lower):
		return "llm returned error payload"
	if clean.startswith("{") and clean.endswith("}"):
		return "llm returned structured error/object text"
	return ""


#============================================
def _referee_outline(
	client: local_llm_wrapper.llm_client.LLMClient,
	draft_a: str,
	draft_b: str,
	max_tokens: int,
) -> str:
	"""
	Run referee comparison between two outline draft texts.
	"""
	labels = [("A", "B"), ("B", "A")]
	label_a, label_b = random.choice(labels)
	if label_a == "B":
		draft_a, draft_b = draft_b, draft_a
	template = prompt_loader.load_prompt("depth_referee_outline.txt")
	prompt = prompt_loader.render_prompt(template, {
		"label_a": label_a,
		"label_b": label_b,
		"draft_a": draft_a,
		"draft_b": draft_b,
	})
	raw = client.generate(
		prompt=prompt,
		purpose="outline referee",
		max_tokens=max_tokens,
	).strip()
	return raw


#============================================
def _polish_outline(
	client: local_llm_wrapper.llm_client.LLMClient,
	drafts: list[str],
	depth: int,
	target_words: int,
	max_tokens: int,
) -> str:
	"""
	Run polish pass to merge multiple outline drafts into one final outline.
	"""
	parts = []
	for i, draft in enumerate(drafts, start=1):
		parts.append(f"Draft {i}:\n{draft}")
	drafts_block = "\n\n".join(parts)
	template = prompt_loader.load_prompt("depth_polish_outline.txt")
	prompt = prompt_loader.render_prompt(template, {
		"draft_count": str(len(drafts)),
		"drafts_block": drafts_block,
		"target_value": str(target_words),
		"target_unit": "words",
	})
	polished = client.generate(
		prompt=prompt,
		purpose="outline polish",
		max_tokens=max_tokens,
	).strip()
	polished = outline_llm.strip_xml_wrapper(polished)
	return polished


#============================================
def is_context_window_error(error: Exception) -> bool:
	"""
	Detect model context-window failures from wrapped transport errors.
	"""
	text = str(error).lower()
	if "contextwindowexceedederror" in text:
		return True
	if "context window" in text:
		return True
	if "exceeded model context window size" in text:
		return True
	return False


#============================================
def generate_global_outline_with_retry(
	client: local_llm_wrapper.llm_client.LLMClient,
	outline: dict,
	repo_summaries: list[dict],
	max_tokens: int,
	target_words: int = DAILY_GLOBAL_TARGET_WORDS,
) -> str:
	"""
	Generate global outline with progressive prompt shrinking on context overflow.
	"""
	attempts = [
		(20, 900),
		(12, 600),
		(8, 400),
		(5, 250),
	]
	last_error = None
	for attempt_index, (repo_limit, excerpt_chars) in enumerate(attempts, start=1):
		log_step(
			f"Generating global outline attempt {attempt_index}/{len(attempts)} "
			+ f"(repo_limit={repo_limit}, excerpt_chars={excerpt_chars})."
		)
		prompt = build_global_llm_prompt(
			outline,
			repo_summaries,
			repo_limit=repo_limit,
			excerpt_chars=excerpt_chars,
			target_words=target_words,
		)
		try:
			result = client.generate(
				prompt=prompt,
				purpose="daily global outline",
				max_tokens=max_tokens,
			).strip()
			result = outline_llm.strip_xml_wrapper(result)
			return result
		except RuntimeError as error:
			last_error = error
			if not is_context_window_error(error):
				raise
			log_step(
				"Global outline attempt hit context window; retrying with smaller prompt."
			)
	if last_error is not None:
		raise last_error
	raise RuntimeError("Global outline generation failed without a captured error.")


#============================================
def enforce_global_outline_word_band(
	client: local_llm_wrapper.llm_client.LLMClient,
	outline: dict,
	repo_summaries: list[dict],
	global_outline: str,
	max_tokens: int,
	target_words: int = DAILY_GLOBAL_TARGET_WORDS,
) -> str:
	"""
	Enforce 0.5x..2x word band around target with one retry.
	"""
	word_count = count_words(global_outline)
	lower_bound = max(1, target_words // 2)
	upper_bound = target_words * 2
	if lower_bound <= word_count <= upper_bound:
		return global_outline
	log_step(
		"Global outline target miss; retrying once "
		+ f"(words={word_count}, target={target_words})."
	)
	retry_prompt = (
		f"Your outline was {word_count} words. "
		+ f"Rewrite to about {target_words} words.\n\n"
		+ build_global_llm_prompt(
			outline,
			repo_summaries,
			target_words=target_words,
		)
	)
	result = client.generate(
		prompt=retry_prompt,
		purpose="daily global outline retry",
		max_tokens=max_tokens,
	).strip()
	result = outline_llm.strip_xml_wrapper(result)
	return result


#============================================
def create_llm_client(
	transport_name: str,
	model_override: str,
) -> local_llm_wrapper.llm_client.LLMClient:
	"""
	Create local-llm-wrapper client for outline summarization.
	"""
	add_local_llm_wrapper_to_path()
	import local_llm_wrapper.llm as llm

	model_choice = llm.choose_model(model_override or None)
	transports = []
	if transport_name == "ollama":
		transports.append(llm.OllamaTransport(model=model_choice))
	elif transport_name == "apple":
		transports.append(llm.AppleTransport())
	elif transport_name == "auto":
		transports.append(llm.AppleTransport())
		transports.append(llm.OllamaTransport(model=model_choice))
	else:
		raise RuntimeError(f"Unsupported llm transport: {transport_name}")
	client = llm.LLMClient(transports=transports, quiet=True)
	return client


#============================================
def load_cached_repo_outline_map(repo_shards_dir: str, outline: dict) -> dict[str, str]:
	"""
	Load repo outline cache from shard JSON files when metadata matches.
	"""
	shards_path = os.path.abspath(repo_shards_dir)
	if not os.path.isdir(shards_path):
		return {}

	target_user = (outline.get("user") or "").strip()
	target_window_start = (outline.get("window_start") or "").strip()
	target_window_end = (outline.get("window_end") or "").strip()
	cache: dict[str, str] = {}

	candidate_paths: list[str] = []
	manifest_path = os.path.join(shards_path, "index.json")
	if os.path.isfile(manifest_path):
		try:
			with open(manifest_path, "r", encoding="utf-8") as handle:
				manifest = json.load(handle)
			entries = manifest.get("repo_shards") or []
			for entry in entries:
				if not isinstance(entry, dict):
					continue
				json_path = str(entry.get("json_path") or "").strip()
				if not json_path:
					continue
				if not os.path.isabs(json_path):
					json_path = os.path.join(shards_path, json_path)
				if os.path.isfile(json_path):
					candidate_paths.append(os.path.abspath(json_path))
		except Exception:
			candidate_paths = []
	if not candidate_paths:
		fallback_paths = glob.glob(os.path.join(shards_path, "*.json"))
		for json_path in fallback_paths:
			if os.path.basename(json_path) == "index.json":
				continue
			candidate_paths.append(os.path.abspath(json_path))

	for json_path in candidate_paths:
		try:
			with open(json_path, "r", encoding="utf-8") as handle:
				shard = json.load(handle)
		except Exception:
			continue
		if not isinstance(shard, dict):
			continue
		shard_user = (shard.get("user") or "").strip()
		shard_window_start = (shard.get("window_start") or "").strip()
		shard_window_end = (shard.get("window_end") or "").strip()
		if target_user and (shard_user != target_user):
			continue
		if target_window_start and (shard_window_start != target_window_start):
			continue
		if target_window_end and (shard_window_end != target_window_end):
			continue
		bucket = shard.get("repo_activity")
		if not isinstance(bucket, dict):
			continue
		repo_full_name = str(bucket.get("repo_full_name") or "").strip()
		if not repo_full_name:
			continue
		repo_outline = str(bucket.get("llm_repo_outline") or "").strip()
		if not repo_outline:
			continue
		cache[repo_full_name] = repo_outline
	return cache


#============================================
def _generate_one_repo_draft(
	client: local_llm_wrapper.llm_client.LLMClient,
	outline: dict,
	bucket: dict,
	scaled_target: int,
	max_tokens: int,
	repo_name: str,
) -> str:
	"""
	Generate one repo outline draft with context window retry.
	"""
	from local_llm_wrapper.errors import ContextWindowError
	prompt = build_repo_llm_prompt_with_target(outline, bucket, scaled_target)
	try:
		draft = client.generate(
			prompt=prompt,
			purpose="daily repo outline",
			max_tokens=max_tokens,
		).strip()
	except (ContextWindowError, RuntimeError) as exc:
		if "context window" not in str(exc).lower():
			raise
		log_step(
			f"Context window exceeded for {repo_name} "
			+ f"(prompt ~{len(prompt)} chars); retrying with trimmed changelog."
		)
		# rebuild prompt with 25% trimmed changelog
		prompt = build_repo_llm_prompt_with_target(
			outline, bucket, scaled_target, changelog_char_budget=6000,
		)
		draft = client.generate(
			prompt=prompt,
			purpose="daily repo outline (trimmed)",
			max_tokens=max_tokens,
		).strip()
	draft = outline_llm.strip_xml_wrapper(draft)
	# enforce word band with one retry
	word_count = count_words(draft)
	lower_bound = max(1, scaled_target // 2)
	upper_bound = scaled_target * 2
	if (word_count < lower_bound) or (word_count > upper_bound):
		log_step(
			"Repo outline target miss; retrying once "
			+ f"({repo_name}: words={word_count}, target={scaled_target})."
		)
		retry_prompt = (
			f"Your outline was {word_count} words. "
			+ f"Rewrite to about {scaled_target} words.\n\n"
			+ prompt
		)
		draft = client.generate(
			prompt=retry_prompt,
			purpose="daily repo outline retry",
			max_tokens=max_tokens,
		).strip()
		draft = outline_llm.strip_xml_wrapper(draft)
	return draft


#============================================
def _generate_repo_outline_with_depth(
	client: local_llm_wrapper.llm_client.LLMClient,
	outline: dict,
	bucket: dict,
	scaled_target: int,
	max_tokens: int,
	depth: int,
	repo_name: str,
	repo_shards_dir: str,
	continue_mode: bool,
) -> str:
	"""
	Generate repo outline using the depth pipeline for multi-draft quality.

	At depth 1, runs a single draft. At depth 2+, generates multiple drafts
	and applies polish (and referee at depth 4) via depth_orchestrator.
	"""
	if depth <= 1:
		# single-pass: generate one draft directly
		result = _generate_one_repo_draft(
			client, outline, bucket, scaled_target, max_tokens, repo_name,
		)
		return result

	# depth 2+: use depth pipeline for multi-draft generation
	repo_slug = github_outline_io.sanitize_repo_slug(repo_name)

	def _gen_draft() -> str:
		return _generate_one_repo_draft(
			client, outline, bucket, scaled_target, max_tokens, repo_name,
		)

	def _referee(draft_a: str, draft_b: str) -> str:
		return _referee_outline(client, draft_a, draft_b, max_tokens)

	def _polish(drafts: list, d: int) -> str:
		return _polish_outline(client, drafts, d, scaled_target, max_tokens)

	depth_cache_dir = os.path.join(os.path.abspath(repo_shards_dir), "depth_cache")
	result = depth_orchestrator.run_depth_pipeline(
		generate_draft_fn=_gen_draft,
		referee_fn=_referee,
		polish_fn=_polish,
		depth=depth,
		cache_dir=depth_cache_dir,
		cache_key_prefix=f"outline_repo_{repo_slug}",
		continue_mode=continue_mode,
		max_tokens=max_tokens,
		quality_check_fn=outline_quality_issue,
		logger=log_step,
	)
	return result


#============================================
def summarize_outline_with_llm(
	outline: dict,
	*,
	transport_name: str,
	model_override: str,
	max_tokens: int,
	repo_limit: int,
	repo_shards_dir: str = "out/outline_repos",
	continue_mode: bool = True,
	depth: int = 1,
) -> dict:
	"""
	Generate repo and global summaries with local-llm-wrapper.
	"""
	log_step(
		f"Initializing LLM summarization with transport={transport_name}, "
		+ f"model={model_override or 'auto'}, max_tokens={max_tokens}, "
		+ f"repo_limit={repo_limit}, continue_mode={continue_mode}"
	)
	repos = outline.get("repo_activity", [])
	repo_total = len(repos)
	selected_repos = repos
	if repo_limit > 0:
		selected_repos = repos[:repo_limit]
	repo_target_words = github_outline_io.compute_repo_outline_target_words(len(selected_repos))
	log_step(
		"Computed repo outline target words: "
		+ f"{repo_target_words} (formula=max(750, ceil(2000/(N-1))), N={len(selected_repos)})"
	)
	log_step(f"Summarizing {len(selected_repos)} repo(s) out of {repo_total} total.")
	log_step("")
	cache_hits = 0
	cached_repo_outlines: dict[str, str] = {}
	if continue_mode:
		cached_repo_outlines = load_cached_repo_outline_map(repo_shards_dir, outline)
		log_step(
			f"Loaded {len(cached_repo_outlines)} cached repo outline(s) from "
			+ os.path.abspath(repo_shards_dir)
		)
	else:
		log_step("Continue mode disabled; regenerating all repo outlines.")

	repo_summaries = []
	client = None
	for rank, bucket in enumerate(selected_repos, start=1):
		repo_name = bucket.get("repo_full_name", "")
		# scale word target per repo based on input data richness
		scaled_target = github_outline_io.compute_repo_word_target(bucket, repo_target_words)
		# log input stats driving the scaled target (uses truncated changelog)
		msg_chars = sum(len(m) for m in bucket.get("commit_messages", []))
		issue_chars = sum(len(t) for t in bucket.get("issue_titles", []))
		pr_chars = sum(len(t) for t in bucket.get("pull_request_titles", []))
		truncated = github_outline_io.truncate_changelog_entries(
			bucket.get("changelog_entries", [])
		)
		changelog_chars = sum(len(e.get("entry_text", "")) for e in truncated)
		commit_chars = msg_chars + issue_chars + pr_chars
		input_chars = commit_chars + changelog_chars
		log_step(
			f"Repo {rank}/{len(selected_repos)} {repo_name}: "
			+ f"commit_chars={commit_chars}, changelog_chars={changelog_chars}, "
			+ f"total_input_chars={input_chars}, total_input_words={input_chars // 5}, "
			+ f"scaled_target={scaled_target}, ceiling={repo_target_words}"
		)
		repo_outline = cached_repo_outlines.get(repo_name, "")
		if repo_outline:
			# validate cached outline against scaled word target guardrails
			cached_word_count = count_words(repo_outline)
			cache_lower = max(1, scaled_target // 2)
			cache_upper = scaled_target * 2
			if cache_lower <= cached_word_count <= cache_upper:
				cache_hits += 1
				log_step(f"Reusing cached repo outline {rank}/{len(selected_repos)}: {repo_name}")
			else:
				log_step(
					f"Rejecting cached repo outline for {repo_name}; "
					+ f"words={cached_word_count} outside guardrail "
					+ f"[{cache_lower}-{cache_upper}] (target={scaled_target})"
				)
				repo_outline = ""
		if not repo_outline:
			if client is None:
				client = create_llm_client(transport_name, model_override)
			log_step(
				f"Generating repo outline {rank}/{len(selected_repos)}: "
				+ f"{repo_name} (target={scaled_target} words, depth={depth})"
			)
			repo_outline = _generate_repo_outline_with_depth(
				client=client,
				outline=outline,
				bucket=bucket,
				scaled_target=scaled_target,
				max_tokens=max_tokens,
				depth=depth,
				repo_name=repo_name,
				repo_shards_dir=repo_shards_dir,
				continue_mode=continue_mode,
			)
		bucket["llm_repo_outline"] = repo_outline
		log_step(
			f"Completed repo outline for {repo_name}; chars={len(repo_outline)}, "
			+ f"words={count_words(repo_outline)}, target={scaled_target}"
		)
		repo_summaries.append(
			{
				"repo_full_name": bucket.get("repo_full_name", ""),
				"total_activity": bucket.get("total_activity", 0),
				"repo_outline": repo_outline,
			}
		)

	# compute total input size going into the global outline
	total_outline_chars = sum(len(s.get("repo_outline", "")) for s in repo_summaries)
	total_outline_words = sum(count_words(s.get("repo_outline", "")) for s in repo_summaries)
	# scale global target: 75% of input words, capped at 2000
	global_target = min(DAILY_GLOBAL_TARGET_WORDS, max(400, total_outline_words * 3 // 4))
	log_step("")
	log_step(
		"Generating global compilation outline from repo summaries: "
		+ f"input_chars={total_outline_chars}, input_words={total_outline_words}, "
		+ f"target={global_target} words, depth={depth}"
	)
	if client is None:
		client = create_llm_client(transport_name, model_override)

	if depth <= 1:
		# depth 1: original single-pass behavior
		global_outline = generate_global_outline_with_retry(
			client,
			outline,
			repo_summaries,
			max_tokens=max_tokens,
			target_words=global_target,
		)
		global_outline = enforce_global_outline_word_band(
			client,
			outline,
			repo_summaries,
			global_outline,
			max_tokens=max_tokens,
			target_words=global_target,
		)
	else:
		# depth 2-4: use depth pipeline for global outline
		def _generate_one_outline() -> str:
			"""Generate one global outline draft."""
			result = generate_global_outline_with_retry(
				client,
				outline,
				repo_summaries,
				max_tokens=max_tokens,
				target_words=global_target,
			)
			return enforce_global_outline_word_band(
				client,
				outline,
				repo_summaries,
				result,
				max_tokens=max_tokens,
				target_words=global_target,
			)

		def _referee(draft_a: str, draft_b: str) -> str:
			return _referee_outline(client, draft_a, draft_b, max_tokens)

		def _polish(drafts: list, d: int) -> str:
			return _polish_outline(
				client, drafts, d, global_target, max_tokens,
			)

		depth_cache_dir = os.path.join(
			os.path.abspath(repo_shards_dir), "depth_cache",
		)
		global_outline = depth_orchestrator.run_depth_pipeline(
			generate_draft_fn=_generate_one_outline,
			referee_fn=_referee,
			polish_fn=_polish,
			depth=depth,
			cache_dir=depth_cache_dir,
			cache_key_prefix="outline_global",
			continue_mode=continue_mode,
			max_tokens=max_tokens,
			quality_check_fn=outline_quality_issue,
			logger=log_step,
		)
	outline["llm_global_outline"] = global_outline
	outline["llm_repo_summaries_count"] = len(selected_repos)
	outline["llm_cached_repo_outline_count"] = cache_hits
	outline["llm_generated_repo_outline_count"] = len(selected_repos) - cache_hits
	outline["llm_transport"] = transport_name
	outline["llm_model"] = model_override or "auto"
	log_step(f"Completed global outline; chars={len(global_outline)}")
	return outline


#============================================
def main() -> None:
	"""
	Run outline generation from JSONL input.
	"""
	args = parse_args()
	settings, settings_path = pipeline_settings.load_settings(args.settings)
	user = pipeline_settings.get_github_username(settings, "vosslab")
	default_transport = pipeline_settings.get_enabled_llm_transport(settings)
	default_model = pipeline_settings.get_llm_provider_model(settings, default_transport)
	default_max_tokens = pipeline_settings.get_setting_int(settings, ["llm", "max_tokens"], 1200)
	default_repo_limit = pipeline_settings.get_setting_int(settings, ["llm", "repo_limit"], 0)
	default_depth = pipeline_settings.get_llm_depth(settings, 1)
	input_path = pipeline_settings.resolve_user_scoped_out_path(
		args.input,
		DEFAULT_INPUT_PATH,
		user,
	)
	if input_path == pipeline_settings.resolve_user_scoped_out_path(
		DEFAULT_INPUT_PATH,
		DEFAULT_INPUT_PATH,
		user,
	):
		input_path = github_outline_io.resolve_latest_fetch_input(input_path)
	outline_json_path = pipeline_settings.resolve_user_scoped_out_path(
		args.outline_json,
		DEFAULT_OUTLINE_JSON,
		user,
	)
	outline_txt_path = pipeline_settings.resolve_user_scoped_out_path(
		args.outline_txt,
		DEFAULT_OUTLINE_TXT,
		user,
	)
	repo_shards_dir = pipeline_settings.resolve_user_scoped_out_path(
		args.repo_shards_dir,
		DEFAULT_REPO_SHARDS_DIR,
		user,
	)
	daily_outlines_dir = pipeline_settings.resolve_user_scoped_out_path(
		args.daily_outlines_dir,
		DEFAULT_DAILY_OUTLINES_DIR,
		user,
	)

	transport_name = args.llm_transport or default_transport
	if transport_name not in {"ollama", "apple", "auto"}:
		raise RuntimeError(f"Unsupported llm transport in settings: {transport_name}")
	model_override = default_model
	if args.llm_model is not None:
		model_override = args.llm_model.strip()
	max_tokens = default_max_tokens if args.llm_max_tokens is None else args.llm_max_tokens
	repo_limit = default_repo_limit if args.llm_repo_limit is None else args.llm_repo_limit
	if max_tokens < 1:
		raise RuntimeError("llm max tokens must be >= 1")
	if repo_limit < 0:
		raise RuntimeError("llm repo limit must be >= 0")
	# depth: CLI overrides settings.yaml
	depth = args.depth if args.depth is not None else default_depth
	depth_orchestrator.validate_depth(depth)

	log_step(f"Using settings file: {settings_path}")
	log_step(
		"Using LLM settings: "
		+ f"transport={transport_name}, model={model_override or 'auto'}, "
		+ f"max_tokens={max_tokens}, repo_limit={repo_limit}, depth={depth}"
	)
	log_step(f"Parsing input JSONL: {os.path.abspath(input_path)}")
	outline = github_outline_io.parse_jsonl_to_outline(input_path)
	log_step(
		f"Parsed outline totals: repos={outline.get('totals', {}).get('repos', 0)}, "
		+ f"commits={outline.get('totals', {}).get('commit_records', 0)}, "
		+ f"issues={outline.get('totals', {}).get('issue_records', 0)}, "
		+ f"prs={outline.get('totals', {}).get('pull_request_records', 0)}"
	)
	outline = summarize_outline_with_llm(
		outline,
		transport_name=transport_name,
		model_override=model_override,
		max_tokens=max_tokens,
		repo_limit=repo_limit,
		repo_shards_dir=repo_shards_dir,
		continue_mode=args.continue_mode,
		depth=depth,
	)
	github_outline_io.write_outline_outputs(
		outline,
		outline_json_path,
		outline_txt_path,
		repo_shards_dir,
		args.skip_repo_shards,
		log_fn=log_step,
	)
	daily_json_path, daily_md_path = github_outline_io.write_daily_outline_snapshot(
		outline,
		daily_outlines_dir,
	)
	log_step(f"Wrote daily outline JSON: {daily_json_path}")
	log_step(f"Wrote daily outline Markdown: {daily_md_path}")
	log_step("Outline stage complete.")


if __name__ == "__main__":
	main()
