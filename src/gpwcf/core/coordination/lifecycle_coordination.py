"""Step Composition Internal Component Lifecycle Coordination.

Implementation task: 08_Common_Coordination
Related diagrams:
  class: 03_Diagrams_Codes_Files/08_Common_Coordination.dot
  association: C_Association_Diagram_Code/08_Common_Coordination_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/03_Dependency_Direction_Rules.dot

Contract basis:
  - Step_Composition_Internal_Component_Lifecycle_Coordination_Contract.json
    (``pipeline.step-composition.internal-component-lifecycle-coordination.contract``)

Framework-level coordination contract under which the concrete Step
Composition makes lifecycle decisions for Step-internal runtime component
instances (eligibility, admission, invocation authorization, quiescence,
reuse, release) and keeps evidence independent — without imposing a common
technical lifecycle implementation.

Architectural position (deliberate non-goals of the contract):

  - NOT a component type: no Generic Supporting Unit, no universal runtime
    component type, no common lifecycle interface, factory, pool, service
    locator, scheduler, reference counter, state machine, or disposal API.
  - The conceptual lifecycle milestones below are NOT a mandatory enum, state
    machine, fixed sequence, or required set of separately materialized
    states; specializations may omit, combine, repeat, refine, or add
    milestones and use different names and technical states.
  - No universal activation, invocation, cancellation, retry, replacement, or
    recovery policy; no universal result, event, or publication protocol.

Authority model: the concrete Step owns Step Composition, which owns
lifecycle decisions and coordination. The component implementation performs
its implementation-specific technical mechanics through its own specialized
interaction boundary and never grants itself admission or association
authority. Targets and external resource owners never acquire lifecycle
authority over the associated component merely by being the target. Outer
levels stay out: Stage Composition invokes the owning Step without managing
its internal instances; the Pipeline imposes no global lifecycle manager.

This module is declarative: it exposes the conceptual vocabulary (distinct
lifetimes and milestones) only. Lifecycle state, if any, is owned and
interpreted by the concrete Step Composition under its specialized contracts.
"""

from dataclasses import dataclass
from typing import ClassVar

__all__ = [
    "RuntimeInstanceLifetime",
    "AssociationLifetime",
    "InvocationLifetime",
    "OperationLifetime",
    "ResourceCapabilityLifetime",
    "OutputAndEvidenceRetentionLifetime",
    "StepCompositionInternalComponentLifecycleCoordination",
]


@dataclass(frozen=True)
class RuntimeInstanceLifetime:
    """Conceptual lifetime of ONE concrete runtime component instance.

    Deliberately distinct from every other lifetime below: ending an
    association, completing an invocation, or retaining evidence does not by
    itself require instance release; reuse retains the same instance identity,
    while a replacement instance receives a NEW instance identity even when
    implementation, configuration, logical role, or resource category are
    identical.
    """


@dataclass(frozen=True)
class AssociationLifetime:
    """Conceptual lifetime of each relationship between the instance and a
    Step-owned target scope.

    One lifetime per association identity. Ending an association does not by
    itself release the runtime instance; new associations receive new
    identities under the specialized contracts.
    """


@dataclass(frozen=True)
class InvocationLifetime:
    """Conceptual lifetime of one authorized invocation, activity, subscription
    activation, or other specialized work unit.

    Distinct from the instance lifetime and from any nested operation
    lifetime. A completed invocation/activity does not imply that the instance
    must be released; each new invocation/activity receives a new
    invocation/activity identity.
    """


@dataclass(frozen=True)
class OperationLifetime:
    """Conceptual lifetime of each nested operation/attempt where the component
    behavior defines one (e.g. Error Handling operation attempts), distinct
    from its enclosing invocation lifetime.
    """


@dataclass(frozen=True)
class ResourceCapabilityLifetime:
    """Conceptual lifetime of borrowed views, handles, callbacks,
    registrations, subscriptions, leases, or other technical access resources.

    Resource-capability boundaries are owned by the specialized resource and
    ownership contracts; retaining identity metadata or output content must
    not implicitly retain callbacks, subscriptions, handles, or leases.
    """


@dataclass(frozen=True)
class OutputAndEvidenceRetentionLifetime:
    """Conceptual lifetime during which produced results, records, entries, or
    historical evidence must remain available and interpretable.

    Evidence independence: outputs and historical provenance may outlive the
    component instance, its associations, and its invocations. Retaining
    evidence never by itself requires retaining the runtime instance or its
    technical resources, and release does not erase outputs or evidence
    already accepted or retained under their independent contracts.
    """


class StepCompositionInternalComponentLifecycleCoordination:
    """Cross-cutting lifecycle-coordination contract owned by the concrete
    Step Composition.

    Defines, declaratively, the reusable conceptual distinctions the concrete
    Step Composition coordinates:

      - **Eligibility**: the component satisfies the lifecycle eligibility
        conditions required by its specialized contract (preparation,
        readiness, association, compatibility) before participation.
      - **Admission**: Step Composition's decision that a provisioned,
        prepared instance is eligible to participate in the Step's internal
        composition. Provisioning does not prove readiness; readiness does not
        imply admission or invocation authorization; admission does not
        require an active association or immediate invocation.
      - **Invocation authorization**: Step Composition authorizes each new
        invocation/activity only when the specialized lifecycle and
        association preconditions are satisfied.
      - **Quiescence**: Step Composition has withdrawn authorization for new
        work and is reconciling active work and associated obligations (active
        invocations, operations, callbacks, subscriptions, sampling cycles,
        asynchronous and queued work completed, cancelled, drained, or
        reconciled; associations that could authorize new work ended,
        deactivated, or rendered unusable).
      - **Release**: permitted only after new-work authorization is withdrawn
        and specialized obligations that could be invalidated are reconciled.
        Successful release is recorded only after confirmation; a FAILED or
        INDETERMINATE release remains unresolved and must NOT be represented
        as ``Released`` or treated as eligible for reuse without explicit
        reconciliation.
      - **Evidence independence**: produced outputs and historical provenance
        may outlive the instance, its associations, and its invocations. If
        output custody is unresolved, the instance must not be destroyed or
        released in a way that loses the only recoverable representation.

    Lifecycle failures remain distinct lifecycle/execution facts: they are not
    automatically the component's domain output, validation outcome,
    observation record, error occurrence, or handling-operation result. Retry,
    replacement, quarantine, compensation, escalation, or termination policy
    is defined by the concrete Step.
    """

    document_id: ClassVar[str] = (
        "pipeline.step-composition.internal-component-lifecycle-coordination.contract"
    )

    #: Reusable conceptual milestones ONLY — not a mandatory enum, state
    #: machine, fixed sequence, or required set of separately materialized
    #: states. A specialization may omit, combine, repeat, refine, or add
    #: milestones and may use different names and technical states.
    conceptual_milestones: ClassVar[tuple[str, ...]] = (
        "ProvisionedOrAcquired",
        "Prepared",
        "Ready",
        "Admitted",
        "AvailableOrInUse",
        "Quiescing",
        "RetainedForReuse",
        "Released",
    )

    #: The six conceptually distinct lifetimes. They remain distinct even when
    #: a concrete implementation chooses to align some of their boundaries;
    #: specialized behaviors may define additional nested lifetimes.
    conceptual_lifetimes: ClassVar[tuple[type, ...]] = (
        RuntimeInstanceLifetime,
        AssociationLifetime,
        InvocationLifetime,
        OperationLifetime,
        ResourceCapabilityLifetime,
        OutputAndEvidenceRetentionLifetime,
    )
