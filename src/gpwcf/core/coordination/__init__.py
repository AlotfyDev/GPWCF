"""Core coordination contracts: Step Composition association & lifecycle coordination.

Implementation task: 08_Common_Coordination
Related diagrams:
  class: 03_Diagrams_Codes_Files/08_Common_Coordination.dot
  association: C_Association_Diagram_Code/08_Common_Coordination_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/03_Dependency_Direction_Rules.dot

A pair of framework-level coordination contracts owned by the concrete Step
Composition:

  - :mod:`association_coordination` — explicit component-instance-to-target
    relationships and per-invocation binding
    (``pipeline.step-composition.association-coordination.contract``).
  - :mod:`lifecycle_coordination` — lifecycle authority, eligibility,
    admission, quiescence, release, and evidence independence
    (``pipeline.step-composition.internal-component-lifecycle-coordination.contract``).

Both are deliberately generic: no validator/observer/error-handler specifics
live here (per-pattern specialization lives in the supporting-pattern
contracts). Dependency boundary: this package imports only the standard
library and ``gpwcf.core.identities`` — nothing above it.
"""

from gpwcf.core.coordination.association_coordination import (
    Association,
    AssociationIdentity,
    AssociationTarget,
    Dissociation,
    InvocationBinding,
    StepCompositionAssociationCoordination,
)
from gpwcf.core.coordination.identities import (
    AssociationTargetIdentity,
    ComponentAssociationIdentity,
    ComponentInstanceIdentity,
    ComponentInvocationIdentity,
)
from gpwcf.core.coordination.lifecycle_coordination import (
    AssociationLifetime,
    InvocationLifetime,
    OperationLifetime,
    OutputAndEvidenceRetentionLifetime,
    ResourceCapabilityLifetime,
    RuntimeInstanceLifetime,
    StepCompositionInternalComponentLifecycleCoordination,
)

__all__ = [
    # association coordination
    "Association",
    "AssociationTarget",
    "AssociationIdentity",
    "InvocationBinding",
    "Dissociation",
    "StepCompositionAssociationCoordination",
    # coordination identity roles
    "ComponentInstanceIdentity",
    "ComponentAssociationIdentity",
    "AssociationTargetIdentity",
    "ComponentInvocationIdentity",
    # lifecycle coordination
    "RuntimeInstanceLifetime",
    "AssociationLifetime",
    "InvocationLifetime",
    "OperationLifetime",
    "ResourceCapabilityLifetime",
    "OutputAndEvidenceRetentionLifetime",
    "StepCompositionInternalComponentLifecycleCoordination",
]
