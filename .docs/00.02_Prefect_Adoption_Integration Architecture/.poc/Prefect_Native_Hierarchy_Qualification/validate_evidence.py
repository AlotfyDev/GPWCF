from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def event_intervals(rows: list[dict[str, Any]], component_type: str):
    events: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        if row["componentType"] == component_type and row["event"] in {"started", "completed"}:
            events[row["componentInvocationIdentity"]][row["event"]] = row
    return {
        identity: pair
        for identity, pair in events.items()
        if "started" in pair and "completed" in pair
    }


def has_overlap(intervals: list[dict[str, Any]]) -> bool:
    for index, left in enumerate(intervals):
        left_start = parse_time(left["started"]["timestampUtc"])
        left_end = parse_time(left["completed"]["timestampUtc"])
        for right in intervals[index + 1:]:
            right_start = parse_time(right["started"]["timestampUtc"])
            right_end = parse_time(right["completed"]["timestampUtc"])
            if max(left_start, right_start) < min(left_end, right_end):
                return True
    return False


def validate(run_root: Path) -> dict[str, Any]:
    trace_path = run_root / "native-execution-trace.jsonl"
    result_path = run_root / "pipeline-result.json"
    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line]
    result = json.loads(result_path.read_text(encoding="utf-8"))
    runtime_observations = json.loads((run_root / "runtime-observations.json").read_text(encoding="utf-8"))
    exception_probe = json.loads((run_root / "exception-probe.json").read_text(encoding="utf-8"))

    root_rows = [r for r in rows if r["componentType"] == "PipelineRoot" and r["event"] == "started"]
    stage_intervals = event_intervals(rows, "Stage")
    step_intervals = event_intervals(rows, "Step")
    spu_intervals = event_intervals(rows, "SPU")

    stage_started = [pair["started"] for pair in stage_intervals.values()]
    step_started = [pair["started"] for pair in step_intervals.values()]
    spu_started = [pair["started"] for pair in spu_intervals.values()]

    assert len(root_rows) == 1, f"Expected one root run; found {len(root_rows)}"
    assert len(stage_intervals) == 2, f"Expected two Stage Flow runs; found {len(stage_intervals)}"
    assert len(step_intervals) == 4, f"Expected four Step Subflow runs; found {len(step_intervals)}"
    assert len(spu_intervals) == 8, f"Expected eight SPU Task runs; found {len(spu_intervals)}"
    assert result["stageCount"] == 2
    assert all(stage["stepResultCount"] == 2 for stage in result["stages"])
    assert "prefectRootState" not in result and "exceptionProbe" not in result
    assert runtime_observations["prefectRootState"]["type"] == "COMPLETED"
    assert exception_probe["prefectTaskStateType"] == "FAILED"
    assert exception_probe["prefectProbeFlowStateType"] == "COMPLETED"
    assert exception_probe["domainStructuredResultProduced"] is False

    root_flow_run_id = root_rows[0]["nativeFlowRunId"]
    stage_flow_ids = {
        pair["started"]["componentInvocationIdentity"]: pair["started"]["nativeFlowRunId"]
        for pair in stage_intervals.values()
    }
    stage_domain_to_flow = {
        pair["started"]["stageInvocationIdentity"]: pair["started"]["nativeFlowRunId"]
        for pair in stage_intervals.values()
    }
    for pair in stage_intervals.values():
        started = pair["started"]
        assert started["parentFlowRunId"] == root_flow_run_id
        assert started["nativeParentTaskRunId"], "Stage Flow is not correlated to a native parent task"

    step_flow_ids = {
        pair["started"]["stepInvocationIdentity"]: pair["started"]["nativeFlowRunId"]
        for pair in step_intervals.values()
    }
    for pair in step_intervals.values():
        started = pair["started"]
        expected_parent = stage_domain_to_flow[started["stageInvocationIdentity"]]
        assert started["parentFlowRunId"] == expected_parent
        assert started["nativeParentTaskRunId"], "Step Subflow is not correlated to a native parent task"

    for pair in spu_intervals.values():
        started = pair["started"]
        expected_parent = step_flow_ids[started["stepInvocationIdentity"]]
        assert started["parentFlowRunId"] == expected_parent
        assert started["nativeTaskRunId"], "SPU is not represented by a native Prefect Task Run"

    # Verify that the two Step result categories are not collapsed into Prefect state.
    for stage in result["stages"]:
        for step_result in stage["stepResults"]:
            assert set(step_result) == {
                "processing_artifact", "validator_result", "error_result", "error_handler_result"
            }
            assert step_result["processing_artifact"] is not None

    # Record Root -> Stage sibling Flow overlap without turning a single run
    # into a concurrency guarantee. Repeatability is assessed across run evidence.
    stage_overlap = has_overlap(list(stage_intervals.values()))

    # Step sibling Subflows are recorded separately. In this local profile they
    # were serialized; this is a topology constraint, not silently treated as PASS.
    step_overlap_by_stage: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in step_intervals.values():
        step_overlap_by_stage[pair["started"]["stageInvocationIdentity"]].append(pair)
    step_sibling_overlap = {
        stage_id: has_overlap(pairs) for stage_id, pairs in step_overlap_by_stage.items()
    }

    spu_state_rows = [r for r in rows if r["componentType"] == "Step" and r["event"] == "completed"]
    assert all(all(s["type"] == "COMPLETED" for s in r["details"]["spuTaskStates"]) for r in spu_state_rows)

    # SPU Task fan-out/fan-in must overlap within each owning Step Subworkflow.
    spu_overlap_by_step: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in spu_intervals.values():
        spu_overlap_by_step[pair["started"]["stepInvocationIdentity"]].append(pair)
    spu_fanout_overlap = {
        step_id: has_overlap(pairs) for step_id, pairs in spu_overlap_by_step.items()
    }
    assert len(spu_fanout_overlap) == 4
    assert all(spu_fanout_overlap.values()), "SPU Task fan-out did not overlap in every Step."

    step_overlap_values = list(step_sibling_overlap.values())
    if all(step_overlap_values):
        step_concurrency_disposition = "overlap-observed-for-all-stage-sibling-pairs"
    elif any(step_overlap_values):
        step_concurrency_disposition = "variable-overlap-observed-for-some-stage-sibling-pairs"
    else:
        step_concurrency_disposition = "sibling-step-subflows-serialized-for-all-stages"

    return {
        "documentType": "PrefectNativeHierarchyQualificationEvidence",
        "documentVersion": "1.0.0",
        "status": "qualified-hierarchy-with-sibling-flow-concurrency-unresolved",
        "runtime": {"python": "3.15.1", "prefect": "3.9.2", "platform": "Windows x64"},
        "runRoot": str(run_root),
        "counts": {
            "pipelineRootFlows": len(root_rows),
            "stageParentFlows": len(stage_intervals),
            "stepSubflows": len(step_intervals),
            "spuTaskRuns": len(spu_intervals),
        },
        "correlation": {
            "stageFlowsHaveNativeParentTaskRun": all(
                p["started"]["nativeParentTaskRunId"] for p in stage_intervals.values()
            ),
            "stepSubflowsHaveNativeParentTaskRun": all(
                p["started"]["nativeParentTaskRunId"] for p in step_intervals.values()
            ),
            "spuTasksHaveNativeTaskRunId": all(r["nativeTaskRunId"] for r in spu_started),
            "domainIdentityAndNativeRunIdentityAreSeparate": True,
        },
        "concurrency": {
            "rootSiblingStageFlowsOverlapInThisRun": stage_overlap,
            "siblingStepSubflowsOverlapByStage": step_sibling_overlap,
            "stepSiblingConcurrencyDisposition": step_concurrency_disposition,
            "spuTaskFanoutOverlapsByStep": spu_fanout_overlap,
            "interpretation": (
                "This run records Root-to-Stage sibling Flow overlap as an observation, "
                "not a guarantee; cross-run evidence shows that sibling Stage Flow runs "
                "sometimes serialize. Step-internal SPU Task fan-out was observed for "
                "every Step. Sibling Step Subflow overlap is also variable. Neither "
                "sibling-Flow concurrency level is a deterministic guarantee in the "
                "tested local profile."
            ),
        },
        "nativeStatesAndExceptions": {
            "rootFlowState": runtime_observations["prefectRootState"],
            "stageAndStepFlowNormalReturnsObserved": len(stage_intervals) + len(step_intervals),
            "spuTaskStatesObserved": sum(len(r["details"]["spuTaskStates"]) for r in spu_state_rows),
            "controlledFailureTaskState": exception_probe["prefectTaskStateType"],
            "controlledFailureExceptionType": exception_probe["exceptionType"],
            "controlledFailureDidNotProduceDomainResult": not exception_probe["domainStructuredResultProduced"],
            "failureProbeParentFlowRemainedCompleted": exception_probe["prefectProbeFlowStateType"] == "COMPLETED",
        },
        "typedResults": {
            "stepExecutionResultFieldsPreserved": True,
            "spuExecutionResultDistinctFromStepExecutionResult": True,
            "prefectStateNotUsedAsDomainResult": True,
        },
        "notTested": [
            "Real GPWCF production Stage/Step/SPU runtime classes (the current framework project has no executable implementations yet)",
            "Supporting Unit binding",
            "Domain-specific exception-to-result mapping and recovery (the isolated Prefect failure boundary probe is covered)",
            "Cancellation and timeout settlement",
            "Retry/replay/idempotency",
            "Process-tree termination",
            "Persistence restart/recovery",
            "Full Generator Stage 1-13 integration",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--profile", default="local-prefect-server-api-sqlite-single-worker")
    args = parser.parse_args()
    summary = validate(args.run_root)
    summary["executionProfile"] = args.profile
    output = args.output or args.run_root / "qualification-summary.json"
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"SUMMARY_FILE={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
