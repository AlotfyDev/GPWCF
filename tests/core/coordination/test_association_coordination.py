"""Contract tests for Common Coordination — Association Coordination.

Implementation task: 08_Common_Coordination
Related diagrams:
  class: 03_Diagrams_Codes_Files/08_Common_Coordination.dot
  association: C_Association_Diagram_Code/08_Common_Coordination_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/03_Dependency_Direction_Rules.dot

Covers (association-coordination contract):
  - Identity role separation: association identity distinct from component
    instance, target, invocation, and Step identities
  - AssociationTarget: scope kind + instance distinction, Step membership
  - Establishment validity conditions and authority (Step Composition calls
    the operations; target/component gain no management authority)
  - Invocation binding: full five-role provenance, target matches the selected
    association, per-invocation identity distinctness, in-flight attribution
  - Change and dissociation: new association identity on change, effective end
    per association, dissociation ≠ instance release, evidence survives
  - No universal cardinality/registry/manager imposed
"""

import dataclasses

import pytest

from gpwcf.core.coordination import (
    Association,
    AssociationIdentity,
    AssociationTarget,
    AssociationTargetIdentity,
    ComponentAssociationIdentity,
    ComponentInstanceIdentity,
    ComponentInvocationIdentity,
    Dissociation,
    InvocationBinding,
    StepCompositionAssociationCoordination,
)
from gpwcf.core.identities import StepIdentity


def a_step(value: str = "step-1") -> StepIdentity:
    return StepIdentity(value)


def a_component(value: str = "component-1") -> ComponentInstanceIdentity:
    return ComponentInstanceIdentity(value)


def an_association_identity(value: str = "assoc-1") -> AssociationIdentity:
    return AssociationIdentity(value)


def an_invocation_identity(value: str = "inv-1") -> ComponentInvocationIdentity:
    return ComponentInvocationIdentity(value)


def a_target_identity(
    scope_kind: str = "validator-target-scope", instance: str = "target-1"
) -> AssociationTargetIdentity:
    return AssociationTargetIdentity(scope_kind, instance)


def a_target(step: StepIdentity | None = None) -> AssociationTarget:
    return AssociationTarget(a_target_identity(), step or a_step())


def an_association(
    *,
    association_identity: AssociationIdentity | None = None,
    component: ComponentInstanceIdentity | None = None,
    target: AssociationTarget | None = None,
    step: StepIdentity | None = None,
) -> Association:
    step = step or a_step()
    target = target or a_target(step)
    return Association(
        association_identity=association_identity or an_association_identity(),
        component_instance_identity=component or a_component(),
        association_target_identity=target.identity,
        step_instance_identity=step,
    )


# --------------------------------------------------------------------------
# Identity roles
# --------------------------------------------------------------------------


def test_association_identity_is_component_association_identity_role():
    """The entity class and the conceptual role name are the same type."""
    assert AssociationIdentity is ComponentAssociationIdentity


def test_identity_roles_are_pairwise_distinct_types():
    """Equal values of different identity roles are never equal (nominal types)."""
    step = a_step("same-value")
    component = a_component("same-value")
    association = an_association_identity("same-value")
    target = a_target_identity("scope", "same-value")
    invocation = an_invocation_identity("same-value")

    roles = {step, component, association, target, invocation}
    assert len(roles) == 5  # equal opaque values do not collapse across roles

    assert step != component
    assert component != association
    assert association != target
    assert invocation != association
    assert target != component

    for first in (type(step), type(component), type(association), type(target), type(invocation)):
        for second in (type(step), type(component), type(association), type(target), type(invocation)):
            if first is not second:
                assert not issubclass(first, second)


def test_target_identity_distinguishes_scope_kind_and_instance():
    """A target identity differs when EITHER scope kind or instance differs."""
    assert a_target_identity("scope-a", "t1") == a_target_identity("scope-a", "t1")
    assert a_target_identity("scope-a", "t1") != a_target_identity("scope-a", "t2")
    # same instance value under a different scope kind is a DIFFERENT target
    assert a_target_identity("scope-a", "t1") != a_target_identity("scope-b", "t1")
    assert hash(a_target_identity("scope-a", "t1")) == hash(a_target_identity("scope-a", "t1"))


def test_target_identity_validation():
    with pytest.raises(ValueError):
        a_target_identity("", "t1")
    with pytest.raises(ValueError):
        a_target_identity("scope", "  ")
    with pytest.raises(TypeError):
        a_target_identity("scope", 42)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Association entity
# --------------------------------------------------------------------------


def test_association_entity_has_the_four_contract_provenance_fields():
    field_names = [field.name for field in dataclasses.fields(Association)]
    assert field_names == [
        "association_identity",
        "component_instance_identity",
        "association_target_identity",
        "step_instance_identity",
    ]


