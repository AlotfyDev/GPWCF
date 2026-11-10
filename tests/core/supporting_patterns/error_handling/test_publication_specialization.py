"""Single Step Publication Specialization tests (task 07).

Exercises the mandatory per-Step branches of
``Single_Step_Publication_Specialization_Contract.json`` (endToEndContract)
against the working specialization surface (publisher + recovery.py), with the
custody trace of ``Common/11,00_Publication.json`` asserted on every branch:

  1.  reservation rejected before the operation starts
  2.  operation throws pre-result (nothing produced, explicit release)
  3.  entry preparation fails (result keeps Unit custody -> Recovery Owner)
  4.  accepted + acknowledgement observed (happy path + aggregation)
  5.  accepted + acknowledgement lost (reconciled against Consumed evidence)
  6.  publish rejected pre-acceptance (same-entry retry permitted)
  7.  Publisher contract violation definitely-before-acceptance (owner retains)
  8.  violation indeterminate / status unavailable (escrow + escalate)
  9.  idempotent same-entry retry under a Consumed reservation
  10. conflicting different content under a Consumed reservation
  11. invocation closure while a publication is unresolved
  12. Recovery Owner custody, alternate-owner transfer, exactly-once
      reconciliation of escrow records

Plus: escrow records are non-publishable and never counted in
``ErrorHandlerResult``; replacement execution is never permitted; sequence
monotonicity/no-duplicates; identity no-reuse; Composition-owned retention
reclamation (tombstones, EXPIRED, Reserved never removed).
"""

import pytest

from gpwcf.core.supporting_patterns.error_handling import (
    AcceptanceKnowledge,
    AmbiguousAcceptanceEscrow,
    CustodyDisposition,
    CustodyPhase,
    CustodyTraceRecorder,
    ErrorHandlingComposition,
    ErrorHandlingOperationEntry,
    HandledErrorOccurrenceReference,
    PublicationIdentityPolicy,
    PublicationOutcome,
    PublicationRecoveryProcedure,
    PublicationSequencePolicy,
    PublicationStatus,
    PublicationStatusRetentionPolicy,
    PublisherContractViolation,
    RecoveryDecision,
    RecoveryOwner,
    StatusQueryOutcome,
    derive_accepted_entry_identity,
)
from gpwcf.core.supporting_patterns.error_handling.identities import (
    ErrorHandlingInvocationIdentity,
    ErrorHandlingUnitIdentity,
    HandlingOperationAttemptIdentity,
    HandlingOperationIdentity,
    OperationEntryPublisherIdentity,
)
from gpwcf.core.supporting_patterns.error_handling.operation_entry_publisher import (
    OperationEntryPublisher,
)

PUBLISHER_ID = OperationEntryPublisherIdentity("publisher-step-1")
UNIT_ID = ErrorHandlingUnitIdentity("unit-1")
INVOCATION_ID = ErrorHandlingInvocationIdentity("invocation-1")
STEP_ID = "step-instance-1"
ASSOC_ID = "association-1"
TARGET_ID = "association-target-1"


def an_entry(
    attempt: HandlingOperationAttemptIdentity,
    operation: str = "op-1",
    *,
    result: object = "handled:resolved",
) -> ErrorHandlingOperationEntry[str]:
    return ErrorHandlingOperationEntry[str](
        error_handling_unit_identity=UNIT_ID,
        handling_operation_attempt_identity=attempt,
        handling_operation_identity=HandlingOperationIdentity(operation),
        error_handling_invocation_identity=INVOCATION_ID,
        step_instance_identity=STEP_ID,
        error_handling_unit_association_identity=ASSOC_ID,
        association_target_identity=TARGET_ID,
        target_occurrence_references=(
            HandledErrorOccurrenceReference("spu-1", "occ-1"),
        ),
        operation_result=result,  # type: ignore[arg-type]
    )


