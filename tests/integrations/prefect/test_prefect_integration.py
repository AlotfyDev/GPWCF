"""Real tests for Prefect Integration (Task 09).

Implementation task: 09_Prefect_Integration
Related diagrams:
  class: 03_Diagrams_Codes_Files/09_Prefect_Integration.dot
  sequence: B_Sequencial_Diagram_Code/07_Prefect_Integration_Sequence.puml
  association: C_Association_Diagram_Code/09_Prefect_Integration_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/06_Core_vs_Prefect_Integration_Boundary.dot

Tests cover:
  - Integration binding tests for Flow/Subflow/Task mapping
  - Identity correlation tests (domain vs native)
  - Result preservation tests through Prefect execution
  - Architecture test: Core does not import Prefect
"""

import pytest

from gpwcf.core.identities import (
    PipelineInvocationIdentity,
    StageIdentity,
    StageInvocationIdentity,
    StepIdentity,
    SPUIdentity,
)
from gpwcf.core.stage import StageResult
from gpwcf.core.step import StepExecutionResult
from gpwcf.core.step.results import Absent, OptionalResultContributions, Present

from gpwcf.integrations.prefect import (
    DomainNativeIdentityCorrelation,
    PrefectIntegrationPackage,
    PrefectNotAvailableError,
    PREFECT_AVAILABLE,
    SPUTaskBinding,
    StageFlowDeploymentBinding,
    StageResultPersistenceRetrieval,
    StepSubflowBinding,
    SupportingPatternTaskBinding,
    TypedResultPreservation,
    RunDeploymentAsSubflowProfile,
)

# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def package():
    return PrefectIntegrationPackage()


@pytest.fixture
def stage_identity():
    return StageIdentity("stage-1")


@pytest.fixture
def step_identity():
    return StepIdentity("step-1")


@pytest.fixture
def spu_identity():
    return SPUIdentity("spu-1")


@pytest.fixture
def stage_invocation_id():
    return StageInvocationIdentity("inv-1")


@pytest.fixture
def step_invocation_id():
    from gpwcf.core.identities import StepInvocationIdentity

    return StepInvocationIdentity("step-inv-1")


@pytest.fixture
def pipeline_invocation_id():
    return PipelineInvocationIdentity("pipe-1")


@pytest.fixture
def step_execution_result(step_identity, stage_identity, step_invocation_id):
    return StepExecutionResult(
        step_identity=step_identity,
        step_invocation_identity=step_invocation_id,
        owning_stage_identity=stage_identity,
        parent_stage_invocation_identity=StageInvocationIdentity("stage-inv-1"),
        pipeline_invocation_identity=None,
        processing_artifact=Present("step-artifact"),
        optional_result_contributions=OptionalResultContributions.all_absent(),
    )


@pytest.fixture
def stage_result(stage_identity, stage_invocation_id, pipeline_invocation_id):
    return StageResult(
        stage_identity=stage_identity,
        stage_invocation_identity=stage_invocation_id,
        owning_pipeline_invocation_identity=pipeline_invocation_id,
        parent_stage_invocation_identity=None,
        processing_artifact=Present("stage-artifact"),
        stage_outputs=Absent(),
        stage_flow_result=__import__(
            "gpwcf.core.stage.results", fromlist=["StageFlowResult"]
        ).StageFlowResult(),
        domain_outcome=Absent(),
    )


# --------------------------------------------------------------------------
# Package availability
# --------------------------------------------------------------------------


def test_prefect_availability_is_bool():
    """PREFECT_AVAILABLE is a boolean reflecting whether Prefect is installed."""
    assert isinstance(PREFECT_AVAILABLE, bool)


def test_package_prefect_available_matches(package):
    """PrefectIntegrationPackage.prefect_available matches module-level flag."""
    assert package.prefect_available is PREFECT_AVAILABLE


# --------------------------------------------------------------------------
# Identity correlation tests (domain vs native)
# --------------------------------------------------------------------------


def test_domain_native_identity_correlation_records_binding(package):
    """Domain identity value correlates to Prefect native identity value."""
    corr = DomainNativeIdentityCorrelation()
    corr.correlate("stage-1", "flow-run-123")
    assert corr.native_for_domain("stage-1") == "flow-run-123"
    assert corr.domain_for_native("flow-run-123") == "stage-1"


def test_domain_native_identity_correlation_rejects_empty_values(package):
    """Correlation rejects empty domain or native identity values."""
    corr = DomainNativeIdentityCorrelation()
    with pytest.raises(ValueError, match="non-empty string"):
        corr.correlate("", "native")
    with pytest.raises(ValueError, match="non-empty string"):
        corr.correlate("domain", "")


def test_domain_and_native_identities_are_distinct_namespaces(package):
    """Domain identities and Prefect operational identities are separate namespaces."""
    corr = DomainNativeIdentityCorrelation()
    corr.correlate("stage-1", "flow-run-123")
    # Looking up a native identity by a domain value string that happens to be a
    # native identity returns None (separate namespace).
    assert corr.domain_for_native("stage-1") is None
    assert corr.native_for_domain("flow-run-123") is None


