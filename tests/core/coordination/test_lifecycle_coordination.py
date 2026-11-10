"""Contract tests for Common Coordination — Internal Component Lifecycle Coordination.

Implementation task: 08_Common_Coordination
Related diagrams:
  class: 03_Diagrams_Codes_Files/08_Common_Coordination.dot
  association: C_Association_Diagram_Code/08_Common_Coordination_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/03_Dependency_Direction_Rules.dot

Covers (internal-component-lifecycle-coordination contract):
  - Six conceptually distinct lifetimes (runtime instance, association,
    invocation/activity, operation, resource capability, output/evidence
    retention) as distinct types — boundaries never collapse
  - The eight conceptual lifecycle milestones as descriptive metadata only —
    explicitly NOT a mandatory enum, state machine, or materialized states
  - Authority: Step Composition owns lifecycle decisions; no component
    self-authorization surface, no universal factory/pool/manager
  - Evidence and resource independence (outputs/evidence outlive the instance)
  - Release rules: failed or indeterminate release is never ``Released``
"""

import dataclasses
import enum
import inspect

import pytest

from gpwcf.core.coordination import (
    AssociationLifetime,
    InvocationLifetime,
    OperationLifetime,
    OutputAndEvidenceRetentionLifetime,
    ResourceCapabilityLifetime,
    RuntimeInstanceLifetime,
    StepCompositionInternalComponentLifecycleCoordination,
)
from gpwcf.core.coordination import lifecycle_coordination as lifecycle_module

ALL_LIFETIME_TYPES = (
    RuntimeInstanceLifetime,
    AssociationLifetime,
    InvocationLifetime,
    OperationLifetime,
    ResourceCapabilityLifetime,
    OutputAndEvidenceRetentionLifetime,
)


# --------------------------------------------------------------------------
# Six distinct conceptual lifetimes
# --------------------------------------------------------------------------


def test_conceptual_lifetimes_are_six_distinct_types():
    assert len(ALL_LIFETIME_TYPES) == 6
    for first in ALL_LIFETIME_TYPES:
        for second in ALL_LIFETIME_TYPES:
            if first is not second:
                assert first is not second
                assert not issubclass(first, second)
                assert not issubclass(second, first)


def test_lifetime_markers_are_value_tokens_within_their_type():
    """Instances are interchangeable value tokens of exactly one lifetime."""
    assert RuntimeInstanceLifetime() == RuntimeInstanceLifetime()
    # cross-type instances never compare equal — boundaries never collapse
    assert RuntimeInstanceLifetime() != AssociationLifetime()
    assert InvocationLifetime() != OperationLifetime()
    assert OutputAndEvidenceRetentionLifetime() != RuntimeInstanceLifetime()
    assert len({life() for life in ALL_LIFETIME_TYPES}) == 6


def test_runtime_instance_lifetime_distinct_from_association_lifetime():
    """Ending an association does not by itself release the runtime instance."""
    assert RuntimeInstanceLifetime is not AssociationLifetime
    assert RuntimeInstanceLifetime() != AssociationLifetime()


def test_invocation_lifetime_distinct_from_operation_lifetime():
    """Nested operations have their own lifetime, distinct from the invocation."""
    assert InvocationLifetime is not OperationLifetime
    assert InvocationLifetime() != OperationLifetime()


def test_output_evidence_retention_lifetime_independent_of_runtime_instance():
    """Retaining evidence never by itself requires retaining the instance."""
    assert OutputAndEvidenceRetentionLifetime is not RuntimeInstanceLifetime
    assert not issubclass(
        OutputAndEvidenceRetentionLifetime, RuntimeInstanceLifetime
    )
    assert OutputAndEvidenceRetentionLifetime() != RuntimeInstanceLifetime()


def test_lifetime_markers_are_immutable_and_usable_as_keys():
    marker = RuntimeInstanceLifetime()
    with pytest.raises(dataclasses.FrozenInstanceError):
        marker.name = "mutated"  # type: ignore[misc]
    assert {marker: "value"}[RuntimeInstanceLifetime()] == "value"


