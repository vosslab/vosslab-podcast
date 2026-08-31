"""Deterministic bounded editorial projections over authoritative evidence packets."""

# Standard Library
import collections

# local repo modules
import daily_blog.schema
import daily_blog.io_utils


PROJECTION_POLICY_VERSION = "story-first-lifecycle-authority-round-robin-adaptive-v4"
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
	return _ranked_item_queues(packet.items, excerpt_chars)


#============================================
def _ranked_item_queues(
	items: tuple[daily_blog.schema.EvidenceItem, ...],
	excerpt_chars: int,
) -> dict[int, dict[str, collections.deque]]:
	"""Group an already-canonical evidence sequence into exact-slice queues."""
	queues: dict[int, dict[str, collections.deque]] = {}
	for item in items:
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
def _select_excerpts_from_items(
	items: tuple[daily_blog.schema.EvidenceItem, ...],
	limits: dict[str, int],
	cards: list[daily_blog.schema.RepositoryCard],
	base_context_chars: int,
	context_chars: int,
) -> list[daily_blog.schema.EvidenceExcerpt]:
	"""Select exact excerpts for an aggregate context under its complete frame cap."""
	selected = []
	queues = _ranked_item_queues(items, limits["excerpt_chars"])
	repositories = [card.repository for card in cards]
	used_chars = base_context_chars
	for excerpt in _coverage_excerpts(queues, repositories):
		used_chars, retained = _try_select_excerpt(
			selected,
			excerpt,
			used_chars,
			context_chars,
		)
		if not retained:
			raise RuntimeError(
				"Bounded evidence context cap cannot retain citable exact evidence for "
				+ "every survivor repository."
			)
	for item in items:
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
				used_chars, _retained = _try_select_excerpt(
					selected,
					excerpt,
					used_chars,
					context_chars,
				)
	return selected


#============================================
def _coverage_fits_context(
	items: tuple[daily_blog.schema.EvidenceItem, ...],
	limits: dict[str, int],
	cards: list[daily_blog.schema.RepositoryCard],
	base_context_chars: int,
	context_chars: int,
) -> bool:
	"""Return whether one exact slice per survivor fits this complete frame."""
	coverage_items: dict[int, dict[str, daily_blog.schema.EvidenceItem]] = {}
	for item in items:
		by_repository = coverage_items.setdefault(item.authority_rank, {})
		if item.repository not in by_repository:
			by_repository[item.repository] = item
	selected = []
	used_chars = base_context_chars
	for repository in [card.repository for card in cards]:
		item = None
		for rank in sorted(coverage_items, reverse=True):
			item = coverage_items[rank].get(repository)
			if item is not None:
				break
		if item is None:
			raise RuntimeError(
				f"Bounded evidence context lacks exact evidence for survivor: {repository}"
			)
		end = min(len(item.content), limits["excerpt_chars"])
		excerpt = daily_blog.schema.EvidenceExcerpt.create(item, 0, end)
		used_chars, retained = _try_select_excerpt(
			selected, excerpt, used_chars, context_chars,
		)
		if not retained:
			return False
	return True


#============================================
def _bounded_context_base_chars(
	report_date: str,
	timezone_name: str,
	context_chars: int,
	effective_excerpt_chars: int,
	limits: dict[str, int],
	packet_ids: list[str],
	model_packet_ids: list[str],
	cards: list[daily_blog.schema.RepositoryCard],
) -> int:
	"""Return the exact empty-frame contribution for one candidate slice cap."""
	base = daily_blog.schema.BoundedEvidenceContext.create(
		report_date, timezone_name, context_chars, effective_excerpt_chars, limits, packet_ids,
		model_packet_ids, cards, [],
	)
	base_text = base.render_context(context_chars)
	return len(base_text)


