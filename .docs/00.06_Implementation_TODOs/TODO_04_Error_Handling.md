# TODO 04 — Error Handling Unit

**Status:** ✅ implemented | **Priority:** high | **Effort:** high | **Depends on:** 01, 11

**Task JSON:** `.docs\00.05_Implementation_Tasks\04_Error_Handling.json`
**Dossier:** `.docs\00.06_Implementation_TODOs\dossiers\04_Error_Handling.md`

## Read first

1. Task JSON + dossier (sequence diagram yields the exact publication flow; association diagram yields entry fields).
2. `.docs\00.00_Primary_Architecture\Stage_Step_Level\01.02_Step_Error_Handling\ErrorHandlingUnit_Contract.json` (top relevance hit)
3. `.docs\00.00_Primary_Architecture\Stage_Step_Level\01.02_Step_Error_Handling\ErrorHandlerResult_Contract.json`
4. `.docs\00.00_Primary_Architecture\Stage_Step_Level\01.02_Step_Error_Handling\OperationEntryPublisher_Contract.json`
5. `.docs\00.00_Primary_Architecture\Stage_Step_Level\01.02_Step_Error_Handling\PublicationReservation_Contract.json`
6. `.docs\00.00_Primary_Architecture\Common\10.00_Error_Handling.json`

## Source files implemented

| File | Content |
|------|---------|
| `src\gpwcf\core\supporting_patterns\error_handling\identities.py` *(new)* | Pattern-local nominal identity types on a local `_PatternIdentityValue` base (deliberate replica of the `core.identities` value-type pattern; the pattern imports nothing from `gpwcf`): `ErrorHandlingUnitIdentity`, `ErrorHandlingInvocationIdentity`, `HandlingOperationAttemptIdentity`, `HandlingOperationIdentity`, `OperationEntryPublisherIdentity`, `PublicationReservationIdentity`. Cross-layer identities (Step instance, Unit Association, association target, producer SPU, occurrence) travel as opaque validated non-empty string VALUES. |
| `src\gpwcf\core\supporting_patterns\error_handling\operation_entry_publisher.py` | Working publication protocol machinery: `PublicationStatus` (Reserved/Consumed/Released), `PublicationOutcome`, `PublicationRejection`, `PublisherContractViolation` (dedicated violation exception channel), `ReservationGrant`, `PublicationAcknowledgement`, `ReleaseAcknowledgement`, `PublicationReservation` (opaque capability; issuer-token guarded; publisher-only state), `OperationEntryPublisher[THandlingOperationResult]` (reserve/publish/status/release, atomic acceptance, capacity accounting, idempotent retry, thread-safe). |
| `src\gpwcf\core\supporting_patterns\error_handling\error_handling_unit.py` | `HandledErrorOccurrenceReference` (producerSPUIdentity + occurrenceIdentity pair), `ErrorHandlingOperationEntry[THandlingOperationResult]` (9 contract fields, composite identity, provenance + target-occurrence rules), `ErrorHandlingUnit[TErrorHandlingUnitInput, THandlingOperationResult]` (ABC; assigned identity; `execute(input, operationEntryPublisher) -> None`), `ErrorHandlerResult[THandlingOperationEntry, TErrorHandlingContext = object]` (non-empty aggregate + optional context; NO ErrorResult containment), `RecoveryOwner` + `RecoveryEscrowRecord` (verifiable custody escrow/transfer). |
| `src\gpwcf\core\supporting_patterns\error_handling\composition.py` *(new)* | `ErrorHandlingComposition[THandlingOperationResult, TErrorHandlingContext = object]` — `create_publisher` (owns-and-supplies-per-invocation), `collect_accepted_entries`, `assemble` (preserves entries without merging; rejects empty), `unresolved_reservations` (invocation-closure check). |
| `src\gpwcf\core\supporting_patterns\error_handling\__init__.py` | Public surface of the pattern package. |

## Test files implemented

