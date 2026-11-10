"""StageResult serialization/persistence integration test (Task 03 DoD).

StageResult must round-trip via stdlib json. Persistence mapping itself is
finalized by task 09's Prefect persistence binding; this test covers the
serialization boundary contract only.
"""

import json

import pytest

from gpwcf.core.identities import (
    PipelineInvocationIdentity,
    StageIdentity,
    StageInvocationIdentity,
)
from gpwcf.core.stage import (
    StageFlowResult,
    StageInvocation,
    StageResult,
)
from gpwcf.core.step.results import Absent, Present


def _make_flow_result() -> StageFlowResult:
    flow = StageFlowResult()
    flow.record_flow_transition("fan-out to 2 Steps")
    return flow


def test_stage_result_serializes_to_json_round_trip():
    """StageResult serializes to JSON and deserializes back with equal values."""
    result = StageResult(
        stage_identity=StageIdentity("stage-1"),
        stage_invocation_identity=StageInvocationIdentity("inv-1"),
        owning_pipeline_invocation_identity=PipelineInvocationIdentity("pipe-1"),
        parent_stage_invocation_identity=None,
        processing_artifact=Present("fan-out-result"),
        stage_outputs=Absent(),
        stage_flow_result=_make_flow_result(),
        domain_outcome=Absent(),
    )

    payload = {
        "stage_identity": result.stage_identity.value,
        "stage_invocation_identity": result.stage_invocation_identity.value,
        "owning_pipeline_invocation_identity": result.owning_pipeline_invocation_identity.value
        if result.owning_pipeline_invocation_identity
        else None,
        "parent_stage_invocation_identity": result.parent_stage_invocation_identity.value
        if result.parent_stage_invocation_identity
        else None,
        "processing_artifact": (
            {"Present": result.processing_artifact.value}
            if isinstance(result.processing_artifact, Present)
            else {"Absent": None}
        ),
        "stage_outputs": (
            {"Present": result.stage_outputs.value}
            if isinstance(result.stage_outputs, Present)
            else {"Absent": None}
        ),
        "domain_outcome": (
            {"Present": result.domain_outcome.value}
            if isinstance(result.domain_outcome, Present)
            else {"Absent": None}
        ),
        "stage_flow_result": {
            "sealed": result.stage_flow_result.sealed,
            "step_invocations": [],
            "flow_transitions": [
                {"description": t.description, "sequence": t.sequence}
                for t in result.stage_flow_result.flow_transitions
            ],
            "exceptions": [],
        },
    }

    text = json.dumps(payload, indent=2)
    parsed = json.loads(text)

    assert parsed["stage_identity"] == "stage-1"
    assert parsed["stage_invocation_identity"] == "inv-1"
    assert parsed["owning_pipeline_invocation_identity"] == "pipe-1"
    assert parsed["parent_stage_invocation_identity"] is None
    assert parsed["processing_artifact"] == {"Present": "fan-out-result"}
    assert parsed["stage_outputs"] == {"Absent": None}
    assert parsed["domain_outcome"] == {"Absent": None}
    assert parsed["stage_flow_result"]["sealed"] is False
    assert len(parsed["stage_flow_result"]["flow_transitions"]) == 1
    assert parsed["stage_flow_result"]["flow_transitions"][0]["description"] == "fan-out to 2 Steps"


def test_stage_result_serializes_with_absent_artifact():
    """StageResult with Absent processing_artifact serializes correctly."""
    result = StageResult(
        stage_identity=StageIdentity("stage-1"),
        stage_invocation_identity=StageInvocationIdentity("inv-2"),
        owning_pipeline_invocation_identity=None,
        parent_stage_invocation_identity=None,
        processing_artifact=Absent(),
        stage_outputs=Absent(),
        stage_flow_result=StageFlowResult(),
        domain_outcome=Absent(),
    )

    payload = {
        "processing_artifact": {"Absent": None},
        "stage_outputs": {"Absent": None},
        "domain_outcome": {"Absent": None},
    }
    text = json.dumps(payload)
    parsed = json.loads(text)
    assert parsed["processing_artifact"] == {"Absent": None}


def test_stage_result_serializes_with_present_none():
    """Present(None) serializes distinctly from Absent (discriminated presence)."""
    result = StageResult(
        stage_identity=StageIdentity("stage-1"),
        stage_invocation_identity=StageInvocationIdentity("inv-3"),
        owning_pipeline_invocation_identity=None,
        parent_stage_invocation_identity=None,
        processing_artifact=Present(None),
        stage_outputs=Absent(),
        stage_flow_result=StageFlowResult(),
        domain_outcome=Absent(),
    )

    payload = {
        "processing_artifact": {"Present": None},
    }
    text = json.dumps(payload)
    parsed = json.loads(text)
    assert parsed["processing_artifact"] == {"Present": None}


def test_stage_result_with_pipeline_invocation_identity_none():
    """owning_pipeline_invocation_identity is None when not supplied (consumer correlation optional)."""
    result = StageResult(
        stage_identity=StageIdentity("stage-1"),
        stage_invocation_identity=StageInvocationIdentity("inv-4"),
        owning_pipeline_invocation_identity=None,
        parent_stage_invocation_identity=None,
        processing_artifact=Present("x"),
        stage_outputs=Absent(),
        stage_flow_result=StageFlowResult(),
        domain_outcome=Absent(),
    )
    assert result.owning_pipeline_invocation_identity is None


def test_stage_result_identity_fields_are_nominal_types():
    """Identity fields use nominal identity value types, not raw strings."""
    result = StageResult(
        stage_identity=StageIdentity("stage-1"),
        stage_invocation_identity=StageInvocationIdentity("inv-5"),
        owning_pipeline_invocation_identity=None,
        parent_stage_invocation_identity=None,
        processing_artifact=Present("x"),
        stage_outputs=Absent(),
        stage_flow_result=StageFlowResult(),
        domain_outcome=Absent(),
    )
    assert type(result.stage_identity) is StageIdentity
    assert type(result.stage_invocation_identity) is StageInvocationIdentity
    assert result.stage_identity.value == "stage-1"
    assert result.stage_invocation_identity.value == "inv-5"