def test_package_identity_correlation_property(package):
    """Package exposes an identity_correlation registry."""
    corr = package.identity_correlation
    assert isinstance(corr, DomainNativeIdentityCorrelation)


# --------------------------------------------------------------------------
# Stage Flow/Deployment Binding tests
# --------------------------------------------------------------------------


def test_stage_flow_deployment_binding(package, stage_identity):
    """Stage identity correlates to Prefect Deployment ID."""
    binding = StageFlowDeploymentBinding(package)
    dep_id = binding.bind_stage_to_deployment(stage_identity, "dep-456")
    assert dep_id == "dep-456"
    assert package.identity_correlation.native_for_domain("stage-1") == "dep-456"


def test_stage_flow_deployment_binding_rejects_wrong_types(package, stage_identity):
    """Binding rejects non-StageIdentity and empty deployment ID."""
    binding = StageFlowDeploymentBinding(package)
    with pytest.raises(TypeError, match="StageIdentity"):
        binding.bind_stage_to_deployment("not-a-stage-identity", "dep")
    with pytest.raises(ValueError, match="non-empty string"):
        binding.bind_stage_to_deployment(stage_identity, "")


def test_stage_flow_deployment_binding_requires_prefect(package):
    """Stage Flow/Deployment binding reports Prefect requirement."""
    binding = StageFlowDeploymentBinding(package)
    assert binding.requires_prefect() is PREFECT_AVAILABLE


# --------------------------------------------------------------------------
# run_deployment(as_subflow=True) Profile tests
# --------------------------------------------------------------------------


def test_run_deployment_as_subflow_profile_name():
    """Profile name is the accepted mechanism string."""
    profile = RunDeploymentAsSubflowProfile(PrefectIntegrationPackage())
    assert profile.profile_name() == "run_deployment(as_subflow=True)"


def test_run_deployment_as_subflow_profile_accepted():
    """run_deployment(as_subflow=True) is the accepted profile when Prefect available."""
    profile = RunDeploymentAsSubflowProfile(PrefectIntegrationPackage())
    assert profile.is_accepted_profile() is PREFECT_AVAILABLE


# --------------------------------------------------------------------------
# Step Subflow Binding tests
# --------------------------------------------------------------------------


def test_step_subflow_binding(package, step_identity):
    """Step identity correlates to Prefect Step Subflow ID."""
    binding = StepSubflowBinding(package)
    subflow_id = binding.bind_step_to_subflow(step_identity, "subflow-789")
    assert subflow_id == "subflow-789"
    assert package.identity_correlation.native_for_domain("step-1") == "subflow-789"


def test_step_subflow_binding_rejects_wrong_types(package, step_identity):
    """Binding rejects non-StepIdentity and empty subflow ID."""
    binding = StepSubflowBinding(package)
    with pytest.raises(TypeError, match="StepIdentity"):
        binding.bind_step_to_subflow("not-a-step-identity", "subflow")
    with pytest.raises(ValueError, match="non-empty string"):
        binding.bind_step_to_subflow(step_identity, "")


# --------------------------------------------------------------------------
# SPU Task Binding tests
# --------------------------------------------------------------------------


def test_spu_task_binding(package, spu_identity):
    """SPU identity correlates to Prefect Task Run ID."""
    binding = SPUTaskBinding(package)
    task_run_id = binding.bind_spu_to_task(spu_identity, "task-run-abc")
    assert task_run_id == "task-run-abc"
    assert package.identity_correlation.native_for_domain("spu-1") == "task-run-abc"


def test_spu_task_binding_rejects_wrong_types(package, spu_identity):
    """Binding rejects non-SPUIdentity and empty task run ID."""
    binding = SPUTaskBinding(package)
    with pytest.raises(TypeError, match="SPUIdentity"):
        binding.bind_spu_to_task("not-a-spu-identity", "task")
    with pytest.raises(ValueError, match="non-empty string"):
        binding.bind_spu_to_task(spu_identity, "")


# --------------------------------------------------------------------------
# Supporting Pattern Task Binding tests
# --------------------------------------------------------------------------


def test_supporting_pattern_task_binding(package):
    """Supporting pattern name correlates to Prefect Task Run ID."""
    binding = SupportingPatternTaskBinding(package)
    task_run_id = binding.bind_supporting_pattern_to_task("validator", "task-run-def")
    assert task_run_id == "task-run-def"


def test_supporting_pattern_task_binding_rejects_empty(package):
    """Binding rejects empty pattern name or task run ID."""
    binding = SupportingPatternTaskBinding(package)
    with pytest.raises(ValueError, match="non-empty string"):
        binding.bind_supporting_pattern_to_task("", "task")
    with pytest.raises(ValueError, match="non-empty string"):
        binding.bind_supporting_pattern_to_task("validator", "")


