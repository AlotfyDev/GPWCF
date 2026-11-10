"""GPWCF Core Public API.

Curated re-export surface for Core domain contracts. Consumers import only
from this surface; internal gpwcf.core.* paths are not part of the compatibility
boundary. Core remains usable with Prefect absent — no Prefect types appear here.

Implementation task: 10.C
"""

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
    OutputAndEvidenceRetentionLifetime,
    ResourceCapabilityLifetime,
    StepCompositionAssociationCoordination,
    StepCompositionInternalComponentLifecycleCoordination,
    RuntimeInstanceLifetime,
    AssociationLifetime,
    InvocationLifetime,
    OperationLifetime,
)
from gpwcf.core.diagnostics import Diagnostic, DiagnosticCode
from gpwcf.core.identities import (
    InvocationIdentity,
    PipelineInvocationIdentity,
    SPUIdentity,
    StageIdentity,
    StageInvocationIdentity,
    StepIdentity,
    StepInvocationIdentity,
)
from gpwcf.core.processing_units.spu import SPUExecutionResult, StepProcessingUnit
from gpwcf.core.step import (
    OptionalResultContributions,
    Step,
    StepExecutionResult,
)
from gpwcf.core.step.invocation import (
    StepCallable,
    StepInvocation,
    StepInvocationRejected,
    StepExecutionContext,
)
from gpwcf.core.step.results import Absent, OptionalResultSlot, Present
from gpwcf.core.stage import (
    Stage,
    StageCallableContract,
    StageComposition,
    StageExecutionContractViolation,
    StageFlowResult,
    StageInvocation,
    StageInvocationRejected,
    StageResult,
    StageSettlementReport,
)
from gpwcf.core.stage.errors import (
    StageError,
    StageErrorTypeDefinition,
    StageErrorTypeDefinitionRegistry,
)
from gpwcf.core.stage.results import (
    StageFlowException,
    StageFlowTransition,
    StageStepInvocation,
)

__all__ = [
    # Results
    "Absent",
    "Present",
    "OptionalResultSlot",
    "OptionalResultContributions",
    # Identities
    "PipelineInvocationIdentity",
    "StageIdentity",
    "StageInvocationIdentity",
    "StepIdentity",
    "StepInvocationIdentity",
    "SPUIdentity",
    "InvocationIdentity",
    # Diagnostics
    "Diagnostic",
    "DiagnosticCode",
    # SPU
    "StepProcessingUnit",
    "SPUExecutionResult",
    # Step
    "Step",
    "StepExecutionResult",
    "StepCallable",
    "StepInvocation",
    "StepInvocationRejected",
    "StepExecutionContext",
    # Stage
    "Stage",
    "StageCallableContract",
    "StageComposition",
    "StageExecutionContractViolation",
    "StageFlowResult",
    "StageInvocation",
    "StageInvocationRejected",
    "StageResult",
    "StageSettlementReport",
    # Stage errors
    "StageError",
    "StageErrorTypeDefinition",
    "StageErrorTypeDefinitionRegistry",
    # Stage results internals
    "StageFlowException",
    "StageFlowTransition",
    "StageStepInvocation",
    # Coordination
    "Association",
    "AssociationIdentity",
    "AssociationTarget",
    "AssociationTargetIdentity",
    "ComponentAssociationIdentity",
    "ComponentInstanceIdentity",
    "ComponentInvocationIdentity",
    "Dissociation",
    "InvocationBinding",
    "StepCompositionAssociationCoordination",
    "StepCompositionInternalComponentLifecycleCoordination",
    "RuntimeInstanceLifetime",
    "AssociationLifetime",
    "InvocationLifetime",
    "OperationLifetime",
    "ResourceCapabilityLifetime",
    "OutputAndEvidenceRetentionLifetime",
]
