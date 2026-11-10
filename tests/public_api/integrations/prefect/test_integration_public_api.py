"""Integration Public API conformance tests (Task 10.D).

Verifies:
  - Integration Public API exposes the curated symbol set
  - Integration Public API complements Core Public API (disjoint symbol sets)
  - PREFECT_AVAILABLE reflects actual Prefect availability
"""

import ast
import inspect

import pytest

from gpwcf.public_api.integrations import prefect as prefect_mod

# --------------------------------------------------------------------------
# Expected Integration Public API symbol set
# --------------------------------------------------------------------------

INTEGRATION_PUBLIC_SYMBOLS = {
    "PREFECT_AVAILABLE",
    "PrefectNotAvailableError",
    "PrefectIntegrationPackage",
    "StageFlowDeploymentBinding",
    "StepSubflowBinding",
    "SPUTaskBinding",
    "SupportingPatternTaskBinding",
    "DomainNativeIdentityCorrelation",
    "TypedResultPreservation",
    "StageResultPersistenceRetrieval",
    "RunDeploymentAsSubflowProfile",
}


def test_integration_public_api_symbols_match_curated_set():
    """The Integration Public API exposes exactly the curated symbol set."""
    public = {name for name in vars(prefect_mod) if not name.startswith("_")}
    assert public == INTEGRATION_PUBLIC_SYMBOLS, (
        f"Symbol mismatch:\n  missing: {INTEGRATION_PUBLIC_SYMBOLS - public}\n  extra:   {public - INTEGRATION_PUBLIC_SYMBOLS}"
    )


def test_integration_public_api_complements_core_api():
    """Integration Public API symbols do not overlap Core Public API symbols."""
    from gpwcf.public_api import core as core_mod

    core_public = {name for name in vars(core_mod) if not name.startswith("_")}
    integration_public = {name for name in vars(prefect_mod) if not name.startswith("_")}
    overlap = core_public & integration_public
    assert not overlap, f"Core and Integration Public APIs share symbols: {overlap}"


def test_prefect_availability_is_bool():
    """PREFECT_AVAILABLE is a boolean reflecting whether Prefect is installed."""
    assert isinstance(prefect_mod.PREFECT_AVAILABLE, bool)


def test_prefect_not_available_error_is_runtime_error():
    """PrefectNotAvailableError is a RuntimeError subclass."""
    assert issubclass(prefect_mod.PrefectNotAvailableError, RuntimeError)
    err = prefect_mod.PrefectNotAvailableError("prefect not installed")
    assert str(err) == "prefect not installed"


def test_prefect_integration_package_instantiable():
    """PrefectIntegrationPackage can be instantiated without Prefect."""
    pkg = prefect_mod.PrefectIntegrationPackage()
    assert pkg.prefect_available is prefect_mod.PREFECT_AVAILABLE


def test_domain_native_identity_correlation():
    """Domain/Native identity correlation records and resolves mappings."""
    corr = prefect_mod.DomainNativeIdentityCorrelation()
    corr.correlate("stage-1", "flow-run-123")
    assert corr.native_for_domain("stage-1") == "flow-run-123"
    assert corr.domain_for_native("flow-run-123") == "stage-1"


def test_typed_result_preservation_is_prefect_state_free():
    """TypedResultPreservation.is_prefect_state_domain_result() is always False."""
    trp = prefect_mod.TypedResultPreservation(prefect_mod.PrefectIntegrationPackage())
    assert trp.is_prefect_state_domain_result() is False


def test_run_deployment_as_subflow_profile():
    """RunDeploymentAsSubflowProfile has the accepted profile name."""
    profile = prefect_mod.RunDeploymentAsSubflowProfile(prefect_mod.PrefectIntegrationPackage())
    assert profile.profile_name() == "run_deployment(as_subflow=True)"
