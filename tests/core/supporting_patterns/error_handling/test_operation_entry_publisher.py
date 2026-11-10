"""Contract tests for the OperationEntryPublisher publication protocol.

Task 04 (working machinery, OperationEntryPublisher_Contract.json /
PublicationReservation_Contract.json):
  - reserve/grant: binding identities, opaque capability, attempt-identity rules,
    capacity accounting (over-reserve rejected), invocation-closing rejection
  - publish: atomic acceptance (no partial acceptance, no duplicate entry),
    binding-match validation, foreign/invalid reservations, terminal-state use
  - idempotent retry: same logical entry under a Consumed reservation
    acknowledges the ORIGINAL acceptance; conflicting reuse never accepted
  - get_publication_status: three valid states; unknown/foreign reported
    distinctly (None); lookup never mutates
  - release: capacity return, Consumed rejection, idempotent re-release
  - state machine: forbidden transitions structurally unrepresentable
  - Publication Acceptance Order and monotonic sequence metadata

Task 07 (Single Step Publication Specialization surface):
  - correlated envelopes: grant capacity evidence, accepted-acknowledgement
    full correlation incl. the derived AcceptedEntryIdentity
  - query envelope: StatusQueryOutcome outcomes vs lifecycle states
  - no-fail ownership transfer (preallocated envelope, poisoned user code)
  - status-record retention: tombstones, EXPIRED (never rejected-proof),
    Reserved records never removed, identity no-reuse
"""

import pytest

from gpwcf.core.supporting_patterns.error_handling.error_handling_unit import (
    ErrorHandlingOperationEntry,
    HandledErrorOccurrenceReference,
)
from gpwcf.core.supporting_patterns.error_handling.identities import (
    AcceptedEntryIdentity,
    ErrorHandlingInvocationIdentity,
    ErrorHandlingUnitIdentity,
    HandlingOperationAttemptIdentity,
    HandlingOperationIdentity,
    OperationEntryPublisherIdentity,
    PublicationReservationIdentity,
)
from gpwcf.core.supporting_patterns.error_handling.operation_entry_publisher import (
    AcceptanceKnowledge,
    OperationEntryPublisher,
    PreallocatedEntryEnvelope,
    PublicationAcknowledgement,
    PublicationIdentityPolicy,
    PublicationOutcome,
    PublicationRejection,
    PublicationReservation,
    PublicationSequencePolicy,
    PublicationStatus,
    PublicationStatusQuery,
    PublicationStatusRetentionPolicy,
    PublisherContractViolation,
    ReleaseAcknowledgement,
    ReservationGrant,
    StatusQueryOutcome,
    derive_accepted_entry_identity,
)

PUBLISHER_ID = OperationEntryPublisherIdentity("publisher-1")
UNIT_ID = ErrorHandlingUnitIdentity("unit-1")
INVOCATION_ID = ErrorHandlingInvocationIdentity("invocation-1")
STEP_ID = "step-instance-1"
ASSOC_ID = "association-1"
TARGET_ID = "association-target-1"


def a_publisher(total_capacity: int = 2) -> OperationEntryPublisher[str]:
    return OperationEntryPublisher[str](
        PUBLISHER_ID,
        invocation_identity=INVOCATION_ID,
        error_handling_unit_identity=UNIT_ID,
        step_instance_identity=STEP_ID,
        error_handling_unit_association_identity=ASSOC_ID,
        association_target_identity=TARGET_ID,
        total_capacity=total_capacity,
    )


def an_attempt(name: str = "attempt-1") -> HandlingOperationAttemptIdentity:
    return HandlingOperationAttemptIdentity(name)


def an_entry(
    attempt: HandlingOperationAttemptIdentity | None = None,
    operation: str = "op-1",
    *,
    unit: ErrorHandlingUnitIdentity = UNIT_ID,
    invocation: ErrorHandlingInvocationIdentity = INVOCATION_ID,
    step: str = STEP_ID,
    association: str = ASSOC_ID,
    target: str = TARGET_ID,
    result: str = "handled:resolved",
    targets: tuple[HandledErrorOccurrenceReference, ...] | None = None,
) -> ErrorHandlingOperationEntry[str]:
    return ErrorHandlingOperationEntry[str](
        error_handling_unit_identity=unit,
        handling_operation_attempt_identity=attempt or an_attempt(),
        handling_operation_identity=HandlingOperationIdentity(operation),
        error_handling_invocation_identity=invocation,
        step_instance_identity=step,
        error_handling_unit_association_identity=association,
        association_target_identity=target,
        target_occurrence_references=(
            targets
            if targets is not None
            else (HandledErrorOccurrenceReference("spu-1", "occ-1"),)
        ),
        operation_result=result,
)


def reserve_and_grant(
    publisher: OperationEntryPublisher[str], attempt: HandlingOperationAttemptIdentity
) -> PublicationReservation:
    grant = publisher.reserve(attempt)
    assert grant.granted
    assert grant.reservation is not None
    return grant.reservation


# --------------------------------------------------------------------------
# reserve / ReservationGrant
# --------------------------------------------------------------------------


