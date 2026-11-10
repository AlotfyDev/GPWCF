# TODO 07 — Publication / Atomic Acceptance

**Status:** ✅ implemented | **Priority:** high | **Effort:** high | **Depends on:** 04

**Task JSON:** `.docs\00.05_Implementation_Tasks\07_Publication.json`
**Dossier:** `.docs\00.06_Implementation_TODOs\dossiers\07_Publication.md`

## Read first

1. Task JSON + dossier (parsed publication class diagram + specialization sequence).
2. `.docs\00.00_Primary_Architecture\Stage_Step_Level\01.02_Step_Error_Handling\Single_Step_Publication_Specialization_Contract.json`
3. `.docs\00.00_Primary_Architecture\Common\11,00_Publication.json`
4. `.docs\00.00_Primary_Architecture\Stage_Step_Level\01.02_Step_Error_Handling\OperationEntryPublisher_Contract.json` (already read in task 04)

## Source files to implement

| File | Notes |
|------|-------|
| `src\gpwcf\core\supporting_patterns\error_handling\operation_entry_publisher.py` | replace placeholders `ReservationGrant`, `PublicationAcknowledgement`, `PublicationStatus`, `PublicationRejection`, `ReleaseAcknowledgement`, `PublisherContractViolation` |
| New: `src\gpwcf\core\supporting_patterns\error_handling\recovery.py` | `RecoveryOwner` specialization surface + custody/escrow procedure + `publicationSequenceNumber` rules |

## Test files to implement

- Extend `tests\core\supporting_patterns\error_handling\test_operation_entry_publisher.py`
- New: `tests\core\supporting_patterns\error_handling\test_publication_specialization.py`
  (representation tests, recovery/custody, idempotent retry, ambiguous outcomes)

## Implementation checklist

- [x] Concrete protocol representations (the **mandatory per-Step** Single Step Publication Specialization):
      `ReservationGrant` (granted / rejected / violation outcome, publisher-bound),
      `PublicationAcknowledgement` (identifies the accepted publication),
      `PublicationStatus` (Reserved / Consumed / Released),
      `PublicationRejection` (request-level failure — **no acceptance occurred**),
      `ReleaseAcknowledgement` (released reservation confirmed),
      `PublisherContractViolation` (publisher breached a guarantee attached to a valid reservation).
- [x] No-fail final ownership-transfer strategy for `THandlingOperationResult` and
      `ErrorHandlingOperationEntry`: the acceptance point never throws through the boundary;
      complete-entry transfer is non-throwing.
- [x] Named **Step-owned** Recovery Owner + recovery procedure for:
      publisher contract violation, indeterminate/ambiguous acceptance.
- [x] Identity rules: generation, uniqueness, stability, retirement/reuse
      (including `publicationSequenceNumber`).
- [x] Publication-status record retention: retention window, tombstone, expiry rules.
- [x] End-to-end state & custody trace covering **all branches**:
      granted→published→accepted; granted→published→indeterminate→escrow; rejected;
      released; violation→escrow.
- [x] **Exception/missing acknowledgement is never treated as proof of rejection** —
      ambiguous outcomes route to Recovery Owner escrow instead.
- [x] Idempotent retry: same logical entry with a consumed reservation must not duplicate.

## Acceptance criteria (from task JSON)

- [x] Concrete publication protocol representations defined per Step
- [x] No-fail final ownership-transfer strategy for THandlingOperationResult and ErrorHandlingOperationEntry
- [x] Named Step-owned Recovery Owner with recovery procedure for contract violation/indeterminate acceptance
- [x] Identity generation, uniqueness, stability, retirement, reuse rules defined
- [x] Publication-status retention, tombstone, expiry rules defined
- [x] End-to-end state and custody trace covering all branches
- [x] Exception/missing acknowledgement never treated as proof of rejection

## Definition of Done

- [x] Publication protocol representation tests
- [x] Recovery Owner custody transfer tests
- [x] Idempotent retry tests (same logical entry, consumed reservation)
- [x] Architecture test: TBD not permitted for required specializations
      (e.g. scan for `NotImplementedError`/`TODO` in the publication module)
