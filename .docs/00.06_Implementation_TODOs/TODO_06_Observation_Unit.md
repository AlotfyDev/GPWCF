# TODO 06 — SPU Observation Unit

**Status:** ✅ implemented | **Priority:** medium | **Effort:** medium | **Depends on:** 02 (see note) | **Implementation order:** value types + lifecycle now; association authority finalized inside task 02

**Task JSON:** `.docs\00.05_Implementation_Tasks\06_Observation_Unit.json`
**Dossier:** `.docs\00.06_Implementation_TODOs\dossiers\06_Observation_Unit.md`

## Read first

1. Task JSON + dossier.
2. `.docs\00.00_Primary_Architecture\Stage_Step_Level\01.04_SPU_ObservationUnit_SPUObU\Step_Supporting_Observation_Unit_Contract.json`
3. `.docs\00.00_Primary_Architecture\Stage_Step_Level\01.04_SPU_ObservationUnit_SPUObU\Step_Supporting_Observation_Unit_Association_Contract.json`
4. `.docs\00.00_Primary_Architecture\Stage_Step_Level\01.04_SPU_ObservationUnit_SPUObU\Step_Supporting_Observation_Unit_Lifecycle_Contract.json`

## Source files to implement (currently placeholders)

| File | Placeholder symbols to replace |
|------|-------------------------------|
| `src\gpwcf\core\supporting_patterns\observation\observation_unit.py` | `ObservationRecord`, `ObservationUnitAssociation`, `ObservationUnitLifecycle` |
| New: `src\gpwcf\core\supporting_patterns\observation\identities.py` | `observationUnitIdentity`, `observationUnitAssociationIdentity`, `observationInvocationIdentity`, `observationRecordIdentity` |

## Test files to implement

- `tests\core\supporting_patterns\observation\test_observation_unit.py`
- New: `tests\architecture\test_observation_boundaries.py`

## Implementation checklist

- [x] Observation activity forms supported against Step-owned target scopes:
      call, callback, sampling, subscription.
- [x] `ObservationRecord` fully **independent of StepExecutionResult** (never merged into it).
- [x] Observation Record provenance — all six references present on every record:
      `stepInstanceIdentity`, `observationUnitIdentity`, `observationUnitAssociationIdentity`,
      `associationTargetIdentity`, `observationInvocationIdentity`, `observationRecordIdentity`.
- [x] **Association = applicability only**; it does not guarantee active observation.
- [x] Step Composition is sole authority for association establishment / change / dissociation.
      *(Value types + coordination machinery now: `ObservationUnitAssociations` is the
      Step-Composition-owned book enforcing admitted-only establishment, dissociation,
      identity no-reuse; the StepComposition wiring itself is finalized in task 02.)*
- [x] **Dissociation does not erase records** — historical provenance retained after dissociation.
- [x] `ObservationUnitLifecycle` milestones aligned with the lifecycle coordination contract (task 08).

## Acceptance criteria (from task JSON)

- [x] Observation activity against target scopes implemented
- [x] Observation Records independent of StepExecutionResult
- [x] Observation Record provenance: stepInstanceIdentity, observationUnitIdentity, observationUnitAssociationIdentity, associationTargetIdentity, observationInvocationIdentity, observationRecordIdentity
- [x] Association = applicability only; does not guarantee active observation
- [x] Step Composition sole authority for association establishment/change/dissociation
      *(book machinery + gating now; StepComposition wiring in task 02)*
- [x] Dissociation does not erase observation records; historical provenance retained

## Definition of Done

- [x] Observation record provenance tests (six identity fields, retained after dissociation)
- [x] Association lifecycle tests (establish / change / dissociate; records survive)
- [x] Architecture test: no automatic observation guarantee from association
- [x] `pytest` green

## Cross-task note

Same 02↔06 dependency cycle note as task 05: value types now; Step-Composition-owned
association operations are finalized in task 02; re-run these tests after 02 lands.

## Implementation summary (2026-11-10)

