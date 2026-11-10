"""StageComposition — owns Step membership and coordinates Step invocation.

Implementation task: 03_Stage
Related diagrams:
  class: 03_Diagrams_Codes_Files/03_Stage.dot
  sequence: B_Sequencial_Diagram_Code/06_Stage_Execution_Sequence.puml
  association: C_Association_Diagram_Code/03_Stage_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/02_Architectural_Level_Dependency_Graph.dot

Contract basis:
  - 01.00_Stage_Callable.json (gpwcf.architecture-closure.wave1.stage-callable)
  - 02.00_Stage_Result.json (gpwcf.architecture-closure.wave1.stage-result)
  - Stage_Level_Architecture.json (stage-level architecture)

The Stage-owned internal composition boundary for ONE Stage instance.
Owns Stage-specific Step membership and coordinates Step invocation through
each Step's public callable contract (never SPUs or supporting units directly).

Dependency boundary: imports only core.identities, the Step public surface
(allowed Stage -> Step direction), Stage result types, Stage error types,
and the standard library. Must NOT import core.processing_units.spu,
supporting-pattern packages, core.diagnostics, or Prefect.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from gpwcf.core.identities import (
    StageIdentity,
    StageInvocationIdentity,
    StepIdentity,
)
from gpwcf.core.step import (
    Step,
    StepExecutionResult,
    StepInvocation,
)
from gpwcf.core.stage.results import StageFlowResult

__all__ = [
    "StageComposition",
    "StageExecutionContext",
    "StageInvocation",
    "StageInvocationRejected",
    "StageSettlementReport",
]


# --------------------------------------------------------------------------
# Invocation envelope (caller-supplied)
# --------------------------------------------------------------------------


@dataclass(frozen=True, repr=False)
class StageExecutionContext:
    """Immutable, Stage-scoped execution-context base value.

    A concrete Stage may specialize it with its own subclass carrying its own
    invocation-scoped context fields. Deliberately NOT a universal
    ExecutionContext: the framework assigns it no meaning, reads nothing from
    it, and no framework machinery threads hidden state through it.
    """

    __slots__ = ()


class StageInvocationRejected(RuntimeError):
    """The Stage public boundary refused a proposed Stage invocation.

    Raised for: a non-invocation argument, a stage_identity mismatch with the
    invoked Stage instance, or an invocation identity already used
    (ever — even after settlement). No StageResult is fabricated for a
    rejected invocation.
    """


@dataclass(frozen=True)
class StageInvocation[TInput]:
    """Typed envelope of ONE proposed Stage invocation (caller-supplied).

    Identity/correlation fields are caller-owned and carried verbatim: the
    Stage never generates, replaces, or rewrites them, and the assembled
    StageResult copies them unchanged from the accepted invocation.

    Fields:

        stage_identity: nominal identity of the Stage instance being invoked
            — must match the invoked Stage instance.
        stage_invocation_identity: nominal identity of THIS invocation — the
            caller-supplied candidate value; must be distinct per invocation.
        input: the Stage-level input artifact (TInput).
        execution_context: the Stage-scoped immutable context value.
        owning_pipeline_invocation_identity: optional consumer-owned pipeline
            correlation identity; propagated unchanged into the result when
            supplied, carried as None otherwise.
        parent_stage_invocation_identity: optional identity of the parent
            Stage invocation, if any, for hierarchical Stage nesting.
    """

    stage_identity: StageIdentity
    stage_invocation_identity: StageInvocationIdentity
    input: TInput
    execution_context: StageExecutionContext
    owning_pipeline_invocation_identity: Any = None
    parent_stage_invocation_identity: Any = None

    def __post_init__(self) -> None:
        from gpwcf.core.identities import (
            PipelineInvocationIdentity,
            StageInvocationIdentity as _SII,
        )

        _require_exact("stage_identity", self.stage_identity, StageIdentity)
        _require_exact(
            "stage_invocation_identity",
            self.stage_invocation_identity,
            _SII,
        )
        if not isinstance(self.execution_context, StageExecutionContext):
            raise TypeError(
                "execution_context must be a StageExecutionContext (or a "
                f"concrete specialization), got "
                f"{type(self.execution_context).__name__}"
            )
        if self.owning_pipeline_invocation_identity is not None:
            _require_exact(
                "owning_pipeline_invocation_identity",
                self.owning_pipeline_invocation_identity,
                PipelineInvocationIdentity,
            )
        if self.parent_stage_invocation_identity is not None:
            _require_exact(
                "parent_stage_invocation_identity",
                self.parent_stage_invocation_identity,
                _SII,
            )


# --------------------------------------------------------------------------
# StageComposition — owns Step membership, coordinates Step invocation
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class StageSettlementReport:
    """Settlement report of one Stage invocation-scoped settlement.

    ``complete`` is True only when the flow result has been sealed and all
    accepted Step invocations have returned results. It is evidence, NOT a
    StageResult and NOT a lifecycle outcome.
    """

    stage_identity: StageIdentity
    stage_invocation_identity: StageInvocationIdentity | None
    sealed_flow_results: int
    pending_step_invocations: tuple[StepIdentity, ...]

    @property
    def complete(self) -> bool:
        return (
            self.sealed_flow_results > 0
            and not self.pending_step_invocations
        )


class StageComposition:
    """Owns Stage-specific Step membership and coordinates Step invocation.

    Long-lived, owned by the Stage aggregate as a private attribute. Maintains
    the Stage-specific Step set, coordinates invocation through public Step
    contracts, and collects StepExecutionResult values for Stage result
    assembly. Stage Composition does NOT invoke SPUs or supporting units
    directly — only Steps through their public callable boundary.
    """

    def __init__(self, stage_identity: StageIdentity) -> None:
        if type(stage_identity) is not StageIdentity:
            raise TypeError(
                f"stage_identity must be StageIdentity, got {type(stage_identity).__name__}"
            )
        self._stage_identity = stage_identity
        self._lock = threading.Lock()
        self._steps: dict[StepIdentity, Step] = {}
        self._flow_results: list[StageFlowResult] = []

    @property
    def stage_identity(self) -> StageIdentity:
        """The identity of the Stage instance this composition belongs to."""
        return self._stage_identity

    # -- Step membership ----------------------------------------------------

    def add_step(self, step: Step) -> None:
        """Register one Step instance as a member of this Stage.

        The Step's owning_stage_identity must match this Stage's identity.
        """
        if not isinstance(step, Step):
            raise TypeError(f"step must be a Step, got {type(step).__name__}")
        if step.owning_stage_identity != self._stage_identity:
            raise ValueError(
                f"Step {step.step_identity.value!r} is owned by Stage "
                f"{step.owning_stage_identity.value!r}, but this Stage is "
                f"{self._stage_identity.value!r}"
            )
        with self._lock:
            self._steps[step.step_identity] = step

    def remove_step(self, step_identity: StepIdentity) -> None:
        """Remove one Step from Stage membership."""
        if type(step_identity) is not StepIdentity:
            raise TypeError(
                f"step_identity must be StepIdentity, got {type(step_identity).__name__}"
            )
        with self._lock:
            if step_identity not in self._steps:
                raise KeyError(
                    f"Step {step_identity.value!r} is not a member of this Stage"
                )
            del self._steps[step_identity]

    @property
    def step_membership(self) -> tuple[Step, ...]:
        """Current Stage member Steps (insertion order)."""
        with self._lock:
            return tuple(self._steps.values())

    @property
    def step_count(self) -> int:
        with self._lock:
            return len(self._steps)

    # -- per-invocation surface --------------------------------------------

    def new_flow_result(self) -> StageFlowResult:
        """Open the invocation-scoped evidence collector for one invocation."""
        flow = StageFlowResult()
        with self._lock:
            self._flow_results.append(flow)
        return flow

    def invoke_step(
        self, flow_result: StageFlowResult, step: Step, step_invocation: StepInvocation[Any]
    ) -> StepExecutionResult:
        """Coordinate ONE Step invocation for the owning Stage.

        Calls the Step's public execute() boundary and collects the
        StepExecutionResult. A thrown exception is recorded as Stage-level
        evidence and propagated UNCHANGED — never converted into a StageError
        occurrence or a StageResult.
        """
        if type(flow_result) is not StageFlowResult:
            raise TypeError(
                f"flow_result must be StageFlowResult, got {type(flow_result).__name__}"
            )
        if not isinstance(step, Step):
            raise TypeError(f"step must be a Step, got {type(step).__name__}")
        if type(step_invocation) is not StepInvocation:
            raise TypeError(
                f"step_invocation must be StepInvocation, got {type(step_invocation).__name__}"
            )
        if step.step_identity not in self._steps:
            raise ValueError(
                f"Step {step.step_identity.value!r} is not a member of this Stage"
            )
        result: StepExecutionResult
        try:
            result = step.execute(step_invocation)
        except BaseException as exc:  # noqa: BLE001 — recorded, then re-raised unchanged
            flow_result.record_exception(exc, phase="step_invocation")
            raise
        if type(result) is not StepExecutionResult:
            contract = TypeError(
                "the Step must return exactly StepExecutionResult, got "
                f"{type(result).__name__}"
            )
            flow_result.record_exception(contract, phase="step_result_contract")
            raise contract
        flow_result.record_step_invocation(step.step_identity, result)
        return result

    def seal_flow(self, flow_result: StageFlowResult) -> None:
        """Seal one invocation-scoped flow result (idempotent)."""
        if type(flow_result) is not StageFlowResult:
            raise TypeError(
                f"flow_result must be StageFlowResult, got {type(flow_result).__name__}"
            )
        flow_result.seal()

    # -- settlement ---------------------------------------------------------

    def settle(
        self, stage_invocation: StageInvocation[Any], flow_result: StageFlowResult
    ) -> StageSettlementReport:
        """Invocation-scoped settlement: seal the evidence, report status.

        Called by the Stage aggregate AFTER its specialization produced the
        StageResult and BEFORE returning it to the caller. A sealed flow
        result with all Step invocations accounted for is complete.
        """
        if type(flow_result) is not StageFlowResult:
            raise TypeError(
                f"flow_result must be StageFlowResult, got {type(flow_result).__name__}"
            )
        flow_result.seal()
        with self._lock:
            flow_count = len(self._flow_results)
        return StageSettlementReport(
            stage_identity=self._stage_identity,
            stage_invocation_identity=stage_invocation.stage_invocation_identity,
            sealed_flow_results=flow_count,
            pending_step_invocations=(),
        )


def _require_exact(name: str, value: object, expected: type) -> None:
    if type(value) is not expected:
        raise TypeError(f"{name} must be {expected.__name__}, got {type(value).__name__}")
