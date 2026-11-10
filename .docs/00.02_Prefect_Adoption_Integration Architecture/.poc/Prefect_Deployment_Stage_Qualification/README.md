# Prefect Deployment-Backed Stage Invocation Qualification

## Purpose

This isolated PoC evaluates whether Prefect 3.9.2 Deployments and Process Workers can execute sibling GPWCF Stage Parent Flows concurrently while preserving:

- Native Stage Flow Run identity and its deployment identity.
- Root-to-Stage invocation, parent linkage and explicit domain correlation.
- Stage-to-Step-to-SPU hierarchy and typed result assembly.
- Root visibility of each completed Stage result.
- Separation of Prefect operational State from GPWCF domain results.

It is a runtime-mechanics qualification using contract-shaped fixtures. It is not production GPWCF binding and does not modify specialized contracts.

## Runtime and deployment profile

- Windows x64
- CPython 3.15.1 x64
- Prefect 3.9.2
- Local Prefect API server: http://127.0.0.1:4210/api
- API server: one worker with SQLite; UI and scheduler disabled
- Work pool: gpwcf-phase02-stage-qualified-pool (Process type)
- Exactly two ONLINE Process Worker instances:
  - gpwcf-stage-worker-01, flow-run limit 1
  - gpwcf-stage-worker-02, flow-run limit 1
- Both workers execute on the same Windows host and use the same managed Python environment.
- Stage source uses Prefect LocalStorage bound to this PoC directory; no container image, remote Git repository or package installation is used.
- Stage Flow results use Prefect result persistence and local result storage under the same external Prefect home.

The separate API-server worker count, worker-instance count and each worker's flow-run limit are distinct settings. SQLite is qualified only with one API-server worker. The Process Worker instances are separate from the API server.

## Native hierarchy and invocation

Pipeline Root Flow
  -> Root dispatch_stage Task
  -> Prefect run_deployment(..., as_subflow=True)
  -> Prefect-generated deployment subflow Task
  -> Stage Deployment Flow Run
  -> Stage invoke_step Tasks
  -> Prefect-generated child-subflow Tasks
  -> Step Subflow Flow Runs
  -> SPU Task Runs

The Prefect-generated Tasks are runtime relationship/invocation nodes. They are not additional GPWCF semantic components and do not own Stage Composition or Step Composition.

### Root -> Stage parent correlation

In Prefect 3.9.2, run_deployment(as_subflow=True) creates a synthetic Task Run for the deployment invocation. The deployed Stage Flow Run's parent_task_run_id points to that synthetic Task Run, not directly to the user-defined root dispatch Task.

The PoC verifies the full chain:
- Stage Flow Run.parent_task_run_id equals the synthetic deployment Task Run ID.
- The synthetic Task Run task_inputs.__parents__ contains the Root dispatch Task Run ID.
- The Root dispatch result carries the deployment Flow Run ID, deployment parent Task Run ID, Root dispatch Task Run ID, Stage identity and Stage invocation identity.

Therefore, Root-to-Stage correlation is preserved through an explicit native intermediate Task. It is not a direct parent_task_run_id edge from the Stage Flow Run to the Root dispatch Task.

### Stage -> Step parent correlation

Calling a native Step Subflow from the Step dispatch Task also produces a Prefect-generated intermediate Task Run. The Step Flow Run parent_task_run_id points to that Task Run; its task_inputs.__parents__ links back to the Stage's Step dispatch Task Run. The PoC verifies this for every Step invocation.

### Step -> SPU

Each Step Subflow submits two SPU Tasks and joins their futures. The SPU Task Run's flow_run_id identifies the owning Step Flow Run. The Stage does not reference or invoke SPU Tasks directly.

## Result propagation

The Stage Flow uses persist_result=True. The Root waits for each run_deployment call to reach a final state, verifies that the state is COMPLETED, and loads the persisted Stage result.

The returned domain result is not inferred from Prefect State. Prefect State and the typed Stage result remain separate.

The current LocalStorage code source and local result storage are same-host mechanisms. A worker on another machine would require a shared/retrievable code source and shared result storage. Multi-host execution is outside this PoC.

## Concurrency design under test

The qualified topology uses two distinct Process Worker instances, each with a flow-run limit of one, polling the same Process work pool.

A single Process Worker configured with --limit 2 was also explored. It did not provide deterministic sibling Stage overlap in the observed trial, so worker concurrency is not inferred from the numeric limit alone.

Each test Stage includes a configurable fixed delay solely to create a measurable overlap window. This delay is a test fixture, not a production Stage behavior.

The acceptance script refuses to start unless the work pool has exactly the two expected ONLINE worker names. It also records each Stage Flow Run's native Prefect worker name and verifies that the two sibling Stages were assigned to distinct workers.

## Runbook

Run all commands from PowerShell. Keep the server and both workers running while the qualification executes.

1. Start the isolated local API server:

   powershell -ExecutionPolicy Bypass -File .\start-local-prefect-server.ps1

2. Create the dedicated Process work pool:

   powershell -ExecutionPolicy Bypass -File .\create-process-work-pool.ps1

3. Register the two Stage deployments:

   powershell -ExecutionPolicy Bypass -File .\deploy-stage-flows.ps1

4. In a separate terminal, start Worker 01:

   powershell -ExecutionPolicy Bypass -File .\start-stage-worker.ps1 -WorkerName gpwcf-stage-worker-01 -ConcurrencyLimit 1

5. In another terminal, start Worker 02:

   powershell -ExecutionPolicy Bypass -File .\start-stage-worker.ps1 -WorkerName gpwcf-stage-worker-02 -ConcurrencyLimit 1

6. Run the repeated qualification:

   powershell -ExecutionPolicy Bypass -File .\run-deployment-stage-poc.ps1 -Runs 5 -StageDelaySeconds 10

7. Inspect the evidence under .\evidence\ and validate the JSON summaries.

The scripts use the existing isolated environment at C:\poc\GPWCF\prefect-env-managed and the Prefect home at C:\poc\GPWCF\prefect-home-deployment. Both locations are outside the repository.

## Evidence emitted per Root invocation

- root-trace.jsonl
- stage-a-trace.jsonl
- stage-b-trace.jsonl
- pipeline-result.json
- parent-link-observations.json
- native-hierarchy-correlations.json
- concurrency-observation.json
- qualification-summary.json

The run root also receives cross-run-summary.json after all requested repeated runs complete.

The accepted PHASE-02 five-run batch is archived under evidence/qualified_two_worker_batch/. The parent evidence directory also retains exploratory runs from earlier single-worker and setup trials; those are not part of the accepted five-run batch.

## Qualification exclusions

- Production GPWCF Stage, Step, SPU or Supporting Unit classes.
- Generator-specific mapping for STG-01 through STG-13.
- Domain-specific exception-to-result mapping, recovery and error-handler contracts.
- Cancellation, timeout settlement, retry, replay, idempotency and safe release.
- Worker crash/restart and interrupted Flow Run recovery.
- Multi-host code distribution and shared result storage.
- Large artifact transfer, artifact custody and external object storage.
- PostgreSQL-backed multi-worker API-server profile.
- Production capacity, throughput and operational sizing.

## No repository production changes

This PoC is confined to its own .poc directory and its PHASE-02 qualification documents. No GPWCF production source or specialized contract is changed.


After the accepted qualification batch, the two Process Workers and the local Prefect API server were stopped. The external Prefect home, SQLite state database and local result storage were preserved for later inspection; port 4210 is no longer listening.