def test_grant_contains_opaque_reservation_in_reserved_state():
    publisher = a_publisher()
    grant = publisher.reserve(an_attempt("attempt-1"))

    assert isinstance(grant, ReservationGrant)
    assert grant.granted and grant.rejection is None
    reservation = grant.reservation
    assert isinstance(reservation, PublicationReservation)
    assert reservation.state is PublicationStatus.RESERVED


def test_reservation_is_bound_to_publisher_invocation_unit_and_attempt():
    publisher = a_publisher()
    attempt = an_attempt("attempt-1")
    reservation = reserve_and_grant(publisher, attempt)

    assert reservation.publisher_identity == PUBLISHER_ID
    assert reservation.invocation_identity == INVOCATION_ID
    assert reservation.error_handling_unit_identity == UNIT_ID
    assert reservation.handling_operation_attempt_identity == attempt
    assert reservation.identity.value.startswith("reservation-")


def test_reservation_preserves_step_association_and_target_binding():
    publisher = a_publisher()
    reservation = reserve_and_grant(publisher, an_attempt("attempt-1"))

    assert reservation.step_instance_identity == STEP_ID
    assert reservation.error_handling_unit_association_identity == ASSOC_ID
    assert reservation.association_target_identity == TARGET_ID


def test_reservation_cannot_be_constructed_outside_the_issuing_publisher():
    with pytest.raises(TypeError):
        PublicationReservation(
            identity=PublicationReservationIdentity("forged"),
            publisher_identity=PUBLISHER_ID,
            invocation_identity=INVOCATION_ID,
            error_handling_unit_identity=UNIT_ID,
            handling_operation_attempt_identity=an_attempt("attempt-1"),
            step_instance_identity=STEP_ID,
            error_handling_unit_association_identity=ASSOC_ID,
            association_target_identity=TARGET_ID,
        )


def test_reused_attempt_identity_is_rejected():
    publisher = a_publisher()
    attempt = an_attempt("attempt-1")
    reserve_and_grant(publisher, attempt)

    grant = publisher.reserve(attempt)
    assert not grant.granted
    assert grant.reservation is None
    assert grant.rejection is not None
    assert grant.rejection.reason == "attempt-identity-reuse"


def test_rejected_reserve_burns_the_attempt_identity():
    """A new attempt after rejection requires a NEW attempt identity."""
    publisher = a_publisher(total_capacity=1)
    attempt = an_attempt("attempt-1")
    reserve_and_grant(publisher, attempt)
    exhausted = publisher.reserve(an_attempt("attempt-2"))
    assert not exhausted.granted

    # re-presenting a rejected attempt identity is also rejected
    again = publisher.reserve(an_attempt("attempt-2"))
    assert not again.granted
    assert again.rejection is not None


def test_reserve_rejects_when_total_capacity_would_be_overcommitted():
    publisher = a_publisher(total_capacity=1)
    first = publisher.reserve(an_attempt("attempt-1"))
    assert first.granted

    second = publisher.reserve(an_attempt("attempt-2"))
    assert not second.granted
    assert second.rejection is not None
    assert second.rejection.reason == "capacity-exhausted"
    # no capacity was committed to the caller
    assert publisher.reserved_capacity == 1
    assert publisher.occupied_capacity == 0


def test_reserve_rejects_after_invocation_enters_closing_phase():
    publisher = a_publisher()
    publisher.close_for_new_reservations()

    grant = publisher.reserve(an_attempt("attempt-1"))
    assert not grant.granted
    assert grant.rejection is not None
    assert grant.rejection.reason == "invocation-closing"


def test_release_returns_reserved_capacity():
    publisher = a_publisher(total_capacity=1)
    reservation = reserve_and_grant(publisher, an_attempt("attempt-1"))
    assert publisher.reserved_capacity == 1

    ack = publisher.release(reservation)
    assert isinstance(ack, ReleaseAcknowledgement)
    assert ack.released and not ack.idempotent_retry
    assert publisher.reserved_capacity == 0
    assert reservation.state is PublicationStatus.RELEASED
    # capacity became available again
    assert publisher.reserve(an_attempt("attempt-2")).granted


# --------------------------------------------------------------------------
# publish / atomic acceptance
# --------------------------------------------------------------------------


def test_atomic_acceptance_consumes_reservation_and_retains_entry():
    publisher = a_publisher()
    attempt = an_attempt("attempt-1")
    reservation = reserve_and_grant(publisher, attempt)
    entry = an_entry(attempt)

    ack = publisher.publish(reservation, entry)

    assert isinstance(ack, PublicationAcknowledgement)
    assert ack.outcome is PublicationOutcome.ACCEPTED
    assert ack.publication_sequence_number == 1
    assert not ack.idempotent_retry
    assert reservation.state is PublicationStatus.CONSUMED
    assert publisher.accepted_entries() == (entry,)
    # reserved capacity transitioned to occupied retention capacity
    assert publisher.reserved_capacity == 0
    assert publisher.occupied_capacity == 1


def test_publish_rejects_a_foreign_reservation_without_state_change():
    publisher = a_publisher()
    foreign = a_publisher()
    foreign_reservation = reserve_and_grant(foreign, an_attempt("attempt-1"))

    ack = publisher.publish(foreign_reservation, an_entry(an_attempt("attempt-1")))

    assert ack.outcome is PublicationOutcome.REJECTED
    assert ack.detail is not None
    assert ack.detail.reason == "unknown-or-foreign-reservation"
    # nothing was accepted anywhere
    assert publisher.accepted_entries() == ()
    assert foreign.accepted_entries() == ()
    assert foreign_reservation.state is PublicationStatus.RESERVED


