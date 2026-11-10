"""Prefect Integration package — GPWCF domain contracts bound to native Prefect execution.

Implementation task: 09_Prefect_Integration

Prefect 3.9.2 is an opt-in dependency declared only under the optional [prefect]
extra. Core remains standard-library-only and importable without Prefect. This
package owns Prefect integration concerns separate from Core.

Dependency boundary: Core -> PrefectIntegration is FORBIDDEN. CorePublicAPI must
not leak Prefect types and must not depend on PrefectIntegration.
"""

from gpwcf.integrations.prefect.prefect_integration import (
    DomainNativeIdentityCorrelation,
    PrefectIntegrationPackage,
    PrefectNotAvailableError,
    PREFECT_AVAILABLE,
    SPUTaskBinding,
    StageFlowDeploymentBinding,
    StageResultPersistenceRetrieval,
    StepSubflowBinding,
    SupportingPatternTaskBinding,
    TypedResultPreservation,
    RunDeploymentAsSubflowProfile,
)

__all__ = [
    "PREFECT_AVAILABLE",
    "PrefectIntegrationPackage",
    "PrefectNotAvailableError",
    "StageFlowDeploymentBinding",
    "StepSubflowBinding",
    "SPUTaskBinding",
    "SupportingPatternTaskBinding",
    "DomainNativeIdentityCorrelation",
    "TypedResultPreservation",
    "StageResultPersistenceRetrieval",
    "RunDeploymentAsSubflowProfile",
]