class StepPublicationFlow:
    """A minimal concrete Step instantiation of the specialization surface.

    Wires the Composition-owned Publisher, the Step-named Recovery Owner, the
    ambiguous-acceptance escrow, and the custody trace the way a concrete Step
    contract must. Every branch below drives this flow.
    """

    def __init__(self, total_capacity: int = 2) -> None:
        self.composition = ErrorHandlingComposition()
        self.publisher: OperationEntryPublisher[str] = self.composition.create_publisher(
            PUBLISHER_ID,
            invocation_identity=INVOCATION_ID,
            error_handling_unit_identity=UNIT_ID,
            step_instance_identity=STEP_ID,
            error_handling_unit_association_identity=ASSOC_ID,
            association_target_identity=TARGET_ID,
            total_capacity=total_capacity,
        )
        self.trace = CustodyTraceRecorder()
        self.escrow = AmbiguousAcceptanceEscrow()
        self.recovery_owner = RecoveryOwner("step-1-recovery-owner")
        self.procedure = PublicationRecoveryProcedure(
            self.recovery_owner, self.escrow, self.trace
        )
        self.operation_started = False

    # -- Step flow phases (the Unit/Composition responsibilities) ----------

    def reserve(self, attempt: HandlingOperationAttemptIdentity):
        self.trace.record(
            CustodyPhase.BEFORE_RESULT_PRODUCTION,
            handling_operation_attempt_identity=attempt.value,
            note="reserve requested before the operation begins",
        )
        return self.publisher.reserve(attempt)

    def run_operation(self, *, fail: bool = False) -> str:
        self.operation_started = True
        if fail:
            raise ValueError("handling operation failed before producing a result")
        return "handled:resolved"

    def prepare_entry(
        self, attempt: HandlingOperationAttemptIdentity, result: str, *,
        fail: bool = False,
        operation: str = "op-1",
    ) -> ErrorHandlingOperationEntry[str]:
        if fail:
            raise ValueError("entry preparation failed in the Unit")
        entry = an_entry(attempt, operation, result=result)
        self.trace.record(
            CustodyPhase.RESULT_PRODUCED_BEFORE_ACCEPTANCE,
            handling_operation_attempt_identity=attempt.value,
            note="complete entry prepared; Unit retains custody",
        )
        return entry

    def publish(self, reservation, entry):
        ack = self.publisher.publish(reservation, entry)
        if ack.outcome is PublicationOutcome.ACCEPTED and not ack.idempotent_retry:
            self.trace.record(
                CustodyPhase.ATOMIC_ACCEPTANCE,
                reservation_identity=reservation.identity.value,
                handling_operation_attempt_identity=(
                    reservation.handling_operation_attempt_identity.value
                ),
                note="atomic acceptance; retention transferred to Composition",
            )
        return ack

    def collect_and_aggregate(self):
        entries = self.composition.collect_accepted_entries(self.publisher)
        self.trace.record(
            CustodyPhase.AFTER_AGGREGATION,
            note=f"{len(entries)} accepted entries collected into the aggregate",
        )
        return self.composition.assemble(entries)


# --------------------------------------------------------------------------
# branch 1 — reservation rejected before the operation starts
# --------------------------------------------------------------------------


def test_branch_1_reservation_rejected_before_start_burns_no_operation():
    flow = StepPublicationFlow(total_capacity=1)
    granted = flow.reserve(HandlingOperationAttemptIdentity("attempt-1"))
    assert granted.granted

    # capacity is fully committed; a new attempt's reserve is rejected
    rejected = flow.reserve(HandlingOperationAttemptIdentity("attempt-2"))

    assert not rejected.granted
    assert rejected.rejection is not None
    assert rejected.rejection.reason == "capacity-exhausted"
    assert rejected.capacity_committed is False
    # the Unit must NOT begin the Handling Operation for the rejected attempt
    assert flow.operation_started is False


# --------------------------------------------------------------------------
# branch 2 — operation throws pre-result
# --------------------------------------------------------------------------


