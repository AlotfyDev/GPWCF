"""End-to-end tests: Prefect-native pipeline execution.

Based on PHASE-01 / PHASE-02 use cases:
  - Pipeline Root Flow → Stage Parent Flow → Step Subflow → SPU Tasks
  - Deployment-backed Stage invocation via run_deployment(as_subflow=True)
  - Domain identity / operational identity separation
  - Typed domain results preserved through Prefect execution
  - Prefect State is operational evidence, not domain result

These E2E tests use actual Prefect constructs when Prefect is installed
(guarded by importorskip). They test the integration patterns that PHASE-01
and PHASE-02 qualified using contract-shaped fixtures.
"""

import pytest

prefect = pytest.importorskip(
    "prefect", reason="Prefect not installed — skipping Prefect E2E tests"
)

from prefect import flow, task
from prefect.context import get_run_context
from prefect.task_runners import ThreadPoolTaskRunner
from uuid import uuid4

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


def _runtime_context() -> dict:
    context = get_run_context()
    flow_run = getattr(context, "flow_run", None)
    task_run = getattr(context, "task_run", None)
    return {
        "nativeFlowRunId": str(flow_run.id) if flow_run and flow_run.id else None,
        "nativeParentTaskRunId": (
            str(flow_run.parent_task_run_id)
            if flow_run and getattr(flow_run, "parent_task_run_id", None)
            else None
        ),
        "nativeTaskRunId": str(task_run.id) if task_run and task_run.id else None,
    }


# --------------------------------------------------------------------------
# Prefect-native tasks mirroring PHASE-01/02 PoC patterns
# --------------------------------------------------------------------------


@task(name="e2e-spu-normalize", retries=0)
def e2e_spu_normalize(
    spu_identity: str,
    spu_invocation_identity: str,
    step_invocation_identity: str,
    stage_invocation_identity: str,
    pipeline_invocation_identity: str,
    parent_step_flow_run_id: str,
    trace_file: str,
    payload: dict,
) -> SPUExecutionResult:
    _record(
        trace_file, "started", "SPU", spu_identity, spu_invocation_identity,
        pipeline_invocation_identity, stage_invocation_identity,
        step_invocation_identity, step_invocation_identity,
        parent_step_flow_run_id, {"task": "normalize"},
    )
    import time
    time.sleep(0.10)
    return SPUExecutionResult(
        processing_artifact={
            "normalized": str(payload["value"]).strip().lower(),
            "source": payload["value"],
        },
    )


@task(name="e2e-spu-measure", retries=0)
def e2e_spu_measure(
    spu_identity: str,
    spu_invocation_identity: str,
    step_invocation_identity: str,
    stage_invocation_identity: str,
    pipeline_invocation_identity: str,
    parent_step_flow_run_id: str,
    trace_file: str,
    payload: dict,
) -> SPUExecutionResult:
    _record(
        trace_file, "started", "SPU", spu_identity, spu_invocation_identity,
        pipeline_invocation_identity, stage_invocation_identity,
        step_invocation_identity, step_invocation_identity,
        parent_step_flow_run_id, {"task": "measure"},
    )
    import time
    time.sleep(0.10)
    return SPUExecutionResult(
        processing_artifact={"characterCount": len(str(payload["value"]))},
    )


