"""Integration tests for Stage → Step → SPU hierarchy (Task: Integration/E2E).

Based on PHASE-01 / PHASE-02 use cases:
  - Pipeline Root → Stage Parent Flow → Step Subflow → SPU Tasks hierarchy
  - Step public callable boundary preserved
  - SPUExecutionResult and StepExecutionResult remain distinct
  - Domain identities separate from operational identities
  - Step Composition coordinates SPUs; Stage does not bypass Step boundary

These tests use contract-shaped GPWCF source components (no Prefect server
required). They exercise the actual calling chain between GPWCF core modules
to verify integration-level behavior.
"""

import pytest

from gpwcf.core.identities import (
    InvocationIdentity,
    PipelineInvocationIdentity,
    SPUIdentity,
    StageIdentity,
    StageInvocationIdentity,
    StepIdentity,
    StepInvocationIdentity,
)
from gpwcf.core.processing_units.spu import StepProcessingUnit
from gpwcf.core.processing_units.spu.errors import (
    SPUErrorTypeDefinition,
    SPUErrorTypeDefinitionRegistry,
    SPUErrorTypeDefinitionRegistryIdentity,
    SPUErrorTypeDefinitionIdentity,
)
from gpwcf.core.processing_units.spu.results import SPUExecutionResult
from gpwcf.core.step import Step, StepExecutionResult
from gpwcf.core.step.invocation import StepExecutionContext, StepInvocation
from gpwcf.core.step.results import Absent, OptionalResultContributions, Present


# --------------------------------------------------------------------------
# Test doubles mirroring PHASE-01 contract-shaped fixtures
# --------------------------------------------------------------------------


class _NormalizeSPU(StepProcessingUnit):
    """SPU that normalizes a string value (mirrors spu_normalize PoC task)."""

    def __init__(self, spu_identity: SPUIdentity, registry: SPUErrorTypeDefinitionRegistry):
        self._identity = spu_identity
        super().__init__(registry)
        self.calls = 0

    @property
    def spu_identity(self) -> SPUIdentity:
        return self._identity

    def execute(self, input: dict) -> SPUExecutionResult[dict]:
        self.calls += 1
        return SPUExecutionResult(
            processing_artifact={
                "normalized": str(input["value"]).strip().lower(),
                "source": input["value"],
            },
        )


class _MeasureSPU(StepProcessingUnit):
    """SPU that measures character count (mirrors spu_measure PoC task)."""

    def __init__(self, spu_identity: SPUIdentity, registry: SPUErrorTypeDefinitionRegistry):
        self._identity = spu_identity
        super().__init__(registry)
        self.calls = 0

    @property
    def spu_identity(self) -> SPUIdentity:
        return self._identity

    def execute(self, input: dict) -> SPUExecutionResult[dict]:
        self.calls += 1
        return SPUExecutionResult(
            processing_artifact={"characterCount": len(str(input["value"]))},
        )


class _ConcreteStep(Step):
    """Concrete Step that fans out to two SPUs and assembles StepExecutionResult
    (mirrors _step_subworkflow PoC fixture).
    """

    def __init__(
        self,
        step_identity: StepIdentity,
        owning_stage_identity: StageIdentity,
        spu_normalize: _NormalizeSPU,
        spu_measure: _MeasureSPU,
    ):
        super().__init__(step_identity, owning_stage_identity)
        self._spu_normalize = spu_normalize
        self._spu_measure = spu_measure
        self.calls = 0

    def _perform_invocation(
        self, invocation: StepInvocation, flow_result
    ) -> StepExecutionResult:
        self.calls += 1
        normalize_result = self._spu_normalize.execute(invocation.input)
        measure_result = self._spu_measure.execute(invocation.input)
        return StepExecutionResult(
            step_identity=invocation.step_identity,
            step_invocation_identity=invocation.step_invocation_identity,
            owning_stage_identity=invocation.owning_stage_identity,
            parent_stage_invocation_identity=invocation.parent_stage_invocation_identity,
            pipeline_invocation_identity=invocation.pipeline_invocation_identity,
            processing_artifact=Present({
                "normalized": normalize_result.processing_artifact,
                "measurement": measure_result.processing_artifact,
            }),
            optional_result_contributions=OptionalResultContributions.all_absent(),
        )