def test_branch_2_operation_throws_pre_result_no_entry_no_acceptance():
    flow = StepPublicationFlow()
    attempt = HandlingOperationAttemptIdentity("attempt-1")
    grant = flow.reserve(attempt)
    assert grant.granted and grant.reservation is not None

    with pytest.raises(ValueError, match="before producing"):
        flow.run_operation(fail=True)

    # Nothing was produced: no publish, no acceptance, and an EXPLICIT release
    # decision (release is never inferred from the exception).
    ack = flow.publisher.release(grant.reservation)
    assert ack.released
    assert grant.reservation.state is PublicationStatus.RELEASED
    assert flow.publisher.accepted_entries() == ()
    assert flow.composition.unresolved_reservations(flow.publisher) == ()
    phases = flow.trace.phases()
    assert CustodyPhase.BEFORE_RESULT_PRODUCTION in phases
    assert CustodyPhase.ATOMIC_ACCEPTANCE not in phases


# --------------------------------------------------------------------------
# branch 3 — entry preparation fails: result keeps custody via Recovery Owner
# --------------------------------------------------------------------------


def test_branch_3_entry_preparation_failure_keeps_result_in_recovery_custody():
    flow = StepPublicationFlow()
    attempt = HandlingOperationAttemptIdentity("attempt-1")
    grant = flow.reserve(attempt)
    assert grant.reservation is not None
    result = "handled:resolved-but-entry-failed"
    flow.operation_started = True

    with pytest.raises(ValueError, match="preparation"):
        flow.prepare_entry(attempt, result, fail=True)

    # The result is NOT discarded: explicit, verifiable transfer to the named
    # Recovery Owner BEFORE unwinding (a Unit-local variable is not an owner).
    disposition = flow.procedure.confirm_recovery_owner_custody(
        record_identity="custody-attempt-1",
        reason="entry preparation failed; result retains recovery custody",
        result=result,
        attempt_identity=attempt,
    )
    assert disposition is CustodyDisposition.RECOVERY_OWNER_RETAINED
    assert len(flow.recovery_owner.escrow_records()) == 1
    held = flow.recovery_owner.escrow_records()[0]
    assert held.custodied_result == result
    assert flow.publisher.accepted_entries() == ()
    assert flow.trace.phases()[-1] is CustodyPhase.EXPLICIT_RECOVERY_TRANSFER


# --------------------------------------------------------------------------
# branch 4 — accepted + acknowledgement observed
# --------------------------------------------------------------------------


def test_branch_4_accepted_with_acknowledgement_aggregates_with_no_custody_gap():
    flow = StepPublicationFlow()
    attempt = HandlingOperationAttemptIdentity("attempt-1")
    grant = flow.reserve(attempt)
    assert grant.reservation is not None
    result = flow.run_operation()
    entry = flow.prepare_entry(attempt, result)

    ack = flow.publish(grant.reservation, entry)

    assert ack.outcome is PublicationOutcome.ACCEPTED
    assert ack.accepted_entry_identity == derive_accepted_entry_identity(entry)
    assert grant.reservation.state is PublicationStatus.CONSUMED
    aggregate = flow.collect_and_aggregate()
    assert aggregate.operation_entries == (entry,)
    # the end-to-end trace proves there is no custody gap on this branch
    assert flow.trace.phases() == (
        CustodyPhase.BEFORE_RESULT_PRODUCTION,
        CustodyPhase.RESULT_PRODUCED_BEFORE_ACCEPTANCE,
        CustodyPhase.ATOMIC_ACCEPTANCE,
        CustodyPhase.AFTER_AGGREGATION,
    )


# --------------------------------------------------------------------------
# branch 5 — accepted + acknowledgement lost
# --------------------------------------------------------------------------