# --------------------------------------------------------------------------
# Typed Result Preservation tests
# --------------------------------------------------------------------------


def test_typed_result_preservation_returns_spu_result_unchanged(
    package, step_execution_result
):
    """SPUExecutionResult is returned unchanged — never replaced with Prefect State."""
    trp = TypedResultPreservation(package)
    preserved = trp.preserve_spu_execution_result(step_execution_result)
    assert preserved is step_execution_result


def test_typed_result_preservation_rejects_non_step_result(package):
    """Preservation rejects non-StepExecutionResult types."""
    trp = TypedResultPreservation(package)
    with pytest.raises(TypeError, match="StepExecutionResult"):
        trp.preserve_spu_execution_result("not-a-result")  # type: ignore[arg-type]


def test_prefect_state_is_not_domain_result(package):
    """Prefect State is operational evidence, not a domain result — always False."""
    trp = TypedResultPreservation(package)
    assert trp.is_prefect_state_domain_result() is False


# --------------------------------------------------------------------------
# Stage Result Persistence/Retrieval tests
# --------------------------------------------------------------------------


def test_stage_result_persistence_retrieval_round_trip(
    package, stage_identity, stage_result
):
    """StageResult is persisted via reference and retrievable (returns None when unqualified)."""
    srpr = StageResultPersistenceRetrieval(package)
    ref =     srpr.persist_stage_result(stage_identity, stage_result)
    assert ref.startswith("prefect-result-ref:")
    # PHASE-01/02: persistence implementation unqualified -> retrieve returns None
    retrieved = srpr.retrieve_stage_result(ref)
    assert retrieved is None


def test_stage_result_persistence_rejects_wrong_types(package, stage_identity, stage_result):
    """Persistence rejects non-StageIdentity and non-StageResult."""
    srpr = StageResultPersistenceRetrieval(package)
    with pytest.raises(TypeError, match="StageIdentity"):
        srpr.persist_stage_result("not-a-stage-identity", stage_result)
    with pytest.raises(TypeError, match="StageResult"):
        srpr.persist_stage_result(stage_identity, "not-a-result")  # type: ignore[arg-type]


def test_stage_result_retrieval_rejects_invalid_reference(package):
    """Retrieval rejects invalid result references."""
    srpr = StageResultPersistenceRetrieval(package)
    with pytest.raises(ValueError, match="valid prefect result reference"):
        srpr.retrieve_stage_result("invalid-reference")


# --------------------------------------------------------------------------
# Architecture boundary tests
# --------------------------------------------------------------------------


def test_core_modules_do_not_import_prefect():
    """Architecture: Core modules must not import Prefect (task 09 gate).

    Checks actual import statements, not docstring mentions of "Prefect".
    """
    import ast
    import inspect

    modules_to_check = [
        "gpwcf.core.identities",
        "gpwcf.core.step",
        "gpwcf.core.stage",
        "gpwcf.core.processing_units.spu",
        "gpwcf.core.supporting_patterns.error_handling",
        "gpwcf.core.supporting_patterns.validation",
        "gpwcf.core.supporting_patterns.observation",
        "gpwcf.core.coordination",
        "gpwcf.core.diagnostics",
    ]
    for mod_name in modules_to_check:
        mod = __import__(mod_name, fromlist=["x"])
        src = inspect.getsource(mod)
        tree = ast.parse(src)
        imports_prefect = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "prefect" or alias.name.startswith("prefect."):
                        imports_prefect = True
            elif isinstance(node, ast.ImportFrom):
                if node.module and (node.module == "prefect" or node.module.startswith("prefect.")):
                    imports_prefect = True
        assert not imports_prefect, f"{mod_name} imports Prefect"


def test_prefect_optional_import_does_not_break_core():
    """Core imports cleanly regardless of Prefect availability."""
    import gpwcf.core.identities
    import gpwcf.core.step
    import gpwcf.core.stage

    assert gpwcf.core.identities is not None
    assert gpwcf.core.step is not None
    assert gpwcf.core.stage is not None


def test_prefect_not_available_error_is_runtime_error():
    """PrefectNotAvailableError is a RuntimeError subclass."""
    assert issubclass(PrefectNotAvailableError, RuntimeError)
    err = PrefectNotAvailableError("prefect not installed")
    assert str(err) == "prefect not installed"


def test_package_registers_and_retrieves_bindings(package):
    """Package registers and retrieves integration bindings by name."""
    package.register_binding("stage-binding", StageFlowDeploymentBinding(package))
    package.register_binding("step-binding", StepSubflowBinding(package))
    assert "stage-binding" in package.bindings
    assert "step-binding" in package.bindings
    assert isinstance(package.binding("stage-binding"), StageFlowDeploymentBinding)
    assert isinstance(package.binding("step-binding"), StepSubflowBinding)


def test_package_binding_rejects_unknown(package):
    """Retrieving an unknown binding raises KeyError."""
    with pytest.raises(KeyError, match="No integration binding registered"):
        package.binding("nonexistent")
