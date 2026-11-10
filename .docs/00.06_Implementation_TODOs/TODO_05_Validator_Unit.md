# TODO 05 — SPU Validator Unit

**Status:** ✅ implemented | **Priority:** medium | **Effort:** medium | **Depends on:** 02 (see note) | **Implementation order:** value types + lifecycle now; association authority finalized inside task 02

**Task JSON:** `.docs\00.05_Implementation_Tasks\05_Validator_Unit.json`
**Dossier:** `.docs\00.06_Implementation_TODOs\dossiers\05_Validator_Unit.md`

## Read first

1. Task JSON + dossier.
2. `.docs\00.00_Primary_Architecture\Stage_Step_Level\01.03_SPU_ValidatorUnit_SPUVU\Step_Supporting_Validator_Unit_Contract.json`
3. `.docs\00.00_Primary_Architecture\Stage_Step_Level\01.03_SPU_ValidatorUnit_SPUVU\Step_Supporting_Validator_Unit_Association_Contract.json`
4. `.docs\00.00_Primary_Architecture\Stage_Step_Level\01.03_SPU_ValidatorUnit_SPUVU\Step_Supporting_Validator_Unit_Lifecycle_Contract.json`

## Source files to implement (currently placeholders)

| File | Placeholder symbols to replace |
|------|-------------------------------|
| `src\gpwcf\core\supporting_patterns\validation\validator_unit.py` | `SPUValidatorResult`, `ValidatorUnitAssociation`, `ValidatorUnitLifecycle` |
| New: `src\gpwcf\core\supporting_patterns\validation\identities.py` | `validatorUnitIdentity`, `validatorUnitAssociationIdentity`, `associationTargetIdentity` |

## Test files to implement

- `tests\core\supporting_patterns\validation\test_validator_unit.py`
- New: `tests\architecture\test_validator_boundaries.py`

## Implementation checklist

- [x] `SPUValidatorResult`: structured validation result carried **independently** in the
      optional `validatorResult` slot of `SPUExecutionResult`.
- [x] **Validation conclusions are domain results, never automatic invocation failures** —
      no raising, no success/failure status semantics, no Step flow decision.
- [x] Validator Unit Association: `validatorUnitAssociationIdentity` is **distinct from
      participant identities** (`validatorUnitIdentity`, `associationTargetIdentity`).
- [x] Association identity uniqueness + stability (stable for the association's lifetime).
- [x] `ValidatorUnitLifecycle` milestones (from lifecycle contract):
      provisioned → prepared → ready → admitted → (quiesced/released as applicable).
- [x] Step Composition is the **sole authority** for establishing/changing/ending associations —
      the association does not transfer management authority to the validator target.
      *(Value types + coordination machinery now: `ValidatorUnitAssociations` is the
      Step-Composition-owned book enforcing admitted-only establishment, dissociation,
      identity no-reuse; the StepComposition wiring itself is finalized in task 02.)*
- [x] No universal one-validator-per-SPU relationship is imposed (association is explicit and optional).

## Acceptance criteria (from task JSON)

- [x] Validator Unit validation conclusions are domain results, not invocation failures
- [x] SPUValidatorResult carried independently in optional result slot
- [x] Validator Unit Association identity distinct from participant identities
- [x] Step Composition is sole authority for establishing/changing/ending associations
      *(book machinery + gating now; StepComposition wiring in task 02)*
- [x] Association does not transfer association-management authority to target
- [x] Validator Unit Lifecycle milestones implemented (provisioned, prepared, ready, admitted, ...)

## Definition of Done

- [x] Validator unit tests for validation conclusion semantics (failing validation does NOT fail the invocation)
- [x] Association identity uniqueness and stability tests
- [x] Lifecycle milestone tests
- [x] Architecture test: no universal one-validator-per-SPU relationship imposed
- [x] `pytest` green

## Cross-task note

`SPUExecutionResult.validatorResult` slot (task 01) references this result type. After task 02
lands, revisit the Step-Composition-owned association operations and the checklist item
"Step Composition is sole authority" end to end.

## Implementation summary (2026-11-10)

- `validation\identities.py` (new) — nominal immutable identity value types (local
  replica of the core value-type pattern; the package imports nothing from `gpwcf`):
  `ValidatorUnitIdentity` (instance; replacement gets a new identity),
  `ValidatorUnitAssociationIdentity` (relationship; unique while observable, stable for
  the association lifetime, never reused for a different target),
  `AssociationTargetIdentity` (scope KIND + concrete instance — a bare SPU identity can
  never pass as a Step-level target; `AssociationTargetScopeKind`: spu / step /
  step-internal), `ValidatorInvocationIdentity` (one attempt; distinct per invocation
  under the same association).
- `validation\validator_unit.py` — placeholders replaced:
  - `SPUValidatorResult[TValidationOutcome, TValidationEvidence]` — frozen; full
    mandatory provenance (step instance / unit / association / target / invocation);
    `validation_outcome` is the specialization-defined domain conclusion (no universal
    pass/fail boolean, no status field — negative conclusions are normally produced
    results); `validation_evidence`, `validation_subject_reference`,
    `completion_metadata` independently optional. Carried in the
    `SPUExecutionResult.validatorResult` forward-reference slot; distinct from
    StepValidatorResult/StepExecutionResult/ErrorResult/ErrorHandlerResult.
  - `ValidatorUnitAssociation` — frozen; association = APPLICABILITY ONLY; identity
    distinct from both participants (nominal types make conflation unrepresentable).
  - `ValidatorUnitLifecyclePhase` (8 conceptual milestones) +
    `ValidatorUnitReleaseOutcome` (RELEASED / RELEASE_FAILED /
    RELEASE_OUTCOME_UNCERTAIN — an attempted release is never silently labelled
    Released) + `ValidatorUnitLifecycle` — Step-Composition-coordinated machine:
    admission gating (only Ready/RetainedForReuse admit), invocation recording only
    while admitted, quiescence blocks new invocations but drains active ones, release
    requires zero active invocations and records the outcome distinctly.
  - `ValidatorUnitAssociations` — Step-Composition-owned per-unit book: establishment
    only for an admitted instance, identity uniqueness across live AND ended
    associations (no reuse while retained evidence may still be observable),
    dissociation retains the historical descriptor, does not touch the instance
    lifecycle and never ends the unit's other associations, `has_live_associations`
    for the pre-release check. No cardinality caps (multi-target units and
    multi-unit targets are free).
  - `SPUValidatorUnit[...]` — abstract specialization base: `validate` template
    enforces the invocation boundary (exact association binding — foreign
    associations refused; target from the association, never inferred from input;
    full provenance; exceptions propagate and never fabricate a result); concrete
    `evaluate` defines outcome/evidence semantics.
- Tests: `tests\core\supporting_patterns\validation\test_validator_unit.py` (34 tests)
  + `tests\architecture\test_validator_boundaries.py` (5 tests: no Core/Prefect import,
  no universal abstraction types, no cardinality caps, SPU forward-reference purity in
  BOTH directions, TBD/NotImplementedError scan).
- Suite: **292 collected → 291 passed, 1 skipped** (the deliberate task-01
  StepExecutionResult placeholder skip). Task-06 note: the 02↔05/06 cycle is resolved
  per `00_MASTER_TODO.md` — value types now, Step Composition wiring in 02.