def test_branch_5_acceptance_with_lost_acknowledgement_reconciles_from_status():
    flow = StepPublicationFlow()
    attempt = HandlingOperationAttemptIdentity("attempt-1")
    grant = flow.reserve(attempt)
    assert grant.reservation is not None
    entry = flow.prepare_entry(attempt, flow.run_operation())
    flow.publish(grant.reservation, entry)
    # the acknowledgement is lost before the Unit observes it
    lost = True  # (ack variable intentionally dropped by the flow above)

    status = flow.publisher.query_publication_status(grant.reservation)
    decision = flow.procedure.resolve_ambiguous_publication(
        result="handled:resolved",
        entry=entry,
        attempt_identity=attempt,
        reservation=grant.reservation,
        status=status,
    )
    assert lost
    # authoritative Consumed evidence: accepted, never duplicated
    assert decision.disposition is CustodyDisposition.PUBLISHER_ACCEPTED
    assert decision.retry_permitted is False
    assert decision.replacement_execution_permitted is False
    assert flow.escrow.escrow_records() == ()
    assert flow.publisher.accepted_entries() == (entry,)
    assert flow.procedure._trace is not None
    assert flow.trace.phases()[-1] is CustodyPhase.ATOMIC_ACCEPTANCE


# --------------------------------------------------------------------------
# branch 6 — publish rejected pre-acceptance: same-entry retry permitted
# --------------------------------------------------------------------------


def test_branch_6_publish_rejected_pre_acceptance_permits_same_entry_retry():
    flow = StepPublicationFlow()
    attempt = HandlingOperationAttemptIdentity("attempt-1")
    grant = flow.reserve(attempt)
    assert grant.reservation is not None
    entry = flow.prepare_entry(attempt, flow.run_operation())
    other_attempt_entry = an_entry(HandlingOperationAttemptIdentity("attempt-X"))

    rejected = flow.publish(grant.reservation, other_attempt_entry)

    assert rejected.outcome is PublicationOutcome.REJECTED
    assert rejected.detail is not None
    assert rejected.detail.reason == "attempt-identity-mismatch"
    # nothing was accepted; the reservation is still Reserved and trustworthy
    assert grant.reservation.state is PublicationStatus.RESERVED
    assert flow.publisher.accepted_entries() == ()
    status = flow.publisher.query_publication_status(grant.reservation)
    assert status.lifecycle_state is PublicationStatus.RESERVED
    decision = flow.procedure.resolve_ambiguous_publication(
        result="handled:resolved",
        entry=entry,
        attempt_identity=attempt,
        reservation=grant.reservation,
        status=status,
    )
    assert decision.retry_permitted is True
    assert decision.disposition is None
    assert decision.replacement_execution_permitted is False
    # the SAME immutable entry under the SAME reservation is then accepted
    retry = flow.publish(grant.reservation, entry)
    assert retry.outcome is PublicationOutcome.ACCEPTED


# --------------------------------------------------------------------------
# branch 7 — contract violation definitely-before-acceptance
# --------------------------------------------------------------------------


def test_branch_7_violation_definitely_before_acceptance_recovery_owner_retains():
    flow = StepPublicationFlow()
    attempt = HandlingOperationAttemptIdentity("attempt-1")
    grant = flow.reserve(attempt)
    assert grant.reservation is not None
    entry = flow.prepare_entry(attempt, flow.run_operation())

    violation = PublisherContractViolation(
        "reservation released while a produced result was pending publication",
        violation_code="released-with-pending-result",
        violation_identity="violation-1",
        publisher_identity=PUBLISHER_ID,
        publication_reservation_identity=grant.reservation.identity,
        handling_operation_attempt_identity=attempt,
        phase="atomic-acceptance",
        acceptance_knowledge=AcceptanceKnowledge.DEFINITELY_NOT_ACCEPTED,
        violated_guarantee="release-never-loses-a-pending-result",
        custodian_marker="recovery-owner:step-1-recovery-owner",
    )
    decision = flow.procedure.resolve_publisher_contract_violation(
        violation=violation,
        result="handled:resolved",
        entry=entry,
        attempt_identity=attempt,
    )

    assert decision.disposition is CustodyDisposition.RECOVERY_OWNER_RETAINED
    assert decision.retry_permitted is False
    assert decision.replacement_execution_permitted is False
    records = flow.escrow.escrow_records()
    assert len(records) == 1
    record = records[0]
    assert record.publishable is False
    assert record.entry is entry and record.result == "handled:resolved"
    assert record.publication_reservation_identity == grant.reservation.identity.value
    assert record.handling_operation_attempt_identity == attempt.value
    assert flow.escrow.record_disposition(record.escrow_identity) is (
        CustodyDisposition.RECOVERY_OWNER_RETAINED
    )


