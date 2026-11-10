"""OperationEntryPublisher[THandlingOperationResult] — publication protocol with
the per-Step specialization surface.

Implementation tasks: 04_Error_Handling (working protocol machinery),
07_Publication (Single Step Publication Specialization surface)
Related diagrams:
  class: 03_Diagrams_Codes_Files/04_Error_Handling.dot
  sequence: B_Sequencial_Diagram_Code/02_Error_Handling_Sequence.puml
           B_Sequencial_Diagram_Code/08_Publication_Specialization_Sequence.puml
  association: C_Association_Diagram_Code/04_Error_Handling_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/04_Supporting_Pattern_Optional_Dependency.dot

Contract basis:
  - OperationEntryPublisher_Contract.json (``pipeline.operation-entry-publisher.contract``)
  - PublicationReservation_Contract.json (``pipeline.publication-reservation.contract``)
  - Single_Step_Publication_Specialization_Contract.json (task 07 minimum
    information for protocol representations, no-fail transfer, violation
    evidence, identity rules, status retention/expiry)
  - Common/11,00_Publication.json (query outcomes vs lifecycle states,
    custody phases, no universal implementation)

Task 04 scope (working machinery): reserve / publish / publication-status /
release, atomic acceptance, capacity accounting, the reservation state machine,
and idempotent retry.

Task 07 scope (specialization surface, added here and in ``recovery.py``):

  - Correlated protocol envelopes: ``ReservationGrant`` carries the binding
    identities and the capacity/handoff commitment evidence; an accepted
    ``PublicationAcknowledgement`` carries publisher/invocation/reservation/
    unit/attempt/operation identities, the derived ``AcceptedEntryIdentity``,
    and the ``publicationSequenceNumber`` — evidence sufficient to correlate an
    idempotent retry with the original acceptance.
  - ``AcceptedEntryIdentity`` is DERIVED from the entry's composite identity
    (errorHandlingUnitIdentity + handlingOperationIdentity): one attempt starts
    at most one execution and one reservation accepts at most one entry, so the
    derived value can never designate two different entries. Identity values
    are never reused while any reservation, acknowledgement, status record,
    recovery record, accepted entry, or aggregate may still refer to them; a
    replacement Publisher/Unit instance receives a distinct identity.
  - ``PublisherContractViolation`` carries the minimum evidence: violation
    identity and stable code, the known protocol identities, the phase, the
    acceptance knowledge (definitely-not-accepted / definitely-accepted /
    indeterminate), the violated guarantee, the current custodian marker, and
    the recovery reference.
  - Status queries distinguish query OUTCOMES from lifecycle STATES:
    ``StatusQueryOutcome`` (DETERMINABLE/UNKNOWN/INDETERMINATE/UNAVAILABLE/
    INVALID_CAPABILITY/EXPIRED) is not a reservation lifecycle state and a
    failed or expired query is never mapped to Reserved/Released/definitely-
    not-accepted. ``query_publication_status`` returns the full envelope;
    ``get_publication_status`` remains the simple lifecycle accessor.
  - No-fail final ownership-transfer strategy: reserve preallocates a fully
    owning ``PreallocatedEntryEnvelope`` retention slot per reservation. The
    acceptance path's transfer is a fixed-slot reference assignment — no
    allocation of entry payload, no serialization/conversion/deep-copy, and no
    arbitrary user-defined code executes inside the acceptance boundary. All
    fallible entry preparation happens in the Unit before ``publish``.
  - Status-record retention: terminal records are reclaimed only by explicit
    Composition decision (``retire_terminal_records``) once the accepted entry
    is collected and retry observers have left scope; retirement keeps a
    TOMBSTONE (identity + terminal state + sequence) so stale capabilities are
    rejected, late queries report EXPIRED (never definitely-not-accepted), and
    identity reuse cannot make a stale query resolve to a different publication.
    Reserved records are never removed while acceptance may be pending.

Key semantics implemented (per the contracts):

  - The Publisher is the AUTHORITATIVE delivery path for operation entries; it
    is owned by the Step-specific Error Handling Composition and supplied to the
    Unit for one invocation. The Publisher does not schedule operations and
    imposes no semantic ordering.
  - ``reserve`` is called BEFORE the corresponding Handling Operation begins,
    with an attempt identity allocated by the Unit. A granted reservation is
    permanently bound to this Publisher, the invocation, the Unit, the attempt,
    and the Step instance / Unit Association / association target supplied for
    the invocation. One attempt may start at most one actual execution; a
    rejected (or later retried) reserve request burns its attempt identity.
  - Capacity: reservations commit COMPLETE-entry retention capacity. The
    Publisher accounts for outstanding Reserved capacity AND already Occupied
    capacity when granting additional reservations
    (``TotalCapacity >= ReservedCapacity + OccupiedCapacity``); requests that
    would exceed it receive an ordinary rejection — no over-commit. A granted
    reservation is never later rejected for ordinary capacity exhaustion.
  - Atomic acceptance: publication is ONE indivisible transition in which the
    complete matching entry becomes retained and the reservation becomes
    Consumed. Before it, no entry is visible and the reservation stays
    Reserved; after it, acceptance cannot be revoked by a later exception, lost
    acknowledgement, or Unit termination. Ownership transfers ONLY at this
    point; calling ``publish`` alone does not transfer retention responsibility.
  - Idempotent retry: a repeated publish of the SAME logical entry (equal entry
    identity and immutable content) under a Consumed reservation returns an
    acknowledgement identifying the ORIGINAL acceptance — no second entry, no
    second capacity consumption. A different entry under a Consumed reservation
    is never accepted (invalid reuse / conflicting reuse).
  - Status query resolves ambiguous outcomes (exception or lost acknowledgement
    after the acceptance point may have been crossed). Lookup is scoped to the
    exact issuing Publisher and reservation; an unknown, foreign, or invalid
    reservation is reported distinctly from the three valid states; a status
    lookup never mutates the reservation.
  - Release is an explicit operation (never inferred from normal return,
    exception propagation, or invocation closure). Release of a Consumed
    reservation is rejected; re-release of an already Released reservation is
    idempotent and returns capacity only once. The no-pending-result release
    precondition is a normative Error Handling Unit responsibility the
    Publisher cannot independently inspect.
  - Thread safety: concurrent reserve/publish/status/release requests are
    serialized with a lock so reservations are never over-committed and at most
    one logical entry is accepted per reservation. Thread safety of the
    Publisher does not make the Unit itself thread-safe.
  - Identity generation: counter-based within this Publisher's identity scope
    (representation is implementation-defined; uniqueness within the scope is
    mandatory). The sequence counter is a monotonically increasing unbounded
    integer within one Publisher instance's lifetime; a replacement Publisher
    instance opens a new sequence scope correlated to its own publisherIdentity.
  - PublisherContractViolation is the dedicated channel for the Publisher
    breaching a guarantee attached to a valid reservation; it is distinct from
    an ordinary PublicationRejection and never relabeled as one.
"""

from __future__ import annotations

import enum
import threading
from dataclasses import dataclass

from .error_handling_unit import (
    ErrorHandlingOperationEntry,
)
from .identities import (
    AcceptedEntryIdentity,
    ErrorHandlingInvocationIdentity,
    ErrorHandlingUnitIdentity,
    HandlingOperationAttemptIdentity,
    OperationEntryPublisherIdentity,
    PublicationReservationIdentity,
)