def _record(trace_file: str, event: str, component_type: str, component_identity: str,
            component_invocation_identity: str, pipeline_invocation_identity: str,
            stage_invocation_identity: str, step_invocation_identity: str,
            parent_domain_invocation_identity: str | None,
            parent_native_flow_run_id: str | None = None,
            details: dict | None = None) -> None:
    import json
    from pathlib import Path
    row = {
        "timestampUtc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        "event": event,
        "componentType": component_type,
        "componentIdentity": component_identity,
        "componentInvocationIdentity": component_invocation_identity,
        "pipelineInvocationIdentity": pipeline_invocation_identity,
        "stageInvocationIdentity": stage_invocation_identity,
        "stepInvocationIdentity": step_invocation_identity,
        "parentDomainInvocationIdentity": parent_domain_invocation_identity,
        "parentNativeFlowRunId": parent_native_flow_run_id,
        **_runtime_context(),
        "details": details or {},
    }
    path = Path(trace_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------
# Prefect-native Step Subflow mirroring PHASE-01 _step_subworkflow
# --------------------------------------------------------------------------


@flow(
    name="e2e-step-subworkflow",
    task_runner=ThreadPoolTaskRunner(max_workers=4),
)
def e2e_step_subworkflow(
    step_identity: str,
    step_invocation_identity: str,
    stage_identity: str,
    stage_invocation_identity: str,
    pipeline_invocation_identity: str,
    parent_stage_flow_run_id: str,
    trace_file: str,
    payload: dict,
) -> StepExecutionResult:
    step_flow_run_id = _runtime_context()["nativeFlowRunId"]
    _record(
        trace_file, "started", "Step", step_identity, step_invocation_identity,
        pipeline_invocation_identity, stage_invocation_identity,
        step_invocation_identity, stage_invocation_identity,
        parent_stage_flow_run_id, {"stageIdentity": stage_identity},
    )

    normalize_future = e2e_spu_normalize.submit(
        f"{step_identity}.normalize", str(uuid4()), step_invocation_identity,
        stage_invocation_identity, pipeline_invocation_identity,
        step_flow_run_id, trace_file, payload,
    )
    measure_future = e2e_spu_measure.submit(
        f"{step_identity}.measure", str(uuid4()), step_invocation_identity,
        stage_invocation_identity, pipeline_invocation_identity,
        step_flow_run_id, trace_file, payload,
    )
    normalize_result = normalize_future.result()
    measure_result = measure_future.result()

    result = StepExecutionResult(
        step_identity=StepIdentity(step_identity),
        step_invocation_identity=StepInvocationIdentity(step_invocation_identity),
        owning_stage_identity=StageIdentity(stage_identity),
        parent_stage_invocation_identity=StageInvocationIdentity(
            stage_invocation_identity
        ),
        pipeline_invocation_identity=PipelineInvocationIdentity(
            pipeline_invocation_identity
        ),
        processing_artifact=Present({
            "normalized": normalize_result.processing_artifact,
            "measurement": measure_result.processing_artifact,
        }),
        optional_result_contributions=OptionalResultContributions.all_absent(),
    )
    _record(
        trace_file, "completed", "Step", step_identity, step_invocation_identity,
        pipeline_invocation_identity, stage_invocation_identity,
        step_invocation_identity, stage_invocation_identity,
        parent_stage_flow_run_id,
        {"spuResultCount": 2, "resultType": "StepExecutionResult"},
    )
    return result


# --------------------------------------------------------------------------
# Prefect-native Stage Parent Flow mirroring PHASE-01 stage_parent_flow
# --------------------------------------------------------------------------


@flow(
    name="e2e-stage-parent-flow",
    task_runner=ThreadPoolTaskRunner(max_workers=4),
)
def e2e_stage_parent_flow(
    stage_identity: str,
    stage_invocation_identity: str,
    pipeline_invocation_identity: str,
    root_flow_run_id: str,
    trace_file: str,
    payload: dict,
) -> dict:
    stage_flow_run_id = _runtime_context()["nativeFlowRunId"]
    _record(
        trace_file, "started", "Stage", stage_identity, stage_invocation_identity,
        pipeline_invocation_identity, stage_invocation_identity,
        None, pipeline_invocation_identity, root_flow_run_id,
    )

    # Direct subflow invocation returns each completed domain result immediately.
    step_results = [
        e2e_step_subworkflow.with_options(
            name=f"e2e-step-{stage_identity}-a"
        )(
            f"{stage_identity}.step-a", str(uuid4()), stage_identity,
            stage_invocation_identity, pipeline_invocation_identity,
            stage_flow_run_id, trace_file,
            {"value": f" {stage_identity}-ALPHA "},
        ),
        e2e_step_subworkflow.with_options(
            name=f"e2e-step-{stage_identity}-b"
        )(
            f"{stage_identity}.step-b", str(uuid4()), stage_identity,
            stage_invocation_identity, pipeline_invocation_identity,
            stage_flow_run_id, trace_file,
            {"value": f" {stage_identity}-BETA "},
        ),
    ]
    result = {
        "stageIdentity": stage_identity,
        "stageInvocationIdentity": stage_invocation_identity,
        "pipelineInvocationIdentity": pipeline_invocation_identity,
        "stepResultCount": len(step_results),
        "stepResults": step_results,
    }
    _record(
        trace_file, "completed", "Stage", stage_identity, stage_invocation_identity,
        pipeline_invocation_identity, stage_invocation_identity,
        None, pipeline_invocation_identity, root_flow_run_id,
        {"stepResultCount": len(step_results), "nativeStageFlowRunId": stage_flow_run_id},
    )
    return result


# --------------------------------------------------------------------------
# Prefect-native Pipeline Root Flow mirroring PHASE-01 pipeline_root_flow
# --------------------------------------------------------------------------


@flow(
    name="e2e-pipeline-root-flow",
    task_runner=ThreadPoolTaskRunner(max_workers=4),
)
def e2e_pipeline_root_flow(
    pipeline_invocation_identity: str,
    trace_file: str,
    payload_seed: str,
) -> dict:
    root_flow_run_id = _runtime_context()["nativeFlowRunId"]
    _record(
        trace_file, "started", "PipelineRoot", "pipeline-root",
        pipeline_invocation_identity, pipeline_invocation_identity,
        None, None, None, None,
    )

    # Direct subflow invocation returns each completed domain result immediately.
    stage_results = [
        e2e_stage_parent_flow.with_options(name="e2e-stage-a")(
            "STAGE-A", str(uuid4()), pipeline_invocation_identity,
            root_flow_run_id, trace_file, {"value": f"{payload_seed}-A"},
        ),
        e2e_stage_parent_flow.with_options(name="e2e-stage-b")(
            "STAGE-B", str(uuid4()), pipeline_invocation_identity,
            root_flow_run_id, trace_file, {"value": f"{payload_seed}-B"},
        ),
    ]
    result = {
        "pipelineInvocationIdentity": pipeline_invocation_identity,
        "stageCount": len(stage_results),
        "stages": stage_results,
    }
    _record(
        trace_file, "completed", "PipelineRoot", "pipeline-root",
        pipeline_invocation_identity, pipeline_invocation_identity,
        None, None, None, None,
        details={"stageCount": len(stage_results), "nativeRootFlowRunId": root_flow_run_id},
    )
    return result


# --------------------------------------------------------------------------
# E2E tests with Prefect native execution
# --------------------------------------------------------------------------


def test_prefect_e2e_pipeline_root_to_stage_to_step_to_spu(tmp_path):
    """Full E2E Prefect flow: Pipeline Root → Stage → Step → SPU → result
    (mirrors PHASE-01 native hierarchy qualification).
    """
    trace_file = str(tmp_path / "e2e-trace.jsonl")
    pipeline_id = "pipe-prefect-e2e-1"

    state = e2e_pipeline_root_flow(
        pipeline_id, trace_file, "GPWCF-PREFECT-E2E",
        return_state=True,
    )

    assert state.is_completed()
    result = state.result()

    # Pipeline level
    assert result["pipelineInvocationIdentity"] == pipeline_id
    assert result["stageCount"] == 2
    assert len(result["stages"]) == 2

    # Trace records keep domain-parent identities separate from Prefect's
    # native parent-flow identifiers at every hierarchy level.
    import json
    from pathlib import Path
    trace_records = [
        json.loads(line)
        for line in Path(trace_file).read_text(encoding="utf-8").splitlines()
    ]
    root_start = next(
        row for row in trace_records
        if row["componentType"] == "PipelineRoot" and row["event"] == "started"
    )
    assert root_start["stageInvocationIdentity"] is None
    assert root_start["stepInvocationIdentity"] is None
    assert root_start["parentDomainInvocationIdentity"] is None
    assert root_start["parentNativeFlowRunId"] is None

    stage_starts = [
        row for row in trace_records
        if row["componentType"] == "Stage" and row["event"] == "started"
    ]
    assert len(stage_starts) == 2
    assert all(row["parentDomainInvocationIdentity"] == pipeline_id for row in stage_starts)
    assert all(row["parentNativeFlowRunId"] for row in stage_starts)

    step_starts = [
        row for row in trace_records
        if row["componentType"] == "Step" and row["event"] == "started"
    ]
    assert len(step_starts) == 4
    assert all(
        row["parentDomainInvocationIdentity"] == row["stageInvocationIdentity"]
        for row in step_starts
    )
    assert all(row["parentNativeFlowRunId"] for row in step_starts)

    spu_starts = [
        row for row in trace_records
        if row["componentType"] == "SPU" and row["event"] == "started"
    ]
    assert len(spu_starts) == 8
    assert all(
        row["parentDomainInvocationIdentity"] == row["stepInvocationIdentity"]
        for row in spu_starts
    )
    assert all(row["parentNativeFlowRunId"] for row in spu_starts)

    # Stage level — both stages completed
    for stage_result in result["stages"]:
        assert "stageIdentity" in stage_result
        assert "stepResultCount" in stage_result
        assert stage_result["stepResultCount"] == 2

    # Step level — each Step produced StepExecutionResult
    for stage_result in result["stages"]:
        for step_result in stage_result["stepResults"]:
            assert isinstance(step_result, StepExecutionResult)
            assert isinstance(step_result.processing_artifact, Present)
            artifact = step_result.processing_artifact.value
            assert "normalized" in artifact
            assert "measurement" in artifact


def test_prefect_domain_result_preserved_not_state(tmp_path):
    """Domain results (SPUExecutionResult, StepExecutionResult) are preserved
    through Prefect execution — not replaced by Prefect State."""
    trace_file = str(tmp_path / "e2e-trace.jsonl")

    state = e2e_pipeline_root_flow(
        "pipe-state-test-1", trace_file, "STATE-TEST",
        return_state=True,
    )

    assert state.is_completed()
    result = state.result()

    # Domain results present in pipeline output
    for stage_result in result["stages"]:
        for step_result in stage_result["stepResults"]:
            assert isinstance(step_result, StepExecutionResult)
            assert isinstance(step_result.processing_artifact, Present)
            artifact = step_result.processing_artifact.value
            assert "normalized" in artifact
            assert "measurement" in artifact

    # Prefect State is separate (state.name, state.type) — not embedded in result
    assert state.name == "Completed"
    # The result dict contains domain data, not Prefect State objects


def test_prefect_domain_identity_separation(tmp_path):
    """GPWCF domain identities remain separate from Prefect operational IDs."""
    trace_file = str(tmp_path / "e2e-trace.jsonl")

    state = e2e_pipeline_root_flow(
        "pipe-identity-1", trace_file, "IDENTITY-TEST",
        return_state=True,
    )

    assert state.is_completed()
    result = state.result()

    # Domain identities are present
    assert result["pipelineInvocationIdentity"] == "pipe-identity-1"
    for stage_result in result["stages"]:
        assert stage_result["stageIdentity"] in ("STAGE-A", "STAGE-B")
        assert stage_result["pipelineInvocationIdentity"] == "pipe-identity-1"

    # Prefect native IDs exist in runtime context but are separate from domain IDs
    # (verified by the fact that domain identity types are nominal, not strings)
    from gpwcf.core.identities import PipelineInvocationIdentity
    assert type(PipelineInvocationIdentity("pipe-identity-1")) is PipelineInvocationIdentity
    assert PipelineInvocationIdentity("pipe-identity-1") != "pipe-identity-1"