# --------------------------------------------------------------------------
# Conceptual milestones — descriptive only
# --------------------------------------------------------------------------


def test_conceptual_milestones_metadata():
    assert StepCompositionInternalComponentLifecycleCoordination.conceptual_milestones == (
        "ProvisionedOrAcquired",
        "Prepared",
        "Ready",
        "Admitted",
        "AvailableOrInUse",
        "Quiescing",
        "RetainedForReuse",
        "Released",
    )
    assert StepCompositionInternalComponentLifecycleCoordination.document_id == (
        "pipeline.step-composition.internal-component-lifecycle-coordination.contract"
    )


def test_conceptual_lifetimes_metadata_matches_module_types():
    assert StepCompositionInternalComponentLifecycleCoordination.conceptual_lifetimes == (
        ALL_LIFETIME_TYPES
    )


def test_milestones_are_not_an_enum_state_machine_or_materialized_states():
    """No mandatory enum, state machine, fixed sequence, or materialized state
    set may be introduced by the framework coordination contract."""
    public_classes = {
        name: value
        for name, value in vars(lifecycle_module).items()
        if inspect.isclass(value)
    }
    for name, value in public_classes.items():
        assert not issubclass(value, enum.Enum), f"{name} must not be an enum"
        assert "StateMachine" not in name
        assert not name.endswith("State"), name
    # milestones are plain descriptive strings, not state instances
    assert all(
        isinstance(milestone, str)
        for milestone in StepCompositionInternalComponentLifecycleCoordination.conceptual_milestones
    )


def test_release_rule_failed_or_indeterminate_release_is_not_released():
    """The sharp release rule must be carried by the contract surface."""
    docstring = StepCompositionInternalComponentLifecycleCoordination.__doc__ or ""
    assert "must NOT be represented" in docstring
    assert "Released" in docstring


def test_quiescence_precedes_release_and_withdraws_new_work_authorization():
    docstring = " ".join(
        (StepCompositionInternalComponentLifecycleCoordination.__doc__ or "").split()
    )
    assert "withdrawn authorization for new work" in docstring
    assert "Quiescence" in docstring


# --------------------------------------------------------------------------
# Authority
# --------------------------------------------------------------------------


def test_coordination_is_declarative_with_no_component_self_authorization_surface():
    """The framework contract exposes vocabulary only — no operations a component
    could call to grant itself admission, association, or release authority."""
    public_members = {
        name
        for name, value in vars(StepCompositionInternalComponentLifecycleCoordination).items()
        if not name.startswith("_")
    }
    assert public_members == {
        "document_id",
        "conceptual_milestones",
        "conceptual_lifetimes",
    }
    for forbidden in ("admit", "authorize", "release", "provision", "register", "quiesce"):
        assert not hasattr(StepCompositionInternalComponentLifecycleCoordination, forbidden)


def test_no_universal_lifecycle_manager_factory_pool_or_singleton():
    for name, value in vars(lifecycle_module).items():
        assert not isinstance(
            value, StepCompositionInternalComponentLifecycleCoordination
        ), "no module-level coordination singleton may exist"
        if inspect.isfunction(value) and value.__module__ == lifecycle_module.__name__:
            pytest.fail(f"unexpected universal lifecycle operation: {name}")
    for forbidden_name in (
        "LifecycleManager",
        "LifecycleStateMachine",
        "InstancePool",
        "ProvisioningFactory",
        "ServiceLocator",
    ):
        assert not hasattr(lifecycle_module, forbidden_name), forbidden_name


def test_eligibility_admission_evidence_documented():
    """The five contract areas are explicitly defined by the coordination type."""
    docstring = StepCompositionInternalComponentLifecycleCoordination.__doc__ or ""
    for area in ("Eligibility", "Admission", "Quiescence", "Release", "Evidence independence"):
        assert area in docstring, area