__all__ = [
    "PublicationStatus",
    "PublicationOutcome",
    "AcceptanceKnowledge",
    "StatusQueryOutcome",
    "PublicationStatusQuery",
    "PublicationRejection",
    "PublisherContractViolation",
    "ReservationGrant",
    "PublicationAcknowledgement",
    "ReleaseAcknowledgement",
    "PublicationReservation",
    "PreallocatedEntryEnvelope",
    "PublicationStatusRetentionPolicy",
    "PublicationIdentityPolicy",
    "PublicationSequencePolicy",
    "derive_accepted_entry_identity",
    "OperationEntryPublisher",
]

# Module-private issuer token: only this module's publisher holds a reference,
# so PublicationReservation instances cannot be forged outside the issuing
# publisher (the reservation is an opaque capability).
_ISSUER_TOKEN = object()


class PublicationStatus(enum.Enum):
    """Lifecycle state of one PublicationReservation.

    Reserved: granted, capacity committed, no entry accepted yet.
    Consumed: the matching complete entry was atomically accepted; the
    Publisher/Composition now owns retention responsibility. Terminal.
    Released: explicitly released without accepting an entry; reserved capacity
    returned. Terminal.

    Forbidden transitions (Consumed→anything, Released→Consumed,
    any terminal state back to Reserved) are structurally unrepresentable here:
    only the issuing Publisher can move the state, and it enforces the
    permitted transitions exclusively.
    """

    RESERVED = "reserved"
    CONSUMED = "consumed"
    RELEASED = "released"


class PublicationOutcome(enum.Enum):
    """Outcome of one publish request.

    ACCEPTED: the complete entry was atomically accepted and retained.
    REJECTED: a request-level precondition (validity, binding, identity,
        entry structure, or state) failed; nothing was accepted and no
        ownership transfer occurred.
    CONTRACT_VIOLATION: conflicting reuse that must never yield a second
        accepted entry (distinct from an ordinary rejection).
    """

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CONTRACT_VIOLATION = "contract-violation"


class AcceptanceKnowledge(enum.Enum):
    """Acceptance knowledge carried by violation evidence and recovery records.

    DEFINITELY_NOT_ACCEPTED / DEFINITELY_ACCEPTED / INDETERMINATE — never
    inferred from an exception, a lost acknowledgement, or a failed status
    query (those leave acceptance INDETERMINATE, never definitely-not-accepted).
    """

    DEFINITELY_NOT_ACCEPTED = "definitely-not-accepted"
    DEFINITELY_ACCEPTED = "definitely-accepted"
    INDETERMINATE = "indeterminate"


class StatusQueryOutcome(enum.Enum):
    """Outcome of a publication-status query — NOT a lifecycle state.

    DETERMINABLE: the lifecycle state follows in ``PublicationStatusQuery``.
    UNKNOWN: the reservation identity was never issued by this Publisher.
    INDETERMINATE: the query could not safely complete; acceptance knowledge
        is unresolved (never mapped to Reserved/Released/not-accepted).
    UNAVAILABLE: the retention record exists but is temporarily unavailable.
    INVALID_CAPABILITY: the queried object is not a reservation capability.
    EXPIRED: the status record was reclaimed after the Step-defined retention
        window; a tombstone prevents stale reuse and duplicate acceptance.
    """

    DETERMINABLE = "determinable"
    UNKNOWN = "unknown"
    INDETERMINATE = "indeterminate"
    UNAVAILABLE = "unavailable"
    INVALID_CAPABILITY = "invalid-capability"
    EXPIRED = "expired"


@dataclass(frozen=True)
class PublicationRejection:
    """Descriptive rejection detail (diagnostics only, never an error/outcome).

    ``reason`` is a stable short token; ``detail`` is free-form descriptive
    text. A rejection is a request-level failure: NO acceptance occurred and no
    ownership transfer occurred.
    """

    reason: str
    detail: str = ""


class PublisherContractViolation(RuntimeError):
    """The Publisher breached a guarantee attached to a valid reservation or
    exposed an inconsistent acceptance state.

    Dedicated violation channel: distinguishable from PublicationRejection and
    never relabeled as an ordinary rejection. Carries the Single Step
    Publication Specialization minimum evidence: violation identity and stable
    code/category, the known protocol identities, the phase in which the
    violation occurred, the acceptance knowledge, the violated guarantee and
    diagnostic evidence, the current result custodian (or an explicit
    custody-unresolved marker), and the required recovery handoff/reference
    with its recovery status.

    Reporting the violation discards no Unit-owned result and never obscures
    acceptance knowledge. The concrete typed transport (result vs exception vs
    diagnostic object) remains the owning Step's choice; this class is the
    exception-shaped transport of the full evidence set.
    """

    def __init__(
        self,
        message: str,
        *,
        violation_code: str = "publisher-contract-violation",
        violation_identity: str | None = None,
        publisher_identity: OperationEntryPublisherIdentity | None = None,
        invocation_identity: ErrorHandlingInvocationIdentity | None = None,
        publication_reservation_identity: PublicationReservationIdentity | None = None,
        error_handling_unit_identity: ErrorHandlingUnitIdentity | None = None,
        handling_operation_attempt_identity: HandlingOperationAttemptIdentity | None = None,
        handling_operation_identity: str | None = None,
        phase: str = "",
        acceptance_knowledge: AcceptanceKnowledge = AcceptanceKnowledge.INDETERMINATE,
        violated_guarantee: str = "",
        custodian_marker: str = "custody-unresolved",
        recovery_owner_reference: str | None = None,
        recovery_status: str = "pending",
        diagnostics: str = "",
    ) -> None:
        super().__init__(message)
        self.violation_code = violation_code
        self.violation_identity = violation_identity
        self.publisher_identity = publisher_identity
        self.invocation_identity = invocation_identity
        self.publication_reservation_identity = publication_reservation_identity
        self.error_handling_unit_identity = error_handling_unit_identity
        self.handling_operation_attempt_identity = handling_operation_attempt_identity
        self.handling_operation_identity = handling_operation_identity
        self.phase = phase
        self.acceptance_knowledge = acceptance_knowledge
        self.violated_guarantee = violated_guarantee
        self.custodian_marker = custodian_marker
        self.recovery_owner_reference = recovery_owner_reference
        self.recovery_status = recovery_status
        self.diagnostics = diagnostics


@dataclass(frozen=True)
class ReservationGrant:
    """Outcome of one ``reserve`` request: a granted reservation OR a rejection.

    Exactly one of ``reservation`` / ``rejection`` is present. A granted grant
    carries the correlation identities and the evidence that complete-entry
    retention capacity AND the required handoff path have been committed
    (``capacity_committed``); the opaque capability itself cannot be
    manufactured from the copied identity fields. On rejection no capacity was
    committed and the Unit must NOT begin the associated Handling Operation; a
    new attempt requires a new attempt identity and a new reserve request.
    """

    reservation: PublicationReservation | None = None
    rejection: PublicationRejection | None = None
    publisher_identity: OperationEntryPublisherIdentity | None = None
    invocation_identity: ErrorHandlingInvocationIdentity | None = None
    error_handling_unit_identity: ErrorHandlingUnitIdentity | None = None
    handling_operation_attempt_identity: HandlingOperationAttemptIdentity | None = None
    capacity_committed: bool = False
    diagnostics: str = ""

    def __post_init__(self) -> None:
        if (self.reservation is None) == (self.rejection is None):
            raise ValueError(
                "ReservationGrant carries exactly one of reservation or rejection"
            )
        if self.reservation is not None:
            if not self.capacity_committed:
                raise ValueError(
                    "a granted grant evidences committed complete-entry "
                    "retention capacity and handoff path"
                )
            if self.publisher_identity is None or self.invocation_identity is None:
                raise ValueError(
                    "a granted grant carries the publisher and invocation "
                    "correlation identities"
                )
            if self.reservation.publisher_identity != self.publisher_identity:
                raise ValueError(
                    "grant correlation does not match the granted reservation"
                )
        elif self.capacity_committed:
            raise ValueError("a rejected grant commits no capacity")

    @property
    def granted(self) -> bool:
        """Whether a reservation was granted."""
        return self.reservation is not None


