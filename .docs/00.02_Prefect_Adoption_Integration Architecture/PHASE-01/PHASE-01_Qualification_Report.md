# PHASE-01 — Prefect Native Capability Qualification

**Status:** Native hierarchy boundaries qualified; deterministic sibling-Flow concurrency remains open.  
**Runtime:** Prefect 3.9.2 / CPython 3.15.1 / Windows x64  
**Execution profile:** Local Prefect API server with one API-server worker and SQLite state store at C:\poc\GPWCF\prefect-home-sqlite (outside the repository); UI and scheduler disabled. Root, Stage and Step Flows each use ThreadPoolTaskRunner(max_workers=4). The API-server worker count and client-side task-runner thread count are separate settings.

## 1. Objective and qualification boundary

PHASE-01 proves that the selected Prefect version can execute the intended hierarchy using native Flow, child Flow/Subflow and Task constructs:

Pipeline Root -> Stage Parent Flow -> Step Subflow -> SPU Tasks.

The GPWCF project currently has design contracts but no executable production Stage/Step/SPU classes. The PoC therefore uses explicitly labelled contract-shaped fixtures. This is a runtime capability qualification, not production GPWCF binding and not full THIM conformance.

## 2. Implemented native topology

1. The Pipeline Root is a native Prefect Flow.
2. The Root submits two narrow dispatch Tasks. Each dispatch invokes a distinct Stage-specific Flow object created with Flow.with_options(name=...).
3. Each Stage Parent Flow submits Step dispatch Tasks.
4. Each Step dispatch invokes StepFacade.execute(input), the Stage-facing public Step callable in this fixture.
5. StepFacade invokes a Step-specific native Prefect Flow/Subflow.
6. Only the Step Subflow calls the SPU Tasks.
7. Each Step submits two SPU Tasks, joins both futures, and assembles a StepExecutionResult from two separate SPUExecutionResult values.

The dispatch Tasks exist because Prefect 3.9.2 Flow objects do not expose submit() in the inspected API, whereas Task objects do. They are narrow native dispatch mechanics, not GPWCF domain components, and do not own business or composition semantics.

The Step boundary is preserved: Stage code does not call or reference the SPU Task callables. SPU invocation and Step result assembly remain inside the Step Subflow.

## 3. Supported local server profile

The supported SQLite-backed profile is:

- Prefect API server: one server worker
- Database: local SQLite at C:\poc\GPWCF\prefect-home-sqlite, outside the repository
- API: 127.0.0.1:4200/api
- UI and scheduler: disabled
- Root/Stage/Step task runner: ThreadPoolTaskRunner(max_workers=4)

Prefect explicitly rejects API-server multi-worker mode when SQLite is selected. Multi-worker API-server mode requires PostgreSQL. The attempted four-worker server startup failed with that explicit message and was not used as accepted evidence. The runbook defaults to one API-server worker and rejects a higher worker count for this SQLite profile.

The four-thread ThreadPoolTaskRunner is a separate client-side execution setting; it does not mean that the API server has four workers.

## 4. Primary execution evidence

Four repeated runs used the same supported SQLite single-worker API-server profile:

| Run | Root Flow | Stage Flow overlap | Step sibling overlap | SPU fan-out |
|---|---|---|---|---|
| run-5f8ffd7d-ec75-4380-8d25-cf8054a2dde0 | COMPLETED | No | 0 of 2 Stage pairs | 4/4 Steps |
| run-c52c64f9-44bf-4cf5-85eb-85f6834d1cb9 | COMPLETED | Yes (5.472557 s) | 0 of 2 Stage pairs | 4/4 Steps |
| run-0f24960a-b7b0-4285-825f-bc0f18950c67 | COMPLETED | Yes (3.244401 s) | 0 of 2 Stage pairs | 4/4 Steps |
| run-bc923468-7a5e-4c62-8cc8-913b0ddd51ec | COMPLETED | Yes (6.489385 s) | 0 of 2 Stage pairs | 4/4 Steps |

Across the four runs:

- Native hierarchy counts were stable: 1 Root Flow, 2 Stage Parent Flows, 4 Step Subflows and 8 SPU Task Runs per run.
- Root-to-Stage sibling Flow overlap occurred in 3/4 runs. It is **not a deterministic guarantee** in this local profile.
- Stage-to-Step sibling Subflow overlap occurred in 0/8 Stage sibling pairs. They were serialized in all eight observed pairs.
- Step-internal SPU Task fan-out/fan-in overlapped in 16/16 Step invocations.
- Root Flow completed in 4/4 runs.

The four accepted run IDs and their machine-readable summaries are listed in PHASE-01_Repeatability_Evidence.json.

## 5. Native hierarchy and correlation

All four runs recorded native Flow and Task execution records with separate GPWCF-domain correlation fields:

- Each Stage Flow Run has a native parent_task_run_id and explicit Root Flow Run correlation.
- Each Step Flow Run has a native parent_task_run_id and explicit owning Stage Flow Run correlation.
- Each SPU Task Run has a unique native Task Run ID and explicit owning Step Flow Run correlation.
- GPWCF domain identities/invocation identities remain separate from Prefect Flow Run IDs and Task Run IDs.