#============================================
def _adaptive_context_excerpt_chars(
	items: tuple[daily_blog.schema.EvidenceItem, ...],
	limits: dict[str, int],
	cards: list[daily_blog.schema.RepositoryCard],
	report_date: str,
	timezone_name: str,
	context_chars: int,
	packet_ids: list[str],
	model_packet_ids: list[str],
) -> int:
	"""Choose the largest common exact slice cap that preserves all survivors."""
	configured_cap = limits["excerpt_chars"]

	def coverage_fits(excerpt_chars: int) -> bool:
		candidate_limits = {**limits, "excerpt_chars": excerpt_chars}
		base_chars = _bounded_context_base_chars(
			report_date, timezone_name, context_chars, excerpt_chars, limits,
			packet_ids, model_packet_ids, cards,
		)
		return _coverage_fits_context(
			items, candidate_limits, cards, base_chars, context_chars,
		)

	if not coverage_fits(1):
		raise RuntimeError(
			"Bounded evidence context cap cannot retain citable exact evidence for "
			+ "every survivor repository."
		)
	if coverage_fits(configured_cap):
		return configured_cap
	low = 1
	high = configured_cap
	while low < high:
		middle = (low + high + 1) // 2
		if coverage_fits(middle):
			low = middle
		else:
			high = middle - 1
	return low


#============================================
def _bounded_context_base_frame(
	context: daily_blog.schema.BoundedEvidenceContext,
) -> str:
	"""Render the empty-excerpt frame used by deterministic aggregate selection."""
	base = daily_blog.schema.BoundedEvidenceContext.create(
		context.report_date,
		context.timezone,
		context.context_chars,
		context.effective_excerpt_chars,
		dict(context.projection_limits),
		list(context.packet_ids),
		list(context.model_packet_ids),
		list(context.repositories),
		[],
	)
	return base.render_context(context.context_chars)


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
def validate_bounded_evidence_context(
	packets: tuple[daily_blog.schema.EvidencePacket, ...],
	context: daily_blog.schema.BoundedEvidenceContext,
) -> None:
	"""Prove an aggregate context has complete survivor provenance and exact slices."""
	if type(context) is not daily_blog.schema.BoundedEvidenceContext:
		raise RuntimeError("Bounded evidence validation requires BoundedEvidenceContext.")
	if not packets:
		raise RuntimeError("Bounded evidence validation requires survivor packets.")
	ordered = tuple(sorted(packets, key=lambda packet: packet.packet_id))
	if any(type(packet) is not daily_blog.schema.EvidencePacket for packet in ordered):
		raise RuntimeError("Bounded evidence validation requires EvidencePacket values.")
	if any(not packet.complete for packet in ordered):
		raise RuntimeError("Bounded evidence context requires complete survivor packets.")
	if len({packet.packet_id for packet in ordered}) != len(ordered):
		raise RuntimeError("Bounded evidence context has duplicate survivor packets.")
	if len({packet.report_date for packet in ordered}) != 1:
		raise RuntimeError("Bounded evidence survivor packets disagree on report date.")
	if len({packet.timezone for packet in ordered}) != 1:
		raise RuntimeError("Bounded evidence survivor packets disagree on timezone.")
	packet_ids = tuple(packet.packet_id for packet in ordered)
	model_packet_ids = tuple(sorted(
		daily_blog.schema.model_cache_packet_identity(packet) for packet in ordered
	))
	if context.packet_ids != packet_ids:
		raise RuntimeError("Bounded evidence context packet provenance does not match survivors.")
	if context.model_packet_ids != model_packet_ids:
		raise RuntimeError("Bounded evidence model identities do not match survivors.")
	if context.report_date != ordered[0].report_date or context.timezone != ordered[0].timezone:
		raise RuntimeError("Bounded evidence context report identity does not match survivors.")
	if context.context_chars <= 0:
		raise RuntimeError("Bounded evidence context cap is invalid.")
	if (
		type(context.effective_excerpt_chars) is not int
		or not 0 < context.effective_excerpt_chars <= context.projection_limits["excerpt_chars"]
	):
		raise RuntimeError("Bounded evidence context effective excerpt cap is invalid.")
	items = {item.evidence_id: item for packet in ordered for item in packet.items}
	for excerpt in context.excerpts:
		item = items.get(excerpt.evidence_id)
		if item is None:
			raise RuntimeError("Bounded evidence context cites unknown survivor evidence.")
		if (
			excerpt.repository != item.repository
			or excerpt.kind != item.kind
			or excerpt.authority_level != item.authority_level
			or excerpt.authority_rank != item.authority_rank
			or excerpt.commit != item.commit
			or excerpt.path != item.path
			or excerpt.source_content_hash != item.content_hash
			or excerpt.start < 0
			or excerpt.end <= excerpt.start
			or excerpt.end > len(item.content)
			or excerpt.content != item.content[excerpt.start:excerpt.end]
			or excerpt.content_hash != daily_blog.io_utils.sha256_text(
				item.content[excerpt.start:excerpt.end]
			)
	):
			raise RuntimeError("Bounded evidence context excerpt is not an exact source slice.")
	activity_values = tuple(activity for packet in ordered for activity in packet.activity)
	activities = {activity.repository: activity for activity in activity_values}
	if len(activities) != len(activity_values):
		raise RuntimeError("Bounded evidence context survivor activities overlap repositories.")
	if tuple(card.repository for card in context.repositories) != tuple(sorted(
		activities,
		key=lambda repository: _activity_order(activities[repository]),
		)):
		raise RuntimeError("Bounded evidence context repository cards are not canonical.")
	for card in context.repositories:
		expected_card = _repository_card(
			activities[card.repository],
			context.projection_limits["commit_subject_chars"],
		)
		if card != expected_card:
			raise RuntimeError("Bounded evidence context card does not match survivor activity.")
	configured_limits = dict(context.projection_limits)
	expected_excerpt_chars = _adaptive_context_excerpt_chars(
		tuple(item for packet in ordered for item in packet.items), configured_limits,
		list(context.repositories), context.report_date, context.timezone,
		context.context_chars, list(context.packet_ids), list(context.model_packet_ids),
	)
	if context.effective_excerpt_chars != expected_excerpt_chars:
		raise RuntimeError("Bounded evidence context effective excerpt cap is not maximal.")
	selection_limits = {**configured_limits, "excerpt_chars": context.effective_excerpt_chars}
	if tuple(excerpt.excerpt_id for excerpt in context.excerpts) != tuple(
		excerpt.excerpt_id for excerpt in _select_excerpts_from_items(
			tuple(item for packet in ordered for item in packet.items),
			selection_limits,
			list(context.repositories),
			len(_bounded_context_base_frame(context)),
			context.context_chars,
		)
		):
		raise RuntimeError("Bounded evidence context exact excerpts are not canonical.")


