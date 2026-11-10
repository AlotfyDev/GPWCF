"""Error Handling pattern identities: nominal, immutable identity value types.

Implementation task: 04_Error_Handling
Related diagrams:
  class: 03_Diagrams_Codes_Files/04_Error_Handling.dot
  dependency: D_Architectural_Dependency_Diagram_Code/04_Supporting_Pattern_Optional_Dependency.dot

Contract basis:
  - ErrorHandlingUnit_Contract.json (``identityContracts``)
  - OperationEntryPublisher_Contract.json (``identityAndScope``)
  - PublicationReservation_Contract.json (``identity``)

Dependency boundary (``04_Supporting_Pattern_Optional_Dependency.dot``):
``ErrorHandlingUnit -> Core : NO dependency``. This pattern package therefore
imports NOTHING from ``gpwcf`` (standard library only) and defines its own
nominal identity value types for the scopes it owns, replicating the small
immutable value-type pattern used by ``core.identities`` deliberately.

Scope rule:

  - Identities of scopes OWNED by this pattern (unit instance, invocation,
    attempt, operation, publisher, reservation) are nominal types defined here.
  - Identities owned by OTHER layers (Step instance, Unit association,
    association target, producer SPU, SPU error occurrence) are carried as
    opaque, validated, non-empty string VALUES (the originating layer's
    identity value); this package never interprets or re-scopes them.
  - No UUID, counter, timestamp, or other generation mechanism is mandated or
    provided here; identity values are owner-assigned.
"""

__all__ = [
    "ErrorHandlingUnitIdentity",
    "ErrorHandlingInvocationIdentity",
    "HandlingOperationAttemptIdentity",
    "HandlingOperationIdentity",
    "OperationEntryPublisherIdentity",
    "PublicationReservationIdentity",
    "AcceptedEntryIdentity",
]


class _PatternIdentityValue:
    """Immutable nominal identity value; equal only within its own type.

    Deliberate local replica of the shared core value-type pattern: the Error
    Handling pattern has NO Core dependency, so it cannot import the base.
    """

    __slots__ = ("_value",)

    def __new__(cls, value: str) -> "_PatternIdentityValue":
        if cls is _PatternIdentityValue:
            raise TypeError("use a concrete identity type, not _PatternIdentityValue")
        return super().__new__(cls)

    def __init__(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("identity value must be a str")
        if value == "" or value.isspace():
            raise ValueError("identity value must be a non-empty, non-blank string")
        object.__setattr__(self, "_value", value)

    @property
    def value(self) -> str:
        """The opaque, owner-assigned identity value."""
        return self._value

    def __setattr__(self, name: str, object: object) -> None:  # noqa: A002
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        return self._value == other._value  # type: ignore[attr-defined]

    def __hash__(self) -> int:
        return hash((type(self), self._value))

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._value!r})"


class ErrorHandlingUnitIdentity(_PatternIdentityValue):
    """Identifies one concrete Error Handling Unit runtime instance within its
    owning Step instance, independently of any target scopes it may be
    associated with.

    Assigned by Step Composition (or an identity provider supplied by it) when
    the Unit instance is created or admitted. Unique within the owning Step
    instance scope; stable for the unit instance lifetime across invocations
    and association changes. A replacement instance receives a new identity
    while results from the prior instance may still be observed.
    """

    __slots__ = ()


class ErrorHandlingInvocationIdentity(_PatternIdentityValue):
    """Identifies one invocation of one Error Handling Unit runtime instance
    under one selected Association.

    Assigned by Step Composition before the invocation begins. Bound to
    exactly one unit identity and Unit association identity and carries the
    corresponding association target and Step instance. All operation attempts
    and entries produced by the same invocation carry this identity; a repeated
    invocation receives a new identity even when the same Unit instance and
    Association are reused.
    """

    __slots__ = ()


class HandlingOperationAttemptIdentity(_PatternIdentityValue):
    """Identifies one distinct attempt to obtain authorization and begin a
    Handling Operation.

    Assigned by the Error Handling Unit (or a supplied identity provider)
    BEFORE calling ``reserve``; allocating it does not mean the operation
    started. A reservation-rejected attempt has no operation identity. A retry
    that begins a new execution uses a NEW attempt identity; an ambiguous
    publication retry for the same executed attempt reuses the same attempt
    identity and reservation.
    """

    __slots__ = ()


class HandlingOperationIdentity(_PatternIdentityValue):
    """Identifies one actual Handling Operation execution that began after a
    valid PublicationReservation was granted.

    Assigned only after the attempt receives a valid reservation and before
    the actual operation begins; one attempt starts at most one actual
    execution. Together with :class:`ErrorHandlingUnitIdentity` it forms the
    composite identity of one operation entry.
    """

    __slots__ = ()


class OperationEntryPublisherIdentity(_PatternIdentityValue):
    """Identifies one Publisher instance; distinct from Invocation, Unit,
    Attempt, Operation, and Reservation identities."""

    __slots__ = ()


class PublicationReservationIdentity(_PatternIdentityValue):
    """Identifies one reservation instance within the issuing Publisher's
    identity scope; immutable and never reassigned to another reservation.

    The reservation is an opaque capability: knowing or reproducing this
    identity value alone does not authorize creation, mutation, or use.
    """

    __slots__ = ()


class AcceptedEntryIdentity(_PatternIdentityValue):
    """Identifies one immutable logical accepted operation entry.

    DERIVED identity (Single Step Publication Specialization): formed from the
    entry's composite identity (``errorHandlingUnitIdentity`` +
    ``handlingOperationIdentity``). One Handling Operation Attempt starts at
    most one actual execution and one reservation accepts at most one logical
    entry, so the derived value unambiguously correlates an idempotent retry
    with the original acceptance and can never designate two different
    entries. It is assigned by the Publisher at the atomic-acceptance point
    and is never reused or reassigned while the entry, its acknowledgement,
    status record, recovery record, or aggregate may still refer to it.
    """

    __slots__ = ()
