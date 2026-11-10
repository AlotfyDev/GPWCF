"""Coordination identity roles: distinct nominal identity value types.

Implementation task: 08_Common_Coordination
Related diagrams:
  class: 03_Diagrams_Codes_Files/08_Common_Coordination.dot
  association: C_Association_Diagram_Code/08_Common_Coordination_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/03_Dependency_Direction_Rules.dot

Contract basis:
  - Step_Composition_Association_Coordination_Contract.json
    (``pipeline.step-composition.association-coordination.contract``),
    sections ``coreConcepts`` and ``identityInvariants``.

The association coordination contract mandates five distinct conceptual
identity roles:

  ============================  ====================================================  ==========================
  Conceptual role               Meaning                                               Framework value type
  ============================  ====================================================  ==========================
  stepInstanceIdentity          identifies the owning Step instance                   ``core.identities.StepIdentity``
  componentInstanceIdentity     identifies the concrete runtime component instance    ``ComponentInstanceIdentity``
  associationTargetIdentity     identifies the target scope (scope kind + instance)   ``AssociationTargetIdentity``
  componentAssociationIdentity  identifies one particular relationship                ``AssociationIdentity``
  componentInvocationIdentity   identifies one invocation/activity                    ``ComponentInvocationIdentity``
  ============================  ====================================================  ==========================

The roles are mandatory distinctions. A component instance identity must not
be derived from or overloaded to represent an association or target identity;
a component identity alone is insufficient to identify a different scope kind.
The literal field names and representations of a specialized contract may
differ (specialization requirement), but the distinctions must never collapse.

No UUID, counter, address, timestamp, or other generation mechanism is
mandated or provided here: identity values are consumer/owner-assigned and
opaque. Values reuse the immutable nominal value-type pattern of
``core.identities`` (in-type equality/hash, nominal cross-type inequality).
"""

from dataclasses import dataclass

from gpwcf.core.identities import _IdentityValue  # shared core value-type base

__all__ = [
    "ComponentInstanceIdentity",
    "AssociationIdentity",
    "ComponentAssociationIdentity",
    "AssociationTargetIdentity",
    "ComponentInvocationIdentity",
]


def _non_empty(field: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a str")
    if value == "" or value.isspace():
        raise ValueError(f"{field} must be a non-empty, non-blank string")
    return value


class ComponentInstanceIdentity(_IdentityValue):
    """Identifies the concrete Step-internal runtime component instance.

    The component participating in an association may be a Step Processing
    Unit instance or an instance of a selected supporting pattern. This
    identity is deliberately a distinct nominal type from the association,
    target, invocation, and Step identities; it is never overloaded to
    represent an association or target.
    """

    __slots__ = ()


class AssociationIdentity(_IdentityValue):
    """Identifies exactly one component-instance-to-target relationship.

    Conceptual role name: ``componentAssociationIdentity`` (the module-level
    alias ``ComponentAssociationIdentity`` names the same role). Distinct from
    the component instance identity and the target identity. Each distinct
    relationship has a distinct association identity, even when the component
    instance or the target is shared; ending and later recreating a
    relationship requires a NEW association identity whenever prior
    relationship evidence may remain observable.
    """

    __slots__ = ()


#: Conceptual role name for :class:`AssociationIdentity` in the contract's
#: ``requiredConceptualProvenance`` list. Same type, same semantics.
ComponentAssociationIdentity = AssociationIdentity


class ComponentInvocationIdentity(_IdentityValue):
    """Identifies one invocation/activity and remains distinct from the
    instance, association, and target identities.

    Repeated invocations receive distinct invocation identities, even when
    the same component instance and association are reused. A specialized
    contract maps this conceptual role to its own identity names and
    representations; the distinctions between the roles are mandatory.
    """

    __slots__ = ()


@dataclass(frozen=True)
class AssociationTargetIdentity:
    """Identifies the target scope, including its scope kind and concrete
    target instance.

    The target identity must distinguish target scope kind as well as concrete
    target instance; a component identity alone is insufficient to identify a
    different scope kind. ``scope_kind`` is a descriptive, owner-defined
    classification (the concrete Step defines the permitted target kinds);
    ``instance_identity`` is an opaque, owner-assigned value. Equality and
    hashing are scoped by BOTH fields.
    """

    scope_kind: str
    instance_identity: str

    def __post_init__(self) -> None:
        _non_empty("scope_kind", self.scope_kind)
        _non_empty("instance_identity", self.instance_identity)

    def __str__(self) -> str:
        return f"{self.scope_kind}:{self.instance_identity}"
