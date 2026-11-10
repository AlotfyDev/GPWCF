"""Stage results — StageFlowResult (evidence collector) and StageResult (envelope).

Implementation task: 03_Stage
Related diagrams:
  class: 03_Diagrams_Codes_Files/03_Stage.dot
  sequence: B_Sequencial_Diagram_Code/06_Stage_Execution_Sequence.puml
  association: C_Association_Diagram_Code/03_Stage_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/02_Architectural_Level_Dependency_Graph.dot

Contract basis:
  - 02.00_Stage_Result.json (gpwcf.architecture-closure.wave1.stage-result)
  - Stage_Level_Architecture.json

StageFlowResult is the Stage-level invocation-scoped evidence collector,
independent of any individual StepExecutionResult (F-06 gap closure).
StageResult is the Stage invocation result envelope returned to the caller.

Deliberately NOT represented here:

  - Not the result of an individual Step invocation
    (StepExecutionResult is an internal per-Step result consumed by Stage
    Composition; the two types are never interchangeable).
  - No universal success boolean, status, or severity.
  - No Prefect State or native runtime identifiers.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from gpwcf.core.identities import (
    PipelineInvocationIdentity,
    StageIdentity,
    StageInvocationIdentity,
)
from gpwcf.core.step import StepExecutionResult
from gpwcf.core.step.results import Absent, OptionalResultSlot, Present

__all__ = [
    "StageFlowException",
    "StageFlowResult",
    "StageFlowResultSealed",
    "StageFlowTransition",
    "StageResult",
    "StageStepInvocation",
]


@dataclass(frozen=True)
class StageFlowTransition:
    """Evidence of ONE Stage-level flow decision taken by Stage Composition."""

    description: str
    sequence: int


@dataclass(frozen=True)
class StageFlowException:
    """Evidence of ONE exception raised inside Stage-coordinated execution."""

    exception: BaseException
    phase: str
    sequence: int


@dataclass(frozen=True)
class StageStepInvocation:
    """Evidence of ONE coordinated Step invocation at Stage level."""

    step_identity: Any  # StepIdentity imported lazily to avoid circular import
    result: StepExecutionResult
    sequence: int


class StageFlowResultSealed(RuntimeError):
    """An append was attempted on a sealed (settled) Stage flow result."""


class StageFlowResult:
    """Append-only, invocation-scoped evidence collector for ONE Stage invocation.

    Independent of any individual StepExecutionResult — Step results are
    collected here as evidence but StageFlowResult is a distinct Stage-level
    artifact (F-06 gap closure). Every entry is retained; a later internal
    failure never discards an earlier entry.
    :meth:`seal` freezes the collector (idempotent); appends afterwards raise
    StageFlowResultSealed.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._step_invocations: list[StageStepInvocation] = []
        self._flow_transitions: list[StageFlowTransition] = []
        self._exceptions: list[StageFlowException] = []
        self._sealed = False
        self._next_sequence = 0

    # -- read surface ------------------------------------------------------

    @property
    def sealed(self) -> bool:
        """Whether this flow result is sealed (no further appends)."""
        with self._lock:
            return self._sealed

    @property
    def step_invocations(self) -> tuple[StageStepInvocation, ...]:
        with self._lock:
            return tuple(self._step_invocations)

    @property
    def flow_transitions(self) -> tuple[StageFlowTransition, ...]:
        with self._lock:
            return tuple(self._flow_transitions)

    @property
    def exceptions(self) -> tuple[StageFlowException, ...]:
        with self._lock:
            return tuple(self._exceptions)

    # -- append surface ----------------------------------------------------

    def record_step_invocation(
        self, step_identity: Any, result: StepExecutionResult
    ) -> StageStepInvocation:
        from gpwcf.core.identities import StepIdentity

        if type(step_identity) is not StepIdentity:
            raise TypeError(
                f"step_identity must be StepIdentity, got {type(step_identity).__name__}"
            )
        if type(result) is not StepExecutionResult:
            raise TypeError(
                f"result must be exactly StepExecutionResult, got {type(result).__name__}"
            )
        with self._lock:
            self._require_open()
            entry = StageStepInvocation(
                step_identity=step_identity,
                result=result,
                sequence=self._next_sequence,
            )
            self._next_sequence += 1
            self._step_invocations.append(entry)
            return entry

    def record_flow_transition(self, description: str) -> StageFlowTransition:
        if not isinstance(description, str) or description == "" or description.isspace():
            raise ValueError("description must be a non-empty, non-blank string")
        with self._lock:
            self._require_open()
            entry = StageFlowTransition(
                description=description, sequence=self._next_sequence
            )
            self._next_sequence += 1
            self._flow_transitions.append(entry)
            return entry

    def record_exception(self, exception: BaseException, phase: str) -> StageFlowException:
        if not isinstance(exception, BaseException):
            raise TypeError(
                f"exception must be a BaseException, got {type(exception).__name__}"
            )
        if not isinstance(phase, str) or phase == "" or phase.isspace():
            raise ValueError("phase must be a non-empty, non-blank string")
        with self._lock:
            self._require_open()
            entry = StageFlowException(
                exception=exception, phase=phase, sequence=self._next_sequence
            )
            self._next_sequence += 1
            self._exceptions.append(entry)
            return entry

    def seal(self) -> None:
        """Freeze this flow result; idempotent. Further appends are refused."""
        with self._lock:
            self._sealed = True

    # -- internals ---------------------------------------------------------

    def _require_open(self) -> None:
        if self._sealed:
            raise StageFlowResultSealed(
                "this Stage flow result is sealed; no further evidence changes "
                "are accepted"
            )