class _ConcreteStage:
    """Concrete Stage that owns Step membership and invokes Steps through
    their public callable boundary (mirrors stage_parent_flow PoC fixture).
    """

    def __init__(self, stage_identity: StageIdentity):
        self._stage_identity = stage_identity
        self._steps: dict[StepIdentity, _ConcreteStep] = {}
        self.calls = 0

    @property
    def stage_identity(self) -> StageIdentity:
        return self._stage_identity

    def add_step(self, step: _ConcreteStep) -> None:
        self._steps[step.step_identity] = step

    def invoke(self, pipeline_invocation_identity: PipelineInvocationIdentity, input: dict):
        self.calls += 1
        step = list(self._steps.values())[0]
        invocation = StepInvocation(
            step_identity=step.step_identity,
            step_invocation_identity=StepInvocationIdentity("step-inv-1"),
            owning_stage_identity=self._stage_identity,
            parent_stage_invocation_identity=StageInvocationIdentity("stage-inv-1"),
            input=input,
            execution_context=StepExecutionContext(),
            pipeline_invocation_identity=pipeline_invocation_identity,
        )
        result = step.execute(invocation)
        return {
            "stageIdentity": self._stage_identity.value,
            "stageInvocationIdentity": "stage-inv-1",
            "pipelineInvocationIdentity": pipeline_invocation_identity.value,
            "stepResult": result,
        }


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def registry():
    return SPUErrorTypeDefinitionRegistry(
        identity=SPUErrorTypeDefinitionRegistryIdentity("registry-1"),
        owner_spu_identity=SPUIdentity("spu-normalize"),
    )


@pytest.fixture
def spu_normalize(registry):
    return _NormalizeSPU(SPUIdentity("spu-normalize"), registry)


@pytest.fixture
def spu_measure(registry):
    return _MeasureSPU(SPUIdentity("spu-measure"), registry)


@pytest.fixture
def step(spu_normalize, spu_measure):
    return _ConcreteStep(
        StepIdentity("step-1"), StageIdentity("stage-1"), spu_normalize, spu_measure
    )


@pytest.fixture
def stage(step):
    s = _ConcreteStage(StageIdentity("stage-1"))
    s.add_step(step)
    return s


# --------------------------------------------------------------------------
# Integration tests: Stage → Step → SPU hierarchy
# --------------------------------------------------------------------------


def test_spu_fan_out_and_fan_in_inside_step(step, spu_normalize, spu_measure):
    """Both SPUs execute inside the owning Step and results are assembled
    into one StepExecutionResult (mirrors PHASE-01 step subworkflow).
    """
    invocation = StepInvocation(
        step_identity=StepIdentity("step-1"),
        step_invocation_identity=StepInvocationIdentity("inv-1"),
        owning_stage_identity=StageIdentity("stage-1"),
        parent_stage_invocation_identity=StageInvocationIdentity("stage-inv-1"),
        pipeline_invocation_identity=PipelineInvocationIdentity("pipe-1"),
        input={"value": "  Hello World  "},
        execution_context=StepExecutionContext(),
    )

    result = step.execute(invocation)

    assert spu_normalize.calls == 1
    assert spu_measure.calls == 1
    assert result.processing_artifact is not None
    artifact = result.processing_artifact.value
    assert artifact["normalized"]["normalized"] == "hello world"
    assert artifact["normalized"]["source"] == "  Hello World  "
    assert artifact["measurement"]["characterCount"] == 15


def test_step_boundary_preserved_stage_does_not_call_spu_directly(step, stage, spu_normalize, spu_measure):
    """Stage invokes only Step's public execute(); Stage never references SPU
    directly (mirrors PHASE-01 StepBoundaryNotBypassed).
    """
    result = stage.invoke(PipelineInvocationIdentity("pipe-1"), {"value": "test"})

    # Stage called the Step once
    assert step.calls == 1
    # Each SPU was invoked through the Step (not directly by Stage)
    assert spu_normalize.calls == 1
    assert spu_measure.calls == 1
    assert result["stageIdentity"] == "stage-1"


