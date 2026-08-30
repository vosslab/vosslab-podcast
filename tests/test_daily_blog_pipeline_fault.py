"""Focused public-boundary tests for terminal daily-blog pipeline faults."""

# standard library
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.recovery


class _ArtifactNameEqualitySpoof:
	"""Mimic the fixed logical name without actually being a string."""

	#============================================
	def __eq__(self, other: object) -> bool:
		return other == "recovery_fault.json"


class _FalsyIdentitySpoof:
	"""Mimic an omitted artifact field while retaining arbitrary public state."""

	#============================================
	def __bool__(self) -> bool:
		return False


#============================================
def _fault() -> daily_blog.recovery.PipelineFault:
	"""Return one exact typed fault with bounded route facts."""
	observation = daily_blog.recovery.GenerationObservation(
		"stage6", 1, 0, (), daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE,
	)
	return daily_blog.recovery.PipelineFault(
		daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE, 1, "", "", (observation,),
	)


#============================================
def test_pipeline_fault_error_exposes_only_safe_bounded_public_fields() -> None:
	"""Public command handling receives the typed category and logical digest identity."""
	error = daily_blog.recovery.PipelineFaultError(_fault(), "a" * 64)
	assert (error.category, error.digest_sha256, error.artifact_name) == (
		daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE,
		"a" * 64,
		"recovery_fault.json",
	)
	assert str(error) == "Daily blog pipeline fault."


#============================================
@pytest.mark.parametrize(("fault", "digest_sha256", "artifact_name"), [
	(None, "a" * 64, "recovery_fault.json"),
	(_fault(), "not-a-digest", "recovery_fault.json"),
])
def test_pipeline_fault_error_rejects_unbounded_boundary_values(
	fault: object, digest_sha256: str, artifact_name: str,
) -> None:
	"""Only a typed fault, digest identity, and logical artifact name cross the boundary."""
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError):
		daily_blog.recovery.PipelineFaultError(fault, digest_sha256, artifact_name)  # type: ignore[arg-type]


#============================================
def test_pipeline_fault_error_rejects_a_path_derived_artifact_name(
	tmp_path: pathlib.Path,
) -> None:
	"""Only the fixed logical filename may cross the public boundary."""
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError):
		daily_blog.recovery.PipelineFaultError(
			_fault(), "a" * 64, str(tmp_path / "recovery_fault.json"),
		)


#============================================
def test_pipeline_fault_error_rejects_an_equality_spoofed_artifact_name() -> None:
	"""The public logical name remains an exact fixed string, never an arbitrary object."""
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError):
		daily_blog.recovery.PipelineFaultError(_fault(), "a" * 64, _ArtifactNameEqualitySpoof())  # type: ignore[arg-type]


#============================================
@pytest.mark.parametrize(("artifact_id", "artifact_type"), [
	(_FalsyIdentitySpoof(), ""),
	("", _FalsyIdentitySpoof()),
	(_FalsyIdentitySpoof(), _FalsyIdentitySpoof()),
])
def test_pipeline_fault_rejects_falsy_non_string_retained_identity_before_public_error(

	artifact_id: object, artifact_type: object,
) -> None:
	"""A terminal fault cannot retain a spoof object that a public error would expose."""
	observation = daily_blog.recovery.GenerationObservation(
		"stage6", 1, 0, (), daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE,
	)
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError):
		daily_blog.recovery.PipelineFault(
			daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE,
			1,
			artifact_id,  # type: ignore[arg-type]
			artifact_type,  # type: ignore[arg-type]
			(observation,),
		)
