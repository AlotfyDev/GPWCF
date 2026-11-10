# TODO 03 — Stage

**Status:** ☑ implemented | **Priority:** high | **Effort:** high | **Depends on:** 02, 11

**Task JSON:** `.docs\00.05_Implementation_Tasks\03_Stage.json`
**Dossier:** `.docs\00.06_Implementation_TODOs\dossiers\03_Stage.md`

## Read first

1. Task JSON + dossier (parsed Stage class diagram, Stage execution sequence, association diagram).
2. `.docs\00.00_Primary_Architecture\Stage_Level\01.00_Stage_Callable.json`
3. `.docs\00.00_Primary_Architecture\Stage_Level\02.00_Stage_Result.json`
4. `.docs\00.00_Primary_Architecture\Stage_Level\Stage_Level_Architecture.json`
5. `.docs\00.00_Primary_Architecture\Pipeline_Architecture_and_Stage_Interface_Contract.md`
6. `.docs\00.00_Primary_Architecture\03.00_Pipeline_Invocation.json`

## Source files to implement (currently placeholders)

| File | Placeholder symbols to replace |
|------|-------------------------------|
| `src\gpwcf\core\stage\stage.py` | `Stage`, `StageCallableContract`, `StageResult` |
| `src\gpwcf\core\stage\composition\__init__.py` | `StageComposition` (owns Step membership), `StageInvocation` |
| New: `src\gpwcf\core\stage\results.py` | `StageResult[TStagePayload]` (envelope + specialized payload), `StageFlowResult` |
| New: `src\gpwcf\core\stage\errors.py` | `StageErrorTypeDefinition[TErrorContent, THandlingAction]`, `StageErrorTypeDefinitionRegistry`, `StageError` |

## Test files to implement

- `tests\core\stage\test_stage.py`
- New: `tests\core\stage\test_stage_result_persistence.py`
- New: `tests\architecture\test_stage_boundaries.py` (Core must not import Prefect — placeholder until task 09, then enforced for real)

## Implementation checklist

- [x] `StageCallableContract`: public boundary to consuming workflows with explicit
      **acceptance / completion / result / exception** distinctions
      (invocation accepted ≠ completed ≠ result retrieved).
- [x] `StageInvocation`: per-invocation record (Stage-level `InvocationIdentity` correlation).
- [x] Stage owns **Step membership** via `StageComposition`; coordinates Step public contracts only.
- [x] Stage defines Stage-specific flow semantics (Step sequencing is consumer-owned topology;
      framework provides the composition surface).
- [x] `StageResult[TStagePayload]`: envelope separate from Stage outputs, flow result, and domain
      outcome; envelope carries invocation identity + payload.
- [x] `StageFlowResult` is **independent of any StepExecutionResult** (F-06 gap closure).
- [x] Stage registers `StageErrorTypeDefinition` instances via a **Pipeline-assigned** registry;
      creates `StageError` occurrences. Stage-level types are distinct programmatic types from
      SPU-level ones (neither alias nor subtype).
- [x] `Prefect State never substitutes for StageResult` — keep domain result construction in Core.

## Acceptance criteria (from task JSON)

- [x] StageCallableContract boundary implemented (acceptance/completion/result/exception distinctions)
- [x] Stage owns Step membership and Stage Composition
- [x] StageResult envelope separate from Stage outputs, flow result, domain outcome
- [x] Stage registers StageErrorTypeDefinition via Pipeline-assigned registry
- [x] Stage Flow Result independent of StepExecutionResult
- [x] Prefect State never substitutes for StageResult

## Definition of Done

- [x] Stage callable contract tests for acceptance/completion/exception
- [x] StageResult serialization/persistence integration test (round-trip via stdlib `json`;
      persistence mapping is finalized by task 09's Prefect persistence binding)
- [x] Architecture test: Core not permitted to import Prefect
- [x] `pytest` green — 363 collected, 363 passed, 0 failed, 0 skipped

## Summary

Task 03 complete. Sources written:
- `src\gpwcf\core\stage\composition\__init__.py` — `StageExecutionContext`, `StageInvocation[TInput]`, `StageInvocationRejected`, `StageComposition`, `StageSettlementReport` (imports `StageFlowResult` from results.py)
- `src\gpwcf\core\stage\results.py` — `StageFlowTransition`, `StageFlowException`, `StageStepInvocation`, `StageFlowResult`, `StageFlowResultSealed`, `StageResult[TStagePayload]`
- `src\gpwcf\core\stage\errors.py` — `StageErrorTypeDefinition[TErrorContent, THandlingAction]`, `StageErrorTypeDefinitionRegistry`, `StageError[TErrorOccurrenceContext]`
- `src\gpwcf\core\stage\stage.py` — `StageCallableContract[TInput, TOutput]` (ABC), `Stage[TInput, TOutput]` aggregate root with `execute()` template method, `StageExecutionContractViolation`
- `src\gpwcf\core\stage\__init__.py` — exports updated

Tests written:
- `tests\core\stage\test_stage.py` (24 real tests: callable contract acceptance/rejection, Step membership, StageResult envelope, error type definition registration, Prefect-state separation, concurrency)
- `tests\core\stage\test_stage_result_persistence.py` (5 tests: JSON round-trip, Absent/Present discrimination, None vs absence)
- `tests\architecture\test_stage_boundaries.py` (5 tests: no Prefect import in core.stage, no SPU import in composition, Step public contract boundary, StageResult != Prefect State, StageCallableContract is ABC)

`pytest` green: 363 collected, 363 passed, 0 failed, 0 skipped.

Next task: Task 09 — Prefect Integration.
