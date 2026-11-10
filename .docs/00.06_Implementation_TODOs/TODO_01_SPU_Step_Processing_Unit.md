# TODO 01 — SPU / Step Processing Unit

**Status:** ✅ implemented | **Priority:** high | **Effort:** medium | **Depends on:** 11

**Task JSON:** `.docs\00.05_Implementation_Tasks\01_SPU_Step_Processing_Unit.json`
**Dossier:** `.docs\00.06_Implementation_TODOs\dossiers\01_SPU_Step_Processing_Unit.md`

## Read first

1. Task JSON + dossier.
2. `.docs\00.00_Primary_Architecture\Stage_Step_Level\01.00_Step_Processing_Unit_SPU\Step_Processing_Unit_SPU_Contract.json`
   (documentId: `pipeline.step-processing-unit.contract`)
3. `.docs\00.00_Primary_Architecture\Stage_Step_Level\01.00_Step_Processing_Unit_SPU\SPUExecutionResult_Contract.json`
   (documentId: `pipeline.spu-execution-result.contract`)
4. `.docs\00.00_Primary_Architecture\Common\Error_Model.json` (SPU-level error family + registry rules)

## Source files implemented

| File | Content |
|------|---------|
| `src\gpwcf\core\processing_units\spu\spu_unit.py` | `StepProcessingUnit[TInput, TOutput]` (PEP 695 generic ABC): abstract `execute(input: TInput) -> SPUExecutionResult[TOutput]`; constructor receives the Pipeline-assigned `SPUErrorTypeDefinitionRegistry` (SPU never creates its own); docstring carries Step-boundary, Prefect-State, and exception-boundary rules |
| `src\gpwcf\core\processing_units\spu\results\__init__.py` | `SPUExecutionResult[TOutput, TErrorOccurrenceContext = object]` — frozen dataclass with the three independently optional elements; occurrence-collection element validation; `SPUValidatorResult` as forward-reference annotation only (arrives with task 05) |
| `src\gpwcf\core\processing_units\spu\errors.py` *(new)* | SPU error family: nominal identities (`SPUErrorOccurrenceIdentity`, `SPUErrorTypeDefinitionIdentity`, `SPUErrorTypeDefinitionRegistryIdentity`), `SPUErrorTypeDefinitionReference` (registryIdentity + definitionIdentity), `SPUErrorTypeDefinition[TErrorContent, THandlingAction]`, `SPUError[TErrorOccurrenceContext]`, `SPUErrorTypeDefinitionRegistry[TErrorTypeDefinition]` (register/resolve/definitions/create_occurrence) |
| `src\gpwcf\core\processing_units\spu\__init__.py` | public surface of the SPU package |

## Test files implemented

- `tests\core\processing_units\spu\test_spu_unit.py` — 20 tests + 1 skip-by-design
  (concrete non-delegation SPU; execute success; element optionality parametrized;
  no universal status field; preservation via `dataclasses.replace`; exception
  boundary; definition registration/duplicate rejection; registry scoping incl.
  no cross-registry resolution on equal identities; occurrence must reference a
  registered definition; registry stores no occurrences; Pipeline-assigned
  registry required; `SPUExecutionResult` ≠ `StepExecutionResult` with clean skip
  while task 02 is a placeholder)
- `tests\architecture\test_spu_boundaries.py` *(new)* — 4 tests (AST reverse-dependency
  scan for all of `core\processing_units` incl. relative-import resolution; no Prefect/
  `PrefectState` references in the SPU layer; `execute(self, input)` shape with no
  ExecutionContext; result carries exactly the three contract fields)

## Implementation checklist

- [x] `StepProcessingUnit[TInput, TOutput]` generic base (ABC):
      `execute(input: TInput) -> SPUExecutionResult[TOutput]`.
- [x] `SPUExecutionResult[TOutput]` carries three **independently optional** elements
      (absent = `None`, absence is not success/failure):
      `processing_artifact`, `spu_error_occurrences`, `validator_result`
      (forward-reference annotation; no runtime dependency on task 05).
- [x] Preservation invariant: frozen immutable result snapshots; SPU adds later
      evidence with `dataclasses.replace` so earlier produced elements survive.
- [x] `SPUErrorTypeDefinition[TErrorContent, THandlingAction]`: owned by the concrete SPU;
      carries error content description + handling-action description + definition identity.
- [x] `SPUErrorTypeDefinitionRegistry`: stores/resolves definitions for **exactly one owning SPU**
      (`identity` + `owner_spu_identity`); Pipeline exclusively owns the instance and assigns it
      to the SPU (base constructor receives it; SPU never creates its own registry).
      Duplicate identities rejected (no silent overwrite); lookup scoped to the registry
      instance (equal identity values in another registry never cross-resolve); registry
      stores no occurrences.
- [x] `SPUError[TErrorOccurrenceContext]`: occurrence created by the SPU; references exactly one
      registered definition (enforced by `registry.create_occurrence` resolving first);
      carries `occurrence_identity` + typed `context`.
- [x] Exceptions that prevent `execute` from returning are **not** converted to `SPUError`
      and are not an `SPUExecutionResult` (exception boundary — tested).
- [x] SPU does NOT assemble `StepExecutionResult`, does NOT decide Step flow transitions
      (architecture tests + docstrings).

## Acceptance criteria (from task JSON)

- [x] SPU execute(input: TInput) -> SPUExecutionResult[TOutput] signature implemented
- [x] SPUExecutionResult carries processingArtifact, spuErrorOccurrences, validatorResult as independently optional elements
- [x] SPU defines and registers its own SPUErrorTypeDefinition instances via Pipeline-assigned registry
- [x] SPU creates SPUError occurrences for its own processing errors
- [x] No reverse package dependency from SPU to Step (AST scan; also covered by
      `tests\architecture\test_no_universal_supporting_unit.py`)
- [x] Prefect State never substitutes for SPUExecutionResult (no Prefect imports or
      Prefect State references anywhere under `core\processing_units`; `SPUExecutionResult`
      is the only returned domain result type)

## Definition of Done

- [x] Unit tests cover execute success, error occurrence creation, result optionality
- [x] Architecture test enforces SPU does not import Step Composition
- [x] Integration test confirms SPUExecutionResult distinct from StepExecutionResult
      (type-distinctness asserts run now; deep field checks skip cleanly until task 02)
- [x] `pytest` green — **171 passed, 1 skipped** (21 new; 150 from prior tasks)

## Boundary rules honored

- `SPU -> Step [FORBIDDEN (reverse)]` per `02_Architectural_Level_Dependency_Graph.dot` /
  `03_Dependency_Direction_Rules.dot`.
- SPU interacts with supporting units only where the concrete Step composition assigns it;
  no supporting component is mandatory here; `validator_result` is a forward reference only.

## Notes for later tasks

- Task 02 (Step): Step Composition consumes `SPUExecutionResult`; the distinctness test's
  deep checks un-skip once `StepExecutionResult` becomes a dataclass.
- Task 05 (Validator Unit): swap `SPUExecutionResult.validator_result` forward reference
  for the real `SPUValidatorResult` import if desired (runtime contract already accepts it).
- Task 09 (Prefect): binding returns the exact `SPUExecutionResult`; never replaces it
  with Prefect State (already enforced by `test_prefect_state_never_enters_the_spu_domain_result`).
