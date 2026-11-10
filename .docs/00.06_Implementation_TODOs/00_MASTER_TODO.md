# GPWCF — Master Implementation TODO

Project: `SMRB.GenericPipelineWorkflowComponentsFramework` (GPWCF)
All paths in the TODO files are relative to the project root:
`C:\Trading\Projects\Shared_Memory_Reqgion_Broker\SMRB\SMRB.GenericPipelineWorkflowComponentsFramework\`

## Purpose of this folder

One self-sufficient TODO file per implementation task. Each new context window:
1. Read this master file.
2. Pick the next task from the execution order below (respect status).
3. Open that task's `TODO_*.md` and follow it top to bottom.
4. Tick checkboxes as work completes; update the status board here before ending the session.

## Status board

| # | Task | Priority | Effort | Depends on | Status |
|---|------|----------|--------|------------|--------|
| 00 | Environment & Test Runner Setup | blocker | low | — | ✅ implemented |
| 11 | Core Identities & Diagnostics | medium | low | — | ✅ implemented |
| 08 | Common Coordination (Association & Lifecycle) | high | medium | — | ✅ implemented |
| 01 | SPU / Step Processing Unit | high | medium | 11 | ✅ implemented |
| 04 | Error Handling Unit | high | high | 01, 11 | ✅ implemented |
| 07 | Publication / Atomic Acceptance | high | high | 04 | ✅ implemented |
| 05 | SPU Validator Unit | medium | medium | 02 (value types early; see note) | ✅ implemented |
| 06 | SPU Observation Unit | medium | medium | 02 (value types early; see note) | ✅ implemented |
| 02 | Step | high | high | 01, 04, 05, 06 | ✅ implemented |
| 03 | Stage | high | high | 02, 11 | ✅ implemented |
| 09 | Prefect Integration | high | high | 03, 02, 01 | ✅ implemented |
| 10 | Dependency / Packaging / Public API | high | high | 09 | ✅ implemented |

Status values: `pending` → `in_progress` → `implemented` → `verified` (all tests + architecture tests green).

### TODO files in this folder

| File | Covers |
|------|--------|
| `TODO_00_Environment_Test_Setup.md` | pytest install, architecture test package, pytest.ini |
| `TODO_11_Core_Identities_Diagnostics.md` | core.identities, core.diagnostics |
| `TODO_08_Common_Coordination.md` | association + lifecycle coordination contracts |
| `TODO_01_SPU_Step_Processing_Unit.md` | SPU callable, SPUExecutionResult, SPUError model |
| `TODO_04_Error_Handling.md` | Error Handling Unit, publisher protocol, reservation |
| `TODO_07_Publication.md` | publication protocol representations, Recovery Owner |
| `TODO_05_Validator_Unit.md` | SPUValidatorResult, association, lifecycle |
| `TODO_06_Observation_Unit.md` | ObservationRecord provenance, association, lifecycle |
| `TODO_02_Step.md` | Step aggregate, StepExecutionResult, StepComposition, lifecycle |
| `TODO_03_Stage.md` | Stage callable contract, StageResult, Stage errors |
| `TODO_09_Prefect_Integration.md` | Prefect bindings, correlation, result preservation |
| `TODO_10_Dependency_Packaging_Public_API.md` | pyproject, packaging, Public API conformance |

Each TODO references its auto-generated **dossier** under `dossiers\` — parsed diagrams,
scored contract documents, and per-entity design notes for that task.

### Note on the 02 ↔ 05/06 task-dependency cycle

The task JSONs declare `02_Step` depends on `05_Validator_Unit`/`06_Observation_Unit`, while `05`/`06` depend on `02_Step`. Practical resolution (used in the execution order):
- Implement `05`/`06` **value types, identities, and lifecycle contracts first** (SPUValidatorResult, ObservationRecord, association identities, lifecycle milestones). They only depend on `11`.
- `02_Step` then wires the optional result slots and makes **Step Composition the sole association/lifecycle authority** (finalizing the association coordination part of `05`/`06`).
- Cross-check `05`/`06` acceptance criteria that involve Step Composition after `02` lands.

## Recommended execution order

```
00 → 11 → 08 → 01 → 04 → 07 → 05 → 06 → 02 → 03 → 09 → 10
```

Rationale: 11 and 08 are dependency-free foundations. 01 (SPU) is the leaf processing
contract. 04+07 implement the error-handling/publication protocol pair. 05/06 supply the
optional supporting-pattern values consumed by Step's optional result slots. 02 (Step)
owns the composition that coordinates all of the above. 03 (Stage) sits above Step.
09 binds the domain tree to Prefect; 10 closes packaging/Public API/conformance.

## Environment facts (verified 2026-11-10)

- Language: Python **3.15.1**, standard-library-only Core (`requirements.txt` empty by design).
- Project-local venv: `.env\Scripts\python.exe` (declared in the `.pyproj`, id
  `SMRB.GenericPipelineWorkflowComponentsFramework.Python3151`, run with `-s`).
- Solution-shared venv: `..\ .env\Scripts\python.exe` (also 3.15.1).
- **pytest is not installed in either venv yet** → Task 00.
- Package layout: `src\gpwcf\` (core / integrations / public_api), tests under `tests\`
  (core, architecture, integrations, public_api). All source and test files are
  **placeholders** (classes with `pass`, tests with `assert True`).
- `tests\architecture\` exists but has no files yet; architecture tests are part of
  nearly every task's DoD.
- The `.pyproj` declares `TestFramework: none` — tests are run via pytest CLI, not VS.

## Test running conventions (after Task 00)

```powershell
# from project root
C:\Trading\Projects\Shared_Memory_Reqgion_Broker\SMRB\SMRB.GenericPipelineWorkflowComponentsFramework\.env\Scripts\python.exe -m pytest tests -q
# single task scope, e.g. SPU:
.env\Scripts\python.exe -m pytest tests\core\processing_units -q
```

## Documentation map

| Folder | Content |
|--------|---------|
| `.docs\00.06_Implementation_TODOs\dossiers\` | **Auto-generated per-task dossiers** (one per task id): parsed class/sequence/association/dependency diagrams, scored contract-document lists, per-entity design notes, verbatim acceptance criteria & DoD |
| `.docs\00.06_Implementation_TODOs\tools\query_docs.py` | The query tool that regenerates dossiers and does keyword search across all docs (run with the project venv Python) |
| `.docs\00.05_Implementation_Tasks\` | The 11 predefined task JSONs (target, classes, acceptance criteria, DoD, diagrams) — the authoritative task definitions |
| `.docs\00.00_Primary_Architecture\` | 16 design-wave proposals + detailed contracts (SPU, Step, Stage, Error Model, Error Handling, Publication, Validator, Observation, Coordination, Prefect, Packaging, Public API) |
| `.docs\00.02_Prefect_Adoption_Integration Architecture\` | Prefect adoption ADR, PHASE-00..02 qualification reports/evidence, environment & dependency manifest (Prefect 3.9.2) |
| `.docs\00.03_Architecture_Closure_Design\` | Gap closure docs F-01..F-10, dependency & Public API architecture, filesystem architecture, module boundary model |
| `.docs\00.04_Architectural_Dependencies_Analysis\` | Diagram code: `A_Class_Diagram_Code\03_Diagrams_Codes_Files\*.dot`, `B_Sequencial_Diagram_Code\*.puml`, `C_Association_Diagram_Code\*.puml`, `D_Architectural_Dependency_Diagram_Code\*.dot`, plus the resolved entity index `A_Class_Diagram_Code\02_Unique_Class_Entity_Resolved_index\` (per-entity JSON notes) |

### Query tool usage

```powershell
# regenerate all dossiers
.env\Scripts\python.exe .docs\00.06_Implementation_TODOs\tools\query_docs.py

