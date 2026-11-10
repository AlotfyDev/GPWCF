"""StepInvocation[TInput] + StepCallable — the Step public callable boundary.

Implementation task: 02_Step
Related diagrams:
  class: 03_Diagrams_Codes_Files/02_Step.dot
  sequence: B_Sequencial_Diagram_Code/05_Step_Execution_Sequence.puml
  association: C_Association_Diagram_Code/02_Step_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/02_Architectural_Level_Dependency_Graph.dot

Contract basis:
  - 04.00_Step_Callable.json (``gpwcf.architecture-closure.wave2.step-callable``)
  - Step_Contract.json (``pipeline.step.contract``) — public callable boundary

The Stage invokes a Step ONLY through this boundary: ``StepCallable.execute``
receiving ONE typed ``StepInvocation`` envelope (Wave-2 revision — the
invocation is a typed value object, not bare ``input``). The envelope carries
the caller-supplied identity/correlation fields verbatim, the input artifact,
and the Step-scoped execution context; ``execute`` returns the typed
``StepExecutionResult`` envelope built by the Step-owned Step Composition.

Boundary rules:

- The candidate ``StepInvocation`` (including its ``step_invocation_identity``)
  is caller-supplied BEFORE the call; the Step public boundary validates it
  against the Step identity scope and atomically accepts or rejects it. A
  rejected invocation raises :class:`StepInvocationRejected` — NO fabricated
  ``StepExecutionResult`` is returned for a rejected invocation, and no
  partial execution happens.
- A distinct ``step_invocation_identity`` is required for each distinct
  admitted invocation; the same value is never silently reused for a second
  invocation (not even after the first has settled), unless an explicit
  idempotency/replay contract is layered on top by the concrete Step.
- ``StepExecutionContext`` is deliberately NOT a universal execution context:
  it is the Step-scoped, immutable base for the invocation-scoped context a
  concrete Step defines. The framework never reads fields from it and never
  threads hidden state through it.
- Exceptions raised by the Step's internal execution propagate unchanged;
  the callable boundary never converts them into a result.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Never

from gpwcf.core.identities import (
    PipelineInvocationIdentity,
    StageIdentity,
    StageInvocationIdentity,
    StepIdentity,
    StepInvocationIdentity,
)
from gpwcf.core.step.results import StepExecutionResult

__all__ = [
    "StepExecutionContext",
    "StepInvocation",
    "StepInvocationRejected",
    "StepCallable",
]


class StepInvocationRejected(RuntimeError):
    """The Step public boundary refused a proposed Step invocation.

    Raised for: a non-invocation argument, a ``step_identity`` /
    ``owning_stage_identity`` mismatch with the invoked Step instance, an
    invocation identity already used (ever — even after settlement), or
    admission closed by the Step's lifecycle. No ``StepExecutionResult`` is
    fabricated for a rejected invocation.
    """


@dataclass(frozen=True)
class StepExecutionContext:
    """Immutable, Step-scoped execution-context base value.

    A concrete Step may specialize it with its own subclass carrying its own
    invocation-scoped context fields. Deliberately NOT a universal
    ExecutionContext: the framework assigns it no meaning, reads nothing from
    it, and no framework machinery threads hidden state through it.
    """

    __slots__ = ()


@dataclass(frozen=True)
class StepInvocation[TInput]:
    """Typed envelope of ONE proposed Step invocation (caller-supplied).

    Identity/correlation fields are caller-owned and carried verbatim: the
    Step never generates, replaces, or rewrites them, and the assembled
    ``StepExecutionResult`` copies them unchanged from the accepted
    invocation.

    Fields:

        step_identity: nominal identity of the Step instance being invoked —
            must match the invoked Step instance.
        step_invocation_identity: nominal identity of THIS invocation — the
            caller-supplied candidate value; must be distinct per invocation.
        owning_stage_identity: nominal identity of the Stage owning the Step.
        parent_stage_invocation_identity: nominal identity of the Stage
            invocation whose Stage Composition performs this call.
        input: the Step-level input artifact (TInput).
        execution_context: the Step-scoped immutable context value.
        pipeline_invocation_identity: optional consumer-owned pipeline
            correlation identity; propagated unchanged into the result when
            supplied, and carried as None otherwise (absence as None is the
            documented representation for THIS correlation field only —
            result slots use the Absent/Present model).
    """

    step_identity: StepIdentity
    step_invocation_identity: StepInvocationIdentity
    owning_stage_identity: StageIdentity
    parent_stage_invocation_identity: StageInvocationIdentity
    input: TInput
    execution_context: StepExecutionContext
    pipeline_invocation_identity: PipelineInvocationIdentity | None = None

    def __post_init__(self) -> None:
        _require_exact("step_identity", self.step_identity, StepIdentity)
        _require_exact(
            "step_invocation_identity",
            self.step_invocation_identity,
            StepInvocationIdentity,
        )
        _require_exact(
            "owning_stage_identity", self.owning_stage_identity, StageIdentity
        )
        _require_exact(
            "parent_stage_invocation_identity",
            self.parent_stage_invocation_identity,
            StageInvocationIdentity,
        )
        if self.pipeline_invocation_identity is not None:
            _require_exact(
                "pipeline_invocation_identity",
                self.pipeline_invocation_identity,
                PipelineInvocationIdentity,
            )
        if not isinstance(self.execution_context, StepExecutionContext):
            raise TypeError(
                "execution_context must be a StepExecutionContext (or a "
                f"concrete specialization), got {type(self.execution_context).__name__}"
            )


class StepCallable[
    TInput, TOutput, TValidatorResult = Never, TErrorResult = Never, TErrorHandlerResult = Never
](ABC):
    """The Stage-facing callable contract of a Step (Wave-2 signature).

    Generic parameters mirror the concrete Step's selected result types; an
    unselected optional capability keeps its ``typing.Never`` default and its
    contribution slot is statically constrained to Absent.

    One accepted invocation is one execution attempt: ``execute`` validates
    and atomically admits the invocation, performs the Step-owned internal
    composition, and returns the assembled ``StepExecutionResult`` — or raises
    :class:`StepInvocationRejected` for a rejected invocation, or propagates
    an execution exception unchanged. It never returns a fabricated result
    and never returns an SPUExecutionResult as if it were the Step result.
    """

    @abstractmethod
    def execute(
        self, invocation: StepInvocation[TInput]
    ) -> StepExecutionResult[TOutput, TValidatorResult, TErrorResult, TErrorHandlerResult]:
        """Execute ONE admitted Step invocation and return its aggregate result."""
        raise NotImplementedError


def _require_exact(name: str, value: object, expected: type) -> None:
    if type(value) is not expected:
        raise TypeError(
            f"{name} must be exactly {expected.__name__}, got {type(value).__name__}"
        )
