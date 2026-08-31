"""Semantic evidence projection used by editorial model-result caches."""


#============================================
def semantic_value(value: object) -> object:
	"""Remove collection-location observations from nested model inputs."""
	if type(value) is dict:
		return {
			key: semantic_value(item)
			for key, item in value.items()
			if key not in {"cache_path", "refresh_error", "refresh_result", "refreshed_at"}
		}
	if type(value) is list:
		return [semantic_value(item) for item in value]
	return value


#============================================
def packet_content(packet: object) -> dict[str, object]:
	"""Return prompt-relevant packet facts without mutable mirror inventory.

	The caller validates the concrete packet type. Keeping this projection in a
	separate contract owner prevents the durable evidence schema from growing a
	second serialization responsibility.
	"""
	return {
		"schema_version": packet.schema_version,
		"report_date": packet.report_date,
		"timezone": packet.timezone,
		"complete": packet.complete,
		"collection_limits": packet.collection_limits.to_dict(),
		"activity": [
			{
				"repository": activity.repository,
				"repository_url": activity.repository_url,
				"commits": [commit.to_dict() for commit in activity.commits],
				"revision_ranges": [item.to_dict() for item in activity.revision_ranges],
				"snapshot_commits": list(activity.snapshot_commits),
				"is_fork": activity.is_fork,
				"lifecycle_events": [item.to_dict() for item in activity.lifecycle_events],
			}
			for activity in packet.activity
		],
		"items": [item.to_dict() for item in packet.items],
	}
