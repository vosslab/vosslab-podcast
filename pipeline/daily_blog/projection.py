"""Deterministic bounded editorial projections over authoritative evidence packets."""

# Standard Library
import collections

# local repo modules
import daily_blog.schema
import daily_blog.io_utils


PROJECTION_POLICY_VERSION = "story-first-lifecycle-authority-round-robin-v3"
PROJECTION_LIMIT_KEYS = {
	"commit_subject_chars",
	"context_chars",
	"excerpt_chars",
}


#============================================
def _validate_limits(limits: dict[str, int]) -> dict[str, int]:
	"""Require the complete clean-cutover projection limit contract."""
	if set(limits) != PROJECTION_LIMIT_KEYS:
		raise RuntimeError("Projection limits must declare the exact supported keys.")
	for key, value in limits.items():
		if type(value) is not int or value <= 0:
			raise RuntimeError(f"Projection limit must be positive: {key}")
	return dict(limits)


#============================================
def _subject(message: str) -> str:
	"""Return one normalized commit subject."""
	lines = message.splitlines()
	subject = lines[0].strip() if lines else ""
	if not subject:
		subject = "Untitled commit"
	return subject


#============================================
def _repository_card(
	activity: daily_blog.schema.RepositoryActivity,
	commit_subject_chars: int,
) -> daily_blog.schema.RepositoryCard:
	"""Build one bounded activity card without dropping repository identity."""
	if len(activity.lifecycle_events) != 1:
		raise RuntimeError("Repository projection requires one creation lifecycle event.")
	creation = activity.lifecycle_events[0]
	remaining = commit_subject_chars
	shas = []
	subjects = []
	for commit in activity.commits:
		if remaining <= 0:
			break
		subject = _subject(commit.message)
		bounded = subject[:remaining]
		if not bounded:
			break
		shas.append(commit.sha)
		subjects.append(bounded)
		remaining -= len(bounded)
	card = daily_blog.schema.RepositoryCard(
		repository=activity.repository,
		repository_url=activity.repository_url,
		commit_count=len(activity.commits),
		commit_shas=tuple(shas),
		commit_subjects=tuple(subjects),
		created_at=creation.occurred_at,
		created_in_report_window=creation.occurred_in_report_window,
		is_fork=activity.is_fork,
		story_signals=(
			("new_source_repository",)
			if creation.occurred_in_report_window and not activity.is_fork
			else ()
		),
	)
	return card


#============================================
def _activity_order(activity: daily_blog.schema.RepositoryActivity) -> tuple[int, str]:
	"""Put newly created source repositories before routine active repositories."""
	creation = activity.lifecycle_events[0]
	new_source = creation.occurred_in_report_window and not activity.is_fork
	return (0 if new_source else 1, activity.repository.casefold())


#============================================
def _exact_slices(
	item: daily_blog.schema.EvidenceItem,
	excerpt_chars: int,
) -> list[daily_blog.schema.EvidenceExcerpt]:
	"""Split one source into fixed exact slices with explicit offsets and hashes."""
	excerpts = []
	for start in range(0, len(item.content), excerpt_chars):
		end = min(len(item.content), start + excerpt_chars)
		excerpts.append(daily_blog.schema.EvidenceExcerpt.create(item, start, end))
	return excerpts


#============================================
def _candidate_projection(
	packet: daily_blog.schema.EvidencePacket,
	limits: dict[str, int],
	cards: list[daily_blog.schema.RepositoryCard],
	excerpts: list[daily_blog.schema.EvidenceExcerpt],
) -> daily_blog.schema.EditorialProjection:
	"""Create one candidate immutable projection for an exact-size check."""
	projection = daily_blog.schema.EditorialProjection.create(
		packet.packet_id,
		packet.report_date,
		packet.timezone,
		limits,
		cards,
		excerpts,
	)
	return projection


#============================================
def _ranked_queues(
	packet: daily_blog.schema.EvidencePacket,
	excerpt_chars: int,
) -> dict[int, dict[str, collections.deque]]:
	"""Group source slices by authority and repository in stable packet order."""
	queues: dict[int, dict[str, collections.deque]] = {}
	for item in packet.items:
		rank_queues = queues.setdefault(item.authority_rank, {})
		repository_queue = rank_queues.setdefault(item.repository, collections.deque())
		repository_queue.extend(_exact_slices(item, excerpt_chars))
	return queues


