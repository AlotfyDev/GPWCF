from __future__ import annotations

import argparse
import json
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4

from prefect import flow, task
from prefect.context import get_run_context
from prefect.deployments import run_deployment
from prefect.task_runners import ThreadPoolTaskRunner
from prefect.client.orchestration import get_client

T = TypeVar("T")
_TRACE_LOCK = threading.Lock()
STAGE_A_DEPLOYMENT = "gpwcf-stage-a/stage-a-worker"
STAGE_B_DEPLOYMENT = "gpwcf-stage-b/stage-b-worker"
EXPECTED_WORKERS = {"gpwcf-stage-worker-01", "gpwcf-stage-worker-02"}
EXPECTED_WORK_POOL = "gpwcf-phase02-stage-qualified-pool"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def runtime_context() -> dict[str, str | None]:
    context = get_run_context()
    flow_run = getattr(context, "flow_run", None)
    task_run = getattr(context, "task_run", None)
    flow_run_id = flow_run.id if flow_run and flow_run.id else None
    # TaskRunContext does not expose FlowRunContext directly. The TaskRun's
    # flow_run_id still identifies the owning native Flow (e.g. the Step Flow
    # that owns each SPU Task).
    if flow_run_id is None and task_run is not None:
        flow_run_id = getattr(task_run, "flow_run_id", None)
    return {
        "nativeFlowRunId": str(flow_run_id) if flow_run_id else None,
        "nativeParentTaskRunId": (
            str(flow_run.parent_task_run_id)
            if flow_run and getattr(flow_run, "parent_task_run_id", None)
            else None
        ),
        "nativeTaskRunId": str(task_run.id) if task_run and task_run.id else None,
        "nativeWorkerName": (
            flow_run.labels.get("prefect.worker.name")
            if flow_run and getattr(flow_run, "labels", None) else None
        ),
        "nativeWorkPoolName": (
            flow_run.labels.get("prefect.work-pool.name")
            if flow_run and getattr(flow_run, "labels", None) else None
        ),
    }


