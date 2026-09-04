"""Bound oversized repository evidence once for Stage 3 and Stage 4."""

# Standard Library
import collections.abc
import dataclasses
import json

# local repo modules
import daily_blog.agents
import daily_blog.config
import daily_blog.io_utils
import daily_blog.projection
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.loader
import daily_blog.repository_outline_prompts
import daily_blog.schema


_SUMMARY_CHARS = 1200
_SUMMARY_SOURCE_CHARS = 48000


@dataclasses.dataclass(frozen=True)
class RepositoryEvidenceContext:
	"""Model-facing evidence text plus transparent reduction observations."""

	content: str
	summary_attempted: bool
	summary_succeeded: bool

	def __post_init__(self) -> None:
		# ASVS 2.2.1: enforce the existing model-frame limit at the trusted
		# coordinator boundary, including untrusted model-produced summary text.
		if (
			type(self.content) is not str or not self.content
			or len(self.content) > daily_blog.repository_outline_prompts.MAX_EVIDENCE_CONTEXT_CHARS
			or type(self.summary_attempted) is not bool
			or type(self.summary_succeeded) is not bool
			or self.summary_succeeded and not self.summary_attempted
		):
			raise RuntimeError("Repository evidence model context is invalid.")


#============================================
def _context_content(
	packet: daily_blog.schema.EvidencePacket,
	repository: str,
	summary: str,
	material: str,
) -> str:
	"""Encode one machine-owned wrapper around either compact context form."""
	content = json.dumps({
		"schema_version": "repository-evidence-summary.v1",
		"repository": repository,
		"packet_id": packet.packet_id,
		"model_packet_id": daily_blog.schema.model_cache_packet_identity(packet),
		"summary": summary,
		"deterministic_evidence_context": material,
	}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
	return content


#============================================
def _fit_summary(
	packet: daily_blog.schema.EvidencePacket,
	repository: str,
	summary: str,
	context_limit: int,
	context_fits: collections.abc.Callable[[str], bool],
) -> str:
	"""Keep the largest usable model summary within its consumer frame."""
	lower = 1
	upper = min(len(summary), _SUMMARY_CHARS)
	best = ""
	while lower <= upper:
		length = (lower + upper) // 2
		candidate = summary[:length]
		content = _context_content(packet, repository, candidate, "")
		if len(content) <= context_limit and context_fits(content):
			best = candidate
			lower = length + 1
		else:
			upper = length - 1
	return best


#============================================
def _bounded_fallback_content(
	packet: daily_blog.schema.EvidencePacket,
	repository: str,
	config: daily_blog.config.DailyBlogConfig,
	context_limit: int,
	context_fits: collections.abc.Callable[[str], bool],
) -> str:
	"""Render the largest deterministic fallback within the actual consumer frame."""
	minimum = _context_content(packet, repository, "", "")
	if len(minimum) > context_limit or not context_fits(minimum):
		raise daily_blog.agents.EditorialTerminalError(
			"Repository-outline generator limit cannot hold its required evidence envelope."
		)
	lower = 1
	upper = min(config.projection_limits["context_chars"], _SUMMARY_SOURCE_CHARS)
	best = ""
	while lower <= upper:
		length = (lower + upper) // 2
		bounded = daily_blog.projection.build_bounded_evidence_context(
			(packet,), config.projection_limits, length,
		)
		material = bounded.render_context(length)
		content = _context_content(packet, repository, "", material)
		if len(content) <= context_limit and context_fits(content):
			best = material
			lower = length + 1
		else:
			upper = length - 1
	if not best:
		raise daily_blog.agents.EditorialTerminalError(
			"Repository-outline generator limit cannot hold deterministic evidence context."
		)
	content = _context_content(packet, repository, "", best)
	return content


#============================================
def _request(
	packet: daily_blog.schema.EvidencePacket,
	repository: str,
	working_directory: str,
	config: daily_blog.config.DailyBlogConfig,
	prompt: str,
	prompt_identity: dict[str, object],
) -> daily_blog.agents.RouteRequest:
	"""Build one cache-safe request owned by the repository editorial batch."""
	logical_identity = {
		"report_date": packet.report_date,
		"repository": repository,
		"packet_id": daily_blog.schema.model_cache_packet_identity(packet),
		"step": "repository_evidence_summary",
		"role": "repository_evidence_summarizer",
		"prompt_identity": prompt_identity,
	}
	cache_input_hash = daily_blog.io_utils.hash_value(logical_identity)
	return daily_blog.agents.RouteRequest(
		request_id="repository_evidence_summary_" + cache_input_hash[:12],
		step="repository_evidence_summary",
		route=config.repository_outline.generator_route,
		prompt=prompt,
		working_directory=working_directory,
		role="repository_evidence_summarizer",
		retry_attempts=config.repository_outline.route_retry_attempts,
		maximum_parallel_calls=config.repository_outline.maximum_parallel_calls,
		input_hash=daily_blog.io_utils.hash_value({
			"logical": logical_identity, "working_directory": working_directory,
		}),
		contract_version="repository-context-summary-text.v1:" + str(prompt_identity["integrity_sha256"]),
		cache_input_hash=cache_input_hash,
	)


def build_repository_evidence_context(
	packet: daily_blog.schema.EvidencePacket,
	repository: str,
	working_directory: str,
	config: daily_blog.config.DailyBlogConfig,
	budget: daily_blog.agents.RouteBudget,
	runner: object | None,
	context_limit: int,
	cache_load: collections.abc.Callable[
		[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None,
	],
	cache_accept: collections.abc.Callable[
		[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None,
	],
	context_fits: collections.abc.Callable[[str], bool] | None = None,
) -> RepositoryEvidenceContext:
	"""Reduce evidence whenever it cannot fit the actual downstream prompt."""
	if (
		type(context_limit) is not int or context_limit <= 0
		or context_limit > daily_blog.repository_outline_prompts.MAX_EVIDENCE_CONTEXT_CHARS
	):
		raise daily_blog.agents.EditorialTerminalError("Repository evidence context limit is invalid.")
	if context_fits is None:
		context_fits = lambda content: len(content) <= context_limit
	if not callable(context_fits):
		raise daily_blog.agents.EditorialTerminalError("Repository evidence context consumer is invalid.")
	canonical = json.dumps(
		daily_blog.schema.model_cache_packet_content(packet), sort_keys=True,
		separators=(",", ":"), ensure_ascii=True,
	)
	if len(canonical) <= context_limit and context_fits(canonical):
		return RepositoryEvidenceContext(canonical, False, False)

	# ASVS 2.2.1/2.3.2: bind model input to the actual consuming prompt frame.
	source_limit = min(config.projection_limits["context_chars"], _SUMMARY_SOURCE_CHARS)
	bounded = daily_blog.projection.build_bounded_evidence_context(
		(packet,), config.projection_limits, source_limit,
	)
	material = bounded.render_context(source_limit)
	prompts = daily_blog.prompt_registry.loader.load_prompt_set(
		daily_blog.prompt_registry.definitions.CONTEXT_REDUCTION_PROMPT_SET,
	)
	identity = prompts.identity_dict()
	identity["integrity_sha256"] = daily_blog.io_utils.hash_value(identity)
	prompt = prompts.render(
		daily_blog.prompt_registry.definitions.CONTEXT_REDUCTION_RESOURCE,
		{"repository": repository, "material": material},
	)
	request = _request(packet, repository, working_directory, config, prompt, identity)
	result = daily_blog.agents.execute_requests(
		[request], runner, config.repository_outline.maximum_parallel_calls,
		budget, cache_load,
	)[0]
	summary = _fit_summary(
		packet, repository, result.text.strip(), context_limit, context_fits,
	) if result.ok else ""
	if summary and not result.resumed:
		cache_accept(request, result)
	# ASVS 1.5.2: model text is encoded only as plain JSON data. Machine-owned
	# identities come exclusively from the authoritative packet, never from it.
	content = _context_content(packet, repository, summary, "")
	if not summary:
		content = _bounded_fallback_content(packet, repository, config, context_limit, context_fits)
	return RepositoryEvidenceContext(content, True, bool(summary))
