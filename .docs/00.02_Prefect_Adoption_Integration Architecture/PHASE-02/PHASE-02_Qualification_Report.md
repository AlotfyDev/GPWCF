# PHASE-02 — Prefect Deployment-Backed Stage Invocation Qualification

**Disposition:** Qualified for the tested same-host, two-Process-Worker profile.  
**Production integration:** Not yet qualified.  
**Runtime:** Prefect 3.9.2 / CPython 3.15.1 / Windows x64  
**Evidence:** Five repeated Root invocations; all acceptance checks passed.

## 1. Objective

This phase tests a separate Prefect execution profile from the direct native-Subflow profile qualified in PHASE-01.

The question is whether a Pipeline Root can invoke Stage Parent Flows through Prefect Deployments and Process Workers while retaining:

1. Native Stage Flow Run identity and explicit Stage domain identity.
2. A verifiable Root-to-Stage parent/child correlation.
3. Stage result retrieval at the Root boundary.
4. The existing Stage → Step Subflow → SPU Task hierarchy.
5. Repeatable overlap of sibling Stage Flow Run execution.

The PoC uses contract-shaped fixtures only. It does not bind production GPWCF classes or Generator stages.

## 2. Qualified execution profile

| Setting | Qualified value |
|---|---|
| OS | Windows x64 |
| Python | CPython 3.15.1 x64 |
| Prefect | 3.9.2 |
| Prefect API | http://127.0.0.1:4210/api |
| API server workers | 1 |
| API database | SQLite |
| Work pool | gpwcf-phase02-stage-qualified-pool |
| Work pool type | Process |
| Worker instances | gpwcf-stage-worker-01, gpwcf-stage-worker-02 |
| Per-worker flow-run limit | 1 |
| Stage deployments | gpwcf-stage-a/stage-a-worker, gpwcf-stage-b/stage-b-worker |
| Stage test delay | 10 seconds |

The API-server worker count and Process Worker instance count are different controls. The tested profile uses one SQLite-compatible API-server worker and two independent Process Worker instances.

The Root verifies that the work pool has exactly the two expected ONLINE workers before starting the repeated run batch. Each Stage Flow Run also records its native Prefect worker name. The two sibling Stages were assigned to different worker instances in every accepted run.

## 3. Native deployment topology

The executed topology is:

Pipeline Root Flow
→ Root dispatch_stage Task
→ run_deployment(..., as_subflow=True)
→ Prefect-generated deployment invocation Task
→ Stage Deployment Flow Run
→ Stage invoke_step Tasks
→ Prefect-generated child-subflow Tasks
→ Step Subflow Flow Runs
→ SPU Task Runs

The generated Prefect Tasks are runtime invocation/relationship nodes. They are not new GPWCF semantic components and do not own Stage Composition or Step Composition.

### 3.1 Root → Stage parent/child correlation

A significant Prefect 3.9.2 behavior was established experimentally:

run_deployment(..., as_subflow=True) does not make the Stage Deployment Flow Run a direct child of the user-defined Root dispatch Task Run.

Prefect creates an intermediate synthetic Task Run for the deployment invocation. The Stage Flow Run's native parent_task_run_id points to that synthetic Task Run.

The PoC verifies both edges:

- StageFlowRun.parent_task_run_id equals deploymentSyntheticTaskRun.id.
- deploymentSyntheticTaskRun.task_inputs["__parents__"] contains the Root dispatch Task Run ID.

This proves an indirect native parent/child chain:

Root Flow → Root dispatch Task → Prefect deployment Task → Stage Flow

The relationship is preserved, but the architecture must not describe it as a direct Root Flow Run → Stage Flow Run parent edge.

### 3.2 Stage → Step parent/child correlation

The same Prefect-generated intermediate-task pattern appears when a Step Subflow is invoked from the Stage's invoke_step Task.

For each Step invocation, the PoC verifies:

- The Step Flow Run has a native parent_task_run_id.
- The parent is the synthetic child-subflow Task Run.
- That synthetic Task Run's __parents__ input links to the correct Stage-owned Step dispatch Task Run.

This keeps the Stage-facing public Step callable and the Step Subflow boundary observable.

### 3.3 Step → SPU

Each Step Subflow submits two SPU Tasks and joins their results.

The PoC verifies that each SPU Task Run's flow_run_id identifies the owning Step Flow Run. The Stage does not call SPU Tasks directly.

## 4. Deployment source and result persistence

### Deployment code source

The Stage deployment uses Prefect Flow.from_source(...) with a local source directory, resulting in a Prefect LocalStorage pull step for the PoC directory.

No container image, remote Git repository, Docker service or package installation was required.

The Process Workers execute on the same Windows host and can access that path.

### Stage result persistence

The Stage Flow explicitly sets persist_result=True.

The Root calls run_deployment, waits for a terminal state, checks that the Prefect state is COMPLETED, then loads the persisted Stage domain result through the returned Flow Run state.

The tested result storage path is:

C:\poc\GPWCF\prefect-home-deployment\storage

The Prefect home is outside the repository:

C:\poc\GPWCF\prefect-home-deployment

The Prefect setting PREFECT_RESULTS_PERSIST_BY_DEFAULT remains false; persistence is enabled explicitly on the Stage Flow.

