"""Validator Unit pattern identities: nominal, immutable identity value types.

Implementation task: 05_Validator_Unit
Related diagrams:
  class: 03_Diagrams_Codes_Files/01_SPU_Step_Processing_Unit.dot
  association: C_Association_Diagram_Code/05_Validator_Unit_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/04_Supporting_Pattern_Optional_Dependency.dot

Contract basis:
  - Step_Supporting_Validator_Unit_Contract.json (``identitySeparation``,
    ``requiredInvocationInformation``)
  - Step_Supporting_Validator_Unit_Association_Contract.json
    (``associationModel``, ``identityRequirements``)
  - Step_Supporting_Validator_Unit_Lifecycle_Contract.json
    (``lifecycleIdentity``)

Dependency boundary (``04_Supporting_Pattern_Optional_Dependency.dot``):
``ValidatorUnit -> Core : NO dependency``. This pattern package imports NOTHING
from ``gpwcf`` (standard library only) and defines its own nominal identity
value types, replicating the small immutable value-type pattern used by
``core.identities`` deliberately.

Identity separation (each value identifies a DIFFERENT architectural fact and
the nominal types make conflation unrepresentable):

  - ``ValidatorUnitIdentity`` — one concrete validator-unit runtime instance.
    Stable for the instance lifetime; a replacement instance receives a NEW
    identity even for the same implementation/configuration; never derived
    from, or overloaded to represent, an association target or association.
  - ``ValidatorUnitAssociationIdentity`` — one relationship instance between a
    validator-unit instance and one target scope. Unique within the owning
    Step's scope for as long as the association or any retained result/evidence
    referencing it may be observed; stable for the association lifetime;
    ending an association and later establishing a logically similar one
    creates a NEW identity; never reused for a relationship to a different
    target.
  - ``AssociationTargetIdentity`` — the Step-owned target scope: identifies
    BOTH the target scope kind and the concrete target instance, so a bare SPU
    identity can never be mistaken for a Step-level target.
  - ``ValidatorInvocationIdentity`` — one invocation attempt; repeated
    invocations under the same association receive distinct values.

``stepInstanceIdentity`` is owned by the Step layer and travels as an opaque,
validated, non-empty string VALUE (the originating layer's identity value);
this package never interprets or re-scopes it. No UUID, counter, timestamp, or
other generation mechanism is mandated or provided; identity values are
owner-assigned.
"""

from __future__ import annotations

import enum

__all__ = [
    "ValidatorUnitIdentity",
    "ValidatorUnitAssociationIdentity",
    "AssociationTargetIdentity",
    "AssociationTargetScopeKind",
    "ValidatorInvocationIdentity",
]


class _PatternIdentityValue:
    """Immutable nominal identity value; equal only within its own type.

    Deliberate local replica of the shared core value-type pattern: the
    Validator Unit pattern has NO Core dependency, so it cannot import the
    base.
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
        """The opaque identity value."""
        return self._value  # type: ignore[attr-defined,no-any-return]

    def __str__(self) -> str:
        return self._value  # type: ignore[attr-defined,no-any-return]

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._value!r})"  # type: ignore[attr-defined]

    def __eq__(self, other: object) -> bool:
        # Nominal: equal only within the SAME identity type — a validator-unit
        # identity can never compare equal to an association, target, or
        # invocation identity even with the same underlying string.
        if type(self) is not type(other):
            return NotImplemented
        return self._value == other._value  # type: ignore[attr-defined]

    def __hash__(self) -> int:
        return hash((type(self).__name__, self._value))  # type: ignore[attr-defined]


class ValidatorUnitIdentity(_PatternIdentityValue):
    """Identifies one concrete Validator Unit runtime instance.

    Stable for the instance lifetime, including periods with no active
    associations or while retained for reuse. A replacement runtime instance
    receives a distinct identity even when it uses the same implementation,
    configuration, or underlying resource category as a released instance.
    Historical results may reference this identity after release; such a
    reference is historical identity, not proof the instance remains alive.
    """

    __slots__ = ()


class ValidatorUnitAssociationIdentity(_PatternIdentityValue):
    """Identifies one validator-unit instance-to-target-scope relationship.

    Distinct from both participants: one validator-unit instance associated
    with three target scopes is one ``ValidatorUnitIdentity`` plus THREE
    distinct association identities. Unique within the owning Step's identity
    scope for as long as the association or any retained result/reference to it
    may be observed; stable for the association's lifetime; an association
    identity is never reused to represent a relationship to a different target.
    """

    __slots__ = ()


class ValidatorInvocationIdentity(_PatternIdentityValue):
    """Identifies one validator invocation attempt.

    Assigned or reserved before the invocation begins and stable throughout
    invocation and result attribution. Repeated invocations under the SAME
    association receive distinct invocation identities; the association
    identity is not a substitute for an invocation identity.
    """

    __slots__ = ()


class AssociationTargetScopeKind(enum.Enum):
    """The permitted kinds of Step-owned validator association target scopes.

    ``SPU``: a concrete SPU instance within the owning Step.
    ``STEP``: the owning Step instance as a whole.
    ``STEP_INTERNAL``: another explicitly identified internal processing scope
    defined by the concrete Step.
    """

    SPU = "spu"
    STEP = "step"
    STEP_INTERNAL = "step-internal"


class AssociationTargetIdentity:
    """Identifies the Step-owned target scope of a validator association.

    Deliberately NOT a bare wrapped string: the contract requires the target
    identity to identify BOTH the target scope kind and the concrete target
    instance ("an SPU identity alone must not be interpreted as a Step-level
    target"). Equal only to another ``AssociationTargetIdentity`` with the same
    kind and instance value; hashable; immutable.
    """

    __slots__ = ("_scope_kind", "_instance_identity")

    def __init__(self, scope_kind: AssociationTargetScopeKind, instance_identity: str) -> None:
        if not isinstance(scope_kind, AssociationTargetScopeKind):
            raise TypeError("scope_kind must be an AssociationTargetScopeKind")
        if not isinstance(instance_identity, str):
            raise TypeError("instance_identity must be a str")
        if instance_identity == "" or instance_identity.isspace():
            raise ValueError("instance_identity must be a non-empty, non-blank string")
        object.__setattr__(self, "_scope_kind", scope_kind)
        object.__setattr__(self, "_instance_identity", instance_identity)

    @property
    def scope_kind(self) -> AssociationTargetScopeKind:
        """The kind of Step-owned scope the association targets."""
        return self._scope_kind  # type: ignore[attr-defined,no-any-return]

    @property
    def instance_identity(self) -> str:
        """The concrete target instance within the owning Step."""
        return self._instance_identity  # type: ignore[attr-defined,no-any-return]

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            f"{type(self).__name__} is immutable; construct a new value instead"
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return NotImplemented
        return (
            self._scope_kind == other._scope_kind  # type: ignore[attr-defined]
            and self._instance_identity
            == other._instance_identity  # type: ignore[attr-defined]
        )

    def __hash__(self) -> int:
        return hash((type(self).__name__, self._scope_kind, self._instance_identity))

    def __repr__(self) -> str:
        return (
            f"AssociationTargetIdentity({self._scope_kind.value!r}, "
            f"{self._instance_identity!r})"
        )