@dataclass(frozen=True)
class PublicationAcknowledgement:
    """Synchronous acknowledgement of one publish request.

    When ``outcome`` is ACCEPTED the Publisher/Composition has ALREADY assumed
    retention responsibility — the acknowledgement is not mere receipt of the
    request. An accepted acknowledgement carries the full correlation:
    publisher/invocation/reservation/unit/attempt/operation identities, the
    derived ``accepted_entry_identity`` (unambiguous correlation to the exact
    immutable entry), and the ``publication_sequence_number``. A retried
    request returns the ORIGINAL acceptance evidence with
    ``idempotent_retry=True`` — it never represents a second entry.
    """

    outcome: PublicationOutcome
    publication_sequence_number: int | None = None
    idempotent_retry: bool = False
    detail: PublicationRejection | None = None
    publisher_identity: OperationEntryPublisherIdentity | None = None
    invocation_identity: ErrorHandlingInvocationIdentity | None = None
    publication_reservation_identity: PublicationReservationIdentity | None = None
    error_handling_unit_identity: ErrorHandlingUnitIdentity | None = None
    handling_operation_attempt_identity: HandlingOperationAttemptIdentity | None = None
    handling_operation_identity: str | None = None
    accepted_entry_identity: AcceptedEntryIdentity | None = None
    diagnostics: str = ""

    def __post_init__(self) -> None:
        if self.outcome is PublicationOutcome.ACCEPTED:
            if self.publication_sequence_number is None:
                raise ValueError(
                    "an accepted acknowledgement identifies its publication "
                    "sequence number"
                )
            if self.detail is not None:
                raise ValueError("an accepted acknowledgement carries no detail")
            for name in (
                "publisher_identity",
                "invocation_identity",
                "publication_reservation_identity",
                "error_handling_unit_identity",
                "handling_operation_attempt_identity",
                "handling_operation_identity",
                "accepted_entry_identity",
            ):
                if getattr(self, name) is None:
                    raise ValueError(
                        f"an accepted acknowledgement carries {name} for "
                        "unambiguous correlation with the original acceptance"
                    )
        return


@dataclass(frozen=True)
class ReleaseAcknowledgement:
    """Outcome of one release request.

    ``released`` is True when the reservation is (now) Released and its
    reserved capacity became available. A repeated release of an already
    Released reservation may return an idempotent released acknowledgement;
    capacity is returned only once. A Consumed reservation is never released.
    """

    released: bool
    idempotent_retry: bool = False
    detail: PublicationRejection | None = None

    def __post_init__(self) -> None:
        if not self.released and self.idempotent_retry:
            raise ValueError("only a released acknowledgement may be idempotent")


@dataclass(frozen=True)
class PublicationStatusQuery:
    """Full status-query envelope (Single Step Publication Specialization).

    The query OUTCOME (``StatusQueryOutcome``) is distinct from the reservation
    LIFECYCLE state. When the outcome is DETERMINABLE, ``lifecycle_state`` is
    one of the three valid states and a Consumed answer carries the
    accepted-entry correlation and sequence metadata. Any non-determinable
    outcome leaves ``lifecycle_state`` None: a failed, unknown, or expired
    query is never mapped to Reserved, Released, or definitely-not-accepted.
    """

    outcome: StatusQueryOutcome
    lifecycle_state: PublicationStatus | None = None
    publisher_identity: OperationEntryPublisherIdentity | None = None
    invocation_identity: ErrorHandlingInvocationIdentity | None = None
    publication_reservation_identity: PublicationReservationIdentity | None = None
    accepted_entry_identity: AcceptedEntryIdentity | None = None
    publication_sequence_number: int | None = None
    diagnostics: str = ""

    def __post_init__(self) -> None:
        if self.outcome is StatusQueryOutcome.DETERMINABLE:
            if self.lifecycle_state is None:
                raise ValueError(
                    "a determinable query outcome carries the lifecycle state"
                )
            if self.lifecycle_state is PublicationStatus.CONSUMED and (
                self.accepted_entry_identity is None
                or self.publication_sequence_number is None
            ):
                raise ValueError(
                    "a Consumed status answer identifies the accepted entry "
                    "correlation and its sequence metadata"
                )
        elif self.lifecycle_state is not None:
            raise ValueError(
                "a non-determinable query outcome must not report a lifecycle "
                "state (query outcomes are not lifecycle states)"
            )


class PreallocatedEntryEnvelope:
    """Preallocated, fully owning single-slot retention envelope.

    The no-fail final ownership-transfer primitive of this specialization:
    one envelope is pre-created per reservation at reserve time (the granted
    capacity AND the required handoff path are committed), and the transfer at
    atomic acceptance is a fixed-``__slots__`` reference assignment — no
    allocation of entry payload, no serialization, no conversion, no deep copy,
    no clone, and no arbitrary user-defined code executes inside the acceptance
    boundary. All fallible entry preparation happens in the Unit before
    ``publish``; preparation failure leaves the result under the Unit's
    responsibility and the slot simply stays empty.
    """

    __slots__ = ("_received",)

    def __init__(self) -> None:
        object.__setattr__(self, "_received", None)

    @property
    def received(self) -> ErrorHandlingOperationEntry[object] | None:
        """The transferred entry, or None before acceptance."""
        return self._received  # type: ignore[attr-defined,no-any-return]

    def receive(self, entry: ErrorHandlingOperationEntry[object]) -> None:
        """No-fail ownership transfer: one fixed-slot reference assignment."""
        object.__setattr__(self, "_received", entry)

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return (
            f"{type(self).__name__}("
            f"received={'yes' if self._received is not None else 'no'})"  # type: ignore[attr-defined]
        )


@dataclass(frozen=True)
class PublicationSequencePolicy:
    """``publicationSequenceNumber`` rules (Single Step Publication Specialization).

    - Assignment: ONLY at the atomic-acceptance linearization point, under the
      Publisher lock.
    - Monotonicity: strictly monotonically increasing within the declared scope;
      no ambiguous duplicate values within the retained scope.
    - Scope: ONE Publisher instance's lifetime (Publication Acceptance Order at
      that Publisher). It is not the attempt, grant, start, or completion order.
    - Overflow: unbounded integer counter — no overflow occurs.
    - Restart: a replacement Publisher instance opens a NEW sequence scope
      correlated to its own publisherIdentity; prior numbers remain correlated
      to the prior instance and are never confused with the new scope.
    - Entry requirement: not a mandatory entry field; retained as publication
      metadata on the acknowledgement/status correlation.
    """

    monotonic: bool = True
    assignment: str = "atomic-acceptance-linearization-point"
    scope: str = "single-publisher-instance-lifetime"
    overflow_behavior: str = "unbounded-integer-counter-no-overflow"
    restart_behavior: str = "replacement-publisher-opens-new-sequence-scope"

    def validate_acceptance_order(self, sequences: sequence_of_int) -> None:
        """Validate observed sequence metadata: strictly increasing, unique."""
        previous: int | None = None
        for value in sequences:
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError("sequence values must be ints")
            if previous is not None and value <= previous:
                raise ValueError(
                    "publication sequence numbers must be strictly monotonic "
                    f"with no duplicates; observed {previous} -> {value}"
                )
            previous = value


# typing alias for the policy validator (kept stdlib-simple)
sequence_of_int = list[int] | tuple[int, ...]


