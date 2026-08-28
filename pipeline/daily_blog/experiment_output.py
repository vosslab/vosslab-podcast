"""Private transaction ownership for sealed prompt-experiment artifacts."""

# Standard Library
import dataclasses
import os
import pathlib
import uuid

# local repo modules
import daily_blog.private_artifacts


@dataclasses.dataclass(frozen=True)
class ExperimentOutputTransaction:
	"""Held private root and stage descriptors for one immutable experiment output."""

	root_path: pathlib.Path
	output_name: str
	stage_name: str
	root_fd: int
	stage_fd: int

	#============================================
	@property
	def output_path(self) -> pathlib.Path:
		"""Return the final display path without using it for mutation."""
		path = self.root_path / self.output_name
		return path


#============================================
def open_output_transaction(
	output_root: str,
	experiment_id: str,
) -> ExperimentOutputTransaction:
	"""Open a private root and exclusive hidden stage through retained descriptors.

	Args:
		output_root: Existing or creatable private root selected by configuration.
		experiment_id: Validated direct-child name for the immutable final artifact.

	Returns:
		Held descriptors for a fresh stage and its eventual output path.

	Raises:
		RuntimeError: The output root or existing target violates the private-artifact contract.
	"""
	raw_root = pathlib.Path(output_root)
	root = raw_root.resolve()
	root_fd = daily_blog.private_artifacts.open_physical_directory(
		str(root),
		create=True,
		intermediate_mode=0o755,
		leaf_mode=0o700,
	)
	stage_name = ""
	stage_fd = -1
	try:
		daily_blog.private_artifacts.require_directory(root_fd, 0o077)
		try:
			target_fd = daily_blog.private_artifacts.open_directory_at(root_fd, experiment_id)
		except FileNotFoundError:
			target_fd = None
		except (OSError, RuntimeError) as error:
			raise RuntimeError("Experiment output target already exists or is unsafe.") from error
		if target_fd is not None:
			os.close(target_fd)
			raise RuntimeError("Experiment output target already exists.")
		stage_name = f".{experiment_id}-{uuid.uuid4().hex}.stage"
		stage_fd = daily_blog.private_artifacts.create_private_stage_at(
			root_fd,
			stage_name,
			0o077,
		)
	except BaseException:
		if stage_fd >= 0:
			os.close(stage_fd)
		os.close(root_fd)
		raise
	transaction = ExperimentOutputTransaction(
		root,
		experiment_id,
		stage_name,
		root_fd,
		stage_fd,
	)
	return transaction