- [x] `pytest` green

## Boundary rules

- Same optional-dependency rules as task 04 (no Core/Prefect dependency from the pattern).
- The specialization is per-Step owned; framework code provides the reusable protocol shape,
  not a global publisher singleton.

## Implementation summary (2026-11-10)

- `operation_entry_publisher.py` — task 04 machinery enriched with the specialization
  surface: correlated envelopes (`ReservationGrant` with capacity-commitment evidence;
  accepted `PublicationAcknowledgement` with full correlation incl. the derived
  `AcceptedEntryIdentity` + `publicationSequenceNumber`; `PublisherContractViolation`
  with the minimum evidence set: violation identity/code, known identities, phase,
  acceptance knowledge, violated guarantee, custodian marker, recovery reference),
  `AcceptanceKnowledge` / `StatusQueryOutcome` enums, the full
  `PublicationStatusQuery` envelope (query OUTCOMES ≠ lifecycle STATES;
  `get_publication_status` remains the simple task-04 accessor),
  `PreallocatedEntryEnvelope` (no-fail fixed-slot reference transfer preallocated at
  reserve), `PublicationSequencePolicy` / `PublicationIdentityPolicy` /
  `PublicationStatusRetentionPolicy`, `derive_accepted_entry_identity()`, and
  tombstone-aware `retire_terminal_records()` (Reserved never removable → ValueError;
  Consumed retirement returns occupied capacity and drops the entry from the accepted
  view; stale capabilities rejected with reason `reservation-expired`; late queries
  report EXPIRED — never definitely-not-accepted).
- `recovery.py` (new) — the Recovery Owner specialization surface: `CustodyPhase` /
  `CustodyDisposition` / `CustodyTraceEntry` / `CustodyTraceRecorder` (end-to-end
  custody trace), `AmbiguousAcceptanceEscrow` + `AmbiguousAcceptanceEscrowRecord`
  (complete result/entry retained, NON-publishable, correlated, exactly-once
  reconciliation via `reconcile_as_accepted` / `retain_as_recovery_custody` /
  `escalate_unresolved` / `transfer_to_alternate_owner`), `RecoveryDecision`
  (replacement execution never permitted; retry only on authoritative Reserved), and
  `PublicationRecoveryProcedure` (`resolve_ambiguous_publication` — status=None or
  Unknown/Indeterminate/Unavailable/InvalidCapability/Expired → escrow + escalate,
  never proof of rejection; Consumed → reconcile, no duplicate publication;
  Reserved → same-entry same-reservation retry; Released-with-pending-result →
  violation, owner retains — and `resolve_publisher_contract_violation` with
  definitely-accepted reconciliation / definitely-not-accepted retention /
  indeterminate escalation; `confirm_recovery_owner_custody` for verifiable
  two-sided transfer). Re-exports the three policy types as the specialization
  surface.
- `composition.py` — `retire_publication_records(publisher, reservations)`:
  the explicit Composition-owned reclamation decision after aggregation.
- `__init__.py` — all new specialization names exported.
- Tests: publisher file extended (envelope evidence, correlation, query envelope
  outcomes, no-fail acceptance with poisoned user-defined `__eq__`/copy hooks,
  retirement/tombstone/expiry rules, policy validators, replacement-Publisher
  sequence scope); new `test_publication_specialization.py` drives a concrete
  `StepPublicationFlow` through the 12 mandatory endToEndContract branches with
  custody-trace assertions, escrow exactly-once/dedup, sequence monotonicity,
  identity no-reuse, and post-aggregation reclamation; architecture test
  `test_publication_specialization_has_no_tbd_or_unimplemented_code` scans the
  pattern for `raise NotImplementedError` (abstract-stub exempt) and
  TODO/TBD/FIXME markers.
- Suite: **258 passed, 1 skipped** (was 214 passed, 1 skipped after task 04).
