"""Single Step Publication Specialization: Recovery Owner, escrow, custody trace.

Implementation task: 07_Publication
Related diagrams:
  class: 03_Diagrams_Codes_Files/04_Error_Handling.dot
  sequence: B_Sequencial_Diagram_Code/08_Publication_Specialization_Sequence.puml
  association: C_Association_Diagram_Code/07_Publication_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/04_Supporting_Pattern_Optional_Dependency.dot

Contract basis:
  - Single_Step_Publication_Specialization_Contract.json (``publisherViolationRecovery``,
    ``ambiguousAcceptanceEscrow``, ``endToEndContract`` required trace)
  - Common/11,00_Publication.json (``custodyAndRecovery``: custody phases,
    ambiguous-acceptance procedure, prohibited recovery shortcuts)
  - ErrorHandlingUnit_Contract.json / OperationEntryPublisher_Contract.json

Dependency boundary: identical to the whole Error Handling pattern —
``ErrorHandlingUnit -> Core : NO dependency``, ``-> Prefect : NO dependency``;
this module imports only its sibling pattern modules (stdlib only).

This module is the Recovery Owner SPECIALIZATION SURFACE for a concrete Step:

  - :class:`CustodyPhase` / :class:`CustodyTraceRecorder` — the end-to-end
    state and custody trace covering every mandatory branch; each Step's
    publication flow records its custody phases so every branch ends in a
    known custodian or an explicitly represented unresolved/escalated state.
  - :class:`AmbiguousAcceptanceEscrow` + :class:`AmbiguousAcceptanceEscrowRecord`
    — the Step-owned escrow that keeps the COMPLETE result/entry recoverable
    while acceptance is indeterminate. Escrow records are marked
    NON-PUBLISHABLE (they are not accepted ``ErrorHandlingOperationEntry``
    values and must never be counted in ``ErrorHandlerResult``), are
    correlated to publisher/invocation/reservation/attempt/operation/
    accepted-entry identities, and are reconciled exactly once so no accepted
    entry can be aggregated twice and no second logical publication can be
    created silently.
  - :class:`PublicationRecoveryProcedure` — the decision procedure for
    ambiguous outcomes and Publisher Contract Violations: freeze the attempt
    (never start a replacement execution for the same logical operation),
    determine acceptance ONLY from authoritative Publisher evidence, retry
    only the same immutable entry under the same reservation when the state
    is Reserved and the Publisher guarantees remain trustworthy, escrow and
    escalate whenever acceptance stays indeterminate, and record the final
    custody disposition. An exception, a missing acknowledgement, or a failed
    status query is NEVER treated as proof of rejection and never authorizes
    result disposal.
  - Re-exports of :class:`PublicationSequencePolicy`,
    :class:`PublicationIdentityPolicy`, and
    :class:`PublicationStatusRetentionPolicy` — the ``publicationSequenceNumber``
    and identity/retention rules of the specialization surface.

Prohibited shortcuts (enforced by construction below): discarding a produced
result because publish threw or returned no acknowledgement; treating a
status-query failure as non-acceptance; releasing a reservation while a result
is pending without explicit custody transfer; starting a replacement operation
attempt while acceptance is indeterminate; aggregating an escrow record as if
it were an accepted entry.
"""

from __future__ import annotations

import enum
import threading
from dataclasses import dataclass, replace

from .error_handling_unit import (
    ErrorHandlingOperationEntry,
    RecoveryOwner,
)
from .identities import (
    HandlingOperationAttemptIdentity,
    HandlingOperationIdentity,
)
from .operation_entry_publisher import (
    AcceptanceKnowledge,
    OperationEntryPublisher,
    PublicationIdentityPolicy,
    PublicationSequencePolicy,
    PublicationStatus,
    PublicationStatusQuery,
    PublicationStatusRetentionPolicy,
    StatusQueryOutcome,
    PublisherContractViolation,
)