def test_publish_rejects_attempt_identity_mismatch():
    publisher = a_publisher()
    attempt = an_attempt("attempt-1")
    reservation = reserve_and_grant(publisher, attempt)

    ack = publisher.publish(reservation, an_entry(an_attempt("other-attempt")))

    assert ack.outcome is PublicationOutcome.REJECTED
    assert ack.detail is not None and ack.detail.reason == "attempt-identity-mismatch"
    assert reservation.state is PublicationStatus.RESERVED
    assert publisher.accepted_entries() == ()


def test_publish_rejects_unit_identity_mismatch():
    publisher = a_publisher()
    attempt = an_attempt("attempt-1")
    reservation = reserve_and_grant(publisher, attempt)

    ack = publisher.publish(
        reservation,
        an_entry(attempt, unit=ErrorHandlingUnitIdentity("unit-2")),
    )

    assert ack.outcome is PublicationOutcome.REJECTED
    assert ack.detail is not None and ack.detail.reason == "unit-identity-mismatch"
    assert reservation.state is PublicationStatus.RESERVED


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("step", "step-instance-OTHER"),
        ("association", "association-OTHER"),
        ("target", "association-target-OTHER"),
        ("invocation", ErrorHandlingInvocationIdentity("inv-OTHER")),
    ],
    ids=["step", "association", "target", "invocation"],
)
def test_publish_rejects_provenance_mismatches(field_name, bad_value):
    publisher = a_publisher()
    attempt = an_attempt("attempt-1")
    reservation = reserve_and_grant(publisher, attempt)
    kwargs = {
        "step": STEP_ID,
        "association": ASSOC_ID,
        "target": TARGET_ID,
        "invocation": INVOCATION_ID,
    }
    kwargs[field_name] = bad_value

    ack = publisher.publish(reservation, an_entry(attempt, **kwargs))

    assert ack.outcome is PublicationOutcome.REJECTED
    assert ack.detail is not None and ack.detail.reason.endswith("mismatch")
    # no partial acceptance: state, entries, and capacity unchanged
    assert reservation.state is PublicationStatus.RESERVED
    assert publisher.accepted_entries() == ()
    assert publisher.reserved_capacity == 1
    assert publisher.occupied_capacity == 0


def test_publish_on_released_reservation_is_rejected():
    publisher = a_publisher()
    attempt = an_attempt("attempt-1")
    reservation = reserve_and_grant(publisher, attempt)
    publisher.release(reservation)

    ack = publisher.publish(reservation, an_entry(attempt))

    assert ack.outcome is PublicationOutcome.REJECTED
    assert ack.detail is not None and ack.detail.reason == "reservation-released"
    assert publisher.accepted_entries() == ()


def test_idempotent_retry_of_consumed_reservation_acknowledges_original():
    publisher = a_publisher()
    attempt = an_attempt("attempt-1")
    reservation = reserve_and_grant(publisher, attempt)
    entry = an_entry(attempt)
    first = publisher.publish(reservation, entry)

    retry = publisher.publish(reservation, entry)

    assert retry.outcome is PublicationOutcome.ACCEPTED
    assert retry.idempotent_retry is True
    assert retry.publication_sequence_number == first.publication_sequence_number
    # no second entry, no second capacity consumption
    assert publisher.accepted_entries() == (entry,)
    assert publisher.occupied_capacity == 1


def test_different_entry_under_consumed_reservation_is_never_accepted():
    publisher = a_publisher()
    attempt = an_attempt("attempt-1")
    reservation = reserve_and_grant(publisher, attempt)
    accepted = an_entry(attempt)
    publisher.publish(reservation, accepted)

    conflicting = an_entry(attempt, operation="op-2", result="handled:differently")
    ack = publisher.publish(reservation, conflicting)

    assert ack.outcome is PublicationOutcome.CONTRACT_VIOLATION
    assert ack.detail is not None
    assert ack.detail.reason == "invalid-reuse-of-consumed-reservation"
    assert publisher.accepted_entries() == (accepted,)


def test_same_composite_identity_with_different_content_is_conflicting_reuse():
    publisher = a_publisher()
    attempt = an_attempt("attempt-1")
    reservation = reserve_and_grant(publisher, attempt)
    accepted = an_entry(attempt)
    publisher.publish(reservation, accepted)

    mutated = an_entry(attempt, result="handled:TAMPERED")
    ack = publisher.publish(reservation, mutated)

    assert ack.outcome is PublicationOutcome.CONTRACT_VIOLATION
    assert ack.detail is not None
    assert ack.detail.reason == "conflicting-entry-content"
    assert publisher.accepted_entries() == (accepted,)


def test_publish_rejects_entries_that_are_not_operation_entries():
    publisher = a_publisher()
    reservation = reserve_and_grant(publisher, an_attempt("attempt-1"))
    with pytest.raises(TypeError):
        publisher.publish(reservation, "not-an-entry")  # type: ignore[arg-type]