@dataclass(frozen=True)
class PublicationIdentityPolicy:
    """Identity generation/uniqueness/stability/reuse/retirement rules.

    - Representation and issuer: string value types; reservation identities are
      generated by the issuing Publisher (monotonic counter under its lock);
      invocation/unit identities are assigned by Step Composition; attempt and
      operation identities are allocated by the Unit (attempt BEFORE reserve,
      operation only after a valid grant and before operation start); the
      accepted-entry identity is DERIVED from the entry's composite identity.
    - Uniqueness scope: reservation identities within the issuing Publisher;
      attempt identities within the producing Unit/Invocation scope; the
      composite entry identity within the applicable SPU identity scope.
    - Collision prevention: monotonic counters under the Publisher lock; the
      attempt-identity burn rule rejects any re-presentation.
    - Stability: identities are immutable value types; a replacement Publisher
      or Unit instance receives a distinct identity while prior records may
      remain observable.
    - Retirement/reuse: forbidden while any result, reservation, acknowledgement,
      status record, recovery record, accepted entry, or aggregate may still
      refer to the value; tombstones keep retired reservation identities
      unresolvable-but-distinguishable.
    - Provenance: reservation/entry correlation always includes the Step
      instance, Unit Association, association target, and canonical invocation.
    """

    reservation_identity_scope: str = "issuing-publisher-identity-scope"
    attempt_identity_scope: str = "producing-unit-invocation-scope"
    accepted_entry_identity_rule: str = "derived-from-entry-composite-identity"
    collision_prevention: str = "monotonic-counter-under-publisher-lock"
    retirement_rule: str = "no-reuse-while-any-record-may-still-refer-to-it"
    replacement_rule: str = "replacement-instance-receives-a-distinct-identity"

    def validate_no_identity_reuse(self, observed_values: sequence_of_str) -> None:
        """Validate observed identity values for reuse within one scope."""
        seen: set[str] = set()
        for value in observed_values:
            if value in seen:
                raise ValueError(
                    f"identity value {value!r} was reused within its uniqueness "
                    "scope; identity retirement/reuse is forbidden while any "
                    "record may still refer to it"
                )
            seen.add(value)


# typing alias for the policy validator (kept stdlib-simple)
sequence_of_str = list[str] | tuple[str, ...]


@dataclass(frozen=True)
class PublicationStatusRetentionPolicy:
    """Status-record retention, tombstone, and expiry rules (Step-defined).

    Event-based retention (no universal numeric duration is prescribed):

    - ``Reserved`` records are never removed while acceptance is indeterminate
      or a produced result lacks a confirmed custodian.
    - ``Consumed`` records remain queryable (status + idempotent retry) at
      least until the accepted entry is collected into the Step aggregate and
      all permitted retry observers have left scope; reclamation is an explicit
      Composition decision (``retire_terminal_records``).
    - ``Released`` records remain distinguishable from Unknown/Expired during
      the late-request window.
    - Reclamation keeps a TOMBSTONE (identity + terminal state + sequence) so
      stale capabilities are rejected, identity reuse cannot make a stale query
      resolve to a different publication, and no second entry can be created
      under a retired identity.
    - Post-expiry late queries report EXPIRED — never definitely-not-accepted;
      late publish/release attempts on expired capabilities are rejected.
    - Unresolved/indeterminate publication and recovery records are retained
      while custody is unresolved (enforced: Reserved records cannot be
      retired).
    """

    tombstone_on_reclamation: bool = True
    reserved_record_removal_allowed: bool = False
    expired_query_outcome: StatusQueryOutcome = StatusQueryOutcome.EXPIRED
    stale_capability_behavior: str = "rejected-never-accepted-never-expired-as-rejected-proof"
    unresolved_record_retention: str = "retained-while-custody-unresolved"


class PublicationReservation:
    """Opaque, single-use publication capability for exactly one entry.

    One reservation authorizes acceptance of at most one logical operation
    entry for one Handling Operation Attempt. It is permanently bound to the
    issuing Publisher, the invocation, the Error Handling Unit, the attempt,
    and the Step instance / Unit Association / association target of the
    authorized invocation; it must not be transferred to any of them.

    The reservation is an opaque capability: knowing or reproducing its
    identity value alone does not authorize creation, mutation, or use.
    Instances are created ONLY by the issuing Publisher (module-private issuer
    token) and only its Publisher mutates the state.

    Identity: unique within the issuing Publisher's identity scope, immutable,
    never reassigned to another reservation.
    """

    __slots__ = (
        "_identity",
        "_publisher_identity",
        "_invocation_identity",
        "_error_handling_unit_identity",
        "_handling_operation_attempt_identity",
        "_step_instance_identity",
        "_error_handling_unit_association_identity",
        "_association_target_identity",
        "_state",
    )

    def __init__(
        self,
        *,
        identity: PublicationReservationIdentity,
        publisher_identity: OperationEntryPublisherIdentity,
        invocation_identity: ErrorHandlingInvocationIdentity,
        error_handling_unit_identity: ErrorHandlingUnitIdentity,
        handling_operation_attempt_identity: HandlingOperationAttemptIdentity,
        step_instance_identity: str,
        error_handling_unit_association_identity: str,
        association_target_identity: str,
        _issuer_token: object | None = None,
    ) -> None:
        if _issuer_token is not _ISSUER_TOKEN:
            raise TypeError(
                "PublicationReservation is an opaque capability issued only by "
                "its OperationEntryPublisher; it cannot be constructed directly"
            )
        object.__setattr__(self, "_identity", identity)
        object.__setattr__(self, "_publisher_identity", publisher_identity)
        object.__setattr__(self, "_invocation_identity", invocation_identity)
        object.__setattr__(
            self, "_error_handling_unit_identity", error_handling_unit_identity
        )
        object.__setattr__(
            self,
            "_handling_operation_attempt_identity",
            handling_operation_attempt_identity,
        )
        object.__setattr__(self, "_step_instance_identity", step_instance_identity)
        object.__setattr__(
            self,
            "_error_handling_unit_association_identity",
            error_handling_unit_association_identity,
        )
        object.__setattr__(
            self, "_association_target_identity", association_target_identity
        )
        object.__setattr__(self, "_state", PublicationStatus.RESERVED)

    @property
    def identity(self) -> PublicationReservationIdentity:
        """Identity of this reservation within the issuing Publisher's scope."""
        return self._identity

    @property
    def publisher_identity(self) -> OperationEntryPublisherIdentity:
        """The exact Publisher instance that issued this reservation."""
        return self._publisher_identity

    @property
    def invocation_identity(self) -> ErrorHandlingInvocationIdentity:
        """The canonical Error Handling Unit invocation identity binding."""
        return self._invocation_identity

    @property
    def error_handling_unit_identity(self) -> ErrorHandlingUnitIdentity:
        """The concrete Error Handling Unit instance binding."""
        return self._error_handling_unit_identity

    @property
    def handling_operation_attempt_identity(self) -> HandlingOperationAttemptIdentity:
        """The attempt whose possible operation result this reservation retains."""
        return self._handling_operation_attempt_identity

    @property
    def step_instance_identity(self) -> str:
        """Owning Step instance identity (opaque value from the Step layer)."""
        return self._step_instance_identity

    @property
    def error_handling_unit_association_identity(self) -> str:
        """The exact selected Step-owned Association (opaque value)."""
        return self._error_handling_unit_association_identity

    @property
    def association_target_identity(self) -> str:
        """The target scope bound to that Association (opaque value)."""
        return self._association_target_identity

    @property
    def state(self) -> PublicationStatus:
        """Current lifecycle state; mutated only by the issuing Publisher."""
        return self._state

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            "PublicationReservation is immutable; only its issuing Publisher "
            "transitions its state"
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError("PublicationReservation is immutable")

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return (
            f"{type(self).__name__}(identity={str(self._identity)!r}, "
            f"state={self._state.name})"
        )