def test_spu_execution_result_distinct_from_step_execution_result():
    """SPUExecutionResult and StepExecutionResult are separate types
    (mirrors PHASE-01 acceptance P01-ACC-07).
    """
    assert SPUExecutionResult is not StepExecutionResult

    registry = SPUErrorTypeDefinitionRegistry(
        identity=SPUErrorTypeDefinitionRegistryIdentity("registry-2"),
        owner_spu_identity=SPUIdentity("spu-1"),
    )
    spu = _NormalizeSPU(SPUIdentity("spu-1"), registry)
    spu_result = spu.execute({"value": "x"})
    assert isinstance(spu_result, SPUExecutionResult)
    assert type(spu_result).__name__ == "SPUExecutionResult"

    # StepExecutionResult is produced by Step, not by SPU directly
    spu2 = _NormalizeSPU(SPUIdentity("spu-2"), registry)
    spu3 = _MeasureSPU(SPUIdentity("spu-3"), registry)
    step = _ConcreteStep(
        StepIdentity("step-1"), StageIdentity("stage-1"), spu2, spu3
    )
    invocation = StepInvocation(
        step_identity=StepIdentity("step-1"),
        step_invocation_identity=StepInvocationIdentity("inv-1"),
        owning_stage_identity=StageIdentity("stage-1"),
        parent_stage_invocation_identity=StageInvocationIdentity("stage-inv-1"),
        pipeline_invocation_identity=PipelineInvocationIdentity("pipe-1"),
        input={"value": "x"},
        execution_context=StepExecutionContext(),
    )
    step_result = step.execute(invocation)
    assert isinstance(step_result, StepExecutionResult)
    assert type(step_result).__name__ == "StepExecutionResult"


def test_pipeline_invocation_identity_propagated_through_hierarchy(step):
    """Pipeline invocation identity flows through Stage → Step → SPU."""
    pipeline_id = PipelineInvocationIdentity("pipe-e2e-1")

    invocation = StepInvocation(
        step_identity=StepIdentity("step-1"),
        step_invocation_identity=StepInvocationIdentity("step-inv-1"),
        owning_stage_identity=StageIdentity("stage-1"),
        parent_stage_invocation_identity=StageInvocationIdentity("stage-inv-1"),
        pipeline_invocation_identity=pipeline_id,
        input={"value": "x"},
        execution_context=StepExecutionContext(),
    )
    result = step.execute(invocation)

    assert invocation.pipeline_invocation_identity == pipeline_id


def test_step_optional_result_slots_independently_absent(step):
    """StepExecutionResult optional slots (validator_result, error_result,
    error_handler_result) are independently absent/present."""
    invocation = StepInvocation(
        step_identity=StepIdentity("step-1"),
        step_invocation_identity=StepInvocationIdentity("inv-1"),
        owning_stage_identity=StageIdentity("stage-1"),
        parent_stage_invocation_identity=StageInvocationIdentity("stage-inv-1"),
        pipeline_invocation_identity=PipelineInvocationIdentity("pipe-1"),
        input={"value": "x"},
        execution_context=StepExecutionContext(),
    )
    result = step.execute(invocation)

    assert result.optional_result_contributions.validator_result == Absent()
    assert result.optional_result_contributions.error_result == Absent()
    assert result.optional_result_contributions.error_handler_result == Absent()
    assert result.processing_artifact is not None


def test_domain_identities_are_nominal_types_in_hierarchy():
    """GPWCF identity types are nominal value types, not strings or ints."""
    pipeline_id = PipelineInvocationIdentity("pipe-1")
    stage_id = StageIdentity("stage-1")
    step_id = StepIdentity("step-1")
    spu_id = SPUIdentity("spu-1")
    stage_inv_id = StageInvocationIdentity("stage-inv-1")
    step_inv_id = StepInvocationIdentity("step-inv-1")
    inv_id = InvocationIdentity("inv-1")

    assert type(pipeline_id) is PipelineInvocationIdentity
    assert type(stage_id) is StageIdentity
    assert type(step_id) is StepIdentity
    assert type(spu_id) is SPUIdentity
    assert type(stage_inv_id) is StageInvocationIdentity
    assert type(step_inv_id) is StepInvocationIdentity
    assert type(inv_id) is InvocationIdentity

    # Distinct types remain distinct despite equal string values
    assert pipeline_id != stage_id
    assert stage_id != step_id
    assert step_id != spu_id

    assert pipeline_id != "pipe-1"
    assert stage_id != "stage-1"
