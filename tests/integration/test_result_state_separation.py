"""Integration tests for domain result vs Prefect State separation.

Based on PHASE-01 / PHASE-02 use cases:
  - Prefect State is operational execution evidence, NOT a GPWCF domain result
  - SPUExecutionResult, StepExecutionResult, StageResult are domain results
  - Domain results are preserved through Prefect execution unchanged
  - No GPWCF domain structured result is fabricated from Prefect State

These tests verify the result/state separation invariant using actual GPWCF
result types without requiring a Prefect server.
"""

import pytest

from gpwcf.core.processing_units.spu.results import SPUExecutionResult
from gpwcf.core.step import StepExecutionResult
from gpwcf.core.step.results import Absent, OptionalResultContributions, Present
from gpwcf.core.stage.results import StageResult
from gpwcf.core.identities import (
    PipelineInvocationIdentity,
    StageIdentity,
    StageInvocationIdentity,
    StepIdentity,
    StepInvocationIdentity,
)


def test_spu_execution_result_is_not_prefect_state():
    """SPUExecutionResult is a GPWCF domain result, not Prefect State.
    It has no Prefect state attributes (state, run_id, flow_run_id, etc.)."""
    result = SPUExecutionResult(processing_artifact={"normalized": "hello"})

    # Domain result has processing artifact
    assert result.processing_artifact is not None
    assert result.processing_artifact["normalized"] == "hello"

    # No Prefect State attributes
    assert not hasattr(result, "state")
    assert not hasattr(result, "run_id")
    assert not hasattr(result, "flow_run_id")
    assert not hasattr(result, "task_run_id")
    assert not hasattr(result, "deployment_id")


def test_step_execution_result_is_not_prefect_state():
    """StepExecutionResult is a GPWCF domain result, not Prefect State."""
    result = StepExecutionResult(
        step_identity=StepIdentity("step-1"),
        step_invocation_identity=StepInvocationIdentity("inv-1"),
        owning_stage_identity=StageIdentity("stage-1"),
        parent_stage_invocation_identity=StageInvocationIdentity("stage-inv-1"),
        pipeline_invocation_identity=PipelineInvocationIdentity("pipe-1"),
        processing_artifact=Present({"artifact": "value"}),
        optional_result_contributions=OptionalResultContributions.all_absent(),
    )

    # Domain result has processing artifact
    assert result.processing_artifact is not None
    assert result.processing_artifact.value == {"artifact": "value"}

    # No Prefect State attributes
    assert not hasattr(result, "state")
    assert not hasattr(result, "run_id")
    assert not hasattr(result, "flow_run_id")
    assert not hasattr(result, "task_run_id")
    assert not hasattr(result, "deployment_id")


def test_stage_result_is_not_prefect_state():
    """StageResult is a GPWCF domain result, not Prefect State."""
    result = StageResult(
        stage_identity=StageIdentity("stage-1"),
        stage_invocation_identity=StageInvocationIdentity("inv-1"),
        owning_pipeline_invocation_identity=PipelineInvocationIdentity("pipe-1"),
        parent_stage_invocation_identity=None,
        processing_artifact=Present("stage-output"),
        stage_outputs=Absent(),
        stage_flow_result=__import__(
            "gpwcf.core.stage.results", fromlist=["StageFlowResult"]
        ).StageFlowResult(),
        domain_outcome=Absent(),
    )

    # Domain result has processing artifact
    assert result.processing_artifact is not None
    assert result.processing_artifact.value == "stage-output"

    # No Prefect State attributes
    assert not hasattr(result, "state")
    assert not hasattr(result, "run_id")
    assert not hasattr(result, "flow_run_id")
    assert not hasattr(result, "task_run_id")
    assert not hasattr(result, "deployment_id")


def test_domain_result_carries_invocation_identity_not_prefect_ids():
    """Domain results carry GPWCF invocation identities, not Prefect
    operational IDs (Flow Run / Task Run / Deployment IDs)."""
    pipeline_id = PipelineInvocationIdentity("pipe-1")
    stage_inv_id = StageInvocationIdentity("stage-inv-1")
    step_inv_id = StepInvocationIdentity("step-inv-1")

    result = StepExecutionResult(
        step_identity=StepIdentity("step-1"),
        step_invocation_identity=step_inv_id,
        owning_stage_identity=StageIdentity("stage-1"),
        parent_stage_invocation_identity=stage_inv_id,
        pipeline_invocation_identity=pipeline_id,
        processing_artifact=Present("output"),
        optional_result_contributions=OptionalResultContributions.all_absent(),
    )

    # Domain identity fields are present
    assert result.pipeline_invocation_identity == pipeline_id
    assert result.step_invocation_identity == step_inv_id

    # These are NOT Prefect Flow Run IDs or Task Run IDs — they are
    # GPWCF nominal identity types
    assert type(result.pipeline_invocation_identity) is PipelineInvocationIdentity
    assert type(result.step_invocation_identity) is StepInvocationIdentity


def test_absent_vs_present_none_distinction():
    """Absent and Present(None) are distinct — absence is NOT None.
    This mirrors the result/state separation: a missing result is not
    the same as a Prefect FAILED state or a None result."""
    from gpwcf.core.processing_units.spu.results import SPUExecutionResult

    # SPUExecutionResult with processing_artifact=None (explicitly absent)
    result_none = SPUExecutionResult(processing_artifact=None)
    assert result_none.processing_artifact is None

    # SPUExecutionResult with no processing_artifact at all (default None)
    result_default = SPUExecutionResult()
    assert result_default.processing_artifact is None

    # StepExecutionResult optional slots: Absent != Present(None)
    result_absent = StepExecutionResult(
        step_identity=StepIdentity("step-1"),
        step_invocation_identity=StepInvocationIdentity("inv-1"),
        owning_stage_identity=StageIdentity("stage-1"),
        parent_stage_invocation_identity=StageInvocationIdentity("stage-inv-1"),
        pipeline_invocation_identity=PipelineInvocationIdentity("pipe-1"),
        processing_artifact=Present("output"),
        optional_result_contributions=OptionalResultContributions.all_absent(),
    )
    assert result_absent.optional_result_contributions.validator_result == Absent()

    # Present(None) would be distinct from Absent (if a domain type permits None)
    result_present_none = StepExecutionResult(
        step_identity=StepIdentity("step-1"),
        step_invocation_identity=StepInvocationIdentity("inv-2"),
        owning_stage_identity=StageIdentity("stage-1"),
        parent_stage_invocation_identity=StageInvocationIdentity("stage-inv-1"),
        pipeline_invocation_identity=PipelineInvocationIdentity("pipe-1"),
        processing_artifact=Present(None),
        optional_result_contributions=OptionalResultContributions.all_absent(),
    )
    assert result_present_none.processing_artifact.value is None
    assert result_present_none.processing_artifact != Absent()


def test_domain_result_is_immutable_value():
    """Domain results are immutable value objects — they are not
    mutable Prefect State objects that change over time."""
    result = StepExecutionResult(
        step_identity=StepIdentity("step-1"),
        step_invocation_identity=StepInvocationIdentity("inv-1"),
        owning_stage_identity=StageIdentity("stage-1"),
        parent_stage_invocation_identity=StageInvocationIdentity("stage-inv-1"),
        pipeline_invocation_identity=PipelineInvocationIdentity("pipe-1"),
        processing_artifact=Present("output"),
        optional_result_contributions=OptionalResultContributions.all_absent(),
    )

    from dataclasses import FrozenInstanceError
    with pytest.raises(FrozenInstanceError):
        result.processing_artifact = Present("changed")