- `observation\identities.py` (new) — nominal immutable identity value types (local
  replica of the core value-type pattern; the package imports nothing from `gpwcf`):
  `ObservationUnitIdentity` (instance; replacement gets a new identity; historical
  records may reference it after release), `ObservationUnitAssociationIdentity`
  (relationship; unique while observable, stable for the association lifetime, never
  reused in a way that makes prior records ambiguous), `AssociationTargetIdentity`
  (scope KIND + concrete instance — a bare SPU identity can never pass as a Step-level
  target; `AssociationTargetScopeKind`: spu / step / step-internal),
  `ObservationInvocationIdentity` (ONE activity: call, callback, sampling cycle,
  subscription activation, or another mechanism), `ObservationRecordIdentity` (one
  emitted record — multiple records from one activity each keep their own).
- `observation\observation_unit.py` — placeholders replaced:
  - `ObservationRecord[TObservationPayload]` — frozen; the SIX mandatory provenance
    references on every record; specialization-defined payload (no universal event
    schema/timestamp/unit/severity); independently optional metadata
    (`observation_subject_identity`, `observation_timestamp`,
    `source_invocation_identity`, `source_event_identity`, `sequence_metadata`,
    `observation_metadata`). Fully independent of SPUExecutionResult,
    StepValidatorResult, ErrorResult, ErrorHandlerResult, and StepExecutionResult;
    never implies the observed operation succeeded or failed. Provenance is NEVER
    rewritten when the association ends or the instance is released.
  - `ObservationUnitAssociation` — frozen; association = APPLICABILITY ONLY
    (docstring enumerates the contract's "associationIsNot" list: not ownership, not
    an authority transfer, not an activity/record/destination, no guarantee that
    observation is active or lifecycle-ready, no guarantee every fact is observed).
  - `ObservationUnitLifecyclePhase` (9 conceptual milestones incl.
    OBSERVING_OR_SUBSCRIBED) + `ObservationUnitReleaseOutcome` (RELEASED /
    RELEASE_FAILED / RELEASE_OUTCOME_UNCERTAIN — an attempted release is never
    silently labelled Released) + `ObservationUnitLifecycle` — Step-Composition-
    coordinated machine: admission gating, activity recording only while admitted,
    the ongoing mechanism (sampling loop/subscription/callback) recorded distinctly
    and spanning many events without per-event lifecycle transitions, quiescence
    blocks new activities but drains active ones, release requires zero active
    activities AND a deactivated mechanism, and records the outcome distinctly.
  - `ObservationUnitAssociations` — Step-Composition-owned per-unit book:
    establishment only for an admitted instance (and still only applicability —
    establishment never activates observation), identity uniqueness across live AND
    ended associations, dissociation retains the historical descriptor, does not
    touch the instance lifecycle, never ends the unit's other associations and never
    decides pending-record disposition, `has_live_associations` for the pre-release
    check. No cardinality caps or exclusivity (multi-target units and multi-unit
    targets are free).
  - `SPUObservationUnit[...]` — abstract specialization base: `observe` template
    enforces the activity boundary (exact association binding — foreign associations
    refused; target from the association, never inferred from input; per-activity
    metadata passthrough; zero/one/many records per activity; duplicate record
    identities within one activity refused; exceptions propagate and never fabricate
    or revoke records); concrete `perform_observation` returns
    `(payload, record_identity)` emissions with specialization-owned identity
    generation.
- Tests: `tests\core\supporting_patterns\observation\test_observation_unit.py`
  (42 tests: nominal identity separation, six-field provenance, identical-payload
  distinctness, StepExecutionResult independence, applicability-only association,
  no authority transfer to the target, lifecycle milestones incl. mechanism
  activation/deactivation and failed/uncertain release, association book rules,
  activity boundary incl. call/callback/sampling/subscription, zero-record
  completion, failure-no-fabrication) + `tests\architecture\test_observation_boundaries.py`
  (5 tests: no Core/Prefect import, no universal abstraction/telemetry-hub types, no
  cardinality caps, ObservationRecord field-exactness + no result-contract import in
  either direction, TBD/NotImplementedError scan).
- Suite: **333 collected → 332 passed, 1 skipped** (the deliberate task-01
  StepExecutionResult placeholder skip). 05/06 Step-Composition wiring cross-check
  re-run due after task 02 lands.