def test_publisher_contract_violation_is_distinguishable_from_rejection():
    """The dedicated violation channel exists and is not a rejection value."""
    violation = PublisherContractViolation("publisher breached a granted guarantee")
    rejection = PublicationRejection("some-reason", "ordinary request-level failure")

    assert isinstance(violation, Exception)
    assert not isinstance(violation, PublicationRejection)
    assert not isinstance(rejection, Exception)
    with pytest.raises(PublisherContractViolation):
        raise violation


def test_distinct_reservations_publish_independently():
    publisher = a_publisher(total_capacity=2)
    attempt_1 = an_attempt("attempt-1")
    attempt_2 = an_attempt("attempt-2")
    reservation_1 = reserve_and_grant(publisher, attempt_1)
    reservation_2 = reserve_and_grant(publisher, attempt_2)

    ack_1 = publisher.publish(reservation_1, an_entry(attempt_1, operation="op-1"))
    ack_2 = publisher.publish(reservation_2, an_entry(attempt_2, operation="op-2"))

    assert ack_1.outcome is PublicationOutcome.ACCEPTED
    assert ack_2.outcome is PublicationOutcome.ACCEPTED
    assert ack_1.publication_sequence_number < ack_2.publication_sequence_number
    assert len(publisher.accepted_entries()) == 2


def test_accepted_entries_are_exposed_in_publication_acceptance_order():
    """Sequence metadata reflects the acceptance linearization order, which is
    not the attempt or grant order."""
    publisher = a_publisher(total_capacity=3)
    late_attempt = an_attempt("attempt-late")
    early_attempt = an_attempt("attempt-early")
    last_attempt = an_attempt("attempt-last")
    late = reserve_and_grant(publisher, late_attempt)
    early = reserve_and_grant(publisher, early_attempt)
    last = reserve_and_grant(publisher, last_attempt)

    publisher.publish(late, an_entry(late_attempt, operation="op-late"))
    publisher.publish(early, an_entry(early_attempt, operation="op-early"))
    publisher.publish(last, an_entry(last_attempt, operation="op-last"))

    entries = publisher.accepted_entries()
    assert [entry.handling_operation_identity.value for entry in entries] == [
        "op-late",
        "op-early",
        "op-last",
    ]
    assert publisher.publication_sequence_of(late) == 1
    assert publisher.publication_sequence_of(early) == 2
    assert publisher.publication_sequence_of(last) == 3


# --------------------------------------------------------------------------
# get_publication_status
# --------------------------------------------------------------------------


def test_status_reports_the_three_valid_reservation_states():
    publisher = a_publisher(total_capacity=2)
    attempt = an_attempt("attempt-1")
    reservation = reserve_and_grant(publisher, attempt)
    assert publisher.get_publication_status(reservation) is PublicationStatus.RESERVED

    publisher.publish(reservation, an_entry(attempt))
    assert publisher.get_publication_status(reservation) is PublicationStatus.CONSUMED

    released = reserve_and_grant(publisher, an_attempt("attempt-2"))
    publisher.release(released)
    assert publisher.get_publication_status(released) is PublicationStatus.RELEASED


def test_status_reports_unknown_or_foreign_reservations_distinctly():
    publisher = a_publisher()
    foreign = a_publisher()
    foreign_reservation = reserve_and_grant(foreign, an_attempt("attempt-1"))

    assert publisher.get_publication_status(foreign_reservation) is None
    with pytest.raises(TypeError):
        publisher.get_publication_status("not-a-reservation")  # type: ignore[arg-type]


def test_forged_reservation_construction_is_rejected():
    """The issuer token guard makes the reservation an opaque capability."""
    with pytest.raises(TypeError):
        PublicationReservation(
            identity=PublicationReservationIdentity("forged"),
            publisher_identity=PUBLISHER_ID,
            invocation_identity=INVOCATION_ID,
            error_handling_unit_identity=UNIT_ID,
            handling_operation_attempt_identity=an_attempt("ghost"),
            step_instance_identity=STEP_ID,
            error_handling_unit_association_identity=ASSOC_ID,
            association_target_identity=TARGET_ID,
        )


def test_status_lookup_does_not_mutate_the_reservation():
    publisher = a_publisher()
    attempt = an_attempt("attempt-1")
    reservation = reserve_and_grant(publisher, attempt)

    for _ in range(3):
        assert publisher.get_publication_status(reservation) is PublicationStatus.RESERVED
    assert reservation.state is PublicationStatus.RESERVED
    assert publisher.reserved_capacity == 1


# --------------------------------------------------------------------------
# release rules and state machine
# --------------------------------------------------------------------------


def test_release_of_consumed_reservation_is_rejected():
    publisher = a_publisher()
    attempt = an_attempt("attempt-1")
    reservation = reserve_and_grant(publisher, attempt)
    publisher.publish(reservation, an_entry(attempt))

    ack = publisher.release(reservation)

    assert not ack.released
    assert ack.detail is not None
    assert ack.detail.reason == "reservation-consumed"
    assert reservation.state is PublicationStatus.CONSUMED  # terminal, unchanged
    assert publisher.occupied_capacity == 1