The Stage dispatch Tasks are submitted independently, but their nested Stage Flow executions do not overlap consistently. Dispatch-task submission must not be mistaken for child-Flow concurrency.

## 6. Concurrency qualification and consequence

### Root -> Stage

The Root can invoke multiple native Stage Parent Flows, but the two child Stage Flow runs overlapped in only three of four repeated executions. The remaining run serialized them.

Therefore, the tested local direct-subflow pattern does not yet provide a deterministic guarantee for independent Generator Stages that require parallel execution. This is a material open item for any Generator branch whose correctness/performance depends on parallel Stage execution.

### Stage -> Step

Sibling Step Subflow runs were serialized in all eight Stage sibling pairs across the four runs. Treat sibling Step Subflows as sequential in this qualified local profile.

The generic Step Composition contract does not require every Stage to execute sibling Steps concurrently. The actual Generator Step decomposition must be established before deciding whether this limitation affects a given Stage.

### Step -> SPU

Both SPU Tasks overlapped within every Step in all four runs: 16/16 Step invocations. Task fan-out/fan-in inside the Step boundary is qualified for this local profile.

## 7. Result, state and exception separation

- SPUExecutionResult and StepExecutionResult are separate contract-shaped dataclasses.
- StepExecutionResult retains processing_artifact, validator_result, error_result and error_handler_result as independent fields.
- pipeline-result.json contains only the domain-facing pipeline result.
- runtime-observations.json contains Prefect Root Flow state.
- exception-probe.json contains the isolated controlled failure observation.
- In the controlled probe, the Task raised RuntimeError and entered Prefect FAILED. The probe Flow caught the exception and completed. No GPWCF domain structured result was invented from Prefect State.

The probe demonstrates the Prefect operational exception/state boundary only. It does not define the production GPWCF exception-to-result mapping.

## 8. Acceptance results

The machine-readable acceptance matrix is PHASE-01_Acceptance_Results.json.

| Area | Result |
|---|---|
| Native Root / Stage / Step / SPU hierarchy | **PASS** |
| Parent-child correlation and identity separation | **PASS** |
| Step public boundary preserved | **PASS** |
| Typed results preserved and separate from Prefect State | **PASS** |
| Deterministic sibling Stage Flow concurrency | **OPEN — observed in 3/4 runs only** |
| Sibling Step Subflow concurrency | **OPEN — serialized in 8/8 pairs** |
| Step-internal SPU Task fan-out/fan-in | **PASS — 16/16 Step invocations** |
| Controlled Prefect failure/state boundary | **PASS for isolated probe** |
| Production GPWCF runtime-class binding | **Not in this phase** |

**PHASE-01 disposition:** The native hierarchy structure, typed result boundaries and Step-internal SPU task fan-out are qualified. Sibling Flow concurrency at both Root-to-Stage and Stage-to-Step levels is not deterministic in the tested local profile. PHASE-01 is not a sibling-Flow concurrency sign-off or production integration sign-off.

## 9. Required follow-up before relying on parallel Stages

Qualify an alternative Prefect-native execution profile for sibling Stage Flows (for example, a worker/deployment-backed Flow invocation) and verify that it preserves:

- Stage Flow identity and callable boundary
- Root-to-Stage invocation and parent correlation
- Input/context/result propagation
- Completion/failure observation and lifecycle settlement
- The distinction between Prefect operational state and GPWCF domain results

Do not adopt a deployment-based pattern merely to obtain concurrency unless the required hierarchy and parent/child semantics remain valid. If a multi-worker API-server profile is considered, it requires PostgreSQL rather than SQLite and must undergo its own dependency/operations qualification.

The same qualification rule applies to sibling Step Subflows only where a concrete Step Composition requires parallelism.

## 10. Explicitly not tested

- Binding real GPWCF production Stage/Step/SPU classes
- Generator-specific Step/SPU decomposition across STG-01 through STG-13
- Supporting Unit binding
- Domain-specific error-to-result conversion and recovery
- Cancellation, timeout, retry, replay, idempotency and safe release
- Process-tree termination
- Persistence restart/recovery
- Large artifact storage/custody and cross-process payload transfer
- Full Generator end-to-end integration

## 11. Files and evidence

PoC source and run scripts:

.poc/Prefect_Native_Hierarchy_Qualification/

Primary evidence runs:

- evidence/run-5f8ffd7d-ec75-4380-8d25-cf8054a2dde0/
- evidence/run-c52c64f9-44bf-4cf5-85eb-85f6834d1cb9/
- evidence/run-0f24960a-b7b0-4285-825f-bc0f18950c67/
- evidence/run-bc923468-7a5e-4c62-8cc8-913b0ddd51ec/

Decision: PHASE-01_Topology_Decision_Record.json  
Acceptance matrix: PHASE-01_Acceptance_Results.json  
Repeatability: PHASE-01_Repeatability_Evidence.json  
Open questions: PHASE-01_Open_Integration_Questions.json

No production GPWCF source file or specialized contract was modified.