def _assign_state(
    reservation: PublicationReservation, state: PublicationStatus
) -> None:
    """Issuer-only state transition helper (module-private)."""
    object.__setattr__(reservation, "_state", state)


def _require_exact_type(field: str, value: object, expected: type) -> None:
    if type(value) is not expected:
        raise TypeError(
            f"{field} must be exactly {expected.__name__}, "
            f"got {type(value).__name__}"
        )


class OperationEntryPublisher[THandlingOperationResult]:
    """Reservation-backed authoritative delivery path for operation entries.

    Owned by the Step-specific Error Handling Composition and supplied to an
    Error Handling Unit for ONE invocation under the Step-specific lifecycle
    contract; valid only within that invocation and Association lifecycle.

    The Publisher is bound at construction to the Step instance, the invocation,
    the Unit instance, and the exact Association/association target selected by
    Step Composition. It does not schedule operations, impose operation
    concurrency, or define semantic ordering; entry order exposed by
    :meth:`accepted_entries` is Publication Acceptance Order (the order entries
    crossed their atomic-acceptance linearization points), which is not the
    attempt, grant, start, or completion order.
    """

    def __init__(
        self,
        identity: OperationEntryPublisherIdentity,
        *,
        invocation_identity: ErrorHandlingInvocationIdentity,
        error_handling_unit_identity: ErrorHandlingUnitIdentity,
        step_instance_identity: str,
        error_handling_unit_association_identity: str,
        association_target_identity: str,
        total_capacity: int,
        retention_policy: PublicationStatusRetentionPolicy | None = None,
    ) -> None:
        _require_exact_type("identity", identity, OperationEntryPublisherIdentity)
        _require_exact_type(
            "invocation_identity", invocation_identity, ErrorHandlingInvocationIdentity
        )
        _require_exact_type(
            "error_handling_unit_identity",
            error_handling_unit_identity,
            ErrorHandlingUnitIdentity,
        )
        for name, value in (
            ("step_instance_identity", step_instance_identity),
            (
                "error_handling_unit_association_identity",
                error_handling_unit_association_identity,
            ),
            ("association_target_identity", association_target_identity),
        ):
            if not isinstance(value, str) or value == "" or value.isspace():
                raise ValueError(f"{name} must be a non-empty opaque identity value")
        if isinstance(total_capacity, bool) or not isinstance(total_capacity, int):
            raise TypeError("total_capacity must be an int")
        if total_capacity < 1:
            raise ValueError("total_capacity must be at least 1")

        self._identity = identity
        self._invocation_identity = invocation_identity
        self._error_handling_unit_identity = error_handling_unit_identity
        self._step_instance_identity = step_instance_identity
        self._error_handling_unit_association_identity = (
            error_handling_unit_association_identity
        )
        self._association_target_identity = association_target_identity
        self._total_capacity = total_capacity
        self._retention_policy = retention_policy or PublicationStatusRetentionPolicy()
        self._identity_policy = PublicationIdentityPolicy()
        self._sequence_policy = PublicationSequencePolicy()
        self._reserved_capacity = 0
        self._occupied_capacity = 0
        self._lock = threading.Lock()
        self._open_for_reservations = True
        self._reservation_counter = 0
        self._sequence_counter = 0
        # reservation identity -> record(state, envelope, sequence); insertion
        # order of accepted entries is kept via the sequence numbers.
        self._records: dict[PublicationReservationIdentity, _Record] = {}
        self._accepted: list[_Record] = []
        # Reclaimed terminal records: identity -> tombstone (retention/expiry).
        self._tombstones: dict[PublicationReservationIdentity, _Tombstone] = {}
        # Every attempt identity presented to reserve is burned, whether the
        # request was granted or rejected.
        self._used_attempts: set[HandlingOperationAttemptIdentity] = set()

    # ------------------------------------------------------------------ #
    # Identity and binding
    # ------------------------------------------------------------------ #

    @property
    def identity(self) -> OperationEntryPublisherIdentity:
        """Identity of this Publisher instance."""
        return self._identity

    @property
    def invocation_identity(self) -> ErrorHandlingInvocationIdentity:
        """The one Unit invocation this capability is bound to."""
        return self._invocation_identity

    @property
    def error_handling_unit_identity(self) -> ErrorHandlingUnitIdentity:
        """The one Error Handling Unit this capability is bound to."""
        return self._error_handling_unit_identity

    # ------------------------------------------------------------------ #
    # Capacity accounting
    # ------------------------------------------------------------------ #

    @property
    def total_capacity(self) -> int:
        """Total complete-entry retention capacity of this Publisher."""
        return self._total_capacity

    @property
    def reserved_capacity(self) -> int:
        """Outstanding Reserved capacity committed to unconsumed reservations."""
        return self._reserved_capacity

    @property
    def occupied_capacity(self) -> int:
        """Occupied retention capacity holding accepted entries."""
        return self._occupied_capacity

    # ------------------------------------------------------------------ #
    # Invocation closing support (Composition-owned closure)
    # ------------------------------------------------------------------ #

    @property
    def open_for_reservations(self) -> bool:
        """Whether the invocation still admits new reservation requests."""
        return self._open_for_reservations

    def close_for_new_reservations(self) -> None:
        """Enter the invocation closing phase: no new reservations are admitted.

        Composition-owned closure coordination; outstanding reservations are
        NOT automatically released ("Publisher/Composition must not
        automatically release outstanding reservations merely to force
        closure").
        """
        with self._lock:
            self._open_for_reservations = False

    def outstanding_reservations(self) -> tuple[PublicationReservation, ...]:
        """Reservations not yet in a terminal state (closure preconditions)."""
        with self._lock:
            return tuple(
                record.reservation
                for record in self._records.values()
                if record.reservation.state is PublicationStatus.RESERVED
            )

    # ------------------------------------------------------------------ #
    # reserve
    # ------------------------------------------------------------------ #

    def reserve(
        self, handling_operation_attempt_identity: HandlingOperationAttemptIdentity
    ) -> ReservationGrant:
        """Request a PublicationReservation BEFORE the Handling Operation begins.

        The attempt identity must be allocated by the Unit before this call
        (allocating it does not mean the operation started) and must be new
        within the applicable Unit/Invocation scope. On rejection no capacity
        was committed and the associated operation must NOT begin.
        """
        _require_exact_type(
            "handling_operation_attempt_identity",
            handling_operation_attempt_identity,
            HandlingOperationAttemptIdentity,
        )
        with self._lock:
            if not self._open_for_reservations:
                return self._reject_reserve(
                    handling_operation_attempt_identity,
                    "invocation-closing",
                    "no new reservation request is admitted after the "
                    "Invocation enters its closing phase",
                )
            if handling_operation_attempt_identity in self._used_attempts:
                return self._reject_reserve(
                    handling_operation_attempt_identity,
                    "attempt-identity-reuse",
                    "the attempt identity is not new within this Unit/Invocation "
                    "scope; one attempt may start at most one actual execution "
                    "and a retry of reserve requires a new attempt identity",
                )
            if self._reserved_capacity + self._occupied_capacity >= self._total_capacity:
                return self._reject_reserve(
                    handling_operation_attempt_identity,
                    "capacity-exhausted",
                    "granting this reservation would over-commit complete-entry "
                    "retention capacity "
                    f"(total={self._total_capacity}, "
                    f"reserved={self._reserved_capacity}, "
                    f"occupied={self._occupied_capacity})",
                )

            self._reservation_counter += 1
            reservation = PublicationReservation(
                identity=PublicationReservationIdentity(
                    f"reservation-{self._reservation_counter}"
                ),
                publisher_identity=self._identity,
                invocation_identity=self._invocation_identity,
                error_handling_unit_identity=self._error_handling_unit_identity,
                handling_operation_attempt_identity=(
                    handling_operation_attempt_identity
                ),
                step_instance_identity=self._step_instance_identity,
                error_handling_unit_association_identity=(
                    self._error_handling_unit_association_identity
                ),
                association_target_identity=self._association_target_identity,
                _issuer_token=_ISSUER_TOKEN,
            )
            self._used_attempts.add(handling_operation_attempt_identity)
            self._records[reservation.identity] = _Record(reservation=reservation)
            self._reserved_capacity += 1
            return ReservationGrant(
                reservation=reservation,
                publisher_identity=self._identity,
                invocation_identity=self._invocation_identity,
                error_handling_unit_identity=self._error_handling_unit_identity,
                handling_operation_attempt_identity=handling_operation_attempt_identity,
                capacity_committed=True,
                diagnostics=(
                    "complete-entry retention capacity and the preallocated "
                    "owning handoff envelope are committed for this reservation"
                ),
            )

    def _reject_reserve(
        self,
        attempt: HandlingOperationAttemptIdentity,
        reason: str,
        detail: str,
    ) -> ReservationGrant:
        # A rejection burns the attempt identity too: the next request needs a
        # new attempt identity per the contract.
        self._used_attempts.add(attempt)
        return ReservationGrant(
            rejection=PublicationRejection(reason, detail),
            publisher_identity=self._identity,
            invocation_identity=self._invocation_identity,
            error_handling_unit_identity=self._error_handling_unit_identity,
            handling_operation_attempt_identity=attempt,
            capacity_committed=False,
            diagnostics=detail,
        )

    # ------------------------------------------------------------------ #
    # publish
    # ------------------------------------------------------------------ #

    def publish(
        self,
        reservation: PublicationReservation,
        entry: ErrorHandlingOperationEntry[THandlingOperationResult],
    ) -> PublicationAcknowledgement:
        """Submit the complete prepared entry for acceptance.

        For a valid Reserved reservation and a matching, structurally valid
        entry the Publisher MUST accept: no ordinary capacity- or
        resource-exhaustion rejection is possible after a grant. Acceptance is
        one indivisible transition (entry retained + reservation Consumed +
        sequence assigned). Calling publish alone does not transfer retention
        responsibility — only acceptance does.
        """
        if type(entry) is not ErrorHandlingOperationEntry:
            raise TypeError(
                "entry must be an ErrorHandlingOperationEntry, "
                f"got {type(entry).__name__}"
            )
        record = self._resolve_record(reservation)
        if record is None:
            return self._rejected_publish(
                reservation,
                "unknown-or-foreign-reservation",
                "the reservation is unknown to or was not issued by this "
                "Publisher",
            )
        if isinstance(record, _Tombstone):
            # Stale capability after retention expiry: never accepted, never a
            # proof of non-acceptance of the original publication.
            return self._rejected_publish(
                reservation,
                "reservation-expired",
                "the status record for this reservation was reclaimed after "
                "the Step-defined retention window; stale capabilities are "
                "rejected and never accepted",
            )

        with self._lock:
            # Re-validate under the lock: the record may have been reclaimed
            # (retired) between the pre-lock resolution and this point.
            live = self._records.get(reservation.identity)
            if live is not record:
                return self._rejected_publish(
                    reservation,
                    "reservation-expired",
                    "the status record for this reservation was reclaimed; "
                    "stale capabilities are rejected and never accepted",
                )
            state = record.reservation.state
            if state is PublicationStatus.RELEASED:
                return self._rejected_publish(
                    reservation,
                    "reservation-released",
                    "a Released reservation cannot publish; publishing or "
                    "releasing a Released reservation is rejected",
                )
            if state is PublicationStatus.CONSUMED:
                return self._resolve_consumed_retry(record, entry)

            mismatch = self._first_binding_mismatch(record.reservation, entry)
            if mismatch is not None:
                # No partial acceptance: state, entries, and capacity unchanged.
                return PublicationAcknowledgement(
                    outcome=PublicationOutcome.REJECTED, detail=mismatch
                )

            accepted_entry_identity = derive_accepted_entry_identity(entry)

            # ---- atomic acceptance linearization point (single lock hold) ---
            # No-fail transfer: the only ownership handoff is the fixed-slot
            # reference assignment into the preallocated envelope.
            self._sequence_counter += 1
            sequence = self._sequence_counter
            _assign_state(record.reservation, PublicationStatus.CONSUMED)
            record.slot.receive(entry)
            record.sequence = sequence
            record.accepted_entry_identity = accepted_entry_identity
            self._accepted.append(record)
            self._reserved_capacity -= 1
            self._occupied_capacity += 1
            assert (
                self._total_capacity
                >= self._reserved_capacity + self._occupied_capacity
            )
            # -----------------------------------------------------------------

            return PublicationAcknowledgement(
                outcome=PublicationOutcome.ACCEPTED,
                publication_sequence_number=sequence,
                publisher_identity=self._identity,
                invocation_identity=self._invocation_identity,
                publication_reservation_identity=reservation.identity,
                error_handling_unit_identity=reservation.error_handling_unit_identity,
                handling_operation_attempt_identity=(
                    reservation.handling_operation_attempt_identity
                ),
                handling_operation_identity=entry.handling_operation_identity.value,
                accepted_entry_identity=accepted_entry_identity,
            )

    def _rejected_publish(
        self,
        reservation: PublicationReservation,
        reason: str,
        detail: str,
    ) -> PublicationAcknowledgement:
        """Rejection with the known correlation; nothing was accepted."""
        return PublicationAcknowledgement(
            outcome=PublicationOutcome.REJECTED,
            detail=PublicationRejection(reason, detail),
            publisher_identity=self._identity,
            publication_reservation_identity=reservation.identity,
            diagnostics=detail,
        )

    def _resolve_consumed_retry(
        self,
        record: "_Record",
        entry: ErrorHandlingOperationEntry[THandlingOperationResult],
    ) -> PublicationAcknowledgement:
        """Idempotent-retry and conflicting-reuse resolution (lock held)."""
        accepted_entry = record.entry
        assert accepted_entry is not None
        assert record.sequence is not None
        assert record.accepted_entry_identity is not None
        reservation = record.reservation
        if entry == accepted_entry:
            # Same logical entry: retry of the original publication. Acknowledge
            # the ORIGINAL acceptance evidence; no second entry, no second
            # capacity consumption.
            return PublicationAcknowledgement(
                outcome=PublicationOutcome.ACCEPTED,
                publication_sequence_number=record.sequence,
                idempotent_retry=True,
                publisher_identity=self._identity,
                invocation_identity=self._invocation_identity,
                publication_reservation_identity=reservation.identity,
                error_handling_unit_identity=reservation.error_handling_unit_identity,
                handling_operation_attempt_identity=(
                    reservation.handling_operation_attempt_identity
                ),
                handling_operation_identity=entry.handling_operation_identity.value,
                accepted_entry_identity=record.accepted_entry_identity,
                diagnostics=(
                    "idempotent retry: this acknowledgement re-identifies the "
                    "original acceptance and never represents a second entry"
                ),
            )
        same_composite = (
            entry.error_handling_unit_identity
            == accepted_entry.error_handling_unit_identity
            and entry.handling_operation_identity
            == accepted_entry.handling_operation_identity
        )
        if same_composite:
            return PublicationAcknowledgement(
                outcome=PublicationOutcome.CONTRACT_VIOLATION,
                detail=PublicationRejection(
                    "conflicting-entry-content",
                    "the Consumed reservation was re-presented with the same "
                    "operation composite identity but different immutable entry "
                    "content; a second accepted entry must never be created",
                ),
            )
        return PublicationAcknowledgement(
            outcome=PublicationOutcome.CONTRACT_VIOLATION,
            detail=PublicationRejection(
                "invalid-reuse-of-consumed-reservation",
                "once Consumed, the reservation cannot authorize another "
                "distinct entry",
            ),
        )

    def _first_binding_mismatch(
        self,
        reservation: PublicationReservation,
        entry: ErrorHandlingOperationEntry[THandlingOperationResult],
    ) -> PublicationRejection | None:
        """Reservation-to-entry binding validation (lock held)."""
        assert isinstance(entry, ErrorHandlingOperationEntry)
        if entry.handling_operation_attempt_identity != (
            reservation.handling_operation_attempt_identity
        ):
            return PublicationRejection(
                "attempt-identity-mismatch",
                "entry.handlingOperationAttemptIdentity does not match the "
                "reservation's bound Handling Operation Attempt",
            )
        if entry.error_handling_unit_identity != reservation.error_handling_unit_identity:
            return PublicationRejection(
                "unit-identity-mismatch",
                "entry.errorHandlingUnitIdentity does not match the "
                "reservation's bound Error Handling Unit",
            )
        if entry.handling_operation_identity is None:  # pragma: no cover
            # Structurally unrepresentable: the entry field is mandatory.
            return PublicationRejection(
                "missing-operation-identity",
                "the entry lacks the actual handlingOperationIdentity required "
                "for an operation that began",
            )
        if entry.error_handling_invocation_identity != reservation.invocation_identity:
            return PublicationRejection(
                "invocation-identity-mismatch",
                "entry.errorHandlingInvocationIdentity does not match the "
                "Publisher invocation identity",
            )
        if entry.step_instance_identity != reservation.step_instance_identity:
            return PublicationRejection(
                "step-instance-mismatch",
                "entry.stepInstanceIdentity does not match the reservation's "
                "bound Step instance",
            )
        if entry.error_handling_unit_association_identity != (
            reservation.error_handling_unit_association_identity
        ):
            return PublicationRejection(
                "association-mismatch",
                "entry.errorHandlingUnitAssociationIdentity does not match the "
                "reservation's bound Association",
            )
        if entry.association_target_identity != reservation.association_target_identity:
            return PublicationRejection(
                "association-target-mismatch",
                "entry.associationTargetIdentity does not match the target "
                "bound to the reservation",
            )
        return None

    def _resolve_record(
        self, reservation: object
    ) -> "_Record | _Tombstone | None":
        """Validate reservation type and issuer.

        Returns the live record, the retention tombstone for a reclaimed
        identity, or None for an unknown/foreign/invalid capability.
        """
        _require_exact_type("reservation", reservation, PublicationReservation)
        assert isinstance(reservation, PublicationReservation)
        if reservation.publisher_identity != self._identity:
            return None
        record = self._records.get(reservation.identity)
        if record is not None:
            return record
        return self._tombstones.get(reservation.identity)

    # ------------------------------------------------------------------ #
    # get_publication_status
    # ------------------------------------------------------------------ #

    def get_publication_status(
        self, reservation: PublicationReservation
    ) -> PublicationStatus | None:
        """Resolve an ambiguous publication outcome (no mutation).

        Returns the reservation's lifecycle state, or ``None`` — distinct from
        the three valid states — for an unknown, foreign, invalid, or
        EXPIRED (retention-reclaimed) reservation. Status is scoped to this
        exact issuing Publisher. A failed or unknown status query does NOT
        establish that publication was rejected: the caller preserves the
        result and reservation context and uses the Step-specific recovery
        path (``recovery.py`` / ``query_publication_status`` for the full
        envelope).
        """
        _require_exact_type("reservation", reservation, PublicationReservation)
        with self._lock:
            record = self._records.get(reservation.identity)
            if (
                reservation.publisher_identity != self._identity
                or record is None
            ):
                return None
            state = record.reservation.state
            if state is PublicationStatus.CONSUMED:
                # The status response identifies the accepted publication.
                assert record.sequence is not None
                assert record.slot.received is not None
            return state

    def query_publication_status(
        self, reservation: PublicationReservation
    ) -> PublicationStatusQuery:
        """Full status-query envelope (Single Step Publication Specialization).

        Distinguishes query OUTCOMES from lifecycle STATES:

        - DETERMINABLE with the Reserved/Consumed/Released state; a Consumed
          answer carries the accepted-entry correlation and its sequence
          metadata.
        - UNKNOWN for an identity this Publisher never issued (or a foreign
          Publisher's reservation).
        - EXPIRED for a retention-reclaimed (tombstoned) terminal record —
          never mapped to a lifecycle state and never treated as proof of
          non-acceptance of the original publication.
        - INVALID_CAPABILITY for a non-capability object.
        - INDETERMINATE / UNAVAILABLE are returned by recovery wrappers around
          unavailable Publishers, never fabricated here: a determinate answer
          is always truthful.

        A query never mutates the reservation, the records, or the tombstones.
        """
        if not isinstance(reservation, PublicationReservation):
            return PublicationStatusQuery(
                outcome=StatusQueryOutcome.INVALID_CAPABILITY,
                publisher_identity=self._identity,
                diagnostics=(
                    "the queried object is not a PublicationReservation capability"
                ),
            )
        with self._lock:
            if reservation.publisher_identity != self._identity:
                return PublicationStatusQuery(
                    outcome=StatusQueryOutcome.UNKNOWN,
                    publisher_identity=self._identity,
                    publication_reservation_identity=reservation.identity,
                    diagnostics=(
                        "the reservation was not issued by this Publisher"
                    ),
                )
            record = self._records.get(reservation.identity)
            if record is not None:
                state = record.reservation.state
                if state is PublicationStatus.CONSUMED:
                    assert record.sequence is not None
                    assert record.accepted_entry_identity is not None
                    return PublicationStatusQuery(
                        outcome=StatusQueryOutcome.DETERMINABLE,
                        lifecycle_state=state,
                        publisher_identity=self._identity,
                        invocation_identity=self._invocation_identity,
                        publication_reservation_identity=reservation.identity,
                        accepted_entry_identity=record.accepted_entry_identity,
                        publication_sequence_number=record.sequence,
                        diagnostics=(
                            "Consumed proves acceptance: do not publish a "
                            "second logical entry"
                        ),
                    )
                return PublicationStatusQuery(
                    outcome=StatusQueryOutcome.DETERMINABLE,
                    lifecycle_state=state,
                    publisher_identity=self._identity,
                    invocation_identity=self._invocation_identity,
                    publication_reservation_identity=reservation.identity,
                    diagnostics=(
                        "Reserved permits retry of the same immutable logical "
                        "entry under the same reservation"
                        if state is PublicationStatus.RESERVED
                        else "Released: no entry was accepted under this "
                        "reservation"
                    ),
                )
            tombstone = self._tombstones.get(reservation.identity)
            if tombstone is not None:
                return PublicationStatusQuery(
                    outcome=StatusQueryOutcome.EXPIRED,
                    publisher_identity=self._identity,
                    publication_reservation_identity=reservation.identity,
                    diagnostics=(
                        "status record reclaimed after the Step-defined "
                        f"retention window (terminal state at retirement: "
                        f"{tombstone.terminal_state.name}); expired is never "
                        "definitely-not-accepted"
                    ),
                )
            return PublicationStatusQuery(
                outcome=StatusQueryOutcome.UNKNOWN,
                publisher_identity=self._identity,
                publication_reservation_identity=reservation.identity,
                diagnostics=(
                    "no record or tombstone for this reservation identity"
                ),
            )

    # ------------------------------------------------------------------ #
    # Status-record retention (Composition-owned reclamation)
    # ------------------------------------------------------------------ #

    def retire_terminal_records(
        self, reservations: tuple[PublicationReservation, ...] | list[PublicationReservation]
    ) -> int:
        """Reclaim terminal status records after aggregation (tombstoned).

        Explicit Composition decision, permitted ONLY for Consumed/Released
        records whose accepted entries have been collected into the Step
        aggregate and whose retry observers have left scope. Reserved records
        are NEVER removed (acceptance may still be pending or custody
        unresolved). Each reclaimed record keeps a tombstone: stale
        capabilities are rejected (never accepted), late queries report
        EXPIRED, and identity reuse can never resolve a stale query to a
        different publication. Returns the number of records reclaimed;
        already-reclaimed or unknown reservations are ignored (idempotent).
        """
        reclaimed = 0
        with self._lock:
            for reservation in reservations:
                _require_exact_type(
                    "reservation", reservation, PublicationReservation
                )
                record = self._records.get(reservation.identity)
                if record is None:
                    continue  # already reclaimed or unknown: idempotent
                state = record.reservation.state
                if state is PublicationStatus.RESERVED:
                    if not self._retention_policy.reserved_record_removal_allowed:
                        raise ValueError(
                            "a Reserved status record must not be removed while "
                            "acceptance may be pending or result custody is "
                            "unresolved"
                        )
                    continue
                tombstone = _Tombstone(
                    reservation.identity,
                    state,
                    record.sequence,
                    record.accepted_entry_identity,
                )
                self._tombstones[reservation.identity] = tombstone
                if state is PublicationStatus.CONSUMED:
                    # the entry was collected into the Step aggregate; the
                    # Publisher releases the occupied retention capacity
                    self._accepted = [
                        accepted
                        for accepted in self._accepted
                        if accepted.reservation.identity != reservation.identity
                    ]
                    self._occupied_capacity -= 1
                del self._records[reservation.identity]
                reclaimed += 1
            assert (
                self._total_capacity
                >= self._reserved_capacity + self._occupied_capacity
            )
        return reclaimed

    # ------------------------------------------------------------------ #
    # release
    # ------------------------------------------------------------------ #

    def release(
        self, reservation: PublicationReservation
    ) -> ReleaseAcknowledgement:
        """Return reserved capacity when no entry will be published.

        Preconditions the Unit is normatively responsible for (the Publisher
        cannot inspect an unsubmitted Unit-local result): the associated
        operation produced no result requiring publication, or any produced
        result was first transferred to an explicitly designated Step-specific
        Recovery Owner. Release is never inferred from normal return, exception
        propagation, or invocation closure.
        """
        record = self._resolve_record(reservation)
        if record is None:
            return ReleaseAcknowledgement(
                released=False,
                detail=PublicationRejection(
                    "unknown-or-foreign-reservation",
                    "the reservation is unknown to or was not issued by this "
                    "Publisher",
                ),
            )
        if isinstance(record, _Tombstone):
            # Stale capability after retention expiry: rejected, never acted on.
            return ReleaseAcknowledgement(
                released=False,
                detail=PublicationRejection(
                    "reservation-expired",
                    "the status record for this reservation was reclaimed "
                    "after the Step-defined retention window; stale "
                    "capabilities are rejected",
                ),
            )
        with self._lock:
            state = record.reservation.state
            if state is PublicationStatus.RELEASED:
                # Idempotent re-release; capacity was already returned once.
                return ReleaseAcknowledgement(released=True, idempotent_retry=True)
            if state is PublicationStatus.CONSUMED:
                return ReleaseAcknowledgement(
                    released=False,
                    detail=PublicationRejection(
                        "reservation-consumed",
                        "a Consumed reservation cannot be released; its entry "
                        "is accepted and retained",
                    ),
                )
            _assign_state(record.reservation, PublicationStatus.RELEASED)
            self._reserved_capacity -= 1
            assert (
                self._total_capacity
                >= self._reserved_capacity + self._occupied_capacity
            )
            return ReleaseAcknowledgement(released=True)

    # ------------------------------------------------------------------ #
    # Retained-entry access (Composition-side aggregation)
    # ------------------------------------------------------------------ #

    def accepted_entries(
        self,
    ) -> tuple[ErrorHandlingOperationEntry[THandlingOperationResult], ...]:
        """Accepted entries in Publication Acceptance Order.

        Consumed entries remain available for Step-specific collection and
        ErrorHandlerResult aggregation after Unit execution returns or throws;
        invocation closure does not revoke them or change their sequence.
        """
        with self._lock:
            return tuple(record.entry for record in self._accepted)

    def publication_sequence_of(
        self, reservation: PublicationReservation
    ) -> int | None:
        """Sequence metadata for the entry accepted under this reservation.

        None when the reservation is unknown/foreign or has no accepted entry.
        """
        _require_exact_type("reservation", reservation, PublicationReservation)
        with self._lock:
            record = self._records.get(reservation.identity)
            if record is None or record.publisher != self._identity:
                return None
            return record.sequence