def test_association_rejects_collapsed_identity_roles():
    """Passing one role's identity where another role's type is required fails."""
    step = a_step()
    with pytest.raises(TypeError):
        Association(
            association_identity=an_association_identity(),
            component_instance_identity=ComponentInstanceIdentity("c"),
            association_target_identity=a_target_identity(),  # correct type
            step_instance_identity=ComponentInstanceIdentity("c"),  # wrong role type
        )
    with pytest.raises(TypeError):
        Association(
            association_identity=StepIdentity("step-1"),  # wrong role type
            component_instance_identity=a_component(),
            association_target_identity=a_target_identity(),
            step_instance_identity=step,
        )


def test_association_values_are_immutable():
    association = an_association()
    with pytest.raises(dataclasses.FrozenInstanceError):
        association.association_target_identity = a_target_identity("other", "t")


# --------------------------------------------------------------------------
# Establishment, validity, authority
# --------------------------------------------------------------------------


def test_establish_requires_target_to_belong_to_the_owning_step():
    coordination = StepCompositionAssociationCoordination()
    owning_step = a_step("step-1")
    foreign_step = a_step("step-2")
    target = AssociationTarget(a_target_identity(), foreign_step)

    with pytest.raises(ValueError):
        coordination.establish(an_association_identity(), a_component(), target, owning_step)


def test_establish_produces_explicit_relationship_provenance():
    coordination = StepCompositionAssociationCoordination()
    step = a_step("step-1")
    component = a_component("component-1")
    target = a_target(step)
    association_identity = an_association_identity("assoc-1")

    association = coordination.establish(association_identity, component, target, step)

    assert isinstance(association, Association)
    assert association.association_identity == association_identity
    assert association.component_instance_identity == component
    assert association.association_target_identity == target.identity
    assert association.step_instance_identity == step


def test_establish_rejects_mistyped_identities():
    coordination = StepCompositionAssociationCoordination()
    step = a_step()
    target = a_target(step)
    with pytest.raises(TypeError):
        coordination.establish(an_invocation_identity(), a_component(), target, step)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        coordination.establish(an_association_identity(), a_step(), target, step)  # type: ignore[arg-type]


def test_no_universal_cardinality_exclusivity_or_sharing_rule():
    """The framework imposes none; shared instances/targets are not restricted."""
    coordination = StepCompositionAssociationCoordination()
    step = a_step()
    component = a_component()
    target = a_target(step)

    # one component instance, multiple associations (even against the same target)
    first = coordination.establish(an_association_identity("assoc-1"), component, target, step)
    second = coordination.establish(an_association_identity("assoc-2"), component, target, step)
    assert first.association_identity != second.association_identity

    # multiple component instances associated with the same target
    other_component = a_component("component-2")
    third = coordination.establish(an_association_identity("assoc-3"), other_component, target, step)
    assert third.association_target_identity == first.association_target_identity


def test_step_composition_owns_association_authority():
    """All operations are explicit selections by the owner; the object holds no state."""
    coordination = StepCompositionAssociationCoordination()

    # no registry/manager state: instances carry nothing
    assert vars(coordination) == {}

    # the owner passes the applicable association explicitly in every operation
    import inspect

    operation_parameters = {
        name: list(inspect.signature(method).parameters)
        for name, method in vars(StepCompositionAssociationCoordination).items()
        if callable(method) and not name.startswith("_")
    }
    assert set(operation_parameters) == {
        "establish",
        "change_target",
        "dissociate",
        "bind_invocation",
        "ensure_authorizable",
    }
    for name, parameters in operation_parameters.items():
        if name != "establish":
            assert "association" in parameters, name


def test_conceptual_identity_roles_metadata():
    assert StepCompositionAssociationCoordination.conceptual_identity_roles == (
        "stepInstanceIdentity",
        "componentInstanceIdentity",
        "associationTargetIdentity",
        "componentAssociationIdentity",
        "componentInvocationIdentity",
    )
    assert StepCompositionAssociationCoordination.document_id == (
        "pipeline.step-composition.association-coordination.contract"
    )


# --------------------------------------------------------------------------
# Invocation binding
# --------------------------------------------------------------------------


def test_binding_carries_full_five_role_provenance_matching_the_association():
    coordination = StepCompositionAssociationCoordination()
    association = an_association()
    binding = coordination.bind_invocation(association, an_invocation_identity("inv-7"))

    assert isinstance(binding, InvocationBinding)
    assert binding.step_instance_identity == association.step_instance_identity
    assert binding.component_instance_identity == association.component_instance_identity
    assert binding.association_identity == association.association_identity
    assert binding.association_target_identity == association.association_target_identity
    assert binding.invocation_identity == an_invocation_identity("inv-7")


def test_binding_target_matches_selected_association_by_construction():
    """The supplied target identity cannot diverge from the selected association."""
    coordination = StepCompositionAssociationCoordination()
    association = an_association()
    binding = coordination.bind_invocation(association, an_invocation_identity())
    assert binding.association_target_identity == association.association_target_identity


def test_repeated_invocations_receive_distinct_bindings():
    """Same instance + association reused; each invocation identity is distinct."""
    coordination = StepCompositionAssociationCoordination()
    association = an_association()
    first = coordination.bind_invocation(association, an_invocation_identity("inv-1"))
    second = coordination.bind_invocation(association, an_invocation_identity("inv-2"))

    assert first != second
    assert first.invocation_identity != second.invocation_identity
    assert first.association_identity == second.association_identity