#============================================
def minimum_evidence_context(
	packets: tuple[daily_blog.schema.EvidencePacket, ...],
	full: daily_blog.schema.BoundedEvidenceContext,
) -> daily_blog.schema.BoundedEvidenceContext:
	"""Derive the exact smallest one-excerpt-per-survivor evidence frame."""
	if type(full) is not daily_blog.schema.BoundedEvidenceContext:
		raise RuntimeError("Minimum evidence context requires a bounded evidence frame.")
	items = {item.evidence_id: item for packet in packets for item in packet.items}
	first_by_repository: dict[str, daily_blog.schema.EvidenceExcerpt] = {}
	for excerpt in full.excerpts:
		first_by_repository.setdefault(excerpt.repository, excerpt)
	try:
		coverage = [
			daily_blog.schema.EvidenceExcerpt.create(
				items[first_by_repository[card.repository].evidence_id], 0, 1,
			)
			for card in full.repositories
		]
	except (KeyError, ValueError) as error:
		raise RuntimeError(
			"Minimum evidence context cannot preserve citable evidence for every survivor."
		) from error
	cap = 1
	while True:
		context = daily_blog.schema.BoundedEvidenceContext.create(
			full.report_date, full.timezone, cap, 1,
			full.projection_limits.to_dict(), list(full.packet_ids), list(full.model_packet_ids),
			list(full.repositories), coverage,
		)
		model_value = context.model_content_dict()
		model_value["model_context_id"] = context.model_context_id
		next_cap = len(daily_blog.io_utils.canonical_json_bytes(model_value))
		if next_cap == cap:
			validate_bounded_evidence_context(packets, context)
			context.render_context(cap)
			return context
		cap = next_cap