# --------------------------------------------------------------------------
# StageResult — the Stage invocation result envelope
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class StageResult[TStagePayload]:
    """Structured result of ONE accepted Stage invocation, returned to Stage.

    Generic parameter:

        TStagePayload: the Stage-level output artifact type exposed to the
            consuming workflow. It is NOT automatically the output type of
            any one Step.

    Elements:

        Identity/correlation (copied UNCHANGED from the accepted
        StageInvocation — Stage Composition never generates or replaces
        them):

        - stage_identity: the Stage instance that produced the result.
        - stage_invocation_identity: the accepted invocation — the primary
          correlation key for this result.
        - owning_pipeline_invocation_identity: consumer-owned correlation,
          propagated unchanged when supplied, absent (None) otherwise.
        - parent_stage_invocation_identity: optional parent Stage invocation
          identity, if any, for hierarchical Stage nesting.

        Result content:

        - processing_artifact: OptionalResultSlot[TStagePayload] — the
          Stage-level output derived from collected Step results per the
          concrete Stage's aggregation rules.
        - stage_outputs: OptionalResultSlot[Any] — Stage-specific outputs
          beyond the processing artifact.
        - stage_flow_result: StageFlowResult — the Stage's internal
          Step-execution flow evidence, independent of any individual
          StepExecutionResult (F-06 gap closure).
        - domain_outcome: OptionalResultSlot[Any] — the Stage's domain
          outcome, separately typed from outputs and flow result.

    Custody invariants: every Stage-required result that was actually
    produced and collected through Stage Composition is retained here —
    including results produced before a later internal failure; a value is
    included only as Present after production AND collection into Stage
    custody; no value is fabricated for an operation that did not produce
    one.
    """

    stage_identity: StageIdentity
    stage_invocation_identity: StageInvocationIdentity
    owning_pipeline_invocation_identity: PipelineInvocationIdentity | None
    parent_stage_invocation_identity: StageInvocationIdentity | None
    processing_artifact: OptionalResultSlot[TStagePayload]
    stage_outputs: OptionalResultSlot[Any]
    stage_flow_result: StageFlowResult
    domain_outcome: OptionalResultSlot[Any]

    def __post_init__(self) -> None:
        _require_exact("stage_identity", self.stage_identity, StageIdentity)
        _require_exact(
            "stage_invocation_identity",
            self.stage_invocation_identity,
            StageInvocationIdentity,
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
                StageInvocationIdentity,
            )
        if not isinstance(self.processing_artifact, (Absent, Present)):
            raise TypeError(
                "processing_artifact must be an OptionalResultSlot (Absent or "
                f"Present), got {type(self.processing_artifact).__name__}"
            )
        if not isinstance(self.stage_outputs, (Absent, Present)):
            raise TypeError(
                "stage_outputs must be an OptionalResultSlot (Absent or "
                f"Present), got {type(self.stage_outputs).__name__}"
            )
        if type(self.stage_flow_result) is not StageFlowResult:
            raise TypeError(
                "stage_flow_result must be StageFlowResult, got "
                f"{type(self.stage_flow_result).__name__}"
            )
        if not isinstance(self.domain_outcome, (Absent, Present)):
            raise TypeError(
                "domain_outcome must be an OptionalResultSlot (Absent or "
                f"Present), got {type(self.domain_outcome).__name__}"
            )


def _require_exact(name: str, value: object, expected: type) -> None:
    if type(value) is not expected:
        raise TypeError(f"{name} must be {expected.__name__}, got {type(value).__name__}")