The domain result and Prefect operational State are kept separate. The Root receives Stage identity, Stage invocation identity, Pipeline invocation identity and Step results from the persisted domain result; it does not derive those values from Prefect State.

## 5. Repeatability results

Five Root invocations were executed using the exact two-worker topology. Every Root invocation launched both Stage deployments, retrieved both completed Stage results, and passed the native parent/hierarchy checks.

| Run | Root invocation ID | Stage A / Stage B worker assignment | Stage overlap |
|---|---|---|---:|
| 1 | e81a0651-871b-4a70-bd06-9f9f155a387e | Worker 01 / Worker 02 | 7.455 s |
| 2 | 91a299c2-d5e6-4d31-8507-53e15265d667 | Worker 01 / Worker 02 | 8.147 s |
| 3 | 8d48cac4-1880-4053-95b2-9103b70e3574 | Worker 01 / Worker 02 | 14.029 s |
| 4 | f91028e4-58ee-40b4-92f6-89c8e026bf14 | Worker 01 / Worker 02 | 10.842 s |
| 5 | 1ce1b293-5c02-4419-b6ac-e85e3d1d6885 | Worker 02 / Worker 01 | 8.453 s |

**5/5 repeated runs passed.**

Aggregate results:

| Acceptance observation | Result |
|---|---:|
| Root Flow Runs completed | 5/5 |
| Stage Deployment Flow Runs completed | 10/10 |
| Root → Stage synthetic-parent linkage | 10/10 |
| Stage → Step synthetic-parent linkage | 20/20 |
| Native hierarchy correlation checks | 5/5 Root invocations |
| Sibling Stage overlap | 5/5 Root invocations |
| Distinct worker assignment for sibling Stages | 5/5 Root invocations |
| Stage domain results loaded by Root | 10/10 |

Sibling Stage overlap ranged from 7.455 to 14.029 seconds, with a mean of 9.785 seconds.

The exact run IDs, Stage Flow Run IDs, parent Task Run IDs, worker names, timestamps and per-run validation observations are in PHASE-02_Repeatability_Evidence.json. The accepted five-run batch is archived under .poc/Prefect_Deployment_Stage_Qualification/evidence/qualified_two_worker_batch/. Exploratory runs remain in the parent evidence directory and are not included in the accepted batch.

## 6. Single-worker comparison

An exploratory trial using one Process Worker configured with --limit 2 did not provide deterministic sibling Stage overlap: the two Stage Flow bodies executed sequentially in that observed trial.

This is not sufficient evidence to claim that one worker with limit 2 can never run two flows concurrently. It is sufficient to reject that configuration as the qualified concurrency profile for this PoC.

The accepted profile uses two independently registered Process Worker instances, each with a flow-run limit of one. The qualification script enforces the exact worker set and verifies that the two sibling Stages actually ran on different workers.

## 7. Acceptance disposition

The machine-readable acceptance matrix is PHASE-02_Acceptance_Results.json.

**Qualified:**

- Deployment-backed Stage invocation.
- Native Stage Flow Run identity and domain identity separation.
- Indirect Root-to-Stage parent/child correlation through Prefect's synthetic invocation Task.
- Stage result persistence and retrieval by the Root.
- Stage-to-Step parent correlation.
- Step-to-SPU nesting.
- Repeatable sibling Stage overlap using two Process Worker instances.

**Not qualified:**

- Multi-host code distribution and result storage.
- More than two concurrent sibling Stage Deployments.
- Production GPWCF Stage/Step/SPU class binding.
- Generator-specific Stage/Step decomposition.
- Failure, cancellation, timeout, retry, worker restart and interrupted-run recovery.
- PostgreSQL-backed multi-worker Prefect API server.
- Production throughput, resource sizing and operational availability.

## 8. Same-host boundary

The deployment source and result storage are local paths shared by processes on the same host. This is not a multi-host deployment qualification.

A distributed Worker profile requires both:

1. A shared or remotely retrievable code source.
2. A shared result-storage backend accessible to the Root and every Stage Worker.

Those choices must be made with the GPWCF artifact custody and deployment architecture, not assumed from this local PoC.

## 9. Runtime warning

The five-run command exited with code 0 and all acceptance checks passed. A Windows asyncio Proactor ConnectionResetError was nevertheless logged during client connection teardown after the completed batch.

It did not invalidate the completed Flow Runs or the acceptance evidence, but it remains an explicit operational question in PHASE-02_Open_Integration_Questions.json.

## 10. Files and evidence

PoC source and runbooks:

.poc/Prefect_Deployment_Stage_Qualification/

Key files:

- prefect_deployment_stage_qualification.py
- start-local-prefect-server.ps1
- create-process-work-pool.ps1
- deploy-stage-flows.ps1
- start-stage-worker.ps1
- run-deployment-stage-poc.ps1
- README.md

PHASE-02 records:

- PHASE-02_Topology_Decision_Record.json
- PHASE-02_Acceptance_Results.json
- PHASE-02_Repeatability_Evidence.json
- PHASE-02_Open_Integration_Questions.json

No GPWCF production source file or specialized contract was modified.


After the accepted qualification batch, the two Process Workers and the local Prefect API server were stopped. The external Prefect home, SQLite state database and local result storage were preserved for later inspection; port 4210 is no longer listening.