# --------------------------------------------------------------------------
# branch 8 — violation indeterminate / status unavailable: escrow + escalate
# --------------------------------------------------------------------------


def test_branch_8_status_unavailable_escrows_complete_result_and_escalates():
    flow = StepPublicationFlow()
    attempt = HandlingOperationAttemptIdentity("attempt-1")
    grant = flow.reserve(attempt)
    assert grant.reservation is not None
    entry = flow.prepare_entry(attempt, flow.run_operation())
    # the publish outcome AND the status query are both unresolved (no ack, no
    # authoritative status): acceptance knowledge stays INDETERMINATE.
    status = None  # the status query itself failed/transported nothing

    decision = flow.procedure.resolve_ambiguous_publication(
        result="handled:resolved",
        entry=entry,
        attempt_identity=attempt,
        reservation=grant.reservation,
        status=status,
    )

    assert decision.disposition is CustodyDisposition.UNRESOLVED_ESCALATED
    assert decision.retry_permitted is False
    assert decision.replacement_execution_permitted is False
    record = decision.escrow_record
    assert record is not None
    assert record.publishable is False
    assert record.entry is entry  # the COMPLETE result, not only identities
    assert record.accepted_entry_identity == derive_accepted_entry_identity(entry).value
    # the reservation was never touched: the outcome is unresolved, not rejected
    assert grant.reservation.state is PublicationStatus.RESERVED
    assert flow.trace.phases()[-1] is CustodyPhase.ACCEPTANCE_INDETERMINATE
    # a decision record never permits a replacement execution
    with pytest.raises(ValueError):
        RecoveryDecision(
            disposition=CustodyDisposition.UNRESOLVED_ESCALATED,
            replacement_execution_permitted=True,
        )


# --------------------------------------------------------------------------
# branch 9 — idempotent same-entry retry under a Consumed reservation
# --------------------------------------------------------------------------


def test_branch_9_idempotent_retry_reidentifies_the_original_acceptance():
    flow = StepPublicationFlow()
    attempt = HandlingOperationAttemptIdentity("attempt-1")
    grant = flow.reserve(attempt)
    assert grant.reservation is not None
    entry = flow.prepare_entry(attempt, flow.run_operation())
    first = flow.publish(grant.reservation, entry)

    retry = flow.publisher.publish(grant.reservation, entry)

    assert retry.outcome is PublicationOutcome.ACCEPTED
    assert retry.idempotent_retry is True
    assert retry.publication_sequence_number == first.publication_sequence_number
    assert retry.accepted_entry_identity == first.accepted_entry_identity
    assert flow.publisher.accepted_entries() == (entry,)
    assert flow.publisher.occupied_capacity == 1


# --------------------------------------------------------------------------
# branch 10 — conflicting different content under a Consumed reservation
# --------------------------------------------------------------------------


def test_branch_10_conflicting_content_is_a_violation_never_a_second_entry():
    flow = StepPublicationFlow()
    attempt = HandlingOperationAttemptIdentity("attempt-1")
    grant = flow.reserve(attempt)
    assert grant.reservation is not None
    accepted = flow.prepare_entry(attempt, flow.run_operation())
    flow.publish(grant.reservation, accepted)

    conflicting = an_entry(attempt, result="handled:TAMPERED")
    ack = flow.publisher.publish(grant.reservation, conflicting)

    assert ack.outcome is PublicationOutcome.CONTRACT_VIOLATION
    assert ack.detail is not None
    assert ack.detail.reason == "conflicting-entry-content"
    # the original acceptance stands; no second entry can exist
    assert flow.publisher.accepted_entries() == (accepted,)
    # the ORIGINAL was definitely accepted: the recovery procedure reconciles
    decision = flow.procedure.resolve_publisher_contract_violation(
        violation=PublisherContractViolation(
            "conflicting reuse of a Consumed reservation",
            violation_code="conflicting-entry-content",
            publisher_identity=PUBLISHER_ID,
            publication_reservation_identity=grant.reservation.identity,
            acceptance_knowledge=AcceptanceKnowledge.DEFINITELY_ACCEPTED,
            phase="post-acceptance",
        ),
        result="handled:TAMPERED",
        entry=conflicting,
        attempt_identity=attempt,
    )
    assert decision.disposition is CustodyDisposition.PUBLISHER_ACCEPTED
    assert flow.escrow.escrow_records() == ()


