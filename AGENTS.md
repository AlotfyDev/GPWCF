# GPWCF — Agent Instructions (auto-loaded every session)

Project: SMRB.GenericPipelineWorkflowComponentsFramework (GPWCF), Python 3.15.1.
The active implementation to-do list lives here and in `.docs\00.06_Implementation_TODOs\`.

## Session protocol (follow for any implementation work)

1. Read the status board below. Pick the **first task with status `pending`** unless the user says otherwise.
2. Open that task's file `.docs\00.06_Implementation_TODOs\TODO_<Task>.md` and its dossier
   `.docs\00.06_Implementation_TODOs\dossiers\<Task>.md` (parsed diagrams, contract rankings, entity notes).
3. Implement: replace placeholder source classes and placeholder tests (`assert True`) per the TODO file.
4. Run tests: `.env\Scripts\python.exe -m pytest` (project-local venv; install pytest first if missing → task 00).
5. Before ending the session: tick checkboxes in the task's TODO file, update the status board below
   (`pending | in_progress | implemented | verified`), and update the mirror table in
   `.docs\00.06_Implementation_TODOs\00_MASTER_TODO.md`.

## Implementation order & live status

| # | Task | TODO file | Status |
|---|------|-----------|--------|
| 00 | Environment & test runner setup | TODO_00_Environment_Test_Setup.md | implemented |
| 11 | Core Identities & Diagnostics | TODO_11_Core_Identities_Diagnostics.md | implemented |
| 08 | Common Coordination (Association & Lifecycle) | TODO_08_Common_Coordination.md | implemented |
| 01 | SPU / Step Processing Unit | TODO_01_SPU_Step_Processing_Unit.md | implemented |
| 04 | Error Handling Unit | TODO_04_Error_Handling.md | implemented |
| 07 | Publication / Atomic Acceptance | TODO_07_Publication.md | implemented |
| 05 | SPU Validator Unit | TODO_05_Validator_Unit.md | implemented |
| 06 | SPU Observation Unit | TODO_06_Observation_Unit.md | implemented |
| 02 | Step | TODO_02_Step.md | implemented |
| 03 | Stage | TODO_03_Stage.md | implemented |
| 09 | Prefect Integration | TODO_09_Prefect_Integration.md | implemented |
| 10 | Dependency / Packaging / Public API | TODO_10_Dependency_Packaging_Public_API.md | implemented |

## Hard rules (every task)

- Core is **standard-library only**; Prefect only under `src\gpwcf\integrations\prefect\` (optional import).
- Dependency direction Stage → Step → SPU; **SPU must never import Step/Stage**; supporting patterns neither.
- `core.identities` stays dependency-free. Diagnostics are descriptive only, never errors/outcomes.
- Prefect State is operational evidence, never a domain result (`SPUExecutionResult`, `StepExecutionResult`,
  `StageResult` are the domain results).
- Optional result elements are independently present/absent; absence ≠ success/failure.
- No universal Supporting Unit / ExecutionContext / one-validator-per-SPU abstractions (docs forbid them).
- Docs query tool: `.env\Scripts\python.exe .docs\00.06_Implementation_TODOs\tools\query_docs.py --search "<term>"`.
