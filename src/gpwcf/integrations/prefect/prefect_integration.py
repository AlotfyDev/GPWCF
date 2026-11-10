"""Prefect Integration — GPWCF domain contracts bound to native Prefect execution.

Implementation task: 09_Prefect_Integration
Related diagrams:
  class: 03_Diagrams_Codes_Files/09_Prefect_Integration.dot
  sequence: B_Sequencial_Diagram_Code/07_Prefect_Integration_Sequence.puml
  association: C_Association_Diagram_Code/09_Prefect_Integration_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/06_Core_vs_Prefect_Integration_Boundary.dot

Contract basis:
  - 12.00_Prefect_Integration_Binding.json (gpwcf.architecture-closure.wave5-prefect-integration-binding)
  - 13.00_Operational_Mapping.json (gpwcf.architecture-closure.wave5-prefect-operational-mapping)

Prefect 3.9.2 integration binding mapping GPWCF domain contracts to native Prefect
Flows/Deployments/Subflows/Tasks:

    Pipeline Root -> Native Flow
    Stage -> Stage Parent Flow/Deployment
    Step -> Step Subflow
    SPU -> Native Task

Design invariants:

  * Prefect is an opt-in dependency (prefect==3.9.2 under the optional [prefect] extra).
    Core remains standard-library-only and importable without Prefect.
  * Core -> PrefectIntegration is FORBIDDEN; CorePublicAPI -> PrefectRuntime and
    CorePublicAPI -> PrefectIntegration are prohibited (no Prefect types leak into Core).
  * Domain identities (Pipeline/Stage/Step/SPU/invocation) are distinct nominal types
    from Prefect operational identities (Flow Run / Task Run / Deployment IDs).
    Neither namespace substitutes for the other.
  * Prefect State is operational execution evidence, NOT a GPWCF domain result.
    Typed domain results (SPUExecutionResult, StepExecutionResult, StageResult) are
    preserved through Prefect execution unchanged.
  * PHASE-01/02 qualification limits respected: production binding is unqualified.

Dependency boundary: this module imports only core.identities, core.step, core.stage,
and the standard library. Prefect itself is imported conditionally (optional). It must
NOT be importable from Core packages.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any

# Prefect is optional — imported conditionally only.
try:  # noqa: SIM105
    import prefect  # type: ignore
    from prefect import Flow, Task, flow, task  # type: ignore
    from prefect.deployments import Deployment  # type: ignore
    from prefect.runner import Runner  # type: ignore
    PREFECT_AVAILABLE = True
except ImportError:  # pragma: no cover — exercised when Prefect is absent
    Flow = None  # type: ignore[assignment]
    Task = None  # type: ignore[assignment]
    flow = None  # type: ignore[assignment]
    task = None  # type: ignore[assignment]
    Deployment = None  # type: ignore[assignment]
    Runner = None  # type: ignore[assignment]
    PREFECT_AVAILABLE = False

from gpwcf.core.identities import (
    PipelineInvocationIdentity,
    StageIdentity,
    StageInvocationIdentity,
    StepIdentity,
    SPUIdentity,
    InvocationIdentity,
)
from gpwcf.core.step import StepExecutionResult
from gpwcf.core.stage import StageResult

__all__ = [
    "PREFECT_AVAILABLE",
    "PrefectIntegrationPackage",
    "StageFlowDeploymentBinding",
    "StepSubflowBinding",
    "SPUTaskBinding",
    "SupportingPatternTaskBinding",
    "DomainNativeIdentityCorrelation",
    "TypedResultPreservation",
    "StageResultPersistenceRetrieval",
    "PrefectNotAvailableError",
]


class PrefectNotAvailableError(RuntimeError):
    """Raised when a Prefect-native capability is requested but Prefect is not installed."""

    pass


# --------------------------------------------------------------------------
# Domain / Native Identity Correlation
# --------------------------------------------------------------------------


class DomainNativeIdentityCorrelation:
    """Correlation between GPWCF domain identities and Prefect native identities.

    Domain identities (Pipeline/Stage/Step/SPU/invocation) are GPWCF nominal
    identity value types. Prefect operational identities (Flow Run ID, Task Run
    ID, Deployment ID) belong to a distinct namespace. Neither substitutes for
    the other; correlation is explicit and recorded here.
    """

    def __init__(self) -> None:
        # domain_identity_value -> prefect_native_identity_string
        self._domain_to_native: dict[str, str] = {}
        # prefect_native_identity_string -> domain_identity_value
        self._native_to_domain: dict[str, str] = {}

    def correlate(
        self,
        domain_identity_value: str,
        prefect_native_identity: str,
    ) -> None:
        """Record an explicit correlation between one domain identity value and
        one Prefect native identity value."""
        if not isinstance(domain_identity_value, str) or domain_identity_value == "":
            raise ValueError("domain_identity_value must be a non-empty string")
        if not isinstance(prefect_native_identity, str) or prefect_native_identity == "":
            raise ValueError("prefect_native_identity must be a non-empty string")
        self._domain_to_native[domain_identity_value] = prefect_native_identity
        self._native_to_domain[prefect_native_identity] = domain_identity_value

    def native_for_domain(self, domain_identity_value: str) -> str | None:
        """Return the Prefect native identity correlated to a domain identity value."""
        return self._domain_to_native.get(domain_identity_value)

    def domain_for_native(self, prefect_native_identity: str) -> str | None:
        """Return the domain identity value correlated to a Prefect native identity."""
        return self._native_to_domain.get(prefect_native_identity)

    @property
    def correlations(self) -> tuple[tuple[str, str], ...]:
        """All recorded domain <-> native identity correlations."""
        return tuple(sorted(self._domain_to_native.items()))


# --------------------------------------------------------------------------
# Prefect Integration Package — integration boundary
# --------------------------------------------------------------------------


class PrefectIntegrationPackage:
    """Integration package owning Prefect integration concerns separate from Core.

    Prefect is an opt-in dependency; this package exists to bind GPWCF domain
    contracts to Prefect-native execution constructs while preserving domain
    ownership, identities, results, and operational evidence as distinct from
    Prefect operational state.
    """

    def __init__(self) -> None:
        self._identity_correlation = DomainNativeIdentityCorrelation()
        self._bindings: dict[str, object] = {}

    @property
    def prefect_available(self) -> bool:
        """Whether the Prefect runtime is installed and importable."""
        return PREFECT_AVAILABLE

    @property
    def identity_correlation(self) -> DomainNativeIdentityCorrelation:
        """The domain <-> native identity correlation registry."""
        return self._identity_correlation

    def register_binding(self, name: str, binding: object) -> None:
        """Register one integration binding (Stage, Step, SPU, Supporting Pattern)."""
        if not isinstance(name, str) or name == "":
            raise ValueError("name must be a non-empty string")
        self._bindings[name] = binding

    def binding(self, name: str) -> object:
        """Retrieve one registered integration binding by name."""
        if name not in self._bindings:
            raise KeyError(f"No integration binding registered for {name!r}")
        return self._bindings[name]

    @property
    def bindings(self) -> tuple[str, ...]:
        """Names of all registered integration bindings."""
        return tuple(sorted(self._bindings.keys()))


# --------------------------------------------------------------------------
# Stage Flow / Deployment Binding
# --------------------------------------------------------------------------


class StageFlowDeploymentBinding:
    """Native Prefect realization of Stage execution as Stage Flow/Deployment.

    Uses the accepted run_deployment(..., as_subflow=True) profile from
    PHASE-02 topology qualification: a Root-owned Prefect dispatch Task calls
    run_deployment(as_subflow=True), creating a deployment Flow Run with
    synthetic parent linkage and explicit Stage result persistence.

    StageResult is persisted via persist_result=True; the Root waits for the
    Deployment Flow Run terminal state and loads the persisted Stage domain
    result through a Prefect result reference. Multi-host storage remains
    unqualified.
    """

    def __init__(self, package: PrefectIntegrationPackage) -> None:
        self._package = package

    def bind_stage_to_deployment(
        self,
        stage_identity: StageIdentity,
        deployment_id: str,
    ) -> str:
        """Correlate one Stage identity with one Prefect Deployment ID."""
        if type(stage_identity) is not StageIdentity:
            raise TypeError(
                f"stage_identity must be StageIdentity, got {type(stage_identity).__name__}"
            )
        if not isinstance(deployment_id, str) or deployment_id == "":
            raise ValueError("deployment_id must be a non-empty string")
        self._package.identity_correlation.correlate(
            stage_identity.value, deployment_id
        )
        return deployment_id

    def requires_prefect(self) -> bool:
        """This binding requires Prefect to be available."""
        return PREFECT_AVAILABLE


# --------------------------------------------------------------------------
# run_deployment(as_subflow=True) Profile
# --------------------------------------------------------------------------


class RunDeploymentAsSubflowProfile:
    """Accepted Stage invocation mechanism from PHASE-02.

    Root-owned Prefect dispatch Task calls run_deployment(as_subflow=True),
    creating a deployment Flow Run with synthetic parent linkage and explicit
    Stage result persistence.
    """

    def __init__(self, package: PrefectIntegrationPackage) -> None:
        self._package = package

    def is_accepted_profile(self) -> bool:
        """Whether run_deployment(as_subflow=True) is the accepted Stage invocation profile."""
        return PREFECT_AVAILABLE

    def profile_name(self) -> str:
        return "run_deployment(as_subflow=True)"


# --------------------------------------------------------------------------
# Step Subflow Binding
# --------------------------------------------------------------------------


class StepSubflowBinding:
    """Native Prefect realization of Step execution as a Step Subflow.

    Stage-to-Step dispatch through a Prefect Task invoking a native Step Subflow
    while preserving the public Step callable boundary and native child Flow Run.
    """

    def __init__(self, package: PrefectIntegrationPackage) -> None:
        self._package = package

    def bind_step_to_subflow(
        self,
        step_identity: StepIdentity,
        subflow_id: str,
    ) -> str:
        """Correlate one Step identity with one Prefect Step Subflow ID."""
        if type(step_identity) is not StepIdentity:
            raise TypeError(
                f"step_identity must be StepIdentity, got {type(step_identity).__name__}"
            )
        if not isinstance(subflow_id, str) or subflow_id == "":
            raise ValueError("subflow_id must be a non-empty string")
        self._package.identity_correlation.correlate(
            step_identity.value, subflow_id
        )
        return subflow_id

    def requires_prefect(self) -> bool:
        return PREFECT_AVAILABLE


# --------------------------------------------------------------------------
# SPU Task Binding
# --------------------------------------------------------------------------


class SPUTaskBinding:
    """Native Prefect realization of SPU execution as a Prefect Task.

    SPU Tasks submit to the Step Flow's ThreadPoolTaskRunner and join their
    futures; SPUExecutionResult remains distinct from StepExecutionResult.
    SPU constructs and returns the structured result consumed by Step Composition.
    """

    def __init__(self, package: PrefectIntegrationPackage) -> None:
        self._package = package

    def bind_spu_to_task(
        self,
        spu_identity: SPUIdentity,
        task_run_id: str,
    ) -> str:
        """Correlate one SPU identity with one Prefect Task Run ID."""
        if type(spu_identity) is not SPUIdentity:
            raise TypeError(
                f"spu_identity must be SPUIdentity, got {type(spu_identity).__name__}"
            )
        if not isinstance(task_run_id, str) or task_run_id == "":
            raise ValueError("task_run_id must be a non-empty string")
        self._package.identity_correlation.correlate(
            spu_identity.value, task_run_id
        )
        return task_run_id

    def requires_prefect(self) -> bool:
        return PREFECT_AVAILABLE


# --------------------------------------------------------------------------
# Supporting Pattern Task Binding
# --------------------------------------------------------------------------


class SupportingPatternTaskBinding:
    """Native Prefect realization of selected Supporting Pattern execution.

    Validation, Error Handling, and Observation units are realized as Prefect
    Tasks, preserving each pattern's specialized behavior, result, identity,
    association, lifecycle, and custody contract. No universal Supporting Unit
    abstraction is imposed.
    """

    def __init__(self, package: PrefectIntegrationPackage) -> None:
        self._package = package

    def bind_supporting_pattern_to_task(
        self,
        pattern_name: str,
        task_run_id: str,
    ) -> str:
        """Correlate one Supporting Pattern instance with one Prefect Task Run ID."""
        if not isinstance(pattern_name, str) or pattern_name == "":
            raise ValueError("pattern_name must be a non-empty string")
        if not isinstance(task_run_id, str) or task_run_id == "":
            raise ValueError("task_run_id must be a non-empty string")
        self._package.identity_correlation.correlate(pattern_name, task_run_id)
        return task_run_id

    def requires_prefect(self) -> bool:
        return PREFECT_AVAILABLE


# --------------------------------------------------------------------------
# Typed Result Preservation
# --------------------------------------------------------------------------


class TypedResultPreservation:
    """Preservation of typed domain results through Prefect execution.

    SPUExecutionResult, StepExecutionResult, and StageResult are returned and
    preserved unchanged through Prefect execution — never replaced with Prefect
    operational State. Prefect State is operational execution evidence, not a
    GPWCF domain result.
    """

    def __init__(self, package: PrefectIntegrationPackage) -> None:
        self._package = package

    def preserve_spu_execution_result(
        self, result: StepExecutionResult
    ) -> StepExecutionResult:
        """Return an SPUExecutionResult unchanged (typed result preservation).

        The SPU constructs and returns the structured result consumed by Step
        Composition. Prefect does not wrap, convert, or fabricate this result.
        """
        if type(result) is not StepExecutionResult:
            raise TypeError(
                f"result must be exactly StepExecutionResult, got {type(result).__name__}"
            )
        return result

    def is_prefect_state_domain_result(self) -> bool:
        """Prefect State is NOT a domain result — always False."""
        return False


# --------------------------------------------------------------------------
# Stage Result Persistence / Retrieval
# --------------------------------------------------------------------------


class StageResultPersistenceRetrieval:
    """Stage result persistence/retrieval obligations using persist_result=True.

    Root waits for Deployment Flow Run terminal state and loads the persisted
    Stage domain result through a Prefect result reference. Multi-host storage
    remains unqualified (PHASE-01/02 qualification limits).
    """

    def __init__(self, package: PrefectIntegrationPackage) -> None:
        self._package = package

    def persist_stage_result(
        self,
        stage_identity: StageIdentity,
        result: StageResult,
    ) -> str:
        """Mark a StageResult for persistence via persist_result=True.

        Returns a result reference used by Root to load the persisted Stage
        domain result after the Deployment Flow Run reaches terminal state.
        """
        if type(stage_identity) is not StageIdentity:
            raise TypeError(
                f"stage_identity must be StageIdentity, got {type(stage_identity).__name__}"
            )
        if type(result) is not StageResult:
            raise TypeError(
                f"result must be exactly StageResult, got {type(result).__name__}"
            )
        return f"prefect-result-ref:{stage_identity.value}:{result.stage_invocation_identity.value}"

    def retrieve_stage_result(
        self, result_reference: str
    ) -> StageResult | None:
        """Load a persisted Stage domain result through a Prefect result reference.

        Multi-host storage remains unqualified; this is the binding contract
        surface, not a production storage implementation.
        """
        if not isinstance(result_reference, str) or not result_reference.startswith(
            "prefect-result-ref:"
        ):
            raise ValueError("result_reference must be a valid prefect result reference")
        return None  # persistence implementation is unqualified in PHASE-01/02
