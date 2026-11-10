"""GPWCF Prefect Integration Public API.

Curated re-export surface for Prefect integration domain contracts.
Importable only when the optional ``[prefect]`` extra is installed and
Prefect 3.9.2 is available. Core remains independent of Prefect — this
surface never leaks into Core Public API.

Implementation task: 10.C
"""

from gpwcf.integrations.prefect import (
    DomainNativeIdentityCorrelation,
    PREFECT_AVAILABLE,
    PrefectIntegrationPackage,
    PrefectNotAvailableError,
    RunDeploymentAsSubflowProfile,
    SPUTaskBinding,
    StageFlowDeploymentBinding,
    StageResultPersistenceRetrieval,
    StepSubflowBinding,
    SupportingPatternTaskBinding,
    TypedResultPreservation,
)

__all__ = [
    "PREFECT_AVAILABLE",
    "PrefectNotAvailableError",
    "PrefectIntegrationPackage",
    "StageFlowDeploymentBinding",
    "StepSubflowBinding",
    "SPUTaskBinding",
    "SupportingPatternTaskBinding",
    "DomainNativeIdentityCorrelation",
    "TypedResultPreservation",
    "StageResultPersistenceRetrieval",
    "RunDeploymentAsSubflowProfile",
]
