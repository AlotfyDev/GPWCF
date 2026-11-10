"""Stage — aggregate root, callable boundary, composition, results, errors.

Implementation task: 03_Stage

Public exports of the Stage package. Dependency direction: Stage -> Step ->
SPU; this package imports only core.identities, the Step public surface,
the standard library, and its own submodules. It must NOT import
core.processing_units.spu, supporting-pattern packages, core.diagnostics, or
Prefect.
"""

from gpwcf.core.stage.composition import (
    StageComposition,
    StageExecutionContext,
    StageFlowResult,
    StageInvocation,
    StageInvocationRejected,
    StageSettlementReport,
)
from gpwcf.core.stage.errors import (
    StageError,
    StageErrorTypeDefinition,
    StageErrorTypeDefinitionRegistry,
)
from gpwcf.core.stage.results import StageResult
from gpwcf.core.stage.stage import (
    Stage,
    StageCallableContract,
    StageExecutionContractViolation,
)

__all__ = [
    "Stage",
    "StageCallableContract",
    "StageComposition",
    "StageError",
    "StageErrorTypeDefinition",
    "StageErrorTypeDefinitionRegistry",
    "StageExecutionContext",
    "StageExecutionContractViolation",
    "StageFlowResult",
    "StageInvocation",
    "StageInvocationRejected",
    "StageResult",
    "StageSettlementReport",
]
