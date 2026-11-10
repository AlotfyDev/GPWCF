"""End-to-end tests: Pipeline Root → Stage → Step → SPU → assembled result.

Based on PHASE-01 / PHASE-02 use cases:
  - Pipeline Root owns pipeline-level invocation and coordinates Stage execution
  - Stage Parent Flow owns Step membership and coordinates Step execution
  - Step Subflow owns SPU execution and assembles StepExecutionResult
  - Each SPU Task produces SPUExecutionResult consumed by Step Composition

These E2E tests use contract-shaped GPWCF source components (no Prefect server
required) to exercise the full calling chain from Pipeline invocation through
SPU result assembly. They verify the end-to-end behavior that PHASE-01 and
PHASE-02 qualified using Prefect native constructs.
"""

import pytest

from gpwcf.core.identities import (
    PipelineInvocationIdentity,
    StageIdentity,
    StepIdentity,
    SPUIdentity,
    StageInvocationIdentity,
    StepInvocationIdentity,
)
from gpwcf.core.processing_units.spu import StepProcessingUnit
from gpwcf.core.processing_units.spu.errors import (
    SPUErrorTypeDefinitionRegistry,
    SPUErrorTypeDefinitionRegistryIdentity,
)
from gpwcf.core.processing_units.spu.results import SPUExecutionResult
from gpwcf.core.step import Step, StepExecutionResult
from gpwcf.core.step.invocation import StepExecutionContext, StepInvocation
from gpwcf.core.step.results import Absent, OptionalResultContributions, Present


# --------------------------------------------------------------------------
# Full pipeline test doubles mirroring PHASE-01/02 topology
# --------------------------------------------------------------------------


class _NormalizeSPU(StepProcessingUnit):
    """SPU that normalizes a string value."""

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
    """SPU that measures character count."""

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


class _E2EStep(Step):
    """Concrete Step that fans out to two SPUs and assembles StepExecutionResult."""

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


class _E2EStage:
    """Concrete Stage that owns Step membership and invokes Steps through
    their public callable boundary."""

    def __init__(self, stage_identity: StageIdentity):
        self._stage_identity = stage_identity
        self._steps: dict[StepIdentity, _E2EStep] = {}
        self.calls = 0

    @property
    def stage_identity(self) -> StageIdentity:
        return self._stage_identity

    def add_step(self, step: _E2EStep) -> None:
        self._steps[step.step_identity] = step

    def execute_stage(self, pipeline_invocation_identity: PipelineInvocationIdentity, input: dict):
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