- `tests\core\supporting_patterns\error_handling\test_operation_entry_publisher.py` — 24 tests
  (reserve/grant binding; attempt-identity burn on grant AND rejection; capacity/over-reserve;
  invocation-closing rejection; atomic acceptance incl. capacity transition; foreign reservations;
  attempt/unit/step/association/target/invocation binding mismatches with no-partial-acceptance;
  publish-on-Released; idempotent retry acknowledging the ORIGINAL sequence; conflicting reuse and
  same-composite-different-content as CONTRACT_VIOLATION; never a second entry; Publication
  Acceptance Order + monotonic sequence metadata; status three-states + unknown/foreign distinct
  (None) + no-mutation; release rules incl. Consumed rejection and idempotent re-release;
  forbidden transitions structurally unrepresentable; capacity invariant over full lifecycle;
  forged reservation construction rejected; constructor validation).
- `tests\core\supporting_patterns\error_handling\test_error_handling_unit.py` — 19 tests
  (assigned unit identity; execute returns None + no entries-collection API; scripted concrete unit
  walkthrough attempt→reserve→grant→operation identity→publish; rejection means no operation
  begins; reject-then-retry via status Reserved; lost-ack resolved via status Consumed — never a
  second entry; exception before acceptance preserves result and keeps reservation Reserved;
  unaccepted result escrowed to the designated RecoveryOwner; release-when-no-result; entry
  structure rules incl. duplicate-target rejection and producer-pair identity; ErrorHandlerResult
  aggregation without merging / never-empty / no-ErrorResult-containment / optional context;
  RecoveryOwner take/transfer verifiability; composition ownership, collection, aggregation,
  closure check).
- `tests\architecture\test_error_handling_boundaries.py` *(new)* — 4 tests (AST scans:
  pattern imports NO `gpwcf` module at all — `ErrorHandlingUnit -> Core : NO dependency` — and no
  Prefect; `ErrorHandlerResult` carries exactly the two aggregate fields and references no
  `ErrorResult` symbol in executable code; `ErrorHandlingUnit.execute(self, input,
  operation_entry_publisher) -> None` with no entries-collection API; cross-layer identities are
  opaque string values while pattern-owned identities are the six local nominal types).

## Protocol flow (extracted from `02_Error_Handling_Sequence.puml`)

```
StepComposition -> ErrorHandlingUnit   : authorize invocation under Association
ErrorHandlingUnit -> Publisher        : reserve(handlingOperationAttemptIdentity)
Publisher -> Reservation              : grant ReservationGrant (Reserved)
Reservation -> Unit                   : PublicationReservation
ErrorHandlingUnit -> self             : produce THandlingOperationResult
ErrorHandlingUnit -> Publisher        : publish(reservation, ErrorHandlingOperationEntry)
Publisher -> self                     : atomic acceptance linearization point
Publisher -> Unit                     : PublicationAccepted (reservation Consumed)
Publisher -> self                     : retain complete entry
Unit -> ErrorHandlerResult            : assemble operation entries
StepComposition -> self               : integrate as optional errorHandlerResult of StepExecutionResult
```
Rules: no partial acceptance; reservation states `Reserved -> Consumed | Released` only.

## Implementation checklist

- [x] `ErrorHandlingUnit` executes authorized handling operations against target occurrences/resources; produces a specialized `THandlingOperationResult` per operation.
- [x] Identity discipline per attempt/execution (from contract):
      `handlingOperationAttemptIdentity` assigned **before reserve**;
      `handlingOperationIdentity` assigned **after grant, before execution**;
      entries preserve both and must match the reservation binding.
- [x] Ownership: result stays under Unit responsibility **until Publisher atomic acceptance**;
      `publish()` or lost acknowledgement alone neither transfers nor negates ownership.
- [x] `OperationEntryPublisher` protocol: `reserve(attemptIdentity)`, `publish(reservation, entry)`,
      `get_publication_status(reservation)`, `release(reservation)`.
- [x] **Atomic acceptance**: single linearization point (one lock hold: state→Consumed + entry
      retained + sequence assigned); entry retained iff reservation transitions
      `Reserved -> Consumed`; never partially accepted; never duplicate entry for one reservation.