__all__ = [
    "CustodyPhase",
    "CustodyDisposition",
    "CustodyTraceEntry",
    "CustodyTraceRecorder",
    "AmbiguousAcceptanceEscrowRecord",
    "AmbiguousAcceptanceEscrow",
    "RecoveryDecision",
    "PublicationRecoveryProcedure",
    # specialization rule surfaces (defined with the publication protocol)
    "PublicationSequencePolicy",
    "PublicationIdentityPolicy",
    "PublicationStatusRetentionPolicy",
]


class CustodyPhase(enum.Enum):
    """The custody phases of the reservation-backed publication protocol.

    Every successfully produced ``THandlingOperationResult`` passes through
    these phases with NO custody gap: before acceptance the Unit or the
    Recovery Owner retains a complete recoverable representation; after
    confirmed acceptance the Publisher/Composition owns retention; during
    indeterminate acceptance a Step-owned escrow may retain a safety copy while
    the Publisher may already have accepted the same logical entry (an
    explicitly represented custody-indeterminate state, never a second
    publication).
    """

    BEFORE_RESULT_PRODUCTION = "before-result-production"
    RESULT_PRODUCED_BEFORE_ACCEPTANCE = "result-produced-before-acceptance"
    EXPLICIT_RECOVERY_TRANSFER = "explicit-recovery-transfer"
    ATOMIC_ACCEPTANCE = "atomic-acceptance"
    ACCEPTANCE_INDETERMINATE = "acceptance-indeterminate"
    AFTER_AGGREGATION = "after-aggregation"


class CustodyDisposition(enum.Enum):
    """Final recorded custody disposition of one produced result/entry.

    Every branch must end in a known custodian or in the explicitly
    represented unresolved/escalated state — no false success and no false
    rejection is ever recorded.
    """

    PUBLISHER_ACCEPTED = "publisher-accepted"
    RECOVERY_OWNER_RETAINED = "recovery-owner-retained"
    TRANSFERRED_TO_ALTERNATE_OWNER = "transferred-to-alternate-owner"
    UNRESOLVED_ESCALATED = "unresolved-escalated"


@dataclass(frozen=True)
class CustodyTraceEntry:
    """One recorded custody/state transition of the end-to-end trace."""

    order: int
    phase: CustodyPhase
    reservation_identity: str | None = None
    handling_operation_attempt_identity: str | None = None
    handling_operation_identity: str | None = None
    note: str = ""