# --------------------------------------------------------------------------
# branch 11 — closure while a publication is unresolved
# --------------------------------------------------------------------------


def test_branch_11_closure_is_refused_while_publication_is_unresolved():
    flow = StepPublicationFlow()
    attempt = HandlingOperationAttemptIdentity("attempt-1")
    grant = flow.reserve(attempt)
    assert grant.reservation is not None
    entry = flow.prepare_entry(attempt, flow.run_operation())
    # publish outcome lost AND status unavailable -> escrowed and escalated
    flow.procedure.resolve_ambiguous_publication(
        result="handled:resolved",
        entry=entry,
        attempt_identity=attempt,
        reservation=grant.reservation,
        status=None,
    )

    # the invocation cannot be represented as normally and completely closed:
    outstanding = flow.composition.unresolved_reservations(flow.publisher)
    assert outstanding == (grant.reservation,)

    # Reserved records are never removed while custody is unresolved
    with pytest.raises(ValueError):
        flow.composition.retire_publication_records(flow.publisher, outstanding)
    assert flow.publisher.get_publication_status(grant.reservation) is (
        PublicationStatus.RESERVED
    )


# --------------------------------------------------------------------------
# branch 12 — Recovery Owner custody, transfer, exactly-once reconciliation
# --------------------------------------------------------------------------


def test_branch_12_escrow_reconciles_exactly_once_and_never_aggregates_twice():
    flow = StepPublicationFlow()
    attempt = HandlingOperationAttemptIdentity("attempt-1")
    grant = flow.reserve(attempt)
    assert grant.reservation is not None
    entry = flow.prepare_entry(attempt, flow.run_operation())
    flow.publisher.publish(grant.reservation, entry)  # accepted; ack lost
    decision = flow.procedure.resolve_ambiguous_publication(
        result="handled:resolved",
        entry=entry,
        attempt_identity=attempt,
        reservation=grant.reservation,
        status=flow.publisher.query_publication_status(grant.reservation),
    )
    assert decision.disposition is CustodyDisposition.PUBLISHER_ACCEPTED

    # a later escalating record (different attempt) reconciles exactly once
    other = HandlingOperationAttemptIdentity("attempt-2")
    other_entry = flow.prepare_entry(other, "handled:second", fail=False)
    escalated = flow.procedure.resolve_ambiguous_publication(
        result="handled:second",
        entry=other_entry,
        attempt_identity=other,
        reservation=None,
        status=None,
    )
    escrow_identity = escalated.escrow_record.escrow_identity  # type: ignore[union-attr]
    # the record is held PENDING: the escalation is the procedure's decision,
    # the FINAL disposition is recorded by the exactly-once reconciliation
    assert flow.escrow.record_disposition(escrow_identity) is None
    assert flow.escrow.pending_records()[0].escrow_identity == escrow_identity
    # evidence later becomes determinable: reconcile against Consumed
    reconciled = flow.escrow.reconcile_as_accepted(
        escrow_identity, note="publisher later proved acceptance"
    )
    assert reconciled.reconciled is True
    assert reconciled.disposition is CustodyDisposition.PUBLISHER_ACCEPTED
    # exactly once: any further reconciliation is refused
    with pytest.raises(ValueError):
        flow.escrow.reconcile_as_accepted(escrow_identity)
    with pytest.raises(ValueError):
        flow.escrow.escalate_unresolved(escrow_identity)


