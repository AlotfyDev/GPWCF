"""Validator Unit pattern: SPU validation results, associations, lifecycle.

Implementation task: 05_Validator_Unit
Related diagrams:
  class: 03_Diagrams_Codes_Files/01_SPU_Step_Processing_Unit.dot
  sequence: B_Sequencial_Diagram_Code/03_Validator_Unit_Sequence.puml
  association: C_Association_Diagram_Code/05_Validator_Unit_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/04_Supporting_Pattern_Optional_Dependency.dot

Optional Step supporting pattern with NO Core dependency (stdlib only):
pattern-local identities, the SPUValidatorResult (carried independently in the
optional SPUExecutionResult.validatorResult slot), the identity-bearing
Validator Unit Association, the Step-Composition-coordinated instance
lifecycle, and the abstract SPU Validator Unit callable. Validation conclusions
remain domain results, never automatic invocation failures. The concrete Step
specializes what is validated, outcome semantics, evidence, and cardinality —
no universal one-validator-per-SPU relationship is imposed.
"""

from .identities import (
    AssociationTargetIdentity,
    AssociationTargetScopeKind,
    ValidatorInvocationIdentity,
    ValidatorUnitAssociationIdentity,
    ValidatorUnitIdentity,
)
from .validator_unit import (
    SPUValidatorResult,
    SPUValidatorUnit,
    ValidatorUnitAssociation,
    ValidatorUnitAssociations,
    ValidatorUnitLifecycle,
    ValidatorUnitLifecyclePhase,
    ValidatorUnitReleaseOutcome,
)

__all__ = [
    # identities (pattern-owned)
    "ValidatorUnitIdentity",
    "ValidatorUnitAssociationIdentity",
    "AssociationTargetIdentity",
    "AssociationTargetScopeKind",
    "ValidatorInvocationIdentity",
    # result / association / lifecycle / unit
    "SPUValidatorResult",
    "ValidatorUnitAssociation",
    "ValidatorUnitAssociations",
    "ValidatorUnitLifecycle",
    "ValidatorUnitLifecyclePhase",
    "ValidatorUnitReleaseOutcome",
    "SPUValidatorUnit",
]