class CustodyTraceRecorder:
    """Thread-safe recorder of the end-to-end state and custody trace.

    Each Step's publication flow records its custody phases from attempt
    identity allocation through reservation grant, operation start, result
    production, entry preparation, publish, atomic acceptance / indeterminate
    acceptance, reconciliation, collection, and aggregation, so the complete
    trace proves there is no result-custody gap on any branch.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: list[CustodyTraceEntry] = []
        self._order = 0

    def record(
        self,
        phase: CustodyPhase,
        *,
        reservation_identity: str | None = None,
        handling_operation_attempt_identity: str | None = None,
        handling_operation_identity: str | None = None,
        note: str = "",
    ) -> CustodyTraceEntry:
        with self._lock:
            self._order += 1
            entry = CustodyTraceEntry(
                order=self._order,
                phase=phase,
                reservation_identity=reservation_identity,
                handling_operation_attempt_identity=handling_operation_attempt_identity,
                handling_operation_identity=handling_operation_identity,
                note=note,
            )
            self._entries.append(entry)
            return entry

    def entries(self) -> tuple[CustodyTraceEntry, ...]:
        """The trace in recorded order (monotonic; never reordered)."""
        with self._lock:
            return tuple(self._entries)

    def phases(self) -> tuple[CustodyPhase, ...]:
        with self._lock:
            return tuple(entry.phase for entry in self._entries)

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


@dataclass(frozen=True)
class AmbiguousAcceptanceEscrowRecord:
    """One Step-owned escrow record of a produced-but-unaccepted result.

    Holds the COMPLETE result and/or prepared entry (never only an error
    message or identities) correlated to publisher, invocation, reservation,
    attempt, operation, and accepted-entry identities, so the escrow record
    can be reconciled against the authoritative Publisher evidence later.

    Invariants:

    - ``publishable`` is always False: an escrow record is NOT an accepted
      ``ErrorHandlingOperationEntry`` and must never be published again nor
      counted in ``ErrorHandlerResult`` — it prevents a second logical
      publication while acceptance is indeterminate.
    - ``reconciled`` records whether the final disposition was already
      determined; reconciliation happens exactly once.
    """

    escrow_identity: str
    reason: str
    entry: ErrorHandlingOperationEntry[object] | None
    result: object | None
    publisher_identity: str | None = None
    invocation_identity: str | None = None
    publication_reservation_identity: str | None = None
    handling_operation_attempt_identity: str | None = None
    handling_operation_identity: str | None = None
    accepted_entry_identity: str | None = None
    publishable: bool = False
    reconciled: bool = False
    disposition: CustodyDisposition | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.entry is None and self.result is None:
            raise ValueError(
                "an escrow record custodies the complete result and/or the "
                "prepared entry, not only identities or an error message"
            )
        if self.publishable:
            raise ValueError(
                "an escrow record is non-publishable while acceptance is "
                "indeterminate; it is not an accepted operation entry"
            )
        if self.reconciled != (self.disposition is not None):
            raise ValueError(
                "reconciliation state and disposition must be set together"
            )


class AmbiguousAcceptanceEscrow:
    """Step-owned escrow retaining complete recoverable representations.

    The escrow keeps the complete result/entry recoverable before the Unit
    relinquishes its last recoverable reference, so nothing is silently lost
    while acceptance is indeterminate. At most one escrow record per identity
    (no silent overwrite); reconciliation is exactly-once so an escrow record
    can never be aggregated twice and no second accepted entry can be created
    silently.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, AmbiguousAcceptanceEscrowRecord] = {}

    def take_into_escrow(
        self,
        *,
        escrow_identity: str,
        reason: str,
        entry: ErrorHandlingOperationEntry[object] | None = None,
        result: object | None = None,
        publisher_identity: str | None = None,
        invocation_identity: str | None = None,
        publication_reservation_identity: str | None = None,
        handling_operation_attempt_identity: str | None = None,
        handling_operation_identity: str | None = None,
        accepted_entry_identity: str | None = None,
    ) -> AmbiguousAcceptanceEscrowRecord:
        """Take the complete result/entry into escrow (non-publishable)."""
        if not isinstance(escrow_identity, str) or escrow_identity == "":
            raise ValueError("escrow_identity must be a non-empty string")
        with self._lock:
            if escrow_identity in self._records:
                raise ValueError(
                    f"escrow identity {escrow_identity!r} already exists; "
                    "escrow identities are unique and never silently overwritten"
                )
            record = AmbiguousAcceptanceEscrowRecord(
                escrow_identity=escrow_identity,
                reason=reason,
                entry=entry,
                result=result,
                publisher_identity=publisher_identity,
                invocation_identity=invocation_identity,
                publication_reservation_identity=publication_reservation_identity,
                handling_operation_attempt_identity=handling_operation_attempt_identity,
                handling_operation_identity=handling_operation_identity,
                accepted_entry_identity=accepted_entry_identity,
            )
            self._records[escrow_identity] = record
            return record

    def escrow_records(self) -> tuple[AmbiguousAcceptanceEscrowRecord, ...]:
        """The records currently held in escrow."""
        with self._lock:
            return tuple(self._records.values())

    def pending_records(self) -> tuple[AmbiguousAcceptanceEscrowRecord, ...]:
        """The records whose final disposition is not yet reconciled."""
        with self._lock:
            return tuple(
                record for record in self._records.values() if not record.reconciled
            )

    def _reconcile(
        self,
        record_identity: str,
        disposition: CustodyDisposition,
        note: str,
    ) -> AmbiguousAcceptanceEscrowRecord:
        """Exactly-once reconciliation helper (lock held)."""
        record = self._records.get(record_identity)
        if record is None:
            raise KeyError(
                f"no escrow record {record_identity!r} in the ambiguous-"
                "acceptance escrow"
            )
        if record.reconciled:
            raise ValueError(
                f"escrow record {record_identity!r} was already reconciled as "
                f"{record.disposition.name}; an escrow record is reconciled "
                "exactly once so no accepted entry is aggregated twice"
            )
        reconciled = replace(
            record, reconciled=True, disposition=disposition, note=note
        )
        self._records[record_identity] = reconciled
        return reconciled

    def reconcile_as_accepted(
        self, record_identity: str, note: str = ""
    ) -> AmbiguousAcceptanceEscrowRecord:
        """Reconcile against authoritative Consumed evidence: the Publisher
        accepted the entry; the escrow safety copy is released (never
        aggregated, never republished)."""
        with self._lock:
            return self._reconcile(
                record_identity,
                CustodyDisposition.PUBLISHER_ACCEPTED,
                note or "reconciled against authoritative Consumed status",
            )

    def retain_as_recovery_custody(
        self, record_identity: str, note: str = ""
    ) -> AmbiguousAcceptanceEscrowRecord:
        """Record that the Recovery Owner retains the result (definitely not
        accepted — e.g. a pre-acceptance contract violation)."""
        with self._lock:
            return self._reconcile(
                record_identity,
                CustodyDisposition.RECOVERY_OWNER_RETAINED,
                note or "recovery owner retains the definitely-not-accepted result",
            )

    def escalate_unresolved(
        self, record_identity: str, note: str = ""
    ) -> AmbiguousAcceptanceEscrowRecord:
        """Escalate: acceptance could not be determined within the Step's
        operational horizon; the record is retained and escalated."""
        with self._lock:
            return self._reconcile(
                record_identity,
                CustodyDisposition.UNRESOLVED_ESCALATED,
                note or "acceptance remained indeterminate within the "
                "Step-defined horizon; escalated",
            )

    def transfer_to_alternate_owner(
        self, record_identity: str, recipient_owner: RecoveryOwner, note: str = ""
    ) -> AmbiguousAcceptanceEscrowRecord:
        """Transfer the custodied material to an alternate Step-owned owner
        through the verifiable Recovery Owner custody protocol."""
        if not isinstance(recipient_owner, RecoveryOwner):
            raise TypeError(
                "recipient_owner must be a RecoveryOwner (verifiable custody)"
            )
        with self._lock:
            record = self._records.get(record_identity)
            if record is None:
                raise KeyError(
                    f"no escrow record {record_identity!r} in the ambiguous-"
                    "acceptance escrow"
                )
            if record.reconciled:
                raise ValueError(
                    f"escrow record {record_identity!r} was already reconciled"
                )
        transferred = recipient_owner.take_custody(
            record_identity=record.escrow_identity,
            reason=record.reason,
            entry=record.entry,
            result=record.result,
            reservation_identity=record.publication_reservation_identity,
            handling_operation_attempt_identity=(
                record.handling_operation_attempt_identity
            ),
        )
        with self._lock:
            return self._reconcile(
                record_identity,
                CustodyDisposition.TRANSFERRED_TO_ALTERNATE_OWNER,
                note
                or f"custody transferred to {recipient_owner.name} "
                f"({transferred.record_identity})",
            )

    def record_disposition(
        self, record_identity: str
    ) -> CustodyDisposition | None:
        """The recorded final disposition, or None while unreconciled."""
        with self._lock:
            record = self._records.get(record_identity)
            return record.disposition if record is not None else None