class _PipelineRoot:
    """Pipeline Root that owns pipeline-level invocation and coordinates Stage
    execution through Stage public callable boundary (mirrors pipeline_root_flow
    PoC fixture).
    """

    def __init__(self):
        self._stages: dict[StageIdentity, _E2EStage] = {}
        self.calls = 0

    def add_stage(self, stage: _E2EStage) -> None:
        self._stages[stage.stage_identity] = stage

    def execute_pipeline(
        self, pipeline_invocation_identity: PipelineInvocationIdentity, input: dict
    ) -> dict:
        self.calls += 1
        stage_results = []
        for stage in self._stages.values():
            stage_result = stage.execute_stage(pipeline_invocation_identity, input)
            stage_results.append(stage_result)
        return {
            "pipelineInvocationIdentity": pipeline_invocation_identity.value,
            "stageCount": len(stage_results),
            "stages": stage_results,
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
    return _E2EStep(
        StepIdentity("step-1"), StageIdentity("stage-1"), spu_normalize, spu_measure
    )


@pytest.fixture
def stage(step):
    s = _E2EStage(StageIdentity("stage-1"))
    s.add_step(step)
    return s


@pytest.fixture
def root(stage):
    r = _PipelineRoot()
    r.add_stage(stage)
    return r


# --------------------------------------------------------------------------
# E2E tests: Pipeline Root → Stage → Step → SPU
# --------------------------------------------------------------------------


def test_pipeline_root_to_stage_to_step_to_spu_e2e(root, stage, step, spu_normalize, spu_measure):
    """Full E2E flow: Pipeline Root → Stage → Step → SPU → assembled result
    (mirrors PHASE-01 native hierarchy qualification).
    """
    pipeline_id = PipelineInvocationIdentity("pipe-e2e-1")
    input_value = {"value": "  EndToEnd Test  "}

    result = root.execute_pipeline(pipeline_id, input_value)

    # Pipeline level
    assert result["pipelineInvocationIdentity"] == "pipe-e2e-1"
    assert result["stageCount"] == 1
    assert len(result["stages"]) == 1

    # Stage level
    stage_result = result["stages"][0]
    assert stage_result["stageIdentity"] == "stage-1"
    assert stage_result["pipelineInvocationIdentity"] == "pipe-e2e-1"

    # Step level
    step_result = stage_result["stepResult"]
    assert isinstance(step_result, StepExecutionResult)

    # SPU level — both SPUs called through Step
    assert spu_normalize.calls == 1
    assert spu_measure.calls == 1

    # Final artifact assembled by Step from SPU results
    artifact = step_result.processing_artifact.value
    assert artifact["normalized"]["normalized"] == "endtoend test"
    assert artifact["normalized"]["source"] == "  EndToEnd Test  "
    assert artifact["measurement"]["characterCount"] == 17


def test_pipeline_invocation_identity_preserved_end_to_end(root, stage, step, spu_normalize, spu_measure):
    """Pipeline invocation identity is preserved unchanged through all levels
    of the hierarchy (mirrors PHASE-01 identity separation)."""
    pipeline_id = PipelineInvocationIdentity("pipe-preserve-1")

    result = root.execute_pipeline(pipeline_id, {"value": "test"})

    assert result["pipelineInvocationIdentity"] == "pipe-preserve-1"
    for stage_result in result["stages"]:
        assert stage_result["pipelineInvocationIdentity"] == "pipe-preserve-1"


def test_multiple_stages_in_pipeline(root, spu_normalize, spu_measure, registry):
    """Pipeline Root can own multiple Stage instances, each invoking its own Steps
    (mirrors PHASE-01 two Stage Parent Flows per Root invocation).
    """
    stage_a = _E2EStage(StageIdentity("stage-a"))
    step_a = _E2EStep(StepIdentity("step-a"), StageIdentity("stage-a"), spu_normalize, spu_measure)
    stage_a.add_step(step_a)
    root.add_stage(stage_a)

    stage_b = _E2EStage(StageIdentity("stage-b"))
    step_b = _E2EStep(StepIdentity("step-b"), StageIdentity("stage-b"), spu_normalize, spu_measure)
    stage_b.add_step(step_b)
    root.add_stage(stage_b)

    result = root.execute_pipeline(PipelineInvocationIdentity("pipe-multi-1"), {"value": "multi"})

    # root fixture already has stage-1, plus stage-a and stage-b
    assert result["stageCount"] == 3
    stage_identities = {s["stageIdentity"] for s in result["stages"]}
    assert stage_identities == {"stage-1", "stage-a", "stage-b"}

    # Each Stage invoked its Step once
    assert stage_a.calls == 1
    assert stage_b.calls == 1
    # Each Step invoked its SPUs once (plus stage-1's step from fixture)
    assert spu_normalize.calls == 3
    assert spu_measure.calls == 3


def test_step_result_assembled_from_spu_results(step, spu_normalize, spu_measure):
    """StepExecutionResult processing artifact is assembled from SPU results
    (mirrors PHASE-01 step subworkflow result assembly)."""
    invocation = StepInvocation(
        step_identity=StepIdentity("step-1"),
        step_invocation_identity=StepInvocationIdentity("inv-1"),
        owning_stage_identity=StageIdentity("stage-1"),
        parent_stage_invocation_identity=StageInvocationIdentity("stage-inv-1"),
        pipeline_invocation_identity=PipelineInvocationIdentity("pipe-1"),
        input={"value": "  assembly test  "},
        execution_context=StepExecutionContext(),
    )

    result = step.execute(invocation)

    artifact = result.processing_artifact.value
    # Step assembled results from both SPUs
    assert "normalized" in artifact
    assert "measurement" in artifact
    assert artifact["normalized"]["normalized"] == "assembly test"
    assert artifact["measurement"]["characterCount"] == 17

    # SPU results are NOT returned as Step result directly — they are consumed
    # by Step Composition and re-assembled
    assert result.processing_artifact != spu_normalize.execute(invocation.input).processing_artifact


def test_optional_result_slots_absent_in_e2e_result(step):
    """In E2E flow, optional result slots are independently absent when no
    supporting pattern is selected."""
    invocation = StepInvocation(
        step_identity=StepIdentity("step-1"),
        step_invocation_identity=StepInvocationIdentity("inv-1"),
        owning_stage_identity=StageIdentity("stage-1"),
        parent_stage_invocation_identity=StageInvocationIdentity("stage-inv-1"),
        pipeline_invocation_identity=PipelineInvocationIdentity("pipe-1"),
        input={"value": "test"},
        execution_context=StepExecutionContext(),
    )
    result = step.execute(invocation)

    contributions = result.optional_result_contributions
    assert contributions.validator_result == Absent()
    assert contributions.error_result == Absent()
    assert contributions.error_handler_result == Absent()
    assert result.processing_artifact is not None