def test_repeated_release_of_released_reservation_is_idempotent():
    publisher = a_publisher()
    reservation = reserve_and_grant(publisher, an_attempt("attempt-1"))
    assert publisher.release(reservation).released

    ack = publisher.release(reservation)

    assert ack.released and ack.idempotent_retry
    assert publisher.reserved_capacity == 0  # capacity returned only once
    assert reservation.state is PublicationStatus.RELEASED


def test_release_of_foreign_reservation_is_rejected():
    publisher = a_publisher()
    foreign = a_publisher()
    foreign_reservation = reserve_and_grant(foreign, an_attempt("attempt-1"))

    ack = publisher.release(foreign_reservation)

    assert not ack.released
    assert ack.detail is not None
    assert ack.detail.reason == "unknown-or-foreign-reservation"
    assert foreign.reserved_capacity == 1


def test_forbidden_transitions_are_structurally_unrepresentable():
    """Only the issuing publisher can transition the state; direct mutation is
    impossible and terminal states never move back."""
    publisher = a_publisher()
    reservation = reserve_and_grant(publisher, an_attempt("attempt-1"))

    with pytest.raises(AttributeError):
        reservation.state = PublicationStatus.CONSUMED  # type: ignore[misc]
    with pytest.raises(AttributeError):
        reservation.identity = PublicationReservationIdentity("other")  # type: ignore[misc]
    with pytest.raises(AttributeError):
        del reservation._state  # type: ignore[attr-defined]

    publisher.publish(reservation, an_entry(an_attempt("attempt-1")))
    # Consumed is terminal: release is rejected, state never returns to Reserved
    assert not publisher.release(reservation).released
    assert publisher.get_publication_status(reservation) is PublicationStatus.CONSUMED


def test_capacity_invariant_holds_across_the_full_lifecycle():
    publisher = a_publisher(total_capacity=3)
    reservations = [
        reserve_and_grant(publisher, an_attempt(f"attempt-{n}")) for n in range(3)
    ]
    assert publisher.reserved_capacity == 3
    assert publisher.reserved_capacity + publisher.occupied_capacity <= publisher.total_capacity

    publisher.publish(reservations[0], an_entry(an_attempt("attempt-0"), operation="op-0"))
    publisher.publish(reservations[1], an_entry(an_attempt("attempt-1"), operation="op-1"))
    publisher.release(reservations[2])
    assert publisher.reserved_capacity == 0
    assert publisher.occupied_capacity == 2
    assert publisher.reserved_capacity + publisher.occupied_capacity <= publisher.total_capacity


def test_publisher_requires_valid_construction_parameters():
    common = dict(
        invocation_identity=INVOCATION_ID,
        error_handling_unit_identity=UNIT_ID,
        error_handling_unit_association_identity=ASSOC_ID,
        association_target_identity=TARGET_ID,
        total_capacity=1,
    )
    with pytest.raises(TypeError):
        OperationEntryPublisher[str](  # type: ignore[arg-type]
            "not-a-publisher-identity",
            step_instance_identity=STEP_ID,
            **common,
        )
    with pytest.raises(ValueError):
        OperationEntryPublisher[str](
            PUBLISHER_ID,
            step_instance_identity=STEP_ID,
            total_capacity=0,
            **{k: v for k, v in common.items() if k != "total_capacity"},
        )
    with pytest.raises(ValueError):
        OperationEntryPublisher[str](
            PUBLISHER_ID,
            step_instance_identity="",
            **common,
        )


# --------------------------------------------------------------------------
# task 07 — correlated envelopes and capacity evidence
# --------------------------------------------------------------------------


def test_granted_grant_carries_correlation_and_capacity_evidence():
    publisher = a_publisher()
    attempt = an_attempt("attempt-1")

    grant = publisher.reserve(attempt)

    assert grant.capacity_committed is True
    assert grant.publisher_identity == PUBLISHER_ID
    assert grant.invocation_identity == INVOCATION_ID
    assert grant.error_handling_unit_identity == UNIT_ID
    assert grant.handling_operation_attempt_identity == attempt
    assert grant.diagnostics != ""
    # the copied correlation fields cannot manufacture the capability itself
    assert isinstance(grant.reservation, PublicationReservation)


def test_rejected_grant_commits_no_capacity_and_names_the_reason():
    publisher = a_publisher(total_capacity=1)
    assert publisher.reserve(an_attempt("attempt-1")).granted

    grant = publisher.reserve(an_attempt("attempt-2"))

    assert not grant.granted
    assert grant.capacity_committed is False
    assert grant.reservation is None
    assert grant.rejection is not None
    assert grant.rejection.reason == "capacity-exhausted"
    assert grant.publisher_identity == PUBLISHER_ID
    assert publisher.reserved_capacity == 1


def test_grant_envelope_rejects_invalid_evidence_combinations():
    with pytest.raises(ValueError):
        ReservationGrant()  # neither granted nor rejected
    with pytest.raises(ValueError):
        ReservationGrant(
            rejection=PublicationRejection("r", "d"),
            capacity_committed=True,  # a rejected grant commits no capacity
        )