@dataclass(frozen=True)
class RecoveryDecision:
    """Outcome of the recovery procedure for one ambiguous/violated publication.

    ``disposition`` is the procedure's DECISION disposition (None only when
    the decision hands the same immutable entry back to the Unit for a
    permitted same-reservation retry). The escrow record it carries stays
    PENDING: its final disposition is recorded by the exactly-once
    reconciliation when authoritative evidence becomes available, or by the
    Step's explicit horizon decision (``escalate_unresolved``).
    ``replacement_execution_permitted`` is always False: the procedure never
    permits a replacement operation execution for a logical operation whose
    publication outcome is ambiguous or violated. ``retry_permitted`` is True
    ONLY when authoritative evidence shows Reserved and the Publisher
    guarantees remain trustworthy — and even then only the SAME immutable
    entry under the SAME reservation may be retried.
    """

    disposition: CustodyDisposition | None
    retry_permitted: bool = False
    replacement_execution_permitted: bool = False
    escrow_record: AmbiguousAcceptanceEscrowRecord | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.replacement_execution_permitted:
            raise ValueError(
                "the recovery procedure never permits a replacement operation "
                "execution for an ambiguous or violated publication"
            )
        if self.retry_permitted and (
            self.disposition is not None or self.escrow_record is not None
        ):
            raise ValueError(
                "a retry-permitted decision neither finalizes a disposition "
                "nor escrows the entry"
            )


