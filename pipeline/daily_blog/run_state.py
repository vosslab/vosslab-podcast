"""Persistent run records and inspectable per-phase artifacts."""

# Standard Library
import os

# local repo modules
import daily_blog.schema
import daily_blog.io_utils


class RunStore:
	"""Own one run's mutable record until it reaches a terminal immutable state."""

	#============================================
	def __init__(self, output_root: str, owner: str, report_date: str, run_id: str) -> None:
		"""Create the unique run-state directory."""
		self.run_dir = os.path.join(
			os.path.abspath(output_root),
			owner,
			"daily_blog_runs",
			report_date,
			run_id,
		)
		if os.path.exists(self.run_dir):
			raise RuntimeError(f"Immutable run-state directory already exists: {self.run_dir}")
		os.makedirs(self.run_dir)
		self.record_path = os.path.join(self.run_dir, "run_state.json")

	#============================================
	def save(self, record: daily_blog.schema.RunRecord) -> None:
		"""Atomically persist the authoritative typed run record."""
		daily_blog.io_utils.atomic_write_json(self.record_path, record.to_dict())

	#============================================
	def write_artifact(self, name: str, value: object) -> str:
		"""Write one stable inspectable JSON artifact inside this run."""
		if os.path.basename(name) != name or not name.endswith(".json"):
			raise RuntimeError("Run artifacts must use one direct JSON filename.")
		path = os.path.join(self.run_dir, name)
		daily_blog.io_utils.atomic_write_json(path, value)
		return path
