"""Stage[TInput,TOutput] — the Stage aggregate root and public boundary.

Implementation task: 03_Stage
Related diagrams:
  class: 03_Diagrams_Codes_Files/03_Stage.dot
  sequence: B_Sequencial_Diagram_Code/06_Stage_Execution_Sequence.puml
  association: C_Association_Diagram_Code/03_Stage_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/02_Architectural_Level_Dependency_Graph.dot

Contract basis:
  - 01.00_Stage_Callable.json (gpwcf.architecture-closure.wave1.stage-callable)
  - 02.00_Stage_Result.json (gpwcf.architecture-closure.wave1.stage-result)
  - Stage_Level_Architecture.json

The Stage is a bounded orchestration component and the Aggregate Root boundary
for its Stage-owned Step Composition. It exposes a stable callable contract to
its consuming workflow (StageCallableContract.execute receiving ONE typed
StageInvocation) while internally coordinating its Step members through its
private StageComposition.

execute template (fixed ordering):

1. Validate the proposed invocation envelope (type + Stage identity scope);
   rejected invocations raise StageInvocationRejected — no fabricated result,
   no partial execution.
2. Open the invocation-scoped StageFlowResult.
3. _perform_invocation — the concrete Stage's specialization — drives Steps
   through StageComposition and assembles the StageResult there. A thrown
   exception is recorded as flow evidence and propagates UNCHANGED.
4. Identity-consistency check: the assembled result must carry this
   invocation's identity/correlation fields unchanged.
5. Settle: the flow result is sealed and the invocation marked complete.
6. Return the StageResult to the consuming workflow.

The consuming workflow invokes the Stage ONLY through this public callable
boundary; the Stage's Step topology and execution policy stay hidden.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Never

from gpwcf.core.identities import StageIdentity
from gpwcf.core.step import Step, StepExecutionResult
from gpwcf.core.stage.composition import (
    StageComposition,
    StageFlowResult,
    StageInvocation,
    StageInvocationRejected,
    StageSettlementReport,
)
from gpwcf.core.stage.results import StageResult

__all__ = [
    "Stage",
    "StageCallableContract",
    "StageExecutionContractViolation",
]


class StageExecutionContractViolation(RuntimeError):
    """The concrete Stage's specialization violated the execution contract.

    Raised when the assembled result does not carry the accepted invocation's
    identity fields unchanged, is not exactly a StageResult, or when
    settlement is incomplete. The invocation stays unsettled in either case.
    """


class StageCallableContract[TInput, TOutput](ABC):
    """The Stage-facing callable contract of a Stage (Wave-1 signature).

    Generic parameters mirror the concrete Stage's result types. One accepted
    invocation is one execution attempt: execute validates and atomically
    admits the invocation, performs the Stage-owned internal composition
    through StageComposition, and returns the assembled StageResult — or
    raises StageInvocationRejected for a rejected invocation, or propagates
    an execution exception unchanged. It never returns a fabricated result.
    """

    @abstractmethod
    def execute(
        self, invocation: StageInvocation[TInput]
    ) -> StageResult[TOutput]:
        """Execute ONE admitted Stage invocation and return its aggregate result."""
        raise NotImplementedError


class Stage[TInput, TOutput](StageCallableContract[TInput, TOutput]):
    """Aggregate Root of the Stage-owned Step Composition; consuming-workflow
    boundary.

    Generic parameters select the concrete Stage's result types. Subclasses
    implement _perform_invocation and coordinate their Step members through
    self._composition (StageComposition is the sole authority for Step
    membership and invocation coordination).
    """

    def __init__(self, stage_identity: StageIdentity) -> None:
        if type(stage_identity) is not StageIdentity:
            raise TypeError(
                f"stage_identity must be StageIdentity, got {type(stage_identity).__name__}"
            )
        self._stage_identity = stage_identity
        self._composition = StageComposition(stage_identity)

    # -- public read surface -------------------------------------------------

    @property
    def stage_identity(self) -> StageIdentity:
        """The nominal identity of this Stage instance."""
        return self._stage_identity

    @property
    def step_membership(self) -> tuple[Step, ...]:
        """Current Stage member Steps (insertion order)."""
        return self._composition.step_membership

    @property
    def step_count(self) -> int:
        """Number of Steps currently in Stage membership."""
        return self._composition.step_count

    # -- public callable boundary ---------------------------------------------

    def execute(
        self, invocation: StageInvocation[TInput]
    ) -> StageResult[TOutput]:
        """Execute ONE admitted Stage invocation; return its aggregate result.

        Raises StageInvocationRejected for a rejected invocation (no result
        fabricated) and propagates execution exceptions unchanged.
        """
        self._validate_invocation_scope(invocation)

        flow = self._composition.new_flow_result()
        try:
            result = self._perform_invocation(invocation, flow)
        except BaseException as exc:  # noqa: BLE001 — recorded as evidence, re-raised unchanged
            flow.record_exception(exc, phase="stage_invocation")
            raise

        if type(result) is not StageResult:
            raise StageExecutionContractViolation(
                "_perform_invocation must return exactly StageResult, "
                f"got {type(result).__name__}"
            )
        self._check_result_identity_consistency(invocation, result)

        report = self._composition.settle(invocation, flow)
        if not report.complete:
            raise StageExecutionContractViolation(
                "settlement is incomplete: the Stage flow result was not "
                f"properly sealed ({report})"
            )
        return result

    # -- specialization surface -------------------------------------------------

    @abstractmethod
    def _perform_invocation(
        self, invocation: StageInvocation[TInput], flow: StageFlowResult
    ) -> StageResult[TOutput]:
        """Perform this Stage's assigned orchestration responsibility.

        The concrete specialization coordinates its Step members through
        ``self._composition`` (add_step, invoke_step) and assembles the
        returned result via ``self._composition``'s assembly helpers — which
        copy the invocation's identity fields unchanged. A thrown exception
        propagates unchanged; the boundary never converts it into a result.
        """
        raise NotImplementedError

    @property
    def _composition_for_subclasses(self) -> StageComposition:
        """The Stage-owned composition (private-by-convention access surface)."""
        return self._composition

    # -- internals -----------------------------------------------------------

    def _validate_invocation_scope(self, invocation: object) -> None:
        if type(invocation) is not StageInvocation:
            raise StageInvocationRejected(
                "execute requires a StageInvocation envelope, got "
                f"{type(invocation).__name__}"
            )
        if invocation.stage_identity != self._stage_identity:
            raise StageInvocationRejected(
                f"invocation targets Stage {invocation.stage_identity.value!r}, "
                f"but this Stage is {self._stage_identity.value!r}; an "
                "invocation is never silently redirected to another Stage "
                "instance"
            )

    def _check_result_identity_consistency(
        self,
        invocation: StageInvocation[TInput],
        result: StageResult[Any],
    ) -> None:
        expected = {
            "stage_identity": self._stage_identity,
            "stage_invocation_identity": invocation.stage_invocation_identity,
            "owning_pipeline_invocation_identity": invocation.owning_pipeline_invocation_identity,
            "parent_stage_invocation_identity": invocation.parent_stage_invocation_identity,
        }
        actual = {
            "stage_identity": result.stage_identity,
            "stage_invocation_identity": result.stage_invocation_identity,
            "owning_pipeline_invocation_identity": result.owning_pipeline_invocation_identity,
            "parent_stage_invocation_identity": result.parent_stage_invocation_identity,
        }
        for field, expected_value in expected.items():
            if actual[field] != expected_value:
                raise StageExecutionContractViolation(
                    f"assembled result field {field!r} does not match the "
                    "accepted invocation; Stage Composition copies identity "
                    "fields unchanged and never generates or replaces them"
                )


# ABC used for StageCallableContract base class; Never for generic defaults
ABC  # noqa: F841 — imported for StageCallableContract ABC base
Never  # noqa: F841 — imported for StageCallableContract generic defaults
