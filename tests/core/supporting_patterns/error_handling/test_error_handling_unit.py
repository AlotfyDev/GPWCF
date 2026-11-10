"""Contract tests for the Error Handling Unit (task 04_Error_Handling).

Covers (ErrorHandlingUnit_Contract.json / ErrorHandlerResult_Contract.json /
PublicationReservation_Contract.json):
  - assigned unit identity; one invocation under one selected Association
  - the documented protocol walkthrough: attempt identity before reserve, grant,
    operation identity after grant and before operation start, result preserved
    locally, complete entry published with the same reservation
  - no operation begins after a reservation rejection; rejected attempts have
    no operation identity
  - ambiguous publication outcome resolved via get_publication_status (lost ack
    → Consumed = accepted, never a second entry; Reserved = same entry retried)
  - exception before acceptance: result preserved, reservation stays Reserved,
    recovery escrow via the explicitly designated Recovery Owner
  - publisher is the authoritative delivery path: execute returns None and the
    Unit has no competing entries-collection API
  - ErrorHandlerResult: aggregate of accepted entries only, non-empty, preserves
    entries without merging, optional context, NO ErrorResult containment
  - RecoveryOwner custody transfer (verifiable escrow take/transfer)
  - ErrorHandlingComposition: aggregation, publisher ownership, closure check
"""

from dataclasses import dataclass

import pytest

