"""Durable anti-forgery coverage for recovery fault provenance."""

# PIP3 modules
import pytest

# local repo modules
import daily_blog.recovery


#============================================
def test_pipeline_fault_rejects_a_category_that_contradicts_its_observations() -> None:
	"""A public fault cannot serialize a diagnosis contrary to its route facts."""
	observation = daily_blog.recovery.GenerationObservation(
		"stage6", 0, 0, (), daily_blog.recovery.TerminalFaultCategory.CONFIGURATION,
	)
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError):
		daily_blog.recovery.PipelineFault(
			daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE, 0, "", "", (observation,),
		)