# regenerate one task's dossier
.env\Scripts\python.exe .docs\00.06_Implementation_TODOs\tools\query_docs.py 02_Step

# list tasks
.env\Scripts\python.exe .docs\00.06_Implementation_TODOs\tools\query_docs.py --list

# keyword search across task JSONs, contracts, entity notes and diagram code
.env\Scripts\python.exe .docs\00.06_Implementation_TODOs\tools\query_docs.py --search "atomic acceptance"
```

Note: source `.dot` tooltips are truncated at export time; the full design rules live in
the contract JSONs and in `A_Class_Diagram_Code\02_Unique_Class_Entity_Resolved_index\*.json`.
The dossier links both.

## Global architectural invariants (apply to every task)

1. **Core is standard-library-only.** No third-party import in `src\gpwcf\core\**`; Prefect may only appear under `src\gpwcf\integrations\prefect\**` and must be an optional import there.
2. **Dependency direction:** Stage → Step → SPU. The SPU must **not** import Step or Stage. Supporting patterns never import Step/Stage.
3. **`core.identities` is dependency-free** (no imports from other gpwcf modules).
4. **Diagnostics ≠ Error Model.** A `Diagnostic` is descriptive only and never substitutes for Error/Failure/Outcome.
5. **Prefect State is operational evidence, never a domain result.** `SPUExecutionResult`, `StepExecutionResult`, `StageResult` remain the only domain results.
6. **Result element optionality:** all optional result elements are independently present/absent; absence is not success/failure.
7. **Public API surface is curated** in `src\gpwcf\public_api\`; no Prefect types may leak into Core API.
8. **No universal abstractions** where the docs forbid them: no universal Supporting Unit, no universal ExecutionContext, no mandatory validator/handler/observer.

## Update protocol (end of every session)

- Tick completed `- [ ]` boxes in the task file.
- Update the Status board row here (`pending|in_progress|implemented|verified`).
- If new discoveries affect later tasks, add a `Notes` line to the affected `TODO_*.md`.