def test_escalation_closes_the_step_horizon_for_a_pending_record():
    """When no evidence arrives within the Step's operational horizon, the
    Step explicitly records the escalated final disposition exactly once."""
    flow = StepPublicationFlow()
    attempt = HandlingOperationAttemptIdentity("attempt-1")
    entry = flow.prepare_entry(attempt, "handled:unresolved", fail=False)
    decision = flow.procedure.resolve_ambiguous_publication(
        result="handled:unresolved",
        entry=entry,
        attempt_identity=attempt,
        reservation=None,
        status=None,
    )
    escrow_identity = decision.escrow_record.escrow_identity  # type: ignore[union-attr]
    assert flow.escrow.record_disposition(escrow_identity) is None

    escalated = flow.escrow.escalate_unresolved(
        escrow_identity, note="Step horizon reached without evidence"
    )
    assert escalated.disposition is CustodyDisposition.UNRESOLVED_ESCALATED
    assert flow.escrow.pending_records() == ()
    with pytest.raises(ValueError):
        flow.escrow.reconcile_as_accepted(escrow_identity)


def test_branch_12_escrow_record_is_never_counted_in_the_aggregate():
    flow = StepPublicationFlow()
    attempt = HandlingOperationAttemptIdentity("attempt-1")
    grant = flow.reserve(attempt)
    assert grant.reservation is not None
    entry = flow.prepare_entry(attempt, flow.run_operation())
    flow.procedure.resolve_ambiguous_publication(
        result="handled:unresolved",
        entry=entry,
        attempt_identity=attempt,
        reservation=grant.reservation,
        status=None,  # indeterminate: escrowed, non-publishable
    )
    accepted_entry = an_entry(HandlingOperationAttemptIdentity("attempt-2"), "op-2")
    grant_2 = flow.reserve(HandlingOperationAttemptIdentity("attempt-2"))
    assert grant_2.reservation is not None
    flow.publish(grant_2.reservation, accepted_entry)

    aggregate = flow.collect_and_aggregate()

    # only ACCEPTED entries are aggregated; escrow records never are
    assert aggregate.operation_entries == (accepted_entry,)
    escrowed = flow.escrow.escrow_records()[0]
    assert escrowed.publishable is False
    assert escrowed.entry not in aggregate.operation_entries
    assert flow.publisher.accepted_entries() == (accepted_entry,)


def test_branch_12_escrow_transfers_to_an_alternate_step_owned_owner():
    flow = StepPublicationFlow()
    attempt = HandlingOperationAttemptIdentity("attempt-1")
    entry = flow.prepare_entry(attempt, "handled:transfer-me", fail=False)
    decision = flow.procedure.resolve_ambiguous_publication(
        result="handled:transfer-me",
        entry=entry,
        attempt_identity=attempt,
        reservation=None,
        status=None,
    )
    escrow_identity = decision.escrow_record.escrow_identity  # type: ignore[union-attr]
    alternate_owner = RecoveryOwner("step-1-alternate-owner")

    flow.escrow.transfer_to_alternate_owner(escrow_identity, alternate_owner)

    assert flow.escrow.record_disposition(escrow_identity) is (
        CustodyDisposition.TRANSFERRED_TO_ALTERNATE_OWNER
    )
    transferred = alternate_owner.escrow_records()
    assert len(transferred) == 1
    assert transferred[0].custodied_entry is entry


# --------------------------------------------------------------------------
# specialization invariants across branches
# --------------------------------------------------------------------------


def test_sequences_are_strictly_monotonic_with_no_duplicates_across_acceptances():
    flow = StepPublicationFlow(total_capacity=3)
    sequences = []
    for n in range(3):
        attempt = HandlingOperationAttemptIdentity(f"attempt-{n}")
        grant = flow.reserve(attempt)
        assert grant.reservation is not None
        ack = flow.publish(
            grant.reservation,
            flow.prepare_entry(attempt, f"handled:{n}", fail=False),
        )
        assert ack.outcome is PublicationOutcome.ACCEPTED
        assert ack.publication_sequence_number is not None
        sequences.append(ack.publication_sequence_number)

    PublicationSequencePolicy().validate_acceptance_order(sequences)
    assert sequences == [1, 2, 3]


