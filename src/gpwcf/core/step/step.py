"""Step[TInput,TOutput] — the Step aggregate root and public boundary.

Implementation task: 02_Step
Related diagrams:
  class: 03_Diagrams_Codes_Files/02_Step.dot
  sequence: B_Sequencial_Diagram_Code/05_Step_Execution_Sequence.puml
  association: C_Association_Diagram_Code/02_Step_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/02_Architectural_Level_Dependency_Graph.dot

Contract basis:
  - Step_Contract.json (``pipeline.step.contract``)
  - Step_Composition_Contract.json (``pipeline.step-composition.contract``)
  - 04.00_Step_Callable.json (Wave-2 callable signature)
  - 05.00_Step_Execution_Result.json / 06.00_Optional_Result_Contributions.json
  - Step_Termination_Integration_Review.md

The Step is an independently composable, Stage-facing orchestration component
and the Aggregate Root boundary for its Step-owned composition. It exposes a
stable callable contract to its owning Stage (``execute`` receiving ONE typed
``StepInvocation``) while internally coordinating its Step Processing Units
and applicable supporting units through its private StepComposition.

execute template (fixed ordering):

1. Validate the proposed invocation envelope (type + Step identity scope);
   rejected invocations raise ``StepInvocationRejected`` — no fabricated
   result, no partial execution.
2. Admit the invocation at the StepAdmissionBoundary (linearizable; rejects a
   used identity or closed admission).
3. Open the invocation-scoped StepCompositionFlowResult.
4. ``_perform_invocation`` — the concrete Step's specialization — drives SPUs
   and supporting units through the composition and assembles the
   StepExecutionResult there. A thrown exception is recorded as flow evidence
   and propagates UNCHANGED; the invocation stays accepted-but-unsettled.
5. Identity-consistency check: the assembled result must carry this
   invocation's identity/correlation fields unchanged.
6. Settle: the flow result is sealed and the invocation marked complete in
   admission — only after the result was produced and verified.
7. Return the StepExecutionResult to the owning Stage.

The Stage invokes the Step ONLY through this public callable/lifecycle
boundary; the Step's composition topology and execution policy stay hidden.
Lifecycle (retention/retirement) is a SEPARATE public interaction
(:meth:`Step.request_lifecycle`, :meth:`Step.confirm_reuse_readiness`); its
outcomes are recorded distinctly from any StepExecutionResult.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Never

from gpwcf.core.identities import StageIdentity, StepIdentity
from gpwcf.core.step.composition import (
    StepComposition,
    StepCompositionFlowResult,
    StepSettlementReport,
)
from gpwcf.core.step.invocation import (
    StepCallable,
    StepInvocation,
    StepInvocationRejected,
)
from gpwcf.core.step.lifecycle import (
    StepAdmissionBoundary,
    StepLifecycle,
    StepLifecycleDisposition,
    StepLifecycleOutcome,
    StepLifecycleStatus,
)
from gpwcf.core.step.results import (
    StepExecutionResult,
)

__all__ = [
    "Step",
    "StepExecutionContractViolation",
]


class StepExecutionContractViolation(RuntimeError):
    """The concrete Step's specialization violated the execution contract.

    Raised when the assembled result does not carry the accepted invocation's
    identity fields unchanged, is not exactly a StepExecutionResult, or when
    settlement reports unreleased custody (accepted supporting results that
    were silently dropped). The invocation stays unsettled in either case.
    """


class Step[
    TInput, TOutput, TValidatorResult = Never, TErrorResult = Never, TErrorHandlerResult = Never
](StepCallable[TInput, TOutput, TValidatorResult, TErrorResult, TErrorHandlerResult]):
    """Aggregate Root of the Step-owned composition; Stage-facing boundary.

    Generic parameters select the concrete Step's result types; an unselected
    optional capability keeps its ``typing.Never`` default and its
    contribution slot is statically constrained to Absent.

    Subclasses implement :meth:`_perform_invocation` and coordinate their SPU
    and supporting-unit instances through ``self._composition`` (the
    composition is the sole association/custody authority for the
    supporting-pattern books — Validator/Observation units never assemble or
    influence the Step result on their own).
    """

    def __init__(self, step_identity: StepIdentity, owning_stage_identity: StageIdentity) -> None:
        if type(step_identity) is not StepIdentity:
            raise TypeError(
                f"step_identity must be StepIdentity, got {type(step_identity).__name__}"
            )
        if type(owning_stage_identity) is not StageIdentity:
            raise TypeError(
                "owning_stage_identity must be StageIdentity, got "
                f"{type(owning_stage_identity).__name__}"
            )
        self._step_identity = step_identity
        self._owning_stage_identity = owning_stage_identity
        self._admission = StepAdmissionBoundary(step_identity)
        self._composition = StepComposition(step_identity)
        self._lifecycle = StepLifecycle(step_identity, self._admission)

    # -- public read surface -------------------------------------------------

    @property
    def step_identity(self) -> StepIdentity:
        """The nominal identity of this Step instance."""
        return self._step_identity

    @property
    def owning_stage_identity(self) -> StageIdentity:
        """The nominal identity of the Stage owning this Step."""
        return self._owning_stage_identity

    @property
    def lifecycle_status(self) -> StepLifecycleStatus:
        """Current public lifecycle phase (idempotent re-read)."""
        return self._lifecycle.status

    # -- public callable boundary ---------------------------------------------

    def execute(
        self, invocation: StepInvocation[TInput]
    ) -> StepExecutionResult[TOutput, TValidatorResult, TErrorResult, TErrorHandlerResult]:
        """Execute ONE admitted Step invocation; return its aggregate result.

        Raises :class:`StepInvocationRejected` for a rejected invocation (no
        result fabricated) and propagates execution exceptions unchanged (the
        invocation then remains accepted-but-unsettled, so no lifecycle
        disposition can confirm over it).
        """
        self._validate_invocation_scope(invocation)
        self._admission.admit(invocation.step_invocation_identity)

        flow = self._composition.new_flow_result()
        try:
            result = self._perform_invocation(invocation, flow)
        except BaseException as exc:  # noqa: BLE001 — recorded as evidence, re-raised unchanged
            flow.record_exception(exc, phase="step_invocation")
            raise

        if type(result) is not StepExecutionResult:
            raise StepExecutionContractViolation(
                "_perform_invocation must return exactly StepExecutionResult, "
                f"got {type(result).__name__}"
            )
        self._check_result_identity_consistency(invocation, result)

        report = self._composition.settle(invocation, flow)
        if not report.complete:
            raise StepExecutionContractViolation(
                "settlement is incomplete: accepted custody results were "
                "neither assembled into the StepExecutionResult nor released "
                f"({report})"
            )
        self._admission.settle(invocation.step_invocation_identity)
        return result

    # -- public lifecycle boundary --------------------------------------------

    def request_lifecycle(
        self, disposition: StepLifecycleDisposition
    ) -> StepLifecycleOutcome:
        """Stage-requested disposition: retention for reuse or terminal retirement.

        Closes admission first, settles accepted work, and records the
        outcome distinctly (CONFIRMED / FAILED / INDETERMINATE). A confirmed
        retention keeps admission closed until
        :meth:`confirm_reuse_readiness` reopens it; a confirmed terminal
        retirement closes admission permanently.
        """
        return self._lifecycle.request(disposition, self._settlement_report)

    def confirm_reuse_readiness(self) -> None:
        """Explicitly confirm reuse readiness after a confirmed retention.

        Reopens execute admission. Retention never silently reopens
        admission, and a terminally retired Step can never reopen.
        """
        self._lifecycle.confirm_reuse_readiness()

    # -- specialization surface -------------------------------------------------

    @abstractmethod
    def _perform_invocation(
        self, invocation: StepInvocation[TInput], flow: StepCompositionFlowResult
    ) -> StepExecutionResult[TOutput, TValidatorResult, TErrorResult, TErrorHandlerResult]:
        """Perform this Step's assigned processing responsibility.

        The concrete specialization coordinates its SPU and supporting units
        through ``self._composition`` (``invoke_spu``,
        ``record_supporting_result``) and assembles the returned result via
        ``self._composition.assemble_step_result`` — which copies the
        invocation's identity fields unchanged. A thrown exception propagates
        unchanged; the boundary never converts it into a result.
        """
        raise NotImplementedError

    @property
    def _composition_for_subclasses(self) -> StepComposition:
        """The Step-owned composition (private-by-convention access surface)."""
        return self._composition

    # -- internals -----------------------------------------------------------

    def _validate_invocation_scope(self, invocation: object) -> None:
        if type(invocation) is not StepInvocation:
            raise StepInvocationRejected(
                "execute requires a StepInvocation envelope, got "
                f"{type(invocation).__name__}"
            )
        if invocation.step_identity != self._step_identity:
            raise StepInvocationRejected(
                f"invocation targets Step {invocation.step_identity.value!r}, "
                f"but this Step is {self._step_identity.value!r}; an invocation "
                "is never silently redirected to another Step instance"
            )
        if invocation.owning_stage_identity != self._owning_stage_identity:
            raise StepInvocationRejected(
                "invocation declares owning Stage "
                f"{invocation.owning_stage_identity.value!r}, but this Step is "
                f"owned by Stage {self._owning_stage_identity.value!r}"
            )

    def _check_result_identity_consistency(
        self,
        invocation: StepInvocation[TInput],
        result: StepExecutionResult[Any, Any, Any, Any],
    ) -> None:
        expected = {
            "step_identity": self._step_identity,
            "step_invocation_identity": invocation.step_invocation_identity,
            "owning_stage_identity": self._owning_stage_identity,
            "parent_stage_invocation_identity": invocation.parent_stage_invocation_identity,
            "pipeline_invocation_identity": invocation.pipeline_invocation_identity,
        }
        actual = {
            "step_identity": result.step_identity,
            "step_invocation_identity": result.step_invocation_identity,
            "owning_stage_identity": result.owning_stage_identity,
            "parent_stage_invocation_identity": result.parent_stage_invocation_identity,
            "pipeline_invocation_identity": result.pipeline_invocation_identity,
        }
        for field, expected_value in expected.items():
            if actual[field] != expected_value:
                raise StepExecutionContractViolation(
                    f"assembled result field {field!r} does not match the "
                    "accepted invocation; Step Composition copies identity "
                    "fields unchanged and never generates or replaces them"
                )

    def _settlement_report(
        self, drain_set: tuple[Any, ...]
    ) -> StepSettlementReport:
        """Wired as the lifecycle settlement_provider (Step-wide report)."""
        return self._composition.settle_overall(drain_set)
