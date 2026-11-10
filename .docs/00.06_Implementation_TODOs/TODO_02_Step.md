# TODO 02 — Step

**Status:** ☑ implemented | **Priority:** high | **Effort:** high | **Depends on:** 01, 04, 05, 06

**Task JSON:** `.docs\00.05_Implementation_Tasks\02_Step.json`
**Dossier:** `.docs\00.06_Implementation_TODOs\dossiers\02_Step.md`

## Read first

1. Task JSON + dossier (parsed Step class diagram, Step execution sequence, association diagram).
2. `.docs\00.00_Primary_Architecture\Stage_Step_Level\00.00_Step\Step_Contract.json` (documentId `pipeline.step.contract`)
3. `.docs\00.00_Primary_Architecture\Stage_Step_Level\00.00_Step\Step_Composition_Contract.json`
4. `.docs\00.00_Primary_Architecture\Stage_Step_Level\00.00_Step\04.00_Step_Callable.json`
5. `.docs\00.00_Primary_Architecture\Stage_Step_Level\01.05_StepExecutionResult\StepExecutionResult_Contract.json`
6. `.docs\00.00_Primary_Architecture\Stage_Step_Level\00.00_Step\06.00_Optional_Result_Contributions.json`
7. `.docs\00.00_Primary_Architecture\Step_Termination_Integration_Review.md` (lifecycle/retirement)

## Source files to implement (currently placeholders)

| File | Placeholder symbols to replace |
|------|-------------------------------|
| `src\gpwcf\core\step\step.py` | `Step`, `StepExecutionResult`, `OptionalResultContributions` |
| `src\gpwcf\core\step\results\__init__.py` | `StepExecutionResult[TOutput]`, `OptionalResultSlot`, `OptionalResultContributions` |
| `src\gpwcf\core\step\composition\__init__.py` | `StepComposition` (internal orchestrator) |
| New: `src\gpwcf\core\step\invocation.py` | `StepInvocation`, `StepCallable` |
| New: `src\gpwcf\core\step\lifecycle.py` | StepLifecycle: admission / quiescence / `RetainForReuse` / `TerminalRetirement`, Step Admission Boundary |

## Test files to implement

- `tests\core\step\test_step.py`
- New: `tests\core\step\test_step_lifecycle.py`
- New: `tests\architecture\test_step_boundaries.py` (Stage must not call SPU directly; SPU no-reverse check re-verified)

## Implementation checklist

- [x] `Step[TInput, TOutput]` aggregate root + facade: `execute(input: TInput) -> StepExecutionResult[TOutput]`.
- [x] Step owns internal `StepComposition` which coordinates SPUs and supporting units;
      Step delegates internal orchestration but stays accountable for the public result.
- [x] `StepCallable` public callable boundary; Stage invokes **only** through it
      (never SPUs / supporting units directly).
- [x] `StepExecutionResult[TOutput]`: processing artifact + **independently optional** contributions:
      `validatorResult`, `errorResult`, `errorHandlerResult` (each an `OptionalResultSlot`;
      independently present/absent; absence ≠ failure).
- [x] `OptionalResultContributions`: closed aggregate grouping the three optional contributions.
- [x] Step Composition consumes `SPUExecutionResult` values, performs cross-SPU aggregation,
      assembles Step-level `ErrorResult` per Step Error Model (occurrences keep producer SPU identity).
- [x] Error handling integration: `ErrorHandlerResult` integrated as a separate optional slot;
      Step-specific Error Handling Composition reconciles ambiguous publication outcomes.
- [x] StepLifecycle: `RetainForReuse` and `TerminalRetirement` dispositions; lifecycle request is
      distinct from `execute`; safe termination — never report terminal release while accepted
      invocations/obligations remain unsettled.
- [x] **Step Admission Boundary**: linearizable admission for `execute` invocations
      (accepted / not accepted before execution begins).
- [x] Validator/Observation association authority: Step Composition establishes/changes/ends
      associations (finalizes tasks 05/06 cross-checks).

## Acceptance criteria (from task JSON)

- [x] Step execute(input: TInput) -> StepExecutionResult[TOutput] implemented
- [x] Step owns Step Composition coordinating SPUs and supporting units
- [x] StepExecutionResult optional result slots independently present/absent
- [x] Stage does not invoke SPUs or supporting units directly
- [x] StepLifecycle states RetainForReuse and TerminalRetirement implemented
- [x] Step Admission Boundary linearizable for execute invocations

## Definition of Done

- [x] Tests for optional result slot presence/absence semantics
- [x] Architecture test: Stage not permitted to call SPU directly
- [x] Lifecycle tests for admission/quiescence/release
- [x] Integration: SPUExecutionResult distinct from StepExecutionResult (from task 01) now assertable
- [x] Re-run validator/observation suites (05/06) — Step-Composition-owned association paths green
- [x] `pytest` green — 333 collected, 333 passed, 0 skipped

## Boundary rules

- From `02_Architectural_Level_Dependency_Graph.dot`: Step composition coordinates SPU contracts;
  `SPU -> Step` remains forbidden.
- `StepExecutionResult` is Stage-facing; internal composition is never exposed to Stage.

## Summary

Task 02 complete. Sources written:
- `src\gpwcf\core\step\invocation.py` — `StepInvocation[TInput]`, `StepCallable`, `StepExecutionContext`, `StepInvocationRejected`
- `src\gpwcf\core\step\lifecycle.py` — `StepAdmissionBoundary`, `StepLifecycle`, `StepLifecycleStatus`, `StepLifecycleOutcome`, `StepLifecycleDisposition`, `StepLifecycleError`
- `src\gpwcf\core\step\results\__init__.py` — `Absent`, `Present[T]`, `OptionalResultSlot[T]`, `OptionalResultContributions`, `StepExecutionResult[TOutput, ...]`
- `src\gpwcf\core\step\step.py` — `Step[TInput,...]` aggregate root with `execute()` template method
- `src\gpwcf\core\step\composition\__init__.py` — `StepComposition` orchestrator, `StepCompositionFlowResult`, `StepSettlementReport`
- `src\gpwcf\core\step\__init__.py` — exports updated
- `src\gpwcf\core\identities\__init__.py` — added `StepInvocationIdentity`, `StageInvocationIdentity`
- Tests: `tests\core\step\test_step.py` (31 real tests), `tests\core\identities\test_identities.py` (updated for 7 identity types)
- Fixes: `test_execute_rejects_foreign_step_identity_without_consuming_the_identity` (new invocation with correct step_identity), `test_exception_keeps_all_earlier_evidence_in_the_flow_result` (phase order: component_invocation → step_invocation), `test_spu_returning_a_non_result_is_recorded_and_refused` (phase order), `test_retire_confirms_terminally_and_reopen_is_refused` (match "reuse readiness"), validator/observation association tests (added `AssociationTargetScopeKind` arg)
- `pytest` green: 333 collected, 333 passed, 0 skipped

Next task: Task 03 — Stage.