def test_identity_no_reuse_across_reservations_and_accepted_entries():
    flow = StepPublicationFlow(total_capacity=3)
    reservation_values = []
    accepted_entry_identities = []
    for n in range(3):
        attempt = HandlingOperationAttemptIdentity(f"attempt-{n}")
        grant = flow.reserve(attempt)
        assert grant.reservation is not None
        reservation_values.append(grant.reservation.identity.value)
        ack = flow.publish(
            grant.reservation,
            flow.prepare_entry(
                attempt, f"handled:{n}", fail=False, operation=f"op-{n}"
            ),
        )
        assert ack.accepted_entry_identity is not None
        accepted_entry_identities.append(ack.accepted_entry_identity.value)

    # reservation identities are unique within the issuing Publisher scope
    PublicationIdentityPolicy().validate_no_identity_reuse(reservation_values)
    # each DISTINCT logical entry (composite unit+operation identity) has a
    # distinct accepted-entry identity — no reuse while records refer to them
    PublicationIdentityPolicy().validate_no_identity_reuse(accepted_entry_identities)
    assert accepted_entry_identities == ["unit-1/op-0", "unit-1/op-1", "unit-1/op-2"]
    # the derived entry identity is stable across re-derivation of the SAME
    # logical entry: a cross-attempt retry re-derives the SAME value (that is
    # the retry correlation, never a second entry's identity)
    assert accepted_entry_identities[0] == derive_accepted_entry_identity(
        an_entry(HandlingOperationAttemptIdentity("attempt-0"), "op-0")
    ).value


def test_retirement_after_aggregation_returns_capacity_and_reports_expired():
    flow = StepPublicationFlow(total_capacity=1)
    attempt = HandlingOperationAttemptIdentity("attempt-1")
    grant = flow.reserve(attempt)
    assert grant.reservation is not None
    flow.publish(grant.reservation, flow.prepare_entry(attempt, "handled:done"))
    aggregate = flow.collect_and_aggregate()
    assert len(aggregate.operation_entries) == 1

    reclaimed = flow.composition.retire_publication_records(
        flow.publisher, [grant.reservation]
    )
    assert reclaimed == 1
    assert flow.publisher.occupied_capacity == 0
    assert flow.publisher.accepted_entries() == ()
    query = flow.publisher.query_publication_status(grant.reservation)
    assert query.outcome is StatusQueryOutcome.EXPIRED
    assert query.lifecycle_state is None
    # capacity is reusable after reclamation
    assert flow.reserve(HandlingOperationAttemptIdentity("attempt-2")).granted
    # and the retention policy surface still encodes the rules
    assert PublicationStatusRetentionPolicy().tombstone_on_reclamation is True


def test_recovery_procedure_requires_step_owned_recovery_surfaces():
    with pytest.raises(TypeError):
        PublicationRecoveryProcedure("not-an-owner", AmbiguousAcceptanceEscrow())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        PublicationRecoveryProcedure(RecoveryOwner("owner"), "not-an-escrow")  # type: ignore[arg-type]


def test_custody_trace_is_monotonic_and_never_reordered():
    flow = StepPublicationFlow()
    attempt = HandlingOperationAttemptIdentity("attempt-1")
    grant = flow.reserve(attempt)
    assert grant.reservation is not None
    flow.publish(grant.reservation, flow.prepare_entry(attempt, "handled:ok"))

    entries = flow.trace.entries()
    orders = [entry.order for entry in entries]
    assert orders == sorted(orders) == list(range(1, len(entries) + 1))
    assert len(flow.trace) == len(entries)
    phases = flow.trace.phases()
    assert phases[0] is CustodyPhase.BEFORE_RESULT_PRODUCTION
    assert CustodyPhase.AFTER_AGGREGATION not in phases  # not yet aggregated