from gpwcf.core.supporting_patterns.error_handling import (
    ErrorHandlingComposition,
    ErrorHandlingOperationEntry,
    ErrorHandlingUnit,
    ErrorHandlerResult,
    HandledErrorOccurrenceReference,
    PublicationOutcome,
    PublicationStatus,
    RecoveryOwner,
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

UNIT_ID = ErrorHandlingUnitIdentity("unit-1")
INVOCATION_ID = ErrorHandlingInvocationIdentity("invocation-1")
PUBLISHER_ID = OperationEntryPublisherIdentity("publisher-1")
STEP_ID = "step-instance-1"
ASSOC_ID = "association-1"
TARGET_ID = "association-target-1"


@dataclass(frozen=True)
class HandlingInput:
    """Step-specialized input: authorized invocation/Association context,
    operation context, and bounded target-occurrence access."""

    step_instance_identity: str
    error_handling_unit_association_identity: str
    association_target_identity: str
    error_handling_invocation_identity: ErrorHandlingInvocationIdentity
    target_occurrence_references: tuple[HandledErrorOccurrenceReference, ...]


def an_input() -> HandlingInput:
    return HandlingInput(
        step_instance_identity=STEP_ID,
        error_handling_unit_association_identity=ASSOC_ID,
        association_target_identity=TARGET_ID,
        error_handling_invocation_identity=INVOCATION_ID,
        target_occurrence_references=(
            HandledErrorOccurrenceReference("spu-1", "occ-1"),
        ),
    )


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


class _PublishingUnit(ErrorHandlingUnit[HandlingInput, str]):
    """Concrete Unit scripted for the documented protocol flows.

    ``behavior`` selects the flow under test; every flow follows the protocol:
    attempt identity before reserve, operation identity only after a valid
    grant, result preserved locally, complete entry published with the same
    reservation.
    """

    def __init__(self, behavior: str = "publish", unit_identity=UNIT_ID) -> None:
        super().__init__(unit_identity)
        self.behavior = behavior
        self.began_attempts: list[str] = []
        self.assigned_operation_identities: list[HandlingOperationIdentity] = []
        self.local_results: list[str] = []  # result preserved under Unit custody
        self.recovery_owner: RecoveryOwner | None = None
        self.last_status: PublicationStatus | None = None
        self.retry_publish_accepted = False

    def execute(
        self,
        input: HandlingInput,
        operation_entry_publisher: OperationEntryPublisher[str],
    ) -> None:
        attempt = HandlingOperationAttemptIdentity("attempt-1")
        grant = operation_entry_publisher.reserve(attempt)
        if grant.rejection is not None:
            return None  # must not begin the operation

        reservation = grant.reservation
        assert reservation is not None
        operation_identity = HandlingOperationIdentity("op-1")
        self.assigned_operation_identities.append(operation_identity)
        self.began_attempts.append(attempt.value)

        result = "handled:resolved"
        self.local_results.append(result)  # preserved locally before acceptance
        if self.behavior == "raise-before-publish":
            raise RuntimeError("exception before atomic acceptance")

        entry = ErrorHandlingOperationEntry[str](
            error_handling_unit_identity=self.error_handling_unit_identity,
            handling_operation_attempt_identity=attempt,
            handling_operation_identity=operation_identity,
            error_handling_invocation_identity=(
                input.error_handling_invocation_identity
            ),
            step_instance_identity=input.step_instance_identity,
            error_handling_unit_association_identity=(
                input.error_handling_unit_association_identity
            ),
            association_target_identity=input.association_target_identity,
            target_occurrence_references=input.target_occurrence_references,
            operation_result=result,
        )

        if self.behavior == "lost-ack":
            # publish may have crossed its acceptance point before the ack was
            # lost; resolve the ambiguity via publication status.
            ack = operation_entry_publisher.publish(reservation, entry)
            status = operation_entry_publisher.get_publication_status(reservation)
            self.last_status = status
            if status is PublicationStatus.CONSUMED:
                return None  # treat as accepted; never a second logical entry
            if status is PublicationStatus.RESERVED and ack is not None:
                retry = operation_entry_publisher.publish(reservation, entry)
                self.retry_publish_accepted = (
                    retry.outcome is PublicationOutcome.ACCEPTED
                )
                return None
            return None

        if self.behavior == "reject-then-retry":
            wrong = ErrorHandlingOperationEntry[str](
                **{
                    **entry.__dict__,
                    "step_instance_identity": "step-instance-OTHER",
                }
            )
            rejected = operation_entry_publisher.publish(reservation, wrong)
            assert rejected.outcome is PublicationOutcome.REJECTED
            status = operation_entry_publisher.get_publication_status(reservation)
            self.last_status = status
            assert status is PublicationStatus.RESERVED
            ack = operation_entry_publisher.publish(reservation, entry)
            self.retry_publish_accepted = ack.outcome is PublicationOutcome.ACCEPTED
            return None

        if self.behavior == "publish-mismatched-entry":
            wrong = ErrorHandlingOperationEntry[str](
                **{
                    **entry.__dict__,
                    "step_instance_identity": "step-instance-OTHER",
                }
            )
            rejected = operation_entry_publisher.publish(reservation, wrong)
            assert rejected.outcome is PublicationOutcome.REJECTED
            if self.recovery_owner is not None:
                # explicit custody transfer of the still-pending result
                assert rejected.detail is not None
                self.recovery_owner.take_custody(
                    record_identity="record-1",
                    reason=f"publication rejected: {rejected.detail.reason}",
                    result=result,
                    reservation_identity=str(reservation.identity),
                    handling_operation_attempt_identity=attempt.value,
                )
            return None

        if self.behavior == "release-when-no-result":
            operation_entry_publisher.release(reservation)
            return None

        ack = operation_entry_publisher.publish(reservation, entry)
        return None


# --------------------------------------------------------------------------
# Unit identity and callable shape
# --------------------------------------------------------------------------


def test_unit_requires_and_retains_assigned_identity():
    with pytest.raises(TypeError):
        _PublishingUnit(unit_identity="not-an-identity")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        _PublishingUnit(unit_identity=None)  # type: ignore[arg-type]

    unit = _PublishingUnit()
    assert unit.error_handling_unit_identity == UNIT_ID
    # a replacement instance receives a new identity
    other = ErrorHandlingUnitIdentity("unit-2")
    assert _PublishingUnit(unit_identity=other).error_handling_unit_identity == other
    assert other != UNIT_ID


def test_execute_returns_none_and_unit_has_no_entries_collection_api():
    """The Publisher is the authoritative delivery path: no competing collection."""
    unit = _PublishingUnit()
    publisher = a_publisher()

    result = unit.execute(an_input(), publisher)

    assert result is None
    for forbidden in ("accepted_entries", "get_entries", "operation_entries", "drain"):
        assert not hasattr(unit, forbidden), forbidden
    for name, member in vars(type(unit)).items():
        if callable(member) or isinstance(member, property):
            assert name not in {"accepted_entries", "operation_entries"}


# --------------------------------------------------------------------------
# Protocol walkthrough
# --------------------------------------------------------------------------


def test_protocol_walkthrough_attempt_grant_operation_publish():
    unit = _PublishingUnit()
    publisher = a_publisher()

    unit.execute(an_input(), publisher)

    # the attempt began only after the grant; operation identity assigned once
    assert unit.began_attempts == ["attempt-1"]
    assert len(unit.assigned_operation_identities) == 1
    # the entry was accepted and retained by the Publisher
    entries = publisher.accepted_entries()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.error_handling_unit_identity == UNIT_ID
    assert entry.handling_operation_identity == HandlingOperationIdentity("op-1")
    assert entry.handling_operation_attempt_identity == HandlingOperationAttemptIdentity("attempt-1")
    assert entry.operation_result == "handled:resolved"
    assert entry.target_occurrence_references == (
        HandledErrorOccurrenceReference("spu-1", "occ-1"),
    )
    # complete provenance preserved
    assert entry.step_instance_identity == STEP_ID
    assert entry.error_handling_unit_association_identity == ASSOC_ID
    assert entry.association_target_identity == TARGET_ID
    assert entry.error_handling_invocation_identity == INVOCATION_ID
    assert entry.composite_identity == (UNIT_ID, HandlingOperationIdentity("op-1"))


def test_rejected_reservation_means_no_operation_begins():
    """After a rejection the Unit must not begin the associated operation."""
    unit = _PublishingUnit()
    publisher = a_publisher(total_capacity=1)
    # exhaust capacity so the unit's reserve is rejected
    filler = publisher.reserve(HandlingOperationAttemptIdentity("filler-attempt"))
    assert filler.granted

    unit.execute(an_input(), publisher)

    assert unit.began_attempts == []
    assert unit.assigned_operation_identities == []
    assert publisher.accepted_entries() == ()
    # a reservation-rejected attempt has no operation identity: exactly the
    # filler attempt reserved capacity; nothing else was consumed
    assert publisher.reserved_capacity == 1


def test_no_partial_acceptance_when_entry_provenance_is_wrong_then_retry():
    """A rejected publish leaves the reservation Reserved; the same reservation
    and the same logical entry may then be published successfully."""
    unit = _PublishingUnit(behavior="reject-then-retry")
    publisher = a_publisher()

    unit.execute(an_input(), publisher)

    assert unit.last_status is PublicationStatus.RESERVED
    assert unit.retry_publish_accepted is True
    assert len(publisher.accepted_entries()) == 1
    assert publisher.occupied_capacity == 1


# --------------------------------------------------------------------------
# Ambiguous outcomes and result preservation
# --------------------------------------------------------------------------


def test_lost_acknowledgement_resolved_via_publication_status():
    """Consumed status means accepted: the Unit must not create a second entry."""
    unit = _PublishingUnit(behavior="lost-ack")
    publisher = a_publisher()

    unit.execute(an_input(), publisher)

    assert unit.last_status is PublicationStatus.CONSUMED
    assert len(publisher.accepted_entries()) == 1
    assert publisher.occupied_capacity == 1


def test_exception_before_acceptance_preserves_result_and_reservation():
    """An exception before acceptance leaves the Unit responsible: the produced
    result must not be lost and the reservation remains Reserved."""
    unit = _PublishingUnit(behavior="raise-before-publish")
    publisher = a_publisher()
    grant_probe = publisher.reserve(HandlingOperationAttemptIdentity("probe"))
    assert grant_probe.reservation is not None
    reservation_probe = grant_probe.reservation

    with pytest.raises(RuntimeError):
        unit.execute(an_input(), publisher)

    assert unit.local_results == ["handled:resolved"]  # preserved under Unit custody
    entries = publisher.accepted_entries()
    assert entries == ()
    assert reservation_probe.state is PublicationStatus.RESERVED
    assert publisher.get_publication_status(reservation_probe) is PublicationStatus.RESERVED


def test_unaccepted_result_escrowed_to_the_designated_recovery_owner():
    """Explicit custody transfer: no result remains pending publication under
    Unit custody once the Recovery Owner took it."""
    unit = _PublishingUnit(behavior="publish-mismatched-entry")
    recovery_owner = RecoveryOwner("step-recovery-owner")
    unit.recovery_owner = recovery_owner
    publisher = a_publisher()

    unit.execute(an_input(), publisher)

    records = recovery_owner.escrow_records()
    assert len(records) == 1
    record = records[0]
    assert record.custodied_result == "handled:resolved"
    assert record.reservation_identity == "reservation-1"
    assert record.handling_operation_attempt_identity == "attempt-1"
    # the mismatched entry was never accepted
    assert publisher.accepted_entries() == ()
    # the reservation stays Reserved with the pending result now in escrow
    assert publisher.reserved_capacity == 1


def test_release_requested_when_no_result_requires_publication():
    unit = _PublishingUnit(behavior="release-when-no-result")
    publisher = a_publisher()

    unit.execute(an_input(), publisher)

    assert publisher.accepted_entries() == ()
    assert publisher.reserved_capacity == 0
    assert publisher.occupied_capacity == 0


# --------------------------------------------------------------------------
# ErrorHandlingOperationEntry structure
# --------------------------------------------------------------------------


def test_entry_requires_complete_provenance_and_structured_result():
    with pytest.raises(ValueError):
        ErrorHandlingOperationEntry[str](
            error_handling_unit_identity=UNIT_ID,
            handling_operation_attempt_identity=HandlingOperationAttemptIdentity("a"),
            handling_operation_identity=HandlingOperationIdentity("o"),
            error_handling_invocation_identity=INVOCATION_ID,
            step_instance_identity="",
            error_handling_unit_association_identity=ASSOC_ID,
            association_target_identity=TARGET_ID,
            target_occurrence_references=(),
            operation_result="r",
        )
    with pytest.raises(ValueError):
        ErrorHandlingOperationEntry[str](
            error_handling_unit_identity=UNIT_ID,
            handling_operation_attempt_identity=HandlingOperationAttemptIdentity("a"),
            handling_operation_identity=HandlingOperationIdentity("o"),
            error_handling_invocation_identity=INVOCATION_ID,
            step_instance_identity=STEP_ID,
            error_handling_unit_association_identity=ASSOC_ID,
            association_target_identity=TARGET_ID,
            target_occurrence_references=(),
            operation_result=None,  # type: ignore[arg-type]
        )


def test_entry_rejects_duplicate_target_occurrence_references():
    with pytest.raises(ValueError):
        ErrorHandlingOperationEntry[str](
            error_handling_unit_identity=UNIT_ID,
            handling_operation_attempt_identity=HandlingOperationAttemptIdentity("a"),
            handling_operation_identity=HandlingOperationIdentity("o"),
            error_handling_invocation_identity=INVOCATION_ID,
            step_instance_identity=STEP_ID,
            error_handling_unit_association_identity=ASSOC_ID,
            association_target_identity=TARGET_ID,
            target_occurrence_references=(
                HandledErrorOccurrenceReference("spu-1", "occ-1"),
                HandledErrorOccurrenceReference("spu-1", "occ-1"),
            ),
            operation_result="r",
        )


def test_occurrence_reference_is_a_producer_pair_only():
    reference = HandledErrorOccurrenceReference("spu-1", "occ-1")
    assert reference.producer_spu_identity == "spu-1"
    assert reference.occurrence_identity == "occ-1"
    assert reference == HandledErrorOccurrenceReference("spu-1", "occ-1")
    assert reference != HandledErrorOccurrenceReference("spu-1", "occ-2")
    with pytest.raises(ValueError):
        HandledErrorOccurrenceReference("", "occ-1")
    with pytest.raises(ValueError):
        HandledErrorOccurrenceReference("spu-1", "   ")


# --------------------------------------------------------------------------
# ErrorHandlerResult aggregation
# --------------------------------------------------------------------------


def a_result_entry(operation: str = "op-1") -> ErrorHandlingOperationEntry[str]:
    return ErrorHandlingOperationEntry[str](
        error_handling_unit_identity=UNIT_ID,
        handling_operation_attempt_identity=HandlingOperationAttemptIdentity("a"),
        handling_operation_identity=HandlingOperationIdentity(operation),
        error_handling_invocation_identity=INVOCATION_ID,
        step_instance_identity=STEP_ID,
        error_handling_unit_association_identity=ASSOC_ID,
        association_target_identity=TARGET_ID,
        target_occurrence_references=(HandledErrorOccurrenceReference("spu-1", "occ-1"),),
        operation_result=f"handled:{operation}",
    )


def test_error_handler_result_aggregates_accepted_entries_without_merging():
    first, second = a_result_entry("op-1"), a_result_entry("op-2")
    result = ErrorHandlerResult[ErrorHandlingOperationEntry[str]](
        operation_entries=(first, second)
    )

    assert result.operation_entries == (first, second)  # preserved as given
    assert result.operation_entry_count == 2
    assert result.error_handling_context is None


def test_error_handler_result_never_exists_empty():
    with pytest.raises(ValueError):
        ErrorHandlerResult[ErrorHandlingOperationEntry[str]](operation_entries=())


def test_error_handler_result_has_no_error_result_containment():
    """No ErrorResult containment, mutation, erasure, or resolution assertion."""
    result = ErrorHandlerResult[ErrorHandlingOperationEntry[str]](
        operation_entries=(a_result_entry(),)
    )
    field_names = {name for name in vars(result)}
    for forbidden in ("error_result", "errorResult", "ErrorResult", "resolved"):
        assert not any(forbidden.lower() in name.lower() for name in field_names)
    assert not hasattr(result, "error_result")
    assert not hasattr(result, "resolve_occurrences")
    # frozen: no mutation of the aggregate or its entries
    with pytest.raises(Exception):
        result.operation_entries = ()  # type: ignore[misc]


def test_error_handler_result_context_is_independently_optional():
    context = {"composition": "step-specific"}
    with_context: ErrorHandlerResult[ErrorHandlingOperationEntry[str], dict] = (
        ErrorHandlerResult(operation_entries=(a_result_entry(),), error_handling_context=context)
    )
    without_context: ErrorHandlerResult[ErrorHandlingOperationEntry[str], dict] = (
        ErrorHandlerResult(operation_entries=(a_result_entry(),))
    )
    assert with_context.error_handling_context == context
    assert without_context.error_handling_context is None  # absence is not a status


# --------------------------------------------------------------------------
# RecoveryOwner custody transfer
# --------------------------------------------------------------------------


def test_recovery_owner_take_custody_and_transfer_out_are_verifiable():
    owner = RecoveryOwner("step-recovery-owner")
    entry = a_result_entry("op-9")

    record = owner.take_custody(
        record_identity="record-1",
        reason="invocation unwound with unpublished result",
        entry=entry,
        reservation_identity="reservation-1",
        handling_operation_attempt_identity="attempt-1",
    )

    assert record.custodied_entry is entry
    assert owner.escrow_records() == (record,)
    with pytest.raises(ValueError):  # no silent overwrite
        owner.take_custody(record_identity="record-1", reason="again", result="x")

    alternative = RecoveryOwner("alternative-owner")
    transferred = owner.transfer_out("record-1", recipient_owner=alternative)

    assert owner.escrow_records() == ()  # verifiable: no longer held here
    assert transferred.transferred_to == "step-recovery-owner"
    assert alternative.escrow_records() == (transferred,)
    with pytest.raises(KeyError):
        owner.transfer_out("record-1")


def test_recovery_owner_requires_a_name_and_non_empty_records():
    with pytest.raises(ValueError):
        RecoveryOwner("")
    with pytest.raises(ValueError):
        RecoveryOwner("x").take_custody(record_identity="r", reason="why")  # nothing custodied


# --------------------------------------------------------------------------
# ErrorHandlingComposition
# --------------------------------------------------------------------------


def test_composition_owns_publisher_and_collects_accepted_entries():
    composition: ErrorHandlingComposition[str, dict] = ErrorHandlingComposition()
    publisher = composition.create_publisher(
        PUBLISHER_ID,
        invocation_identity=INVOCATION_ID,
        error_handling_unit_identity=UNIT_ID,
        step_instance_identity=STEP_ID,
        error_handling_unit_association_identity=ASSOC_ID,
        association_target_identity=TARGET_ID,
        total_capacity=2,
    )

    unit = _PublishingUnit()
    unit.execute(an_input(), publisher)

    collected = composition.collect_accepted_entries(publisher)
    assert len(collected) == 1
    result = composition.assemble(collected, error_handling_context={"step": "s"})
    assert result.operation_entry_count == 1
    assert result.error_handling_context == {"step": "s"}


def test_composition_unresolved_reservations_blocks_normal_closure():
    composition: ErrorHandlingComposition[str] = ErrorHandlingComposition()
    publisher = composition.create_publisher(
        PUBLISHER_ID,
        invocation_identity=INVOCATION_ID,
        error_handling_unit_identity=UNIT_ID,
        step_instance_identity=STEP_ID,
        error_handling_unit_association_identity=ASSOC_ID,
        association_target_identity=TARGET_ID,
        total_capacity=1,
    )
    outstanding = publisher.reserve(HandlingOperationAttemptIdentity("attempt-1"))
    assert outstanding.granted

    assert composition.unresolved_reservations(publisher) == (outstanding.reservation,)

    publisher.release(outstanding.reservation)  # type: ignore[arg-type]
    assert composition.unresolved_reservations(publisher) == ()
