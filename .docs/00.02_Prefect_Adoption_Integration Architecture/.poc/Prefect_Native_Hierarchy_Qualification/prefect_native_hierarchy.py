from __future__ import annotations

import argparse
import json
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generic, TypeVar
from uuid import uuid4

from prefect import flow, task
from prefect.context import get_run_context
from prefect.task_runners import ThreadPoolTaskRunner

T = TypeVar("T")
_TRACE_LOCK = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_context() -> dict[str, str | None]:
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


def _record(
    trace_file: str,
    event: str,
    component_type: str,
    component_identity: str,
    component_invocation_identity: str,
    pipeline_invocation_identity: str,
    stage_invocation_identity: str | None = None,
    step_invocation_identity: str | None = None,
    parent_domain_invocation_identity: str | None = None,
    parent_flow_run_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    row = {
        "timestampUtc": _utc_now(),
        "event": event,
        "componentType": component_type,
        "componentIdentity": component_identity,
        "componentInvocationIdentity": component_invocation_identity,
        "pipelineInvocationIdentity": pipeline_invocation_identity,
        "stageInvocationIdentity": stage_invocation_identity,
        "stepInvocationIdentity": step_invocation_identity,
        "parentDomainInvocationIdentity": parent_domain_invocation_identity,
        "parentFlowRunId": parent_flow_run_id,
        **_runtime_context(),
        "details": details or {},
    }
    path = Path(trace_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _TRACE_LOCK:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


@dataclass(frozen=True)
class SPUExecutionResult(Generic[T]):
    # Contract-shaped PoC value: individual SPU invocation result only.
    processing_artifact: T | None
    spu_error_occurrences: tuple[dict[str, Any], ...] | None = None
    validator_result: dict[str, Any] | None = None


@dataclass(frozen=True)
class StepExecutionResult(Generic[T]):
    # Contract-shaped PoC value: Stage-facing Step aggregate, not Prefect State.
    processing_artifact: T | None
    validator_result: dict[str, Any] | None = None
    error_result: dict[str, Any] | None = None
    error_handler_result: dict[str, Any] | None = None


@task(name="spu-normalize", retries=0)
def spu_normalize(
    spu_identity: str,
    spu_invocation_identity: str,
    step_invocation_identity: str,
    stage_invocation_identity: str,
    pipeline_invocation_identity: str,
    parent_step_flow_run_id: str,
    trace_file: str,
    payload: dict[str, Any],
) -> SPUExecutionResult[dict[str, Any]]:
    started = time.perf_counter()
    _record(
        trace_file, "started", "SPU", spu_identity, spu_invocation_identity,
        pipeline_invocation_identity, stage_invocation_identity,
        step_invocation_identity, step_invocation_identity,
        parent_step_flow_run_id, {"task": "normalize"},
    )
    time.sleep(0.30)
    result = SPUExecutionResult(
        processing_artifact={
            "normalizedValue": str(payload["value"]).strip().lower(),
            "source": payload["value"],
        }
    )
    _record(
        trace_file, "completed", "SPU", spu_identity, spu_invocation_identity,
        pipeline_invocation_identity, stage_invocation_identity,
        step_invocation_identity, step_invocation_identity,
        parent_step_flow_run_id,
        {"task": "normalize", "elapsedSeconds": time.perf_counter() - started},
    )
    return result


@task(name="spu-measure", retries=0)
def spu_measure(
    spu_identity: str,
    spu_invocation_identity: str,
    step_invocation_identity: str,
    stage_invocation_identity: str,
    pipeline_invocation_identity: str,
    parent_step_flow_run_id: str,
    trace_file: str,
    payload: dict[str, Any],
) -> SPUExecutionResult[dict[str, Any]]:
    started = time.perf_counter()
    _record(
        trace_file, "started", "SPU", spu_identity, spu_invocation_identity,
        pipeline_invocation_identity, stage_invocation_identity,
        step_invocation_identity, step_invocation_identity,
        parent_step_flow_run_id, {"task": "measure"},
    )
    time.sleep(0.30)
    result = SPUExecutionResult(
        processing_artifact={"characterCount": len(str(payload["value"]))}
    )
    _record(
        trace_file, "completed", "SPU", spu_identity, spu_invocation_identity,
        pipeline_invocation_identity, stage_invocation_identity,
        step_invocation_identity, step_invocation_identity,
        parent_step_flow_run_id,
        {"task": "measure", "elapsedSeconds": time.perf_counter() - started},
    )
    return result


@flow(
    name="gpwcf-step-subworkflow",
    task_runner=ThreadPoolTaskRunner(max_workers=4),
)
def _step_subworkflow(
    step_identity: str,
    step_invocation_identity: str,
    stage_identity: str,
    stage_invocation_identity: str,
    pipeline_invocation_identity: str,
    parent_stage_flow_run_id: str,
    trace_file: str,
    payload: dict[str, Any],
) -> StepExecutionResult[dict[str, Any]]:
    step_flow_run_id = _runtime_context()["nativeFlowRunId"]
    _record(
        trace_file, "started", "Step", step_identity, step_invocation_identity,
        pipeline_invocation_identity, stage_invocation_identity,
        step_invocation_identity, stage_invocation_identity,
        parent_stage_flow_run_id, {"stageIdentity": stage_identity},
    )

    # SPU Tasks are children of this Step Subworkflow and are never called by Stage.
    normalize_future = spu_normalize.submit(
        f"{step_identity}.normalize", str(uuid4()), step_invocation_identity,
        stage_invocation_identity, pipeline_invocation_identity,
        step_flow_run_id, trace_file, payload,
    )
    measure_future = spu_measure.submit(
        f"{step_identity}.measure", str(uuid4()), step_invocation_identity,
        stage_invocation_identity, pipeline_invocation_identity,
        step_flow_run_id, trace_file, payload,
    )
    normalize_result = normalize_future.result()
    measure_result = measure_future.result()
    normalize_state = normalize_future.state
    measure_state = measure_future.state

    result = StepExecutionResult(
        processing_artifact={
            "normalized": normalize_result.processing_artifact,
            "measurement": measure_result.processing_artifact,
        }
    )
    _record(
        trace_file, "completed", "Step", step_identity, step_invocation_identity,
        pipeline_invocation_identity, stage_invocation_identity,
        step_invocation_identity, stage_invocation_identity,
        parent_stage_flow_run_id,
        {"spuResultCount": 2, "resultType": "StepExecutionResult",
         "nativeStepFlowRunId": step_flow_run_id,
         "spuTaskStates": [
             {"name": normalize_state.name, "type": normalize_state.type.value},
             {"name": measure_state.name, "type": measure_state.type.value},
         ]},
    )
    return result


class StepFacade:
    """PoC fixture for the documented public Step.execute(input) contract."""

    def __init__(
        self,
        step_identity: str,
        stage_identity: str,
        stage_invocation_identity: str,
        pipeline_invocation_identity: str,
        parent_stage_flow_run_id: str,
        trace_file: str,
    ) -> None:
        self.identity = step_identity
        self.stage_identity = stage_identity
        self.stage_invocation_identity = stage_invocation_identity
        self.pipeline_invocation_identity = pipeline_invocation_identity
        self.parent_stage_flow_run_id = parent_stage_flow_run_id
        self.trace_file = trace_file

    def execute(self, payload: dict[str, Any]) -> StepExecutionResult[dict[str, Any]]:
        # This public callable is the only Stage-facing route into the Step.
        specialized_step_flow = _step_subworkflow.with_options(
            name=f"gpwcf-step-{self.identity}"
        )
        return specialized_step_flow(
            self.identity, str(uuid4()), self.stage_identity,
            self.stage_invocation_identity, self.pipeline_invocation_identity,
            self.parent_stage_flow_run_id, self.trace_file, payload,
        )


@task(name="invoke-step-public-contract", retries=0)
def invoke_step(
    step_identity: str,
    stage_identity: str,
    stage_invocation_identity: str,
    pipeline_invocation_identity: str,
    parent_stage_flow_run_id: str,
    trace_file: str,
    payload: dict[str, Any],
) -> StepExecutionResult[dict[str, Any]]:
    dispatch_id = str(uuid4())
    _record(trace_file, "started", "StepDispatch", step_identity, dispatch_id,
            pipeline_invocation_identity, stage_invocation_identity, dispatch_id,
            stage_invocation_identity, parent_stage_flow_run_id)
    facade = StepFacade(
        step_identity, stage_identity, stage_invocation_identity,
        pipeline_invocation_identity, parent_stage_flow_run_id, trace_file,
    )
    result = facade.execute(payload)
    _record(trace_file, "completed", "StepDispatch", step_identity, dispatch_id,
            pipeline_invocation_identity, stage_invocation_identity, dispatch_id,
            stage_invocation_identity, parent_stage_flow_run_id)
    return result


@flow(
    name="gpwcf-stage-parent-flow",
    task_runner=ThreadPoolTaskRunner(max_workers=4),
)
def stage_parent_flow(
    stage_identity: str,
    stage_invocation_identity: str,
    pipeline_invocation_identity: str,
    root_flow_run_id: str,
    trace_file: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    stage_flow_run_id = _runtime_context()["nativeFlowRunId"]
    _record(
        trace_file, "started", "Stage", stage_identity, stage_invocation_identity,
        pipeline_invocation_identity, stage_invocation_identity,
        None, pipeline_invocation_identity, root_flow_run_id,
    )

    # Stage dispatches only public Step callables. Each callable creates a
    # native Step Subflow; no SPU reference is available at this level.
    step_futures = [
        invoke_step.submit(
            f"{stage_identity}.step-a", stage_identity, stage_invocation_identity,
            pipeline_invocation_identity, stage_flow_run_id, trace_file,
            {"value": f" {stage_identity}-ALPHA "},
        ),
        invoke_step.submit(
            f"{stage_identity}.step-b", stage_identity, stage_invocation_identity,
            pipeline_invocation_identity, stage_flow_run_id, trace_file,
            {"value": f" {stage_identity}-BETA "},
        ),
    ]
    step_results = [future.result() for future in step_futures]
    result = {
        "stageIdentity": stage_identity,
        "stageInvocationIdentity": stage_invocation_identity,
        "stepResultCount": len(step_results),
        "stepResults": [asdict(item) for item in step_results],
    }
    _record(
        trace_file, "completed", "Stage", stage_identity, stage_invocation_identity,
        pipeline_invocation_identity, stage_invocation_identity,
        None, pipeline_invocation_identity, root_flow_run_id,
        {"stepResultCount": len(step_results), "nativeStageFlowRunId": stage_flow_run_id},
    )
    return result


@task(name="invoke-stage-parent-flow", retries=0)
def invoke_stage(
    stage_identity: str,
    stage_invocation_identity: str,
    pipeline_invocation_identity: str,
    root_flow_run_id: str,
    trace_file: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    # Root-level task is a dispatch wrapper only; the Stage remains a native Flow.
    _record(trace_file, "started", "StageDispatch", stage_identity,
            stage_invocation_identity, pipeline_invocation_identity,
            stage_invocation_identity, None, pipeline_invocation_identity,
            root_flow_run_id)
    specialized_stage_flow = stage_parent_flow.with_options(
        name=f"gpwcf-stage-{stage_identity}"
    )
    result = specialized_stage_flow(
        stage_identity, stage_invocation_identity, pipeline_invocation_identity,
        root_flow_run_id, trace_file, payload,
    )
    _record(trace_file, "completed", "StageDispatch", stage_identity,
            stage_invocation_identity, pipeline_invocation_identity,
            stage_invocation_identity, None, pipeline_invocation_identity,
            root_flow_run_id)
    return result


@flow(
    name="gpwcf-pipeline-root-flow",
    task_runner=ThreadPoolTaskRunner(max_workers=4),
)
def pipeline_root_flow(
    pipeline_invocation_identity: str,
    trace_file: str,
    payload_seed: str,
) -> dict[str, Any]:
    root_flow_run_id = _runtime_context()["nativeFlowRunId"]
    _record(
        trace_file, "started", "PipelineRoot", "pipeline-root",
        pipeline_invocation_identity, pipeline_invocation_identity,
    )

    # Root includes/invokes two Stage Parent Flows through native Prefect task
    # dispatch. Prefect creates each Stage as a child Flow Run.
    stage_futures = [
        invoke_stage.submit(
            "STAGE-A", str(uuid4()), pipeline_invocation_identity,
            root_flow_run_id, trace_file, {"value": f"{payload_seed}-A"},
        ),
        invoke_stage.submit(
            "STAGE-B", str(uuid4()), pipeline_invocation_identity,
            root_flow_run_id, trace_file, {"value": f"{payload_seed}-B"},
        ),
    ]
    stage_results = [future.result() for future in stage_futures]
    result = {
        "pipelineInvocationIdentity": pipeline_invocation_identity,
        "stageCount": len(stage_results),
        "stages": stage_results,
    }
    _record(
        trace_file, "completed", "PipelineRoot", "pipeline-root",
        pipeline_invocation_identity, pipeline_invocation_identity,
        details={"stageCount": len(stage_results), "nativeRootFlowRunId": root_flow_run_id},
    )
    return result


@task(name="controlled-failure-probe", retries=0)
def controlled_failure_probe() -> None:
    raise RuntimeError("PHASE-01 controlled failure probe; expected and isolated")


@flow(name="prefect-exception-boundary-probe")
def exception_boundary_probe() -> dict[str, Any]:
    future = controlled_failure_probe.submit()
    try:
        future.result()
    except Exception as exc:
        state = future.state
        return {
            "exceptionType": type(exc).__name__,
            "exceptionMessage": str(exc),
            "prefectTaskRunId": str(getattr(future, "task_run_id", "")),
            "prefectTaskStateName": state.name,
            "prefectTaskStateType": state.type.value,
            "domainStructuredResultProduced": False,
        }
    raise AssertionError("The controlled failure probe unexpectedly completed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, default=Path(__file__).parent / "evidence")
    args = parser.parse_args()

    run_identity = str(uuid4())
    run_root = args.evidence_root / f"run-{run_identity}"
    run_root.mkdir(parents=True, exist_ok=False)
    trace_file = run_root / "native-execution-trace.jsonl"
    result_file = run_root / "pipeline-result.json"

    root_state = pipeline_root_flow(
        run_identity, str(trace_file), "GPWCF-NATIVE-HIERARCHY", return_state=True
    )
    result = root_state.result()
    runtime_observations = {
        "prefectRootState": {"name": root_state.name, "type": root_state.type.value}
    }

    exception_state = exception_boundary_probe(return_state=True)
    exception_result = exception_state.result()
    exception_result["prefectProbeFlowStateName"] = exception_state.name
    exception_result["prefectProbeFlowStateType"] = exception_state.type.value
    (run_root / "exception-probe.json").write_text(
        json.dumps(exception_result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (run_root / "runtime-observations.json").write_text(
        json.dumps(runtime_observations, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    result_file.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "runRoot": str(run_root),
        "traceFile": str(trace_file),
        "resultFile": str(result_file),
        "pipelineResult": result,
        "runtimeObservations": runtime_observations,
        "exceptionProbe": exception_result,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