def test_accepted_acknowledgement_requires_full_correlation():
    with pytest.raises(ValueError):
        # accepted without the correlation evidence set
        PublicationAcknowledgement(
            outcome=PublicationOutcome.ACCEPTED,
            publication_sequence_number=1,
        )
    with pytest.raises(ValueError):
        # accepted acknowledgements never carry a rejection detail
        PublicationAcknowledgement(
            outcome=PublicationOutcome.ACCEPTED,
            publication_sequence_number=1,
            detail=PublicationRejection("x", "y"),
            publisher_identity=PUBLISHER_ID,
            invocation_identity=INVOCATION_ID,
            publication_reservation_identity=PublicationReservationIdentity("r-1"),
            error_handling_unit_identity=UNIT_ID,
            handling_operation_attempt_identity=an_attempt("a-1"),
            handling_operation_identity="op-1",
            accepted_entry_identity=AcceptedEntryIdentity("unit-1/op-1"),
        )


def test_accepted_acknowledgement_carries_derived_entry_identity_and_retry_correlation():
    publisher = a_publisher()
    attempt = an_attempt("attempt-1")
    reservation = reserve_and_grant(publisher, attempt)
    entry = an_entry(attempt, operation="op-1")

    first = publisher.publish(reservation, entry)
    retry = publisher.publish(reservation, entry)

    for ack in (first, retry):
        assert ack.publisher_identity == PUBLISHER_ID
        assert ack.invocation_identity == INVOCATION_ID
        assert ack.publication_reservation_identity == reservation.identity
        assert ack.error_handling_unit_identity == UNIT_ID
        assert ack.handling_operation_attempt_identity == attempt
        assert ack.handling_operation_identity == "op-1"
        assert ack.accepted_entry_identity == AcceptedEntryIdentity("unit-1/op-1")
    assert retry.accepted_entry_identity == first.accepted_entry_identity
    assert retry.publication_sequence_number == first.publication_sequence_number
    assert retry.idempotent_retry is True


def test_derived_accepted_entry_identity_comes_from_entry_composite_identity():
    entry = an_entry(an_attempt("attempt-1"), operation="op-9")
    derived = derive_accepted_entry_identity(entry)

    assert isinstance(derived, AcceptedEntryIdentity)
    assert derived.value == "unit-1/op-9"


def test_rejected_publish_carries_known_correlation_and_diagnostics():
    publisher = a_publisher()
    foreign = a_publisher()
    foreign_reservation = reserve_and_grant(foreign, an_attempt("attempt-1"))

    ack = publisher.publish(foreign_reservation, an_entry(an_attempt("attempt-1")))

    assert ack.outcome is PublicationOutcome.REJECTED
    assert ack.detail is not None and ack.detail.reason == "unknown-or-foreign-reservation"
    assert ack.publisher_identity == PUBLISHER_ID
    assert ack.publication_reservation_identity == foreign_reservation.identity
    assert ack.accepted_entry_identity is None
    assert ack.diagnostics != ""


# --------------------------------------------------------------------------
# task 07 — status-query envelope: outcomes vs lifecycle states
# --------------------------------------------------------------------------


def test_query_envelope_reports_determinable_outcomes_for_all_three_states():
    publisher = a_publisher(total_capacity=2)
    attempt = an_attempt("attempt-1")
    reserved = reserve_and_grant(publisher, attempt)
    query = publisher.query_publication_status(reserved)
    assert query.outcome is StatusQueryOutcome.DETERMINABLE
    assert query.lifecycle_state is PublicationStatus.RESERVED
    assert query.lifecycle_state is not None  # a state IS reported here

    publisher.publish(reserved, an_entry(attempt, operation="op-1"))
    consumed = publisher.query_publication_status(reserved)
    assert consumed.outcome is StatusQueryOutcome.DETERMINABLE
    assert consumed.lifecycle_state is PublicationStatus.CONSUMED
    assert consumed.accepted_entry_identity == AcceptedEntryIdentity("unit-1/op-1")
    assert consumed.publication_sequence_number == 1
    assert consumed.publisher_identity == PUBLISHER_ID
    assert consumed.invocation_identity == INVOCATION_ID
    assert consumed.publication_reservation_identity == reserved.identity

    released = reserve_and_grant(publisher, an_attempt("attempt-2"))
    publisher.release(released)
    released_query = publisher.query_publication_status(released)
    assert released_query.outcome is StatusQueryOutcome.DETERMINABLE
    assert released_query.lifecycle_state is PublicationStatus.RELEASED


def test_query_envelope_reports_unknown_and_invalid_capabilities_distinctly():
    publisher = a_publisher()
    foreign = a_publisher()
    foreign_reservation = reserve_and_grant(foreign, an_attempt("attempt-1"))

    foreign_query = publisher.query_publication_status(foreign_reservation)
    assert foreign_query.outcome is StatusQueryOutcome.UNKNOWN
    assert foreign_query.lifecycle_state is None

    invalid_query = publisher.query_publication_status("not-a-reservation")  # type: ignore[arg-type]
    assert invalid_query.outcome is StatusQueryOutcome.INVALID_CAPABILITY
    assert invalid_query.lifecycle_state is None


