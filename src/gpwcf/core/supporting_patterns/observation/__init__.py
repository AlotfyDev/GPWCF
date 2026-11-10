"""Observation Unit pattern: observation records, associations, lifecycle.

Implementation task: 06_Observation_Unit
Related diagrams:
  class: 03_Diagrams_Codes_Files/01_SPU_Step_Processing_Unit.dot
  sequence: B_Sequencial_Diagram_Code/04_Observation_Unit_Sequence.puml
  association: C_Association_Diagram_Code/06_Observation_Unit_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/04_Supporting_Pattern_Optional_Dependency.dot

Optional Step supporting pattern with NO Core dependency (stdlib only):
pattern-local identities, the ObservationRecord[TObservationPayload] (fully
independent of StepExecutionResult and every other result contract), the
identity-bearing Observation Unit Association (APPLICABILITY ONLY — never a
guarantee that observation is active), the Step-Composition-coordinated
instance lifecycle (provisioned → prepared → ready → admitted →
available/in-use → observing-or-subscribed → quiescing → retained-for-reuse /
released), and the abstract SPU Observation Unit supporting call, callback,
sampling, and subscription activity mechanisms. Observation output never
implies the observed operation succeeded or failed. The concrete Step
specializes what is observed, the payload, the emission mechanism, cardinality,
destination, and custody — no universal telemetry protocol is imposed.
"""

from .identities import (
    AssociationTargetIdentity,
    AssociationTargetScopeKind,
    ObservationInvocationIdentity,
    ObservationRecordIdentity,
    ObservationUnitAssociationIdentity,
    ObservationUnitIdentity,
)
from .observation_unit import (
    ObservationRecord,
    ObservationUnitAssociation,
    ObservationUnitAssociations,
    ObservationUnitLifecycle,
    ObservationUnitLifecyclePhase,
    ObservationUnitReleaseOutcome,
    SPUObservationUnit,
)

__all__ = [
    # identities (pattern-owned)
    "ObservationUnitIdentity",
    "ObservationUnitAssociationIdentity",
    "AssociationTargetIdentity",
    "AssociationTargetScopeKind",
    "ObservationInvocationIdentity",
    "ObservationRecordIdentity",
    # record / association / lifecycle / unit
    "ObservationRecord",
    "ObservationUnitAssociation",
    "ObservationUnitAssociations",
    "ObservationUnitLifecycle",
    "ObservationUnitLifecyclePhase",
    "ObservationUnitReleaseOutcome",
    "SPUObservationUnit",
]