def test_binding_is_immutable_and_survives_later_association_change_or_end():
    """In-flight work stays attributable to its original association."""
    coordination = StepCompositionAssociationCoordination()
    step = a_step()
    association = an_association(step=step)
    binding = coordination.bind_invocation(association, an_invocation_identity("inv-1"))
    snapshot = dataclasses.replace(binding)

    with pytest.raises(dataclasses.FrozenInstanceError):
        binding.association_identity = an_association_identity("rewritten")

    # association ends while work is in progress
    ended = coordination.dissociate(association)
    assert ended.association_identity == binding.association_identity
    # the binding snapshot is unchanged and still fully attributable
    assert binding == snapshot


def test_binding_rejects_mistyped_provenance():
    with pytest.raises(TypeError):
        InvocationBinding(
            step_instance_identity=a_step(),
            component_instance_identity=a_component(),
            association_identity=an_association_identity(),
            association_target_identity=a_target_identity(),
            invocation_identity=an_association_identity(),  # wrong role type
        )


# --------------------------------------------------------------------------
# Change and dissociation
# --------------------------------------------------------------------------


def test_change_target_requires_a_new_association_identity():
    coordination = StepCompositionAssociationCoordination()
    step = a_step()
    association = an_association(step=step)
    new_target = AssociationTarget(a_target_identity("scope", "target-2"), step)

    with pytest.raises(ValueError):
        coordination.change_target(association, association.association_identity, new_target)


def test_change_target_yields_new_relationship_and_preserves_the_old_value():
    coordination = StepCompositionAssociationCoordination()
    step = a_step()
    component = a_component()
    association = an_association(
        association_identity=an_association_identity("assoc-1"),
        component=component,
        step=step,
    )
    new_target = AssociationTarget(a_target_identity("scope", "target-2"), step)

    changed = coordination.change_target(
        association, an_association_identity("assoc-2"), new_target
    )

    assert changed.association_identity == an_association_identity("assoc-2")
    assert changed.association_target_identity == new_target.identity
    assert changed.component_instance_identity == component
    assert changed.step_instance_identity == step
    # the prior relationship snapshot is untouched (ends explicitly via dissociate)
    assert association.association_target_identity != changed.association_target_identity


def test_change_target_rejects_target_outside_the_owning_step():
    coordination = StepCompositionAssociationCoordination()
    association = an_association(step=a_step("step-1"))
    foreign_target = AssociationTarget(a_target_identity("scope", "t"), a_step("step-9"))

    with pytest.raises(ValueError):
        coordination.change_target(
            association, an_association_identity("assoc-2"), foreign_target
        )


def test_dissociation_records_effective_end_per_association():
    """Ending one association does not implicitly end others of the same instance."""
    coordination = StepCompositionAssociationCoordination()
    step = a_step()
    component = a_component()
    first = an_association(
        association_identity=an_association_identity("assoc-1"),
        component=component,
        step=step,
    )
    second = an_association(
        association_identity=an_association_identity("assoc-2"),
        component=component,
        step=step,
    )

    ended = coordination.dissociate(first)
    assert ended.association_identity == first.association_identity
    assert ended.component_instance_identity == component
    assert ended.step_instance_identity == step

    coordination.ensure_authorizable(second, [ended])  # other association survives
    with pytest.raises(ValueError):
        coordination.ensure_authorizable(first, [ended])


def test_ended_association_cannot_authorize_new_invocations():
    coordination = StepCompositionAssociationCoordination()
    association = an_association()
    ended = coordination.dissociate(association)

    coordination.ensure_authorizable(association, [])  # before the end: fine
    with pytest.raises(ValueError):
        coordination.ensure_authorizable(association, [ended])


def test_dissociation_is_not_instance_release():
    """Dissociation neither releases nor replaces the component instance."""
    field_names = [field.name for field in dataclasses.fields(Dissociation)]
    assert field_names == [
        "association_identity",
        "component_instance_identity",
        "step_instance_identity",
    ]
    for forbidden in ("released", "release", "instance_state", "lifecycle_state"):
        assert not hasattr(Dissociation, forbidden), forbidden

    # the component instance identity remains a valid, unchanged identity value
    component = a_component("component-1")
    ended = Dissociation(an_association_identity("assoc-1"), component, a_step())
    assert ended.component_instance_identity == component


def test_no_universal_association_registry_manager_or_service():
    """No registry/manager/runtime-service surface anywhere in the contract module."""
    from gpwcf.core.coordination import association_coordination as module

    forbidden_names = {
        "registry",
        "REGISTRY",
        "manager",
        "MANAGER",
        "store",
        "associations_by_step",
        "global_coordination",
        "default_coordination",
        "singleton",
    }
    for name in vars(module):
        assert name not in forbidden_names, name
        value = getattr(module, name)
        assert not isinstance(value, StepCompositionAssociationCoordination), (
            "no module-level coordination singleton may exist"
        )