#============================================
def _coverage_excerpts(
	queues: dict[int, dict[str, collections.deque]],
	repositories: list[str],
) -> list[daily_blog.schema.EvidenceExcerpt]:
	"""Reserve one highest-authority exact excerpt for every active repository."""
	coverage = []
	for repository in repositories:
		excerpt = None
		for rank in sorted(queues, reverse=True):
			queue = queues[rank].get(repository)
			if queue:
				excerpt = queue.popleft()
				break
		if excerpt is None:
			raise RuntimeError(
				f"Editorial projection lacks citable exact evidence for active repository: {repository}"
			)
		coverage.append(excerpt)
	return coverage


#============================================
def _excerpt_context_chars(excerpt: daily_blog.schema.EvidenceExcerpt) -> int:
	"""Return one excerpt's exact canonical JSON contribution."""
	contents = daily_blog.io_utils.canonical_json_bytes(excerpt.to_dict())
	return len(contents)


#============================================
def _try_select_excerpt(
	selected: list[daily_blog.schema.EvidenceExcerpt],
	excerpt: daily_blog.schema.EvidenceExcerpt,
	context_chars: int,
	context_limit: int,
) -> tuple[int, bool]:
	"""Add one excerpt when its exact incremental JSON contribution fits."""
	separator_chars = 1 if selected else 0
	candidate_chars = context_chars + separator_chars + _excerpt_context_chars(excerpt)
	if candidate_chars > context_limit:
		return context_chars, False
	selected.append(excerpt)
	return candidate_chars, True


#============================================
def _select_excerpts(
	packet: daily_blog.schema.EvidencePacket,
	limits: dict[str, int],
	cards: list[daily_blog.schema.RepositoryCard],
	base_context_chars: int,
) -> list[daily_blog.schema.EvidenceExcerpt]:
	"""Reserve active-repository coverage, then fill by authority round robin."""
	selected = []
	queues = _ranked_queues(packet, limits["excerpt_chars"])
	repositories = [card.repository for card in cards]
	context_chars = base_context_chars
	for excerpt in _coverage_excerpts(queues, repositories):
		context_chars, retained = _try_select_excerpt(
			selected,
			excerpt,
			context_chars,
			limits["context_chars"],
		)
		if not retained:
			raise RuntimeError(
				"Editorial projection budget cannot retain citable exact evidence for "
				+ "every active repository."
			)
	for item in packet.items:
		if item.repository not in repositories:
			repositories.append(item.repository)
	for rank in sorted(queues, reverse=True):
		rank_queues = queues[rank]
		while any(rank_queues.get(repository) for repository in repositories):
			for repository in repositories:
				queue = rank_queues.get(repository)
				if not queue:
					continue
				excerpt = queue.popleft()
				context_chars, _retained = _try_select_excerpt(
					selected,
					excerpt,
					context_chars,
					limits["context_chars"],
				)
	return selected


#============================================
def _validate_exact_slices(
	packet: daily_blog.schema.EvidencePacket,
	projection: daily_blog.schema.EditorialProjection,
) -> None:
	"""Prove every projection excerpt is an exact authoritative source slice."""
	items = {item.evidence_id: item for item in packet.items}
	for excerpt in projection.excerpts:
		item = items.get(excerpt.evidence_id)
		if item is None:
			raise RuntimeError("Editorial projection excerpt cites unknown evidence.")
		if excerpt.source_content_hash != item.content_hash:
			raise RuntimeError("Editorial projection source hash does not match evidence.")
		if excerpt.content != item.content[excerpt.start:excerpt.end]:
			raise RuntimeError("Editorial projection excerpt is not an exact source slice.")


#============================================
def build_projection(
	packet: daily_blog.schema.EvidencePacket,
	projection_limits: dict[str, int],
) -> daily_blog.schema.EditorialProjection:
	"""Build one bounded deterministic projection from complete authoritative evidence."""
	if not packet.complete:
		raise RuntimeError("Editorial projection requires a complete evidence packet.")
	limits = _validate_limits(projection_limits)
	activities = sorted(packet.activity, key=_activity_order)
	cards = [
		_repository_card(activity, limits["commit_subject_chars"])
		for activity in activities
	]
	base = _candidate_projection(packet, limits, cards, [])
	base_context = base.render_context()
	excerpts = _select_excerpts(packet, limits, cards, len(base_context))
	if not excerpts:
		raise RuntimeError("Editorial projection limit cannot retain any exact evidence excerpt.")
	projection = _candidate_projection(packet, limits, cards, excerpts)
	_validate_exact_slices(packet, projection)
	projection.render_context()
	return projection