class _Record:
    """Internal per-reservation acceptance record (publisher-private).

    The accepted entry lives in a ``PreallocatedEntryEnvelope`` reserved at
    grant time — the no-fail ownership transfer target.
    """

    __slots__ = ("reservation", "slot", "sequence", "publisher", "accepted_entry_identity")

    def __init__(self, reservation: PublicationReservation) -> None:
        self.reservation = reservation
        # Preallocated at reserve: the committed handoff path. Transfer at
        # acceptance is a fixed-slot reference assignment (non-throwing).
        self.slot = PreallocatedEntryEnvelope()
        self.sequence: int | None = None
        self.accepted_entry_identity: AcceptedEntryIdentity | None = None
        # The issuing publisher identity is captured for scoped status lookups.
        self.publisher = reservation.publisher_identity

    @property
    def entry(self) -> ErrorHandlingOperationEntry[THandlingOperationResult] | None:
        """The accepted entry retained in the preallocated envelope."""
        return self.slot.received  # type: ignore[return-value,no-any-return]


class _Tombstone:
    """Retention tombstone for a reclaimed terminal status record.

    Keeps the retired reservation identity unresolvable-but-distinguishable:
    stale capabilities are rejected (never accepted), late queries report
    EXPIRED (never definitely-not-accepted), and identity reuse can never make
    a stale query resolve to a different publication.
    """

    __slots__ = ("identity", "terminal_state", "sequence", "accepted_entry_identity")

    def __init__(
        self,
        identity: PublicationReservationIdentity,
        terminal_state: PublicationStatus,
        sequence: int | None,
        accepted_entry_identity: AcceptedEntryIdentity | None,
    ) -> None:
        self.identity = identity
        self.terminal_state = terminal_state
        self.sequence = sequence
        self.accepted_entry_identity = accepted_entry_identity


def derive_accepted_entry_identity(
    entry: ErrorHandlingOperationEntry[THandlingOperationResult],
) -> AcceptedEntryIdentity:
    """Derive the ``AcceptedEntryIdentity`` from the entry's composite identity.

    One attempt starts at most one execution and one reservation accepts at
    most one logical entry, so (errorHandlingUnitIdentity +
    handlingOperationIdentity) unambiguously correlates an idempotent retry
    with the original acceptance.
    """
    return AcceptedEntryIdentity(
        f"{entry.error_handling_unit_identity.value}/"
        f"{entry.handling_operation_identity.value}"
    )