- [x] `PublicationReservation`: opaque single-use capability; states `Reserved/Consumed/Released`;
      forbidden transitions rejected (Consumed→anything, Released→Consumed, double-consume).
- [x] Capacity invariant: `TotalCapacity >= ReservedCapacity + OccupiedCapacity` (publisher-level accounting).
- [x] `ErrorHandlerResult[THandlingOperationEntry, TErrorHandlingContext]`: aggregate of accepted
      operation entries + handling context; targets referenced via `producerSPUIdentity` +
      `occurrenceIdentity` only.
- [x] `ErrorHandlerResult` must NOT contain, mutate, or erase `ErrorResult` (separation rule).
- [x] `RecoveryOwner`: named entity owning ambiguous-acceptance escrow; takes/retains custody of the
      complete result/entry on pre-acceptance publisher contract violation or indeterminate acceptance.

## Acceptance criteria (from task JSON)

- [x] Error Handling Unit performs handling operations and produces THandlingOperationResult
- [x] OperationEntryPublisher atomic acceptance linearization point implemented
- [x] PublicationReservation states Reserved/Consumed/Released with forbidden transitions
- [x] Capacity invariant: TotalCapacity >= ReservedCapacity + OccupiedCapacity
- [x] ErrorHandlerResult aggregate of operation entries with target occurrence references
- [x] Recovery Owner named with ambiguous-acceptance escrow procedure
- [x] No ErrorResult containment/mutation by ErrorHandlerResult

## Definition of Done

- [x] Publisher contract tests for reserve/publish/status/release
- [x] Atomic acceptance tests (no partial acceptance, no duplicate entry)
- [x] Reservation state-machine tests (valid transitions accepted, forbidden transitions raise)
- [x] Capacity invariant tests (over-reserve rejected)
- [x] Recovery Owner custody transfer tests
- [x] Architecture test: no ErrorResult containment by ErrorHandlerResult (AST/attribute scan)
- [x] `pytest` green — **214 passed, 1 skipped** (43 new; 171 from prior tasks; the skip is the
      deliberate placeholder-tolerant `StepExecutionResult` deep check from task 01)

## Boundary rules

- From `04_Supporting_Pattern_Optional_Dependency.dot`:
  `ErrorHandlingUnit -> Core : NO dependency`, `ErrorHandlingUnit -> Prefect : NO dependency`,
  `Step -> ErrorHandlingUnit : optional selection` — enforced by
  `tests\architecture\test_error_handling_boundaries.py` (no `gpwcf.*` import anywhere in the
  pattern package; pattern-local identity types; stdlib only).
- Error Handling Units never gain ownership of SPUError occurrences nor permission to mutate ErrorResult
  (targets referenced as (producerSPUIdentity, occurrenceIdentity) pairs only).

## Task 04 / Task 07 boundary (what was deliberately left for task 07)

Task 04 owns the WORKING protocol machinery (implemented here). Task 07
(`Single_Step_Publication_Specialization_Contract.json`) owns the mandatory per-Step
SPECIALIZATION: concrete protocol envelopes with correlation/diagnostics, the evidenced no-fail
transfer strategy for `THandlingOperationResult`, status retention/expiry policy, custody traces,
named recovery procedure, and concrete identity generation policy. The placeholder docstrings in
`operation_entry_publisher.py` labeled "task 07" were mislabeled — the file belongs to task 04 per
this TODO's file table; task 07 refines on top.

## Notes for later tasks

- Task 02 (Step): `ErrorHandlerResult` integrates as the optional `errorHandlerResult` field of
  `StepExecutionResult`; the Step-specific Error Handling Composition decides aggregation timing.
- Task 07: specialize the envelopes (`ReservationGrant`/ack correlation fields), evidence the
  no-fail transfer strategy, add status retention/expiry and custody traces; keep
  `PublisherContractViolation` distinguishable from `PublicationRejection`.
