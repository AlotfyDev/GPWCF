"""Error Handling Unit, operation entries, ErrorHandlerResult, Recovery Owner.

Implementation task: 04_Error_Handling
Related diagrams:
  class: 03_Diagrams_Codes_Files/04_Error_Handling.dot
  sequence: B_Sequencial_Diagram_Code/02_Error_Handling_Sequence.puml
  association: C_Association_Diagram_Code/04_Error_Handling_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/04_Supporting_Pattern_Optional_Dependency.dot

Contract basis:
  - ErrorHandlingUnit_Contract.json (``pipeline.error-handling-unit.contract``)
  - ErrorHandlerResult_Contract.json (``pipeline.error-handler-result.contract``)
  - PublicationReservation_Contract.json / OperationEntryPublisher_Contract.json
  - Step_Error_Model_Contract.json (producerSPUIdentity + occurrenceIdentity
    target-occurrence reference pairs)

Dependency boundary (``04_Supporting_Pattern_Optional_Dependency.dot``):
``ErrorHandlingUnit -> Core : NO dependency`` — this pattern package imports
nothing from ``gpwcf`` outside itself. Identities owned by other layers (Step
instance, Unit Association, association target, producer SPU, SPU error
occurrence) travel as opaque, validated, non-empty string VALUES.

Protocol responsibilities of a concrete Unit (per the operation-execution
contract):

  1. For each distinct Handling Operation attempt, allocate a NEW
     ``HandlingOperationAttemptIdentity`` BEFORE calling
     ``OperationEntryPublisher.reserve``. A reservation-rejected attempt has no
     operation identity and the operation must not begin.
  2. Only after a valid grant and BEFORE the actual operation begins, assign a
     NEW ``HandlingOperationIdentity`` to the execution. One attempt starts at
     most one actual execution.
  3. If a result is produced, preserve it locally under Unit responsibility,
     prepare the COMPLETE ``ErrorHandlingOperationEntry`` (all provenance +
     ``operationResult``), and ``publish`` it with the same reservation.
  4. Calling publish does not transfer ownership: responsibility transfers only
     at the atomic-acceptance point (an ACCEPTED acknowledgement). If the
     acknowledgement is lost or an exception occurs after acceptance may have
     been crossed, resolve the ambiguity with
     ``OperationEntryPublisher.get_publication_status``: Consumed = accepted
     (never publish a second logical entry), Reserved = the same entry may be
     retried, Released with a pending produced result = Publisher/Composition
     contract violation.
  5. If execute unwinds exceptionally while a produced result remains
     unpublished, the Unit must NOT rely on a Unit-local variable that becomes
     unreachable on unwind: the pending result/entry must be exposed to the
     composition through an explicit recovery envelope, exception payload, or
     invocation-scoped recovery record (e.g. escrowed to the Step-designated
     :class:`RecoveryOwner`).
  6. Request ``release`` only when the operation produced no result requiring
     publication, or after a verifiable custody transfer of any produced result
     to an explicitly authorized alternative owner.

Result-retention invariant: every produced ``THandlingOperationResult`` remains
available — under Unit responsibility before acceptance or under
Publisher/Composition retention after acceptance — until an explicit transfer
or aggregation lifecycle completes.

The Publisher is the AUTHORITATIVE delivery path: the Unit does not
additionally return a competing collection of operation entries (``execute``
returns ``None``). A Unit has no entries-collection API of any kind.

Target occurrences: an entry references the SPUError occurrences it acted upon
ONLY via (producerSPUIdentity, occurrenceIdentity) pairs. Publication does not
transfer ownership of source SPUError occurrences and does not alter ErrorResult
ownership.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .identities import (
    ErrorHandlingInvocationIdentity,
    ErrorHandlingUnitIdentity,
    HandlingOperationAttemptIdentity,
    HandlingOperationIdentity,
)

if TYPE_CHECKING:  # annotation-only; no import cycle at runtime
    from .operation_entry_publisher import OperationEntryPublisher

__all__ = [
    "HandledErrorOccurrenceReference",
    "ErrorHandlingOperationEntry",
    "ErrorHandlingUnit",
    "ErrorHandlerResult",
    "RecoveryOwner",
    "RecoveryEscrowRecord",
]


def _require_opaque_identity(field: str, value: object) -> None:
    """Validate an opaque cross-layer identity value (non-empty string)."""
    if not isinstance(value, str) or value == "" or value.isspace():
        raise ValueError(f"{field} must be a non-empty opaque identity value")


@dataclass(frozen=True)
class HandledErrorOccurrenceReference:
    """Reference to exactly one SPUError occurrence acted upon by an operation.

    Identifies the occurrence using the Step Error Model pair
    ``producerSPUIdentity`` + ``occurrenceIdentity``. Both travel as opaque
    non-empty string values owned by their originating layers; this pattern
    never interprets or re-scopes them. No association to any ErrorResult is
    implied by a target reference.
    """

    producer_spu_identity: str
    occurrence_identity: str

    def __post_init__(self) -> None:
        _require_opaque_identity("producer_spu_identity", self.producer_spu_identity)
        _require_opaque_identity("occurrence_identity", self.occurrence_identity)


@dataclass(frozen=True)
class ErrorHandlingOperationEntry[THandlingOperationResult]:
    """One COMPLETE structured entry for one actual Handling Operation execution.

    Represents an actual operation execution that yielded its structured
    ``operation_result`` — not a declared handling action or a planned
    operation. An operation that throws before producing that result is never
    represented as though it had returned one.

    Composite identity: (``error_handling_unit_identity``,
    ``handling_operation_identity``) uniquely identifies the entry within the
    applicable SPU identity scope. ``handling_operation_attempt_identity`` is
    preserved as the originating reservation-authorized attempt identity but
    does not replace the composite identity.

    Provenance: the entry preserves the exact Step instance, Unit Association,
    association target, and invocation identities bound to the PublicationReservation
    used to publish it. Association-target provenance is distinct from
    ``target_occurrence_references`` (which identify the exact error occurrences
    acted upon).
    """

    error_handling_unit_identity: ErrorHandlingUnitIdentity
    handling_operation_attempt_identity: HandlingOperationAttemptIdentity
    handling_operation_identity: HandlingOperationIdentity
    error_handling_invocation_identity: ErrorHandlingInvocationIdentity
    step_instance_identity: str
    error_handling_unit_association_identity: str
    association_target_identity: str
    target_occurrence_references: tuple[HandledErrorOccurrenceReference, ...]
    operation_result: THandlingOperationResult

    def __post_init__(self) -> None:
        _require_exact_type(
            "error_handling_unit_identity",
            self.error_handling_unit_identity,
            ErrorHandlingUnitIdentity,
        )
        _require_exact_type(
            "handling_operation_attempt_identity",
            self.handling_operation_attempt_identity,
            HandlingOperationAttemptIdentity,
        )
        _require_exact_type(
            "handling_operation_identity",
            self.handling_operation_identity,
            HandlingOperationIdentity,
        )
        _require_exact_type(
            "error_handling_invocation_identity",
            self.error_handling_invocation_identity,
            ErrorHandlingInvocationIdentity,
        )
        _require_opaque_identity("step_instance_identity", self.step_instance_identity)
        _require_opaque_identity(
            "error_handling_unit_association_identity",
            self.error_handling_unit_association_identity,
        )
        _require_opaque_identity(
            "association_target_identity", self.association_target_identity
        )
        if isinstance(self.target_occurrence_references, (str, bytes)) or not isinstance(
            self.target_occurrence_references, tuple
        ):
            raise TypeError(
                "target_occurrence_references must be a tuple of "
                "HandledErrorOccurrenceReference"
            )
        seen: set[HandledErrorOccurrenceReference] = set()
        for reference in self.target_occurrence_references:
            if not isinstance(reference, HandledErrorOccurrenceReference):
                raise TypeError(
                    "target_occurrence_references must contain only "
                    f"HandledErrorOccurrenceReference, got {type(reference).__name__}"
                )
            if reference in seen:
                raise ValueError(
                    "target_occurrence_references must not contain duplicates "
                    f"({reference!r} repeated)"
                )
            seen.add(reference)
        if self.operation_result is None:
            raise ValueError(
                "operation_result is required: an entry represents an actual "
                "execution that yielded its structured operation result"
            )

    @property
    def composite_identity(
        self,
    ) -> tuple[ErrorHandlingUnitIdentity, HandlingOperationIdentity]:
        """The (errorHandlingUnitIdentity, handlingOperationIdentity) pair."""
        return (self.error_handling_unit_identity, self.handling_operation_identity)


class ErrorHandlingUnit[TErrorHandlingUnitInput, THandlingOperationResult](ABC):
    """Step-owned optional Error Handling Unit callable.

    Executes the authorized handling operations assigned by the Step design
    against target occurrences/resources, producing ``THandlingOperationResult``
    values until publication acceptance or custody transfer. The Unit is
    optional and selected per concrete Step; it is not a universal Supporting
    Unit and receives no universal execution context.

    Identity: Step Composition (or an identity provider supplied by it)
    assigns the ``ErrorHandlingUnitIdentity`` when the Unit instance is created
    or admitted into the Step's internal component composition; the Unit
    receives and retains it — construction fails without an assigned identity.
    A replacement instance receives a new identity while results from the prior
    instance may still be observed.

    Invocation: one ``execute`` invocation is one Unit invocation under one
    selected Association. The Step Composition supplies an invocation-bound
    ``OperationEntryPublisher[THandlingOperationResult]``; all operation
    attempts and entries of the invocation carry the invocation identity bound
    to that capability.

    The Unit does NOT assemble ``ErrorHandlerResult`` (the Step-specific Error
    Handling Composition aggregates accepted entries), does NOT decide Step
    flow transitions, and does NOT return a competing collection of operation
    entries: the Publisher is the authoritative delivery path.
    """

    def __init__(self, error_handling_unit_identity: ErrorHandlingUnitIdentity) -> None:
        _require_exact_type(
            "error_handling_unit_identity",
            error_handling_unit_identity,
            ErrorHandlingUnitIdentity,
        )
        self._error_handling_unit_identity = error_handling_unit_identity

    @property
    def error_handling_unit_identity(self) -> ErrorHandlingUnitIdentity:
        """The Step Composition-assigned identity of this Unit instance."""
        return self._error_handling_unit_identity

    @abstractmethod
    def execute(
        self,
        input: TErrorHandlingUnitInput,
        operation_entry_publisher: OperationEntryPublisher[THandlingOperationResult],
    ) -> None:
        """Execute the assigned handling operations for one invocation.

        Follows the module-docstring protocol: new attempt identity before
        ``reserve``; operation identity only after a valid grant and before the
        operation begins; result preserved locally; complete entry published
        with the same reservation; ambiguity resolved via publication status;
        release requested only when no result remains pending publication.
        Returns ``None`` — accepted entries travel exclusively through the
        Publisher. Thrown exceptions are not converted into operation results
        or entries.
        """
        raise NotImplementedError


@dataclass(frozen=True)
class ErrorHandlerResult[THandlingOperationEntry, TErrorHandlingContext = object]:
    """Step-specific aggregate of executed error-handling operations.

    Aggregates ACCEPTED operation entries only, in the order selected by the
    Step-specific Error Handling Composition (preserved as given: no merging,
    no reordering, no deduplication). Constructed only when at least one entry
    was selected — no empty result exists. ``error_handling_context`` is an
    independently optional Step-specialized context; its absence is not a
    success/failure status.

    Deliberately NOT represented here:

    - No ``ErrorResult`` containment of any kind: this aggregate does not
      contain, mutate, erase, or wrap ErrorResult values, and does not assert
      that targeted occurrences are resolved.
    - No Step-level flow decision and no success/failure status.
    - Target occurrences are referenced only via (producerSPUIdentity,
      occurrenceIdentity) pairs carried by the entries.
    """

    operation_entries: tuple[THandlingOperationEntry, ...]
    error_handling_context: TErrorHandlingContext | None = None

    def __post_init__(self) -> None:
        entries = self.operation_entries
        if isinstance(entries, (str, bytes)) or not isinstance(entries, tuple):
            raise TypeError("operation_entries must be a tuple of operation entries")
        if not entries:
            raise ValueError(
                "ErrorHandlerResult is an aggregate of accepted operation "
                "entries and is constructed only when at least one entry was "
                "selected; no empty result exists"
            )
        for entry in entries:
            if entry is None:
                raise TypeError("operation_entries must not contain None")

    @property
    def operation_entry_count(self) -> int:
        """Number of aggregated operation entries."""
        return len(self.operation_entries)


@dataclass(frozen=True)
class RecoveryEscrowRecord:
    """Verifiable record of one custody transfer into (or out of) escrow.

    Created by a :class:`RecoveryOwner` when it takes custody of a produced
    result and/or complete entry whose publication did not complete normally.
    Carries the opaque identity values needed to correlate the pending item
    with its reservation and operation attempt. ``transferred_to`` names the
    receiving owner after a :meth:`RecoveryOwner.transfer_out` re-escrow.
    """

    record_identity: str
    reason: str
    custodied_entry: ErrorHandlingOperationEntry[object] | None
    custodied_result: object | None
    reservation_identity: str | None = None
    handling_operation_attempt_identity: str | None = None
    transferred_to: str | None = None

    def __post_init__(self) -> None:
        _require_opaque_identity("record_identity", self.record_identity)
        if self.reason == "" or self.reason.isspace():
            raise ValueError("reason must be a non-empty descriptive string")
        if self.custodied_entry is None and self.custodied_result is None:
            raise ValueError(
                "an escrow record custodies the produced result and/or the "
                "complete entry; at least one must be present"
            )


class RecoveryOwner:
    """Explicitly designated alternative owner for unpublished produced results.

    Each Step names its Recovery Owner and concrete recovery procedure under
    ``Single_Step_Publication_Specialization_Contract.json`` (task 07); this
    class provides the common working escrow machinery: verifiable custody
    transfer of a produced-but-unpublished result/entry so that no result is
    silently lost when an invocation unwinds or a reservation cannot be
    resolved.

    Escrow rules:

    - ``take_custody`` records the transferred item (identity-unique per owner;
      no silent overwrite) and returns the verifiable escrow record.
    - ``escrow_records`` exposes the currently held records.
    - ``transfer_out`` moves a record out of this owner's escrow — optionally
      re-escrowing it with a recipient owner — so that at most one owner holds
      a record at any time. A produced result must not remain pending
      publication under Unit custody once custody is transferred here.
    """

    def __init__(self, name: str) -> None:
        _require_opaque_identity("name", name)
        self._name = name
        self._records: dict[str, RecoveryEscrowRecord] = {}

    @property
    def name(self) -> str:
        """The Step-designated recovery owner name."""
        return self._name

    def take_custody(
        self,
        *,
        record_identity: str,
        reason: str,
        entry: ErrorHandlingOperationEntry[object] | None = None,
        result: object | None = None,
        reservation_identity: str | None = None,
        handling_operation_attempt_identity: str | None = None,
    ) -> RecoveryEscrowRecord:
        """Take custody of a produced result and/or complete entry."""
        if record_identity in self._records:
            raise ValueError(
                f"escrow record identity {record_identity!r} already exists in "
                f"RecoveryOwner {self._name!r}; identities are unique and must "
                "not be silently overwritten"
            )
        record = RecoveryEscrowRecord(
            record_identity=record_identity,
            reason=reason,
            custodied_entry=entry,
            custodied_result=result,
            reservation_identity=reservation_identity,
            handling_operation_attempt_identity=handling_operation_attempt_identity,
        )
        self._records[record.record_identity] = record
        return record

    def escrow_records(self) -> tuple[RecoveryEscrowRecord, ...]:
        """The records currently in this owner's custody."""
        return tuple(self._records.values())

    def transfer_out(
        self, record_identity: str, recipient_owner: RecoveryOwner | None = None
    ) -> RecoveryEscrowRecord:
        """Transfer a record out of this owner's custody.

        Verifiable: the record is removed from this owner's escrow and, when a
        recipient owner is designated, re-escrowed there under the SAME record
        identity with ``transferred_to`` naming this owner. Unknown record
        identities raise ``KeyError``.
        """
        try:
            record = self._records.pop(record_identity)
        except KeyError:
            raise KeyError(
                f"no escrow record {record_identity!r} in RecoveryOwner "
                f"{self._name!r}"
            ) from None
        if recipient_owner is None:
            return record
        if recipient_owner is self:
            raise ValueError(
                "cannot transfer a record to the RecoveryOwner already holding it"
            )
        transferred = RecoveryEscrowRecord(
            record_identity=record.record_identity,
            reason=record.reason,
            custodied_entry=record.custodied_entry,
            custodied_result=record.custodied_result,
            reservation_identity=record.reservation_identity,
            handling_operation_attempt_identity=(
                record.handling_operation_attempt_identity
            ),
            transferred_to=self._name,
        )
        recipient_owner._records[transferred.record_identity] = transferred
        return transferred


def _require_exact_type(field_name: str, value: object, expected: type) -> None:
    """Exact-type check: nominal identity roles must never collapse."""
    if type(value) is not expected:
        raise TypeError(
            f"{field_name} must be exactly {expected.__name__}, "
            f"got {type(value).__name__}"
        )
