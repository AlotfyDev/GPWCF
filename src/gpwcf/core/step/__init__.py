"""Step — aggregate root, callable boundary, composition, and lifecycle.

Implementation task: 02_Step

Public exports of the Step package. Dependency direction: Stage → Step → SPU;
this package imports only ``core.identities``, the SPU surface, and the
standard library. Concrete Step specializations opt into supporting patterns;
the pattern packages are never imported here.
"""

from gpwcf.core.step.composition import (
    SUPPORTING_RESULT_CATEGORIES,
    ComponentInvocationEntry,
    CustodyEntry,
    ExceptionEntry,
    FlowTransitionEntry,
    StepComposition,
    StepCompositionFlowResult,
    StepCompositionFlowResultSealed,
    StepSettlementReport,
)
from gpwcf.core.step.invocation import (
    StepCallable,
    StepExecutionContext,
    StepInvocation,
    StepInvocationRejected,
)
from gpwcf.core.step.lifecycle import (
    StepAdmissionBoundary,
    StepLifecycle,
    StepLifecycleDisposition,
    StepLifecycleError,
    StepLifecycleOutcome,
    StepLifecycleStatus,
)
from gpwcf.core.step.results import (
    ABSENT,
    Absent,
    OptionalResultContributions,
    OptionalResultSlot,
    Present,
    StepExecutionResult,
)
from gpwcf.core.step.step import (
    Step,
    StepExecutionContractViolation,
)

__all__ = [
    "ABSENT",
    "Absent",
    "ComponentInvocationEntry",
    "CustodyEntry",
    "ExceptionEntry",
    "FlowTransitionEntry",
    "OptionalResultContributions",
    "OptionalResultSlot",
    "Present",
    "SUPPORTING_RESULT_CATEGORIES",
    "Step",
    "StepAdmissionBoundary",
    "StepCallable",
    "StepComposition",
    "StepCompositionFlowResult",
    "StepCompositionFlowResultSealed",
    "StepExecutionContractViolation",
    "StepExecutionResult",
    "StepInvocation",
    "StepInvocationRejected",
    "StepLifecycle",
    "StepLifecycleDisposition",
    "StepLifecycleError",
    "StepLifecycleOutcome",
    "StepLifecycleStatus",
    "StepExecutionContext",
    "StepSettlementReport",
]
