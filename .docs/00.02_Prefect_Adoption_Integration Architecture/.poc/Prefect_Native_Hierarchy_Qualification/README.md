# Prefect Native Hierarchy Qualification PoC

## Purpose

This PoC qualifies Prefect 3.9.2 native Flow/Subflow/Task constructs for the target hierarchy:

Pipeline Root Flow -> Stage Parent Flows -> Step Subflows -> SPU Tasks.

The implementation uses contract-shaped fixtures because the GPWCF project currently has design contracts but no executable production Stage/Step/SPU classes. It does not claim production GPWCF binding and does not modify specialized contracts.

## Runtime

- CPython 3.15.1 x64
- Prefect 3.9.2
- Windows x64
- Existing isolated environment: C:\poc\GPWCF\prefect-env-managed
- Local Prefect API server: 127.0.0.1:4200/api
- One API worker (SQLite requirement); UI and scheduler disabled
- Local SQLite state store outside the repository at C:\poc\GPWCF\prefect-home-sqlite
- ThreadPoolTaskRunner(max_workers=4) for Root, Stage and Step Flow runs (separate from API-server worker count)

No package was installed or upgraded as part of this PoC.

## Run

1. Open a PowerShell terminal and start the local API server:

   powershell -ExecutionPolicy Bypass -File .\start-local-prefect-server.ps1

2. In a second PowerShell terminal, run the hierarchy:

   powershell -ExecutionPolicy Bypass -File .\run-native-hierarchy-poc.ps1

3. Validate a run directory:

   powershell -ExecutionPolicy Bypass -File .\validate-run.ps1 -RunRoot "<path printed by the run script>"

The scripts accept a different Python executable path if the managed environment is moved.

## Topology implementation

- Root invokes Stage Parent Flows through narrow Prefect Task dispatch wrappers.
- Each Stage dispatch wrapper calls a Stage-specific Flow object created with Flow.with_options(name=...).
- Stage submits Step dispatch Tasks. Each dispatch calls the public StepFacade.execute(input) callable.
- StepFacade.execute invokes a Step-specific native Flow/Subflow object.
- Only the Step Subflow references the SPU Task callables.
- The Step Subflow submits two SPU Tasks and joins their futures before assembling StepExecutionResult.

The dispatch Tasks are Prefect execution mechanics only. They do not own GPWCF component semantics or introduce extra GPWCF hierarchy layers.

## Evidence

Primary acceptance runs:

- run-5f8ffd7d-ec75-4380-8d25-cf8054a2dde0
- run-c52c64f9-44bf-4cf5-85eb-85f6834d1cb9
- run-0f24960a-b7b0-4285-825f-bc0f18950c67
- run-bc923468-7a5e-4c62-8cc8-913b0ddd51ec

Each accepted run contains:

- native-execution-trace.jsonl
- pipeline-result.json (domain result only)
- runtime-observations.json (Prefect root state)
- exception-probe.json (isolated controlled failure)
- qualification-summary.json

Earlier run-* directories are retained as exploratory iterations and are not the primary acceptance evidence. The cross-run concurrency summary is recorded in PHASE-01_Repeatability_Evidence.json. Neither Root-to-Stage nor Stage-to-Step sibling Flow concurrency is a deterministic guarantee in the tested local profile. Prefect rejects API-server multi-worker mode with SQLite; that mode requires PostgreSQL. The four-thread ThreadPoolTaskRunner is a separate client-side execution setting.

## Qualified behavior and constraints

- Root sibling Stage Flows overlapped in 2/3 runs under the SQLite single-worker API-server profile; one run serialized them. Do not assume deterministic sibling Stage concurrency.
- Step-internal SPU Task fan-out/fan-in overlapped in all 12 Step invocations across the three runs.
- Sibling Step Subflow overlap was not deterministic: one of six Stage sibling pairs overlapped across the three runs. Do not assume concurrent sibling Step Subflows.
- Native parent_task_run_id correlation is recorded for Stage and Step child Flow runs.
- Prefect Flow Run and Task Run IDs remain separate from GPWCF domain identities.
- A controlled failure Task reached Prefect FAILED while its probe Flow completed after catching the exception. No domain structured result was fabricated.

## Qualification boundary

This PoC proves Prefect native hierarchy mechanics and the observed local execution topology. It does not prove:

- Production GPWCF runtime class binding
- Generator-specific Stage/Step/SPU decomposition
- Supporting Unit binding
- Domain-specific exception/result mapping
- Cancellation, timeout, retry, replay or recovery semantics
- Large artifact custody/persistence
- Full Stage 1-13 Generator integration