def record(path: str, event: str, component_type: str, identity: str,
           invocation_identity: str, pipeline_invocation_identity: str,
           stage_invocation_identity: str | None = None,
           step_invocation_identity: str | None = None,
           details: dict[str, Any] | None = None) -> None:
    row = {
        "timestampUtc": utc_now(),
        "event": event,
        "componentType": component_type,
        "componentIdentity": identity,
        "componentInvocationIdentity": invocation_identity,
        "pipelineInvocationIdentity": pipeline_invocation_identity,
        "stageInvocationIdentity": stage_invocation_identity,
        "stepInvocationIdentity": step_invocation_identity,
        **runtime_context(),
        "details": details or {},
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Each Stage invocation has its own trace file; the Root trace is written
    # only by the Root process. No cross-process shared append is required.
    with _TRACE_LOCK:
        with target.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


@dataclass(frozen=True)
class SPUExecutionResult(Generic[T]):
    processing_artifact: T | None
    spu_error_occurrences: tuple[dict[str, Any], ...] | None = None
    validator_result: dict[str, Any] | None = None


@dataclass(frozen=True)
class StepExecutionResult(Generic[T]):
    processing_artifact: T | None
    validator_result: dict[str, Any] | None = None
    error_result: dict[str, Any] | None = None
    error_handler_result: dict[str, Any] | None = None


@task(name="deployment-poc-spu-normalize", retries=0)
def spu_normalize(spu_identity: str, spu_invocation_identity: str,
                  step_identity: str, step_invocation_identity: str,
                  stage_identity: str, stage_invocation_identity: str,
                  pipeline_invocation_identity: str, trace_file: str,
                  payload: dict[str, Any]) -> SPUExecutionResult[dict[str, Any]]:
    record(trace_file, "started", "SPU", spu_identity, spu_invocation_identity,
           pipeline_invocation_identity, stage_invocation_identity,
           step_invocation_identity, {"operation": "normalize"})
    time.sleep(0.35)
    result = SPUExecutionResult(
        processing_artifact={"normalized": str(payload["value"]).strip().lower()}
    )
    record(trace_file, "completed", "SPU", spu_identity, spu_invocation_identity,
           pipeline_invocation_identity, stage_invocation_identity,
           step_invocation_identity, {"operation": "normalize"})
    return result


@task(name="deployment-poc-spu-measure", retries=0)
def spu_measure(spu_identity: str, spu_invocation_identity: str,
                step_identity: str, step_invocation_identity: str,
                stage_identity: str, stage_invocation_identity: str,
                pipeline_invocation_identity: str, trace_file: str,
                payload: dict[str, Any]) -> SPUExecutionResult[dict[str, Any]]:
    record(trace_file, "started", "SPU", spu_identity, spu_invocation_identity,
           pipeline_invocation_identity, stage_invocation_identity,
           step_invocation_identity, {"operation": "measure"})
    time.sleep(0.35)
    result = SPUExecutionResult(
        processing_artifact={"characterCount": len(str(payload["value"]))}
    )
    record(trace_file, "completed", "SPU", spu_identity, spu_invocation_identity,
           pipeline_invocation_identity, stage_invocation_identity,
           step_invocation_identity, {"operation": "measure"})
    return result


@flow(name="gpwcf-deployment-step-subflow",
      task_runner=ThreadPoolTaskRunner(max_workers=4))
def step_subflow(step_identity: str, step_invocation_identity: str,
                 stage_identity: str, stage_invocation_identity: str,
                 pipeline_invocation_identity: str, trace_file: str,
                 payload: dict[str, Any]) -> StepExecutionResult[dict[str, Any]]:
    step_run_id = runtime_context()["nativeFlowRunId"]
    record(trace_file, "started", "Step", step_identity, step_invocation_identity,
           pipeline_invocation_identity, stage_invocation_identity,
           step_invocation_identity, {"stageIdentity": stage_identity})
    normalized = spu_normalize.submit(
        f"{step_identity}.normalize", str(uuid4()), step_identity,
        step_invocation_identity, stage_identity, stage_invocation_identity,
        pipeline_invocation_identity, trace_file, payload,
    )
    measured = spu_measure.submit(
        f"{step_identity}.measure", str(uuid4()), step_identity,
        step_invocation_identity, stage_identity, stage_invocation_identity,
        pipeline_invocation_identity, trace_file, payload,
    )
    normalized_result = normalized.result()
    measured_result = measured.result()
    result = StepExecutionResult(processing_artifact={
        "normalization": normalized_result.processing_artifact,
        "measurement": measured_result.processing_artifact,
    })
    record(trace_file, "completed", "Step", step_identity, step_invocation_identity,
           pipeline_invocation_identity, stage_invocation_identity,
           step_invocation_identity,
           {"nativeStepFlowRunId": step_run_id, "spuTaskCount": 2,
            "resultType": "StepExecutionResult"})
    return result


class StepFacade:
    """Stage-facing public Step callable for the deployment qualification fixture."""

    def __init__(self, step_identity: str, step_invocation_identity: str,
                 stage_identity: str, stage_invocation_identity: str,
                 pipeline_invocation_identity: str, trace_file: str) -> None:
        self.identity = step_identity
        self.step_invocation_identity = step_invocation_identity
        self.stage_identity = stage_identity
        self.stage_invocation_identity = stage_invocation_identity
        self.pipeline_invocation_identity = pipeline_invocation_identity
        self.trace_file = trace_file

    def execute(self, payload: dict[str, Any]) -> StepExecutionResult[dict[str, Any]]:
        return step_subflow.with_options(
            name=f"gpwcf-step-{self.identity}"
        )(
            self.identity, self.step_invocation_identity, self.stage_identity,
            self.stage_invocation_identity, self.pipeline_invocation_identity,
            self.trace_file, payload,
        )


@task(name="deployment-poc-invoke-step", retries=0)
def invoke_step(step_identity: str, stage_identity: str,
                stage_invocation_identity: str,
                pipeline_invocation_identity: str, trace_file: str,
                payload: dict[str, Any]) -> StepExecutionResult[dict[str, Any]]:
    step_invocation_identity = str(uuid4())
    record(trace_file, "started", "StepDispatch", step_identity,
           step_invocation_identity, pipeline_invocation_identity,
           stage_invocation_identity, step_invocation_identity,
           {"dispatchTaskRunId": runtime_context()["nativeTaskRunId"]})
    facade = StepFacade(step_identity, step_invocation_identity, stage_identity,
                        stage_invocation_identity, pipeline_invocation_identity,
                        trace_file)
    result = facade.execute(payload)
    record(trace_file, "completed", "StepDispatch", step_identity,
           step_invocation_identity, pipeline_invocation_identity,
           stage_invocation_identity, step_invocation_identity,
           {"dispatchTaskRunId": runtime_context()["nativeTaskRunId"]})
    return result


@flow(name="gpwcf-stage-deployment-flow",
      task_runner=ThreadPoolTaskRunner(max_workers=4),
      persist_result=True)
def stage_parent_flow(stage_identity: str, stage_invocation_identity: str,
                      pipeline_invocation_identity: str, root_flow_run_id: str,
                      root_dispatch_task_run_id: str, trace_file: str,
                      stage_delay_seconds: float = 2.0) -> dict[str, Any]:
    stage_flow_run_id = runtime_context()["nativeFlowRunId"]
    record(trace_file, "started", "Stage", stage_identity,
           stage_invocation_identity, pipeline_invocation_identity,
           stage_invocation_identity, details={
               "rootFlowRunId": root_flow_run_id,
               "rootDispatchTaskRunId": root_dispatch_task_run_id,
               "stageDelaySeconds": stage_delay_seconds,
           })
    # Deterministic work window used only to measure sibling Stage overlap.
    time.sleep(stage_delay_seconds)

    futures = [
        invoke_step.submit(
            f"{stage_identity}.step-a", stage_identity,
            stage_invocation_identity, pipeline_invocation_identity, trace_file,
            {"value": f" {stage_identity}-ALPHA "},
        ),
        invoke_step.submit(
            f"{stage_identity}.step-b", stage_identity,
            stage_invocation_identity, pipeline_invocation_identity, trace_file,
            {"value": f" {stage_identity}-BETA "},
        ),
    ]
    step_results = [future.result() for future in futures]
    result = {
        "stageIdentity": stage_identity,
        "stageInvocationIdentity": stage_invocation_identity,
        "pipelineInvocationIdentity": pipeline_invocation_identity,
        "nativeStageFlowRunId": stage_flow_run_id,
        "rootFlowRunId": root_flow_run_id,
        "stepResultCount": len(step_results),
        "stepResults": [asdict(item) for item in step_results],
    }
    record(trace_file, "completed", "Stage", stage_identity,
           stage_invocation_identity, pipeline_invocation_identity,
           stage_invocation_identity, details={
               "nativeStageFlowRunId": stage_flow_run_id,
               "stepResultCount": len(step_results),
           })
    return result


def deploy_stage_flows(work_pool_name: str) -> dict[str, str]:
    deployments: dict[str, str] = {}
    for stage_identity, flow_name, deployment_name in [
        ("STAGE-A", "gpwcf-stage-a", "stage-a-worker"),
        ("STAGE-B", "gpwcf-stage-b", "stage-b-worker"),
    ]:
        # Prefect 3.9.2 requires deployment code provenance when deploying
        # without a container image. LocalStorage explicitly binds this PoC
        # directory; Process Workers on this same host execute from that path.
        sourced_stage_flow = stage_parent_flow.from_source(
            source=str(Path(__file__).parent),
            entrypoint=f"{Path(__file__).name}:stage_parent_flow",
        )
        specialized = sourced_stage_flow.with_options(name=flow_name)
        deployment_id = specialized.deploy(
            name=deployment_name,
            work_pool_name=work_pool_name,
            build=False,
            push=False,
            paused=False,
            parameters={
                "stage_identity": stage_identity,
                "stage_invocation_identity": "deployment-default-not-used",
                "pipeline_invocation_identity": "deployment-default-not-used",
                "root_flow_run_id": "deployment-default-not-used",
                "root_dispatch_task_run_id": "deployment-default-not-used",
                "trace_file": "deployment-default-not-used",
                "stage_delay_seconds": 2.0,
            },
            tags=["gpwcf", "phase-02", "stage-deployment"],
            print_next_steps=False,
        )
        deployments[f"{stage_identity}"] = str(deployment_id)
    return deployments


@task(name="root-dispatch-deployed-stage", retries=0)
def dispatch_stage(stage_identity: str, deployment_name: str,
                   stage_invocation_identity: str,
                   pipeline_invocation_identity: str, root_flow_run_id: str,
                   root_trace_file: str, stage_trace_file: str,
                   stage_delay_seconds: float) -> dict[str, Any]:
    dispatch_context = runtime_context()
    dispatch_task_run_id = dispatch_context["nativeTaskRunId"]
    record(root_trace_file, "started", "StageDispatch", stage_identity,
           stage_invocation_identity, pipeline_invocation_identity,
           stage_invocation_identity, details={
               "deploymentName": deployment_name,
               "rootDispatchTaskRunId": dispatch_task_run_id,
           })
    flow_run = run_deployment(
        deployment_name,
        parameters={
            "stage_identity": stage_identity,
            "stage_invocation_identity": stage_invocation_identity,
            "pipeline_invocation_identity": pipeline_invocation_identity,
            "root_flow_run_id": root_flow_run_id,
            "root_dispatch_task_run_id": dispatch_task_run_id,
            "trace_file": stage_trace_file,
            "stage_delay_seconds": stage_delay_seconds,
        },
        flow_run_name=f"{stage_identity}-{stage_invocation_identity[-8:]}",
        timeout=None,
        poll_interval=0.2,
        as_subflow=True,
        idempotency_key=f"{pipeline_invocation_identity}:{stage_invocation_identity}",
    )
    if flow_run.state is None:
        raise RuntimeError(f"Deployment Flow Run {flow_run.id} has no final state")
    if not flow_run.state.is_completed():
        raise RuntimeError(
            f"Deployment Flow Run {flow_run.id} ended in {flow_run.state.name}"
        )
    domain_result = flow_run.state.result()
    output = {
        "stageIdentity": stage_identity,
        "stageInvocationIdentity": stage_invocation_identity,
        "deploymentName": deployment_name,
        "deploymentFlowRunId": str(flow_run.id),
        "deploymentParentTaskRunId": (
            str(flow_run.parent_task_run_id) if flow_run.parent_task_run_id else None
        ),
        "rootDispatchTaskRunId": dispatch_task_run_id,
        "prefectStateName": flow_run.state.name,
        "prefectStateType": flow_run.state.type.value,
        "domainResult": domain_result,
    }
    record(root_trace_file, "completed", "StageDispatch", stage_identity,
           stage_invocation_identity, pipeline_invocation_identity,
           stage_invocation_identity, details=output)
    return output


@flow(name="gpwcf-deployment-pipeline-root",
      task_runner=ThreadPoolTaskRunner(max_workers=4))
def pipeline_root_flow(pipeline_invocation_identity: str,
                       evidence_run_root: str,
                       stage_delay_seconds: float = 2.0) -> dict[str, Any]:
    root_flow_run_id = runtime_context()["nativeFlowRunId"]
    root_trace = str(Path(evidence_run_root) / "root-trace.jsonl")
    record(root_trace, "started", "PipelineRoot", "pipeline-root",
           pipeline_invocation_identity, pipeline_invocation_identity,
           details={"nativeRootFlowRunId": root_flow_run_id})

    dispatches = [
        dispatch_stage.submit(
            "STAGE-A", STAGE_A_DEPLOYMENT, str(uuid4()),
            pipeline_invocation_identity, root_flow_run_id, root_trace,
            str(Path(evidence_run_root) / "stage-a-trace.jsonl"),
            stage_delay_seconds,
        ),
        dispatch_stage.submit(
            "STAGE-B", STAGE_B_DEPLOYMENT, str(uuid4()),
            pipeline_invocation_identity, root_flow_run_id, root_trace,
            str(Path(evidence_run_root) / "stage-b-trace.jsonl"),
            stage_delay_seconds,
        ),
    ]
    stage_results = [future.result() for future in dispatches]
    result = {
        "pipelineInvocationIdentity": pipeline_invocation_identity,
        "nativeRootFlowRunId": root_flow_run_id,
        "stageCount": len(stage_results),
        "stages": stage_results,
    }
    record(root_trace, "completed", "PipelineRoot", "pipeline-root",
           pipeline_invocation_identity, pipeline_invocation_identity,
           details={"stageCount": len(stage_results)})
    return result


def task_inputs_include_parent(task_inputs: Any, expected_parent_id: str) -> bool:
    if not isinstance(task_inputs, dict):
        return False
    parents = task_inputs.get("__parents__", [])
    for parent in parents:
        value = getattr(parent, "id", None)
        if value is None and isinstance(parent, dict):
            value = parent.get("id")
        if value is not None and str(value) == expected_parent_id:
            return True
    return False


def verify_parent_task_links(stage_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    with get_client(sync_client=True) as client:
        for stage in stage_results:
            parent_id = stage["deploymentParentTaskRunId"]
            dispatch_id = stage["rootDispatchTaskRunId"]
            if not parent_id:
                observations.append({
                    "stageIdentity": stage["stageIdentity"],
                    "passed": False,
                    "reason": "Deployment Flow Run has no parent_task_run_id",
                })
                continue
            parent_task = client.read_task_run(UUID(parent_id))
            links_dispatch = task_inputs_include_parent(
                parent_task.task_inputs, dispatch_id
            )
            observations.append({
                "stageIdentity": stage["stageIdentity"],
                "deploymentParentTaskRunId": parent_id,
                "rootDispatchTaskRunId": dispatch_id,
                "syntheticParentTaskInputs": str(parent_task.task_inputs),
                "syntheticParentLinksRootDispatchTask": links_dispatch,
                "passed": links_dispatch,
            })
    return observations


def verify_stage_native_correlations(run_root: Path, root_flow_run_id: str,
                                     pipeline_invocation_identity: str,
                                     stage_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    with get_client(sync_client=True) as client:
        for stage in stage_results:
            stage_key = stage["stageIdentity"].lower()
            trace_path = run_root / f"{stage_key}-trace.jsonl"
            rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
            stage_rows = [r for r in rows if r["componentType"] == "Stage"]
            stage_started = next(r for r in stage_rows if r["event"] == "started")
            stage_completed = next(r for r in stage_rows if r["event"] == "completed")
            expected_flow_id = stage["deploymentFlowRunId"]
            expected_parent_id = stage["deploymentParentTaskRunId"]
            domain = stage["domainResult"]
            stage_checks = {
                "stageFlowRunIdentityMatchesDeploymentRun": (
                    stage_started["nativeFlowRunId"] == expected_flow_id
                    and stage_completed["nativeFlowRunId"] == expected_flow_id
                    and domain["nativeStageFlowRunId"] == expected_flow_id
                ),
                "stageNativeParentMatchesDeploymentParentTask": (
                    bool(expected_parent_id)
                    and stage_started["nativeParentTaskRunId"] == expected_parent_id
                    and stage_completed["nativeParentTaskRunId"] == expected_parent_id
                ),
                "stageRunsOnExpectedProcessWorkerPool": (
                    stage_started.get("nativeWorkerName") in EXPECTED_WORKERS
                    and stage_started.get("nativeWorkPoolName") == EXPECTED_WORK_POOL
                ),
                "rootAndDomainInvocationCorrelationPreserved": (
                    domain["rootFlowRunId"] == root_flow_run_id
                    and domain["pipelineInvocationIdentity"] == pipeline_invocation_identity
                    and domain["stageIdentity"] == stage["stageIdentity"]
                    and domain["stageInvocationIdentity"] == stage["stageInvocationIdentity"]
                    and stage_started["details"]["rootFlowRunId"] == root_flow_run_id
                    and stage_started["details"]["rootDispatchTaskRunId"] == stage["rootDispatchTaskRunId"]
                ),
            }
            step_starts = [r for r in rows if r["componentType"] == "Step" and r["event"] == "started"]
            step_dispatches = [r for r in rows if r["componentType"] == "StepDispatch" and r["event"] == "started"]
            spu_starts = [r for r in rows if r["componentType"] == "SPU" and r["event"] == "started"]
            step_parent_observations = []
            spu_nesting_checks = []
            for step in step_starts:
                matching_dispatch = next((d for d in step_dispatches
                    if d["stepInvocationIdentity"] == step["stepInvocationIdentity"]), None)
                parent_id = step["nativeParentTaskRunId"]
                linked = False
                if matching_dispatch and parent_id:
                    synthetic_parent = client.read_task_run(UUID(parent_id))
                    linked = task_inputs_include_parent(
                        synthetic_parent.task_inputs, matching_dispatch["nativeTaskRunId"]
                    )
                step_parent_observations.append({
                    "stepIdentity": step["componentIdentity"],
                    "stepFlowRunId": step["nativeFlowRunId"],
                    "syntheticParentTaskRunId": parent_id,
                    "stepDispatchTaskRunId": matching_dispatch["nativeTaskRunId"] if matching_dispatch else None,
                    "syntheticParentLinksStepDispatchTask": linked,
                })
                nested_spus = [spu for spu in spu_starts
                    if spu["stepInvocationIdentity"] == step["stepInvocationIdentity"]]
                spu_nesting_checks.append(
                    len(nested_spus) == 2
                    and all(spu["nativeFlowRunId"] == step["nativeFlowRunId"] for spu in nested_spus)
                    and all(bool(spu["nativeTaskRunId"]) for spu in nested_spus)
                )
            stage_checks["stepParentCorrelationPreserved"] = (
                len(step_starts) == 2 and len(step_dispatches) == 2
                and all(item["syntheticParentLinksStepDispatchTask"] for item in step_parent_observations)
            )
            stage_checks["stepBoundaryAndSpuNestingPreserved"] = (
                len(step_starts) == 2 and len(step_dispatches) == 2
                and len(spu_starts) == 4 and all(spu_nesting_checks)
            )
            observations.append({
                "stageIdentity": stage["stageIdentity"],
                "deploymentFlowRunId": expected_flow_id,
                "deploymentParentTaskRunId": expected_parent_id,
                "nativeWorkerName": stage_started.get("nativeWorkerName"),
                "nativeWorkPoolName": stage_started.get("nativeWorkPoolName"),
                "checks": stage_checks,
                "stepParentObservations": step_parent_observations,
                "passed": all(stage_checks.values()),
            })
    return observations


def calculate_stage_overlap(run_root: Path) -> dict[str, Any]:
    intervals = {}
    for stage_identity in ("STAGE-A", "STAGE-B"):
        trace_path = run_root / f"{stage_identity.lower()}-trace.jsonl"
        rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
        started = next(r for r in rows if r["componentType"] == "Stage" and r["event"] == "started")
        completed = next(r for r in rows if r["componentType"] == "Stage" and r["event"] == "completed")
        intervals[stage_identity] = (
            datetime.fromisoformat(started["timestampUtc"]),
            datetime.fromisoformat(completed["timestampUtc"]),
        )
    overlap = max(0.0, (min(intervals["STAGE-A"][1], intervals["STAGE-B"][1])
                         - max(intervals["STAGE-A"][0], intervals["STAGE-B"][0])).total_seconds())
    return {"siblingStageFlowsOverlap": overlap > 0,
            "overlapSeconds": overlap,
            "stageIntervals": {key: [value[0].isoformat(), value[1].isoformat()]
                               for key, value in intervals.items()}}


def verify_worker_topology(work_pool_name: str) -> dict[str, Any]:
    with get_client(sync_client=True) as client:
        workers = client.read_workers_for_work_pool(work_pool_name)
    online = sorted(w.name for w in workers if str(w.status).upper().endswith("ONLINE"))
    expected = sorted(EXPECTED_WORKERS)
    if online != expected:
        raise RuntimeError(
            f"Expected exactly these two ONLINE workers for qualification: {expected}; found: {online}"
        )
    return {"workPool": work_pool_name, "onlineWorkers": online,
            "workerCount": len(online), "exactExpectedWorkerSet": True}


def run_one(evidence_root: Path, stage_delay_seconds: float) -> dict[str, Any]:
    pipeline_invocation_identity = str(uuid4())
    run_root = evidence_root / f"run-{pipeline_invocation_identity}"
    run_root.mkdir(parents=True, exist_ok=False)
    state = pipeline_root_flow(
        pipeline_invocation_identity,
        str(run_root),
        stage_delay_seconds,
        return_state=True,
    )
    if not state.is_completed():
        raise RuntimeError(f"Root Flow ended in {state.name}")
    result = state.result()
    parent_links = verify_parent_task_links(result["stages"])
    native_correlations = verify_stage_native_correlations(
        run_root, result["nativeRootFlowRunId"], pipeline_invocation_identity,
        result["stages"],
    )
    concurrency = calculate_stage_overlap(run_root)
    stage_worker_names = {item["nativeWorkerName"] for item in native_correlations}
    distinct_worker_assignment = stage_worker_names == EXPECTED_WORKERS
    for item in native_correlations:
        item["checks"]["siblingStagesAssignedToDistinctWorkers"] = distinct_worker_assignment
        item["passed"] = all(item["checks"].values())
    summary = {
        "runId": run_root.name,
        "pipelineInvocationIdentity": pipeline_invocation_identity,
        "rootFlowRunId": result["nativeRootFlowRunId"],
        "stageResults": result["stages"],
        "parentLinkObservations": parent_links,
        "nativeHierarchyCorrelations": native_correlations,
        "concurrency": concurrency,
    }
    if not all(item["passed"] for item in parent_links + native_correlations):
        raise RuntimeError("Deployment hierarchy identity/parent correlation validation failed")
    (run_root / "pipeline-result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (run_root / "parent-link-observations.json").write_text(
        json.dumps(parent_links, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (run_root / "native-hierarchy-correlations.json").write_text(
        json.dumps(native_correlations, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (run_root / "concurrency-observation.json").write_text(
        json.dumps(concurrency, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (run_root / "qualification-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deploy", action="store_true")
    parser.add_argument("--work-pool", default="gpwcf-phase02-stage-qualified-pool")
    parser.add_argument("--evidence-root", type=Path, default=Path(__file__).parent / "evidence")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--stage-delay-seconds", type=float, default=2.0)
    args = parser.parse_args()

    if args.deploy:
        print(json.dumps({
            "workPool": args.work_pool,
            "deployments": deploy_stage_flows(args.work_pool),
        }, indent=2))
        return 0

    if args.runs < 1:
        raise ValueError("--runs must be >= 1")
    worker_topology = verify_worker_topology(args.work_pool)
    summaries = [
        run_one(args.evidence_root, args.stage_delay_seconds)
        for _ in range(args.runs)
    ]
    aggregate = {
        "runCount": len(summaries),
        "workerTopology": worker_topology,
        "runs": summaries,
        "parentLinkPassCount": sum(
            all(item["passed"] for item in s["parentLinkObservations"])
            for s in summaries
        ),
        "nativeHierarchyPassCount": sum(
            all(item["passed"] for item in s["nativeHierarchyCorrelations"])
            for s in summaries
        ),
        "siblingStageOverlapPassCount": sum(
            s["concurrency"]["siblingStageFlowsOverlap"] for s in summaries
        ),
    }
    args.evidence_root.mkdir(parents=True, exist_ok=True)
    (args.evidence_root / "cross-run-summary.json").write_text(
        json.dumps(aggregate, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(aggregate, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