def test_query_outcomes_are_not_lifecycle_states():
    """A non-determinable query outcome never carries a lifecycle state, and a
    Consumed determinable answer must identify the accepted publication."""
    with pytest.raises(ValueError):
        PublicationStatusQuery(outcome=StatusQueryOutcome.DETERMINABLE)
    with pytest.raises(ValueError):
        PublicationStatusQuery(
            outcome=StatusQueryOutcome.UNKNOWN,
            lifecycle_state=PublicationStatus.RESERVED,
        )
    with pytest.raises(ValueError):
        PublicationStatusQuery(
            outcome=StatusQueryOutcome.DETERMINABLE,
            lifecycle_state=PublicationStatus.CONSUMED,  # no entry correlation
        )
    with pytest.raises(ValueError):
        PublicationStatusQuery(
            outcome=StatusQueryOutcome.INDETERMINATE,
            lifecycle_state=PublicationStatus.RELEASED,
        )


# --------------------------------------------------------------------------
# task 07 — no-fail ownership transfer
# --------------------------------------------------------------------------


def test_preallocated_envelope_transfer_is_a_reference_assignment():
    envelope = PreallocatedEntryEnvelope()
    assert envelope.received is None

    entry = an_entry(an_attempt("attempt-1"))
    envelope.receive(entry)

    assert envelope.received is entry  # same object: no copy, no conversion


class _PoisonedResult:
    """A user-defined result whose comparisons/copies all explode."""

    def __eq__(self, other: object) -> bool:
        raise AssertionError("user-defined __eq__ must not run at acceptance")

    def __ne__(self, other: object) -> bool:
        raise AssertionError("user-defined __ne__ must not run at acceptance")

    def __hash__(self) -> int:
        raise AssertionError("user-defined __hash__ must not run at acceptance")

    def __deepcopy__(self, memo: dict[int, object]) -> object:
        raise AssertionError("no deep copy may run at acceptance")

    def __copy__(self) -> object:
        raise AssertionError("no copy may run at acceptance")


def test_atomic_acceptance_is_no_fail_with_poisoned_user_defined_result():
    """No arbitrary user-defined code (comparison/copy hooks) executes inside
    the acceptance boundary: the transfer is a fixed-slot reference assignment."""
    publisher = a_publisher()
    attempt = an_attempt("attempt-1")
    reservation = reserve_and_grant(publisher, attempt)
    entry = ErrorHandlingOperationEntry(
        error_handling_unit_identity=UNIT_ID,
        handling_operation_attempt_identity=attempt,
        handling_operation_identity=HandlingOperationIdentity("op-1"),
        error_handling_invocation_identity=INVOCATION_ID,
        step_instance_identity=STEP_ID,
        error_handling_unit_association_identity=ASSOC_ID,
        association_target_identity=TARGET_ID,
        target_occurrence_references=(
            HandledErrorOccurrenceReference("spu-1", "occ-1"),
        ),
        operation_result=_PoisonedResult(),
    )

    ack = publisher.publish(reservation, entry)  # must not raise

    assert ack.outcome is PublicationOutcome.ACCEPTED
    assert ack.publication_sequence_number == 1
    assert reservation.state is PublicationStatus.CONSUMED
    accepted = publisher.accepted_entries()
    assert len(accepted) == 1
    assert accepted[0] is entry  # identity, never equality


# --------------------------------------------------------------------------
# task 07 — status-record retention: tombstones and expiry
# --------------------------------------------------------------------------


def test_retire_reclaims_consumed_record_returns_capacity_and_tombstones():
    publisher = a_publisher(total_capacity=1)
    attempt = an_attempt("attempt-1")
    reservation = reserve_and_grant(publisher, attempt)
    entry = an_entry(attempt, operation="op-1")
    publisher.publish(reservation, entry)
    assert publisher.occupied_capacity == 1

    reclaimed = publisher.retire_terminal_records([reservation])

    assert reclaimed == 1
    # capacity returned and the entry dropped from the accepted view
    assert publisher.occupied_capacity == 0
    assert publisher.accepted_entries() == ()
    assert publisher.publication_sequence_of(reservation) is None
    # the tombstone keeps the identity distinguishable
    query = publisher.query_publication_status(reservation)
    assert query.outcome is StatusQueryOutcome.EXPIRED
    assert query.lifecycle_state is None
    # the simple accessor reports reclaimed records as unresolvable (None)
    assert publisher.get_publication_status(reservation) is None
    # capacity became grantable again
    assert publisher.reserve(an_attempt("attempt-2")).granted


def test_retired_capabilities_are_rejected_never_accepted_and_never_a_rejection_proof():
    publisher = a_publisher()
    attempt = an_attempt("attempt-1")
    reservation = reserve_and_grant(publisher, attempt)
    entry = an_entry(attempt)
    publisher.publish(reservation, entry)
    assert publisher.retire_terminal_records([reservation]) == 1

    late_publish = publisher.publish(reservation, entry)
    assert late_publish.outcome is PublicationOutcome.REJECTED
    assert late_publish.detail is not None
    assert late_publish.detail.reason == "reservation-expired"

    late_release = publisher.release(reservation)
    assert not late_release.released
    assert late_release.detail is not None
    assert late_release.detail.reason == "reservation-expired"

    # EXPIRED is never a proof of definite non-acceptance
    assert publisher.query_publication_status(reservation).outcome is (
        StatusQueryOutcome.EXPIRED
    )


