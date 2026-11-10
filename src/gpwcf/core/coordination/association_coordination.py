"""Step Composition Association Coordination.

Implementation task: 08_Common_Coordination
Related diagrams:
  class: 03_Diagrams_Codes_Files/08_Common_Coordination.dot
  association: C_Association_Diagram_Code/08_Common_Coordination_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/03_Dependency_Direction_Rules.dot

Contract basis:
  - Step_Composition_Association_Coordination_Contract.json
    (``pipeline.step-composition.association-coordination.contract``)

Framework-level coordination contract governing association relationships
between Step-internal runtime component instances and Step-owned target
scopes, binding each authorized invocation to the exact relationship.

Architectural position (deliberate non-goals of the contract):

  - NOT a component type: no Generic Supporting Unit, no universal runtime
    component type, no base class, interface, or callable signature.
  - NOT a registry, manager, or runtime service: the operations below are
    pure derivations and validations. The concrete Step Composition owns this
    coordination object and holds the authoritative association-to-instance-
    and-target correspondence; no association state is stored here.
  - No universal cardinality, exclusivity, or sharing rule is imposed; the
    concrete Step defines multiplicity, compatibility, and ordering.
  - Association existence is not technical readiness, not lifecycle
    admission, not invocation authorization, and does not itself activate
    observation, processing, or handling behavior.
  - Specialized component contracts (Validator, Observation, Error Handling)
    keep their own identity names, target-access semantics, and additional
    constraints; nothing here replaces them.

Authority model: only Step Composition establishes, changes, rebinds,
deactivates, and ends associations. Associated components consume the
association context supplied for an invocation and never create, select,
mutate, rebind, or terminate their own associations. Every operation below
takes the applicable :class:`Association` (and its owning Step context)
explicitly — the caller's explicit selection IS the authority act.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar

from gpwcf.core.coordination.identities import (
    AssociationIdentity,
    AssociationTargetIdentity,
    ComponentInstanceIdentity,
    ComponentInvocationIdentity,
)
from gpwcf.core.identities import StepIdentity

__all__ = [
    "Association",
    "AssociationTarget",
    "AssociationIdentity",
    "InvocationBinding",
    "Dissociation",
    "StepCompositionAssociationCoordination",
]


def _require_exact_type(field: str, value: object, expected: type) -> None:
    """Exact-type check: nominal identity roles must never collapse."""
    if type(value) is not expected:
        raise TypeError(
            f"{field} must be exactly {expected.__name__}, got {type(value).__name__}"
        )


@dataclass(frozen=True)
class AssociationTarget:
    """Step-owned scope to which a component is applicable under an association.

    The target belongs to the owning Step's internal composition and is
    identified independently of the associated component instance and the
    association. It is NOT necessarily the exact subject/resource acted upon
    by every invocation or operation; the specialized invocation or operation
    contract defines the exact subject. Association does not transfer
    ownership of the target or its resources to the associated component.
    """

    identity: AssociationTargetIdentity
    step_instance_identity: StepIdentity

    def __post_init__(self) -> None:
        _require_exact_type("identity", self.identity, AssociationTargetIdentity)
        _require_exact_type(
            "step_instance_identity", self.step_instance_identity, StepIdentity
        )


@dataclass(frozen=True)
class Association:
    """Explicit relationship between one component instance and one target
    scope within the owning Step instance; distinct from both participants.

    Entity provenance (one identity per conceptual role):

      - ``association_identity`` — the relationship itself
        (exactly one component-instance-to-target relationship within one
        owning Step instance)
      - ``component_instance_identity`` — the concrete runtime instance
        participating in the association
      - ``association_target_identity`` — the Step-owned target scope
      - ``step_instance_identity`` — the owning Step instance

    An association value is an immutable snapshot. Ending and later
    recreating a relationship requires a new association identity; a change
    that alters the component participant or target is represented as ending
    the prior relationship and establishing a new association identity.
    """

    association_identity: AssociationIdentity
    component_instance_identity: ComponentInstanceIdentity
    association_target_identity: AssociationTargetIdentity
    step_instance_identity: StepIdentity

    def __post_init__(self) -> None:
        _require_exact_type(
            "association_identity", self.association_identity, AssociationIdentity
        )
        _require_exact_type(
            "component_instance_identity",
            self.component_instance_identity,
            ComponentInstanceIdentity,
        )
        _require_exact_type(
            "association_target_identity",
            self.association_target_identity,
            AssociationTargetIdentity,
        )
        _require_exact_type(
            "step_instance_identity", self.step_instance_identity, StepIdentity
        )


@dataclass(frozen=True)
class InvocationBinding:
    """Explicit selection of ONE association context under which a particular
    invocation or activity is authorized.

    Required conceptual provenance (all five roles must be present and
    distinct):

      - ``step_instance_identity`` — the owning Step instance
      - ``component_instance_identity`` — the participating component instance
      - ``association_identity`` — the selected relationship
      - ``association_target_identity`` — the target bound to that association
      - ``invocation_identity`` — this particular invocation/activity

    Invariants: the supplied association target identity must match the
    selected association; the component must not infer, substitute, or
    silently broaden the association scope; an invocation authorized under an
    association remains attributable to that original association even if the
    association changes or ends while work is in progress (bindings are
    immutable snapshots); the invocation's exact subject need not equal the
    association target.
    """

    step_instance_identity: StepIdentity
    component_instance_identity: ComponentInstanceIdentity
    association_identity: AssociationIdentity
    association_target_identity: AssociationTargetIdentity
    invocation_identity: ComponentInvocationIdentity

    def __post_init__(self) -> None:
        _require_exact_type(
            "step_instance_identity", self.step_instance_identity, StepIdentity
        )
        _require_exact_type(
            "component_instance_identity",
            self.component_instance_identity,
            ComponentInstanceIdentity,
        )
        _require_exact_type(
            "association_identity", self.association_identity, AssociationIdentity
        )
        _require_exact_type(
            "association_target_identity",
            self.association_target_identity,
            AssociationTargetIdentity,
        )
        _require_exact_type(
            "invocation_identity", self.invocation_identity, ComponentInvocationIdentity
        )


@dataclass(frozen=True)
class Dissociation:
    """Record of the effective end of ONE association.

    Step Composition decides and records the effective end of an association;
    from the effective end point the association cannot authorize new
    invocations or activities. Deliberately NOT represented here:

      - Dissociation does not by itself destroy, release, or replace the
        component instance (the component instance identity is carried
        unchanged; there is no release state on this record).
      - Ending one association does not implicitly end other associations of
        the same instance (one record per ended association).
      - Dissociation does not invalidate accepted outputs or historical
        evidence produced under the association (retained evidence preserves
        its association, target, component, Step, and invocation provenance
        and may outlive the runtime objects).
    """

    association_identity: AssociationIdentity
    component_instance_identity: ComponentInstanceIdentity
    step_instance_identity: StepIdentity

    def __post_init__(self) -> None:
        _require_exact_type(
            "association_identity", self.association_identity, AssociationIdentity
        )
        _require_exact_type(
            "component_instance_identity",
            self.component_instance_identity,
            ComponentInstanceIdentity,
        )
        _require_exact_type(
            "step_instance_identity", self.step_instance_identity, StepIdentity
        )


class StepCompositionAssociationCoordination:
    """Cross-cutting association-coordination contract owned by the concrete
    Step Composition.

    Pure coordination surface: every operation validates and derives
    association values; the OWNER (Step Composition) holds and interprets the
    resulting state. Targets and associated components gain no
    association-management authority from this contract.

    Conceptual identity roles (mandatory distinctions; see
    :mod:`gpwcf.core.coordination.identities`):
    ``stepInstanceIdentity``, ``componentInstanceIdentity``,
    ``associationTargetIdentity``, ``componentAssociationIdentity``,
    ``componentInvocationIdentity``.
    """

    document_id: ClassVar[str] = (
        "pipeline.step-composition.association-coordination.contract"
    )

    conceptual_identity_roles: ClassVar[tuple[str, ...]] = (
        "stepInstanceIdentity",
        "componentInstanceIdentity",
        "associationTargetIdentity",
        "componentAssociationIdentity",
        "componentInvocationIdentity",
    )

    def establish(
        self,
        association_identity: AssociationIdentity,
        component_instance_identity: ComponentInstanceIdentity,
        target: AssociationTarget,
        step_instance_identity: StepIdentity,
    ) -> Association:
        """Establish an explicit component-instance-to-target relationship.

        Structural preconditions checked here (general preconditions of the
        contract): all identity roles are of the correct distinct types, and
        the target scope belongs to the owning Step's internal composition.
        Compatibility, lifecycle eligibility, and uniqueness within the
        observation scope remain Step Composition responsibilities under the
        specialized contracts.
        """
        if target.step_instance_identity != step_instance_identity:
            raise ValueError(
                "association target does not belong to the owning Step instance's "
                "internal composition"
            )
        return Association(
            association_identity=association_identity,
            component_instance_identity=component_instance_identity,
            association_target_identity=target.identity,
            step_instance_identity=step_instance_identity,
        )

    def change_target(
        self,
        association: Association,
        new_association_identity: AssociationIdentity,
        new_target: AssociationTarget,
    ) -> Association:
        """Change the target of a relationship by ending the prior relationship
        and establishing a NEW association identity.

        The conservative framework rule applies: a change that alters the
        participant or target is represented as a new relationship with a new
        association identity (safe in-place changes with preserved identity
        semantics may only be defined by a specialization). The prior
        :class:`Association` value is never mutated; record its effective end
        with :meth:`dissociate`. Already-authorized invocations keep their
        original binding provenance.
        """
        if not isinstance(association, Association):
            raise TypeError("association must be an Association")
        if new_target.step_instance_identity != association.step_instance_identity:
            raise ValueError(
                "new association target does not belong to the same owning Step "
                "instance's internal composition"
            )
        if new_association_identity == association.association_identity:
            raise ValueError(
                "changing the target of a relationship requires a new association "
                "identity; the prior relationship's identity must not be reused"
            )
        return Association(
            association_identity=new_association_identity,
            component_instance_identity=association.component_instance_identity,
            association_target_identity=new_target.identity,
            step_instance_identity=association.step_instance_identity,
        )

    def dissociate(self, association: Association) -> Dissociation:
        """Record the effective end of one association.

        One record per ended association: ending one association does not
        implicitly end other associations of the same instance, and
        dissociation does not release, destroy, or replace the component
        instance. In-flight work reconciliation is defined by the concrete
        Step; accepted outputs and historical evidence remain valid.
        """
        if not isinstance(association, Association):
            raise TypeError("association must be an Association")
        return Dissociation(
            association_identity=association.association_identity,
            component_instance_identity=association.component_instance_identity,
            step_instance_identity=association.step_instance_identity,
        )

    def bind_invocation(
        self,
        association: Association,
        invocation_identity: ComponentInvocationIdentity,
    ) -> InvocationBinding:
        """Bind one invocation/activity to the explicitly selected association.

        Step Composition selects the applicable association for each
        invocation (passing it here IS the selection). The binding's target
        provenance matches the selected association by construction, so the
        supplied target can never diverge from the selected relationship.
        Each invocation keeps its own distinct invocation identity.
        """
        if not isinstance(association, Association):
            raise TypeError("association must be an Association")
        _require_exact_type(
            "invocation_identity", invocation_identity, ComponentInvocationIdentity
        )
        return InvocationBinding(
            step_instance_identity=association.step_instance_identity,
            component_instance_identity=association.component_instance_identity,
            association_identity=association.association_identity,
            association_target_identity=association.association_target_identity,
            invocation_identity=invocation_identity,
        )

    def ensure_authorizable(
        self,
        association: Association,
        dissociations: Iterable[Dissociation] = (),
    ) -> None:
        """Confirm an association can still authorize new invocations/activities.

        ``dissociations`` is the effective-end record set held by the owning
        Step Composition (passed in explicitly — no registry lives here).
        Raises ``ValueError`` when the association has a recorded effective
        end: from the effective end point, an association cannot authorize new
        invocations or activities.
        """
        if not isinstance(association, Association):
            raise TypeError("association must be an Association")
        ended = {record.association_identity for record in dissociations}
        if association.association_identity in ended:
            raise ValueError(
                "association has a recorded effective end; from the effective end "
                "point it cannot authorize new invocations or activities"
            )
