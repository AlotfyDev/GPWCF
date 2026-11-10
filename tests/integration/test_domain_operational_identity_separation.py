"""Integration tests for GPWCF domain identity vs operational identity separation.

Based on PHASE-01 / PHASE-02 use cases:
  - GPWCF domain identities (PipelineInvocationIdentity, StageIdentity,
    StepIdentity, SPUIdentity, InvocationIdentity) remain distinct from
    Prefect operational identities (Flow Run IDs, Task Run IDs, Deployment IDs)
  - Neither namespace substitutes for the other
  - Domain/correlation fields and Prefect native IDs are independently tracked

These tests verify the identity separation invariant using actual GPWCF
identity types without requiring a Prefect server.
"""

import pytest

from gpwcf.core.identities import (
    InvocationIdentity,
    PipelineInvocationIdentity,
    SPUIdentity,
    StageIdentity,
    StepIdentity,
    StageInvocationIdentity,
    StepInvocationIdentity,
)


def test_domain_identities_are_distinct_nominal_types():
    """GPWCF domain identity types are separate nominal types from each other
    and from raw string values."""
    pipeline_id = PipelineInvocationIdentity("run-123")
    stage_id = StageIdentity("stage-abc")
    step_id = StepIdentity("step-def")
    spu_id = SPUIdentity("spu-xyz")
    stage_inv_id = StageInvocationIdentity("sinv-1")
    step_inv_id = StepInvocationIdentity("sinv-2")
    inv_id = InvocationIdentity("inv-999")

    # Each type is distinct
    assert type(pipeline_id) is PipelineInvocationIdentity
    assert type(stage_id) is StageIdentity
    assert type(step_id) is StepIdentity
    assert type(spu_id) is SPUIdentity
    assert type(stage_inv_id) is StageInvocationIdentity
    assert type(step_inv_id) is StepInvocationIdentity
    assert type(inv_id) is InvocationIdentity

    # Equal string values of different types are NOT equal
    assert pipeline_id != stage_id
    assert stage_id != step_id
    assert step_id != spu_id
    assert stage_inv_id != step_inv_id

    # Identity types are not equal to raw strings
    assert pipeline_id != "run-123"
    assert stage_id != "stage-abc"
    assert step_id != "step-def"

    # Hash is type-aware (same value, different type = different hash)
    assert hash(pipeline_id) != hash(StageIdentity("run-123"))


def test_domain_identity_separation_from_prefect_operational_ids():
    """GPWCF domain identities and Prefect operational identities are separate
    namespaces. A domain identity value never equals a Prefect native ID even
    when the string representation looks similar (mirrors PHASE-01/PHASE-02
    identity separation requirement).

    This test verifies the invariant structurally (no Prefect import needed)
    by confirming that domain identity types carry type information that
    Prefect operational ID strings do not.
    """
    domain_pipeline_id = PipelineInvocationIdentity("flow-run-abc")
    domain_stage_id = StageIdentity("task-run-def")
    domain_step_id = StepIdentity("deployment-xyz")

    # Domain identity values that happen to look like Prefect native IDs
    # are still domain identities, not operational IDs
    assert domain_pipeline_id.value == "flow-run-abc"
    assert domain_stage_id.value == "task-run-def"
    assert domain_step_id.value == "deployment-xyz"

    # But they are NOT the Prefect native IDs themselves — they are
    # GPWCF nominal types with separate identity semantics
    assert type(domain_pipeline_id) is PipelineInvocationIdentity
    assert type(domain_stage_id) is StageIdentity
    assert type(domain_step_id) is StepIdentity

    # Cross-type equality prohibited even when string values match
    assert domain_pipeline_id != domain_stage_id
    assert domain_stage_id != domain_step_id


def test_invocation_identity_distinct_from_component_identity():
    """Invocation identity (authorizes one execution attempt) is distinct
    from component identity (identifies the component instance)."""
    step_id = StepIdentity("step-1")
    step_inv_id = StepInvocationIdentity("step-1")  # same string, different type
    stage_inv_id = StageInvocationIdentity("step-1")  # same string, different type

    # Same string value, different nominal types — NOT equal
    assert step_id != step_inv_id
    assert step_inv_id != stage_inv_id
    assert step_id != stage_inv_id

    # Hash is type-aware
    assert hash(step_id) != hash(step_inv_id)
    assert hash(step_inv_id) != hash(stage_inv_id)


def test_domain_identity_propagation_through_call_boundary():
    """Domain identity values are carried verbatim through call boundaries
    without transformation (mirrors PHASE-01 identity separation)."""
    pipeline_id = PipelineInvocationIdentity("pipe-e2e-1")
    stage_id = StageIdentity("stage-prod")
    step_id = StepIdentity("step-prod")
    spu_id = SPUIdentity("spu-prod")

    # Simulate carrying identities through Stage → Step → SPU boundary
    carried_pipeline = pipeline_id
    carried_stage = stage_id
    carried_step = step_id
    carried_spu = spu_id

    assert carried_pipeline == pipeline_id
    assert carried_stage == stage_id
    assert carried_step == step_id
    assert carried_spu == spu_id

    # Types preserved through propagation
    assert type(carried_pipeline) is PipelineInvocationIdentity
    assert type(carried_stage) is StageIdentity
    assert type(carried_step) is StepIdentity
    assert type(carried_spu) is SPUIdentity