def test_reserved_records_are_never_removable():
    publisher = a_publisher(total_capacity=2)
    reserved = reserve_and_grant(publisher, an_attempt("attempt-1"))
    consumed = reserve_and_grant(publisher, an_attempt("attempt-2"))
    publisher.publish(consumed, an_entry(an_attempt("attempt-2")))

    with pytest.raises(ValueError):
        publisher.retire_terminal_records([reserved])
    # nothing was removed
    assert publisher.get_publication_status(reserved) is PublicationStatus.RESERVED


def test_retirement_is_idempotent_and_ignores_unknown_reservations():
    publisher = a_publisher()
    reservation = reserve_and_grant(publisher, an_attempt("attempt-1"))
    publisher.release(reservation)

    assert publisher.retire_terminal_records([reservation]) == 1
    assert publisher.retire_terminal_records([reservation]) == 0


def test_retired_record_keeps_terminal_state_and_sequence_in_its_tombstone():
    publisher = a_publisher()
    attempt = an_attempt("attempt-1")
    reservation = reserve_and_grant(publisher, attempt)
    publisher.publish(reservation, an_entry(attempt))

    publisher.retire_terminal_records([reservation])

    query = publisher.query_publication_status(reservation)
    assert query.outcome is StatusQueryOutcome.EXPIRED
    # diagnostics expose the terminal state at retirement, never a new state
    assert "CONSUMED" in query.diagnostics


def test_replacement_publisher_opens_a_new_sequence_scope():
    first = a_publisher()
    replacement_id = OperationEntryPublisherIdentity("publisher-1-replacement")
    second = OperationEntryPublisher[str](
        replacement_id,
        invocation_identity=INVOCATION_ID,
        error_handling_unit_identity=UNIT_ID,
        step_instance_identity=STEP_ID,
        error_handling_unit_association_identity=ASSOC_ID,
        association_target_identity=TARGET_ID,
        total_capacity=2,
    )
    assert first._identity != second._identity
    reservation_1 = reserve_and_grant(first, an_attempt("attempt-1"))
    reservation_2 = reserve_and_grant(second, an_attempt("attempt-1"))

    first.publish(reservation_1, an_entry(an_attempt("attempt-1")))
    ack_2 = second.publish(reservation_2, an_entry(an_attempt("attempt-1")))

    # each Publisher instance's sequence scope starts with its own acceptance
    assert first.publication_sequence_of(reservation_1) == 1
    assert ack_2.publication_sequence_number == 1
    assert ack_2.publisher_identity == replacement_id


# --------------------------------------------------------------------------
# task 07 — policy surfaces (sequence, identity, retention)
# --------------------------------------------------------------------------


def test_sequence_policy_validates_strict_monotonicity_without_duplicates():
    policy = PublicationSequencePolicy()
    policy.validate_acceptance_order([1, 2, 10])
    policy.validate_acceptance_order((5,))
    policy.validate_acceptance_order([])
    with pytest.raises(ValueError):
        policy.validate_acceptance_order([1, 1])  # duplicate
    with pytest.raises(ValueError):
        policy.validate_acceptance_order([2, 1])  # decreasing
    with pytest.raises(TypeError):
        policy.validate_acceptance_order([1, "2"])  # type: ignore[list-item]


def test_identity_policy_validates_no_reuse_within_a_scope():
    policy = PublicationIdentityPolicy()
    policy.validate_no_identity_reuse(("reservation-1", "reservation-2"))
    policy.validate_no_identity_reuse(())
    with pytest.raises(ValueError):
        policy.validate_no_identity_reuse(("reservation-1", "reservation-1"))


def test_retention_policy_defaults_encode_the_event_based_rules():
    policy = PublicationStatusRetentionPolicy()
    assert policy.tombstone_on_reclamation is True
    assert policy.reserved_record_removal_allowed is False
    assert policy.expired_query_outcome is StatusQueryOutcome.EXPIRED
    assert "never" in policy.stale_capability_behavior


def test_acceptance_knowledge_has_the_three_contract_values():
    assert AcceptanceKnowledge.DEFINITELY_NOT_ACCEPTED.value == "definitely-not-accepted"
    assert AcceptanceKnowledge.DEFINITELY_ACCEPTED.value == "definitely-accepted"
    assert AcceptanceKnowledge.INDETERMINATE.value == "indeterminate"


def test_publisher_contract_violation_carries_the_minimum_evidence():
    violation = PublisherContractViolation(
        "guarantee breached",
        violation_code="released-with-pending-result",
        violation_identity="violation-1",
        publisher_identity=PUBLISHER_ID,
        publication_reservation_identity=PublicationReservationIdentity("r-1"),
        phase="atomic-acceptance",
        acceptance_knowledge=AcceptanceKnowledge.INDETERMINATE,
        violated_guarantee="release-never-loses-a-pending-result",
        custodian_marker="recovery-owner:step-x",
        recovery_owner_reference="step-x-recovery-owner",
        diagnostics="observed during recovery",
    )
    assert violation.violation_code == "released-with-pending-result"
    assert violation.violation_identity == "violation-1"
    assert violation.publisher_identity == PUBLISHER_ID
    assert violation.acceptance_knowledge is AcceptanceKnowledge.INDETERMINATE
    assert violation.custodian_marker == "recovery-owner:step-x"
    assert violation.recovery_status == "pending"
    # positional message construction keeps working (task 04 compatibility)
    assert str(PublisherContractViolation("plain message")) == "plain message"