#============================================
def build_bounded_evidence_context(
	packets: tuple[daily_blog.schema.EvidencePacket, ...],
	projection_limits: dict[str, int],
	context_chars: int,
) -> daily_blog.schema.BoundedEvidenceContext:
	"""Build one deterministic survivor-only prompt context under an existing cap.

	``context_chars`` is owned by the caller's existing prompt budget.  Selection
	drops only whole exact excerpts; it never slices a serialized frame.
	"""
	if type(context_chars) is not int or context_chars <= 0:
		raise RuntimeError("Bounded evidence context cap must be a positive integer.")
	if not packets:
		raise RuntimeError("Bounded evidence context requires survivor packets.")
	if any(type(packet) is not daily_blog.schema.EvidencePacket for packet in packets):
		raise RuntimeError("Bounded evidence context requires EvidencePacket values.")
	ordered = tuple(sorted(packets, key=lambda packet: packet.packet_id))
	if any(not packet.complete for packet in ordered):
		raise RuntimeError("Bounded evidence context requires complete survivor packets.")
	if len({packet.packet_id for packet in ordered}) != len(ordered):
		raise RuntimeError("Bounded evidence context has duplicate survivor packets.")
	if len({packet.report_date for packet in ordered}) != 1:
		raise RuntimeError("Bounded evidence survivor packets disagree on report date.")
	if len({packet.timezone for packet in ordered}) != 1:
		raise RuntimeError("Bounded evidence survivor packets disagree on timezone.")
	limits = _validate_limits(projection_limits)
	activities = sorted(
		(activity for packet in ordered for activity in packet.activity),
		key=_activity_order,
	)
	if len({activity.repository for activity in activities}) != len(activities):
		raise RuntimeError("Bounded evidence survivor packets overlap repositories.")
	cards = [_repository_card(activity, limits["commit_subject_chars"]) for activity in activities]
	items = tuple(item for packet in ordered for item in packet.items)
	if {card.repository for card in cards} != {item.repository for item in items}:
		raise RuntimeError(
			"Bounded evidence survivor activity and citable repository coverage disagree."
		)
	packet_ids = [packet.packet_id for packet in ordered]
	model_packet_ids = sorted(
		daily_blog.schema.model_cache_packet_identity(packet) for packet in ordered
	)
	effective_excerpt_chars = _adaptive_context_excerpt_chars(
		items, limits, cards, ordered[0].report_date, ordered[0].timezone,
		context_chars, packet_ids, model_packet_ids,
	)
	selection_limits = {**limits, "excerpt_chars": effective_excerpt_chars}
	base_context_chars = _bounded_context_base_chars(
		ordered[0].report_date, ordered[0].timezone, context_chars, effective_excerpt_chars, limits,
		packet_ids, model_packet_ids, cards,
	)
	excerpts = _select_excerpts_from_items(
		items,
		selection_limits,
		cards,
		base_context_chars,
		context_chars,
	)
	if not excerpts:
		raise RuntimeError("Bounded evidence context cannot retain an exact evidence excerpt.")
	context = daily_blog.schema.BoundedEvidenceContext.create(
		ordered[0].report_date,
		ordered[0].timezone,
		context_chars,
		effective_excerpt_chars,
		limits,
		packet_ids,
		model_packet_ids,
		cards,
		excerpts,
	)
	validate_bounded_evidence_context(ordered, context)
	context.render_context(context_chars)
	return context


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