class PublicationRecoveryProcedure:
    """Decision procedure for ambiguous outcomes and contract violations.

    Implements the mandatory recovery decision procedure on top of the
    Publisher's authoritative evidence and the Step-owned escrow:

    1. Freeze the affected attempt's publication state — a replacement
       execution for the same logical operation is never permitted.
    2. Preserve the complete result/entry (Unit custody, Recovery Owner
       custody, or escrow) before any unwinding or resource release.
    3. Determine acceptance ONLY from the authoritative Publisher status
       evidence; a failed/unavailable/unknown/expired query leaves acceptance
       INDETERMINATE and is never proof of rejection.
    4. Definitely accepted → reconcile the original acknowledgement/entry; no
       duplicate recovery publication and no second accepted entry.
    5. Reserved + trustworthy guarantees → retry the SAME immutable entry under
       the SAME reservation only.
    6. Released while a produced result is pending → Publisher Contract
       Violation; the Recovery Owner retains the result.
    7. Indeterminate → escrow the complete representation (non-publishable),
       prohibit a second publication/attempt, and escalate; the record is
       reconciled when evidence later becomes available.
    """

    def __init__(
        self,
        recovery_owner: RecoveryOwner,
        escrow: AmbiguousAcceptanceEscrow,
        trace: CustodyTraceRecorder | None = None,
    ) -> None:
        if not isinstance(recovery_owner, RecoveryOwner):
            raise TypeError("recovery_owner must be a RecoveryOwner")
        if not isinstance(escrow, AmbiguousAcceptanceEscrow):
            raise TypeError("escrow must be an AmbiguousAcceptanceEscrow")
        self._recovery_owner = recovery_owner
        self._escrow = escrow
        self._trace = trace

    # ------------------------------------------------------------------ #
    # Trace helpers
    # ------------------------------------------------------------------ #

    def _record(
        self,
        phase: CustodyPhase,
        *,
        reservation_identity: str | None = None,
        attempt_identity: str | None = None,
        operation_identity: str | None = None,
        note: str = "",
    ) -> None:
        if self._trace is not None:
            self._trace.record(
                phase,
                reservation_identity=reservation_identity,
                handling_operation_attempt_identity=attempt_identity,
                handling_operation_identity=operation_identity,
                note=note,
            )

    # ------------------------------------------------------------------ #
    # Ambiguous publish outcome
    # ------------------------------------------------------------------ #

    def resolve_ambiguous_publication(
        self,
        *,
        result: object,
        entry: ErrorHandlingOperationEntry[object],
        attempt_identity: HandlingOperationAttemptIdentity,
        operation_identity: HandlingOperationIdentity | None = None,
        reservation: object | None = None,
        status: PublicationStatusQuery | None,
        publisher: OperationEntryPublisher[object] | None = None,
    ) -> RecoveryDecision:
        """Resolve a publish outcome whose acknowledgement was lost, threw, or
        was never observed.

        ``status`` is the authoritative Publisher status envelope; pass None
        when the status query itself failed (exception/transport loss) — that
        is INDETERMINATE, never proof of rejection.
        """
        reservation_identity = (
            str(reservation.identity) if reservation is not None else None
        )
        accepted_entry_reference = None
        if entry is not None:
            accepted_entry_reference = (
                f"{entry.error_handling_unit_identity.value}/"
                f"{entry.handling_operation_identity.value}"
            )

        if status is None or status.outcome in (
            StatusQueryOutcome.INDETERMINATE,
            StatusQueryOutcome.UNAVAILABLE,
            StatusQueryOutcome.UNKNOWN,
            StatusQueryOutcome.INVALID_CAPABILITY,
            StatusQueryOutcome.EXPIRED,
        ):
            # Acceptance knowledge is unresolved: escrow the COMPLETE
            # representation, mark it non-publishable, prohibit a second
            # publication/attempt, and escalate.
            escrow_record = self._escrow.take_into_escrow(
                escrow_identity=f"escrow-{accepted_entry_reference or id(result)}",
                reason=(
                    "publication acceptance indeterminate: "
                    + (
                        "status query failed/unavailable"
                        if status is None
                        else f"status outcome {status.outcome.value}"
                    )
                ),
                entry=entry,
                result=result,
                publisher_identity=(
                    str(status.publisher_identity)
                    if status is not None and status.publisher_identity is not None
                    else None
                ),
                invocation_identity=(
                    str(status.invocation_identity)
                    if status is not None and status.invocation_identity is not None
                    else None
                ),
                publication_reservation_identity=(
                    status.publication_reservation_identity.value
                    if status is not None
                    and status.publication_reservation_identity is not None
                    else reservation_identity
                ),
                handling_operation_attempt_identity=attempt_identity.value,
                handling_operation_identity=(
                    operation_identity.value if operation_identity else None
                ),
                accepted_entry_identity=accepted_entry_reference,
            )
            self._record(
                CustodyPhase.ACCEPTANCE_INDETERMINATE,
                reservation_identity=reservation_identity,
                attempt_identity=attempt_identity.value,
                operation_identity=(
                    operation_identity.value if operation_identity else None
                ),
                note="complete result escrowed non-publishable; escalated",
            )
            return RecoveryDecision(
                disposition=CustodyDisposition.UNRESOLVED_ESCALATED,
                escrow_record=escrow_record,
                note=(
                    "acceptance indeterminate: complete result retained in "
                    "escrow, second publication prohibited"
                ),
            )

        assert status.outcome is StatusQueryOutcome.DETERMINABLE
        lifecycle = status.lifecycle_state
        assert lifecycle is not None

        if lifecycle is PublicationStatus.CONSUMED:
            # Definitely accepted: reconcile the original acknowledgement/entry;
            # never publish a duplicate.
            self._record(
                CustodyPhase.ATOMIC_ACCEPTANCE,
                reservation_identity=reservation_identity,
                attempt_identity=attempt_identity.value,
                operation_identity=(
                    operation_identity.value if operation_identity else None
                ),
                note="reconciled against authoritative Consumed status",
            )
            return RecoveryDecision(
                disposition=CustodyDisposition.PUBLISHER_ACCEPTED,
                note="publication accepted; no duplicate recovery publication",
            )

        if lifecycle is PublicationStatus.RESERVED:
            # Not accepted; Publisher guarantees remain trustworthy. Only the
            # SAME immutable entry under the SAME reservation may be retried.
            self._record(
                CustodyPhase.RESULT_PRODUCED_BEFORE_ACCEPTANCE,
                reservation_identity=reservation_identity,
                attempt_identity=attempt_identity.value,
                operation_identity=(
                    operation_identity.value if operation_identity else None
                ),
                note="authoritative Reserved status: same-entry retry permitted",
            )
            return RecoveryDecision(
                disposition=None,
                retry_permitted=True,
                note=(
                    "retry ONLY the same immutable entry under the same "
                    "reservation"
                ),
            )

        # RELEASED while a produced result is still pending publication is a
        # Publisher/Composition contract violation: the Recovery Owner retains.
        escrow_record = self._escrow.take_into_escrow(
            escrow_identity=f"escrow-{accepted_entry_reference}",
            reason=(
                "publisher contract violation: Released status while a "
                "produced result remained pending publication"
            ),
            entry=entry,
            result=result,
            publisher_identity=(
                str(status.publisher_identity)
                if status.publisher_identity is not None
                else None
            ),
            invocation_identity=(
                str(status.invocation_identity)
                if status.invocation_identity is not None
                else None
            ),
            publication_reservation_identity=(
                status.publication_reservation_identity.value
                if status.publication_reservation_identity is not None
                else reservation_identity
            ),
            handling_operation_attempt_identity=attempt_identity.value,
            handling_operation_identity=(
                operation_identity.value if operation_identity else None
            ),
            accepted_entry_identity=accepted_entry_reference,
        )
        self._record(
            CustodyPhase.EXPLICIT_RECOVERY_TRANSFER,
            reservation_identity=reservation_identity,
            attempt_identity=attempt_identity.value,
            operation_identity=(
                operation_identity.value if operation_identity else None
            ),
            note="Released-with-pending-result violation: recovery owner retains",
        )
        return RecoveryDecision(
            disposition=CustodyDisposition.RECOVERY_OWNER_RETAINED,
            escrow_record=escrow_record,
            note="Released-with-pending-result is a Publisher contract violation",
        )

    # ------------------------------------------------------------------ #
    # Publisher contract violation
    # ------------------------------------------------------------------ #

    def resolve_publisher_contract_violation(
        self,
        *,
        violation: PublisherContractViolation,
        result: object,
        entry: ErrorHandlingOperationEntry[object] | None = None,
        attempt_identity: HandlingOperationAttemptIdentity | None = None,
        operation_identity: HandlingOperationIdentity | None = None,
    ) -> RecoveryDecision:
        """Recovery disposition for a Publisher Contract Violation.

        For a pre-acceptance violation the Recovery Owner is distinct from the
        failed Publisher retention path; the complete result (and prepared
        entry when available) is escrowed here. Retry through the violated
        Publisher path is never blindly permitted.
        """
        accepted_entry_reference = None
        if entry is not None:
            accepted_entry_reference = (
                f"{entry.error_handling_unit_identity.value}/"
                f"{entry.handling_operation_identity.value}"
            )
        knowledge = violation.acceptance_knowledge

        if knowledge is AcceptanceKnowledge.DEFINITELY_ACCEPTED:
            # The Publisher accepted despite the inconsistency; reconcile and
            # never create a duplicate recovery publication.
            self._record(
                CustodyPhase.ATOMIC_ACCEPTANCE,
                reservation_identity=(
                    str(violation.publication_reservation_identity)
                    if violation.publication_reservation_identity
                    else None
                ),
                attempt_identity=(
                    violation.handling_operation_attempt_identity.value
                    if violation.handling_operation_attempt_identity
                    else (
                        attempt_identity.value if attempt_identity else None
                    )
                ),
                operation_identity=(
                    operation_identity.value if operation_identity else None
                ),
                note="violation after confirmed acceptance; reconciled",
            )
            return RecoveryDecision(
                disposition=CustodyDisposition.PUBLISHER_ACCEPTED,
                note="violation with definitely-accepted knowledge: reconciled",
            )

        escrow_record = self._escrow.take_into_escrow(
            escrow_identity=(
                f"escrow-{violation.violation_identity or accepted_entry_reference or id(result)}"
            ),
            reason=(
                f"publisher contract violation [{violation.violation_code}] "
                f"in phase {violation.phase or 'unknown'}: "
                f"{violation.violated_guarantee or (violation.args[0] if violation.args else '')}"
            ),
            entry=entry,
            result=result,
            publisher_identity=(
                str(violation.publisher_identity)
                if violation.publisher_identity is not None
                else None
            ),
            invocation_identity=(
                str(violation.invocation_identity)
                if violation.invocation_identity is not None
                else None
            ),
            publication_reservation_identity=(
                str(violation.publication_reservation_identity)
                if violation.publication_reservation_identity is not None
                else None
            ),
            handling_operation_attempt_identity=(
                violation.handling_operation_attempt_identity.value
                if violation.handling_operation_attempt_identity is not None
                else (attempt_identity.value if attempt_identity else None)
            ),
            handling_operation_identity=(
                violation.handling_operation_identity
                or (operation_identity.value if operation_identity else None)
            ),
            accepted_entry_identity=accepted_entry_reference,
        )
        self._record(
            CustodyPhase.EXPLICIT_RECOVERY_TRANSFER,
            reservation_identity=(
                str(violation.publication_reservation_identity)
                if violation.publication_reservation_identity
                else None
            ),
            attempt_identity=(
                violation.handling_operation_attempt_identity.value
                if violation.handling_operation_attempt_identity
                else (attempt_identity.value if attempt_identity else None)
            ),
            operation_identity=(
                operation_identity.value if operation_identity else None
            ),
            note=(
                "publisher contract violation: complete result escrowed with "
                f"acceptance knowledge {knowledge.value}"
            ),
        )
        if knowledge is AcceptanceKnowledge.DEFINITELY_NOT_ACCEPTED:
            decision = RecoveryDecision(
                disposition=CustodyDisposition.RECOVERY_OWNER_RETAINED,
                escrow_record=escrow_record,
                note=(
                    "pre-acceptance violation: recovery owner retains; retry "
                    "through the violated path is not blindly permitted"
                ),
            )
            self._escrow.retain_as_recovery_custody(
                escrow_record.escrow_identity,
                note=decision.note,
            )
            return decision

        decision = RecoveryDecision(
            disposition=CustodyDisposition.UNRESOLVED_ESCALATED,
            escrow_record=escrow_record,
            note=(
                "violation with indeterminate acceptance: escrow retained and "
                "escalated; second publication prohibited"
            ),
        )
        # The record stays PENDING: the final disposition is reconciled
        # exactly once when authoritative evidence becomes available (or the
        # Step explicitly closes its horizon via escalate_unresolved).
        return decision

    # ------------------------------------------------------------------ #
    # Verifiable custody transfer into the Recovery Owner
    # ------------------------------------------------------------------ #

    def confirm_recovery_owner_custody(
        self,
        *,
        record_identity: str,
        reason: str,
        result: object | None = None,
        entry: ErrorHandlingOperationEntry[object] | None = None,
        reservation_identity: str | None = None,
        attempt_identity: HandlingOperationAttemptIdentity | None = None,
    ) -> CustodyDisposition:
        """Explicitly transfer custody to the named Recovery Owner.

        Verifiable two-sided transfer: the Unit hands the complete result/entry
        to the Recovery Owner BEFORE unwinding or releasing resources (a
        Unit-local variable lost on unwind is not a Recovery Owner). Returns
        the recorded disposition.
        """
        self._recovery_owner.take_custody(
            record_identity=record_identity,
            reason=reason,
            entry=entry,
            result=result,
            reservation_identity=reservation_identity,
            handling_operation_attempt_identity=(
                attempt_identity.value if attempt_identity else None
            ),
        )
        self._record(
            CustodyPhase.EXPLICIT_RECOVERY_TRANSFER,
            reservation_identity=reservation_identity,
            attempt_identity=(
                attempt_identity.value if attempt_identity else None
            ),
            note=f"custody transferred to recovery owner ({record_identity})",
        )
        return CustodyDisposition.RECOVERY_OWNER_RETAINED
