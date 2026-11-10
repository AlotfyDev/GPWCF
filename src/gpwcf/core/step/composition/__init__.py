"""StepComposition — the Step-owned internal composition boundary.

Implementation task: 02_Step
Related diagrams:
  class: 03_Diagrams_Codes_Files/02_Step.dot
  sequence: B_Sequencial_Diagram_Code/05_Step_Execution_Sequence.puml
  association: C_Association_Diagram_Code/02_Step_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/02_Architectural_Level_Dependency_Graph.dot

Contract basis:
  - Step_Composition_Contract.json (``pipeline.step-composition.contract``)
  - 04.00_Step_Callable.json (result assembly copies invocation identity)
  - 05.00_Step_Execution_Result.json / 06.00_Optional_Result_Contributions.json

The internal orchestration boundary that coordinates ONE concrete Step's SPU
and applicable supporting-unit instances, retains invocation evidence, applies
Step-specific flow decisions, and supplies/assembles the information required
for ``StepExecutionResult``. Its topology and execution policy stay hidden
behind the Step aggregate root; the owning Stage never sees it.

Authority rules (task 02 finalizes the deferred 05/06 wiring):

- Step Composition is the SOLE authority for establishing, changing, and
  ending validator-unit and observation-unit associations (the
  ``ValidatorUnitAssociations`` / ``ObservationUnitAssociations`` books are
  the per-unit coordination surfaces it drives) and for recording the
  supporting-pattern lifecycle decisions. Supporting units never assemble or
  influence the Step result on their own.
- The SPU returns only its own ``SPUExecutionResult``; Step Composition
  consumes it and decides its contribution. ``invoke_spu`` propagates a thrown
  exception UNCHANGED — never converted into an occurrence or a result —
  while the invocation evidence gathered so far is retained.
- Custody: a supporting result is included in the assembled Step result only
  after production AND acceptance into Step custody
  (:meth:`StepComposition.record_supporting_result`). Acceptance creates a
  release obligation: every custody entry is either assembled into the
  ``StepExecutionResult`` or explicitly released with a recorded reason —
  nothing is silently dropped, and a value is never fabricated for an
  operation that did not produce one.
- ``assemble_step_result`` copies the identity/correlation fields UNCHANGED
  from the accepted ``StepInvocation``; Step Composition never generates or
  replaces them.
- Later failures never discard earlier results: the flow result is an
  append-only collector; sealing only freezes further appends.

Dependency boundary: this package imports only ``core.identities``, the SPU
surface (allowed Stage → Step → SPU direction), the Step result types, and
the standard library. It must NOT import supporting-pattern packages (the
concrete Step's composition drives them as pattern-scoped types selected by
the concrete Step), ``core.stage``, or Prefect.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from gpwcf.core.identities import SPUIdentity, StepIdentity
from gpwcf.core.processing_units.spu import SPUExecutionResult, StepProcessingUnit
from gpwcf.core.step.invocation import StepInvocation
from gpwcf.core.step.results import (
    ABSENT,
    Absent,
    OptionalResultContributions,
    OptionalResultSlot,
    Present,
    StepExecutionResult,
)

__all__ = [
    "SUPPORTING_RESULT_CATEGORIES",
    "ComponentInvocationEntry",
    "CustodyEntry",
    "ExceptionEntry",
    "FlowTransitionEntry",
    "StepComposition",
    "StepCompositionFlowResult",
    "StepCompositionFlowResultSealed",
    "StepSettlementReport",
]


#: The closed baseline set of supporting-result categories a custody entry
#: may carry. Each category maps to exactly one ``OptionalResultContributions``
#: slot; a new category requires an explicit reviewed contract revision.
SUPPORTING_RESULT_CATEGORIES = (
    "validator_result",
    "error_result",
    "error_handler_result",
)


class StepCompositionFlowResultSealed(RuntimeError):
    """An append was attempted on a sealed (settled) Step composition flow result."""


@dataclass(frozen=True)
class ComponentInvocationEntry:
    """Invocation evidence of ONE coordinated SPU invocation."""

    spu_identity: SPUIdentity
    result: SPUExecutionResult
    sequence: int


@dataclass(frozen=True)
class FlowTransitionEntry:
    """Evidence of ONE Step-specific flow decision taken by Step Composition."""

    description: str
    sequence: int


@dataclass(frozen=True)
class ExceptionEntry:
    """Evidence of ONE exception raised inside the coordinated execution.

    The original exception instance is retained for evidence; it is never
    converted into a result element and never swallowed here.
    """

    exception: BaseException
    phase: str
    sequence: int


@dataclass(frozen=True)
class CustodyEntry:
    """ONE supporting result accepted into Step Composition custody.

    ``category`` is one of ``SUPPORTING_RESULT_CATEGORIES``; ``source`` is the
    supporting unit's identity when the result came from a coordinated unit,
    or None for a Step-level composition decision. The entry never implies
    that the value is successful, failing, or included in the Step result —
    inclusion happens only at assembly.
    """

    category: str
    value: Any
    source: SPUIdentity | None
    sequence: int


class StepCompositionFlowResult:
    """Append-only, invocation-scoped evidence collector.

    One instance covers exactly ONE admitted Step invocation. Every entry is
    retained; a later internal failure never discards an earlier entry.
    :meth:`seal` freezes the collector (idempotent); appends afterwards raise
    :class:`StepCompositionFlowResultSealed`.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._component_invocations: list[ComponentInvocationEntry] = []
        self._flow_transitions: list[FlowTransitionEntry] = []
        self._exceptions: list[ExceptionEntry] = []
        self._custody: list[CustodyEntry] = []
        self._released_sequences: dict[int, str] = {}
        self._sealed = False
        self._next_sequence = 0

    # -- read surface ------------------------------------------------------

    @property
    def sealed(self) -> bool:
        """Whether this flow result is sealed (no further appends)."""
        with self._lock:
            return self._sealed

    @property
    def component_invocations(self) -> tuple[ComponentInvocationEntry, ...]:
        with self._lock:
            return tuple(self._component_invocations)

    @property
    def flow_transitions(self) -> tuple[FlowTransitionEntry, ...]:
        with self._lock:
            return tuple(self._flow_transitions)

    @property
    def exceptions(self) -> tuple[ExceptionEntry, ...]:
        with self._lock:
            return tuple(self._exceptions)

    @property
    def custody(self) -> tuple[CustodyEntry, ...]:
        """ALL custody entries ever accepted (released ones included)."""
        with self._lock:
            return tuple(self._custody)

    @property
    def outstanding_custody(self) -> tuple[CustodyEntry, ...]:
        """Custody entries accepted but neither assembled nor released."""
        with self._lock:
            return tuple(e for e in self._custody if e.sequence not in self._released_sequences)

    # -- append surface ----------------------------------------------------

    def record_component_invocation(
        self, spu_identity: SPUIdentity, result: SPUExecutionResult
    ) -> ComponentInvocationEntry:
        if type(spu_identity) is not SPUIdentity:
            raise TypeError(f"spu_identity must be SPUIdentity, got {type(spu_identity).__name__}")
        if type(result) is not SPUExecutionResult:
            raise TypeError(
                "result must be exactly SPUExecutionResult, got "
                f"{type(result).__name__}"
            )
        with self._lock:
            self._require_open()
            entry = ComponentInvocationEntry(
                spu_identity=spu_identity, result=result, sequence=self._next_sequence
            )
            self._next_sequence += 1
            self._component_invocations.append(entry)
            return entry

    def record_flow_transition(self, description: str) -> FlowTransitionEntry:
        if not isinstance(description, str) or description == "" or description.isspace():
            raise ValueError("description must be a non-empty, non-blank string")
        with self._lock:
            self._require_open()
            entry = FlowTransitionEntry(description=description, sequence=self._next_sequence)
            self._next_sequence += 1
            self._flow_transitions.append(entry)
            return entry

    def record_exception(self, exception: BaseException, phase: str) -> ExceptionEntry:
        if not isinstance(exception, BaseException):
            raise TypeError(
                f"exception must be a BaseException, got {type(exception).__name__}"
            )
        if not isinstance(phase, str) or phase == "" or phase.isspace():
            raise ValueError("phase must be a non-empty, non-blank string")
        with self._lock:
            self._require_open()
            entry = ExceptionEntry(exception=exception, phase=phase, sequence=self._next_sequence)
            self._next_sequence += 1
            self._exceptions.append(entry)
            return entry

    def take_into_custody(
        self, category: str, value: Any, *, source: SPUIdentity | None = None
    ) -> CustodyEntry:
        if category not in SUPPORTING_RESULT_CATEGORIES:
            raise ValueError(
                f"unknown supporting-result category {category!r}; the baseline "
                f"set is closed: {SUPPORTING_RESULT_CATEGORIES}"
            )
        if source is not None and type(source) is not SPUIdentity:
            raise TypeError(f"source must be SPUIdentity or None, got {type(source).__name__}")
        with self._lock:
            self._require_open()
            entry = CustodyEntry(
                category=category, value=value, source=source, sequence=self._next_sequence
            )
            self._next_sequence += 1
            self._custody.append(entry)
            return entry

    def release(self, entry: CustodyEntry, reason: str) -> None:
        """Explicitly release ONE outstanding custody entry with a reason.

        Releases the recorded obligation for an accepted value that will NOT
        be included in the assembled Step result. The custody entry itself is
        retained as evidence; a release is recorded as a flow transition.
        """
        if not isinstance(reason, str) or reason == "" or reason.isspace():
            raise ValueError("reason must be a non-empty, non-blank string")
        with self._lock:
            self._require_open()
            self._release_locked(entry, reason)

    def release_all(self, reason: str) -> None:
        """Release ALL outstanding custody entries with one recorded reason."""
        if not isinstance(reason, str) or reason == "" or reason.isspace():
            raise ValueError("reason must be a non-empty, non-blank string")
        with self._lock:
            self._require_open()
            for entry in tuple(self._custody):
                self._release_locked(entry, reason)

    def seal(self) -> None:
        """Freeze this flow result; idempotent. Further appends are refused."""
        with self._lock:
            self._sealed = True

    # -- internals ---------------------------------------------------------

    def _require_open(self) -> None:
        if self._sealed:
            raise StepCompositionFlowResultSealed(
                "this Step composition flow result is sealed; no further "
                "evidence or custody changes are accepted"
            )

    def _release_locked(self, entry: CustodyEntry, reason: str) -> None:
        if entry not in self._custody:
            raise KeyError("custody entry does not belong to this flow result")
        if entry.sequence in self._released_sequences:
            return
        self._released_sequences[entry.sequence] = reason
        self._flow_transitions.append(
            FlowTransitionEntry(
                description=(
                    f"custody released: category={entry.category!r} reason={reason!r}"
                ),
                sequence=self._next_sequence,
            )
        )
        self._next_sequence += 1


class StepSettlementReport:
    """Settlement report of one invocation-scoped or Step-wide settlement.

    ``complete`` is True only when every accepted invocation has settled AND
    every custody obligation has been released/assembled AND every flow
    result has been sealed. A settlement report is evidence — it is NOT a
    ``StepExecutionResult`` and NOT a lifecycle outcome.
    """

    def __init__(
        self,
        *,
        step_identity: StepIdentity,
        step_invocation_identity: Any,
        unsettled_invocations: tuple[Any, ...],
        outstanding_custody: int,
        unsealed_flow_results: int,
    ) -> None:
        self._step_identity = step_identity
        self._step_invocation_identity = step_invocation_identity
        self._unsettled_invocations = tuple(unsettled_invocations)
        self._outstanding_custody = outstanding_custody
        self._unsealed_flow_results = unsealed_flow_results

    @property
    def step_identity(self) -> StepIdentity:
        return self._step_identity

    @property
    def step_invocation_identity(self) -> Any:
        """The settled invocation's identity, or None for a Step-wide report."""
        return self._step_invocation_identity

    @property
    def unsettled_invocations(self) -> tuple[Any, ...]:
        """Accepted-but-unsettled invocation identities (Step-wide reports)."""
        return self._unsettled_invocations

    @property
    def outstanding_custody(self) -> int:
        return self._outstanding_custody

    @property
    def unsealed_flow_results(self) -> int:
        return self._unsealed_flow_results

    @property
    def complete(self) -> bool:
        return (
            not self._unsettled_invocations
            and self._outstanding_custody == 0
            and self._unsealed_flow_results == 0
        )

    def __repr__(self) -> str:
        return (
            "StepSettlementReport(step_invocation_identity="
            f"{getattr(self._step_invocation_identity, 'value', None)!r}, "
            f"unsettled={len(self._unsettled_invocations)}, "
            f"outstanding_custody={self._outstanding_custody}, "
            f"unsealed_flow_results={self._unsealed_flow_results}, "
            f"complete={self.complete})"
        )


class StepComposition:
    """The Step-owned internal composition boundary for ONE Step instance.

    Long-lived, owned by the Step aggregate as a private attribute. Per
    admitted invocation it opens a fresh :class:`StepCompositionFlowResult`;
    the concrete Step's specialization drives SPUs and supporting units
    through this composition and assembles the Step result here. The
    composition itself holds no validation/error/observation results — it
    retains evidence and custody, and it is the sole authority for the
    coordination decisions.
    """

    def __init__(self, step_identity: StepIdentity) -> None:
        if type(step_identity) is not StepIdentity:
            raise TypeError(f"step_identity must be StepIdentity, got {type(step_identity).__name__}")
        self._step_identity = step_identity
        self._lock = threading.Lock()
        self._flow_results: list[StepCompositionFlowResult] = []

    @property
    def step_identity(self) -> StepIdentity:
        """The identity of the Step instance this composition belongs to."""
        return self._step_identity

    # -- per-invocation surface --------------------------------------------

    def new_flow_result(self) -> StepCompositionFlowResult:
        """Open the invocation-scoped evidence collector for one invocation."""
        flow = StepCompositionFlowResult()
        with self._lock:
            self._flow_results.append(flow)
        return flow

    def invoke_spu(
        self,
        flow_result: StepCompositionFlowResult,
        spu_identity: SPUIdentity,
        spu: StepProcessingUnit,
        input: Any,
    ) -> SPUExecutionResult:
        """Coordinate ONE SPU invocation for the owning Step.

        Records the invocation evidence and returns the SPU's own
        ``SPUExecutionResult`` to the concrete Step for its aggregation
        decision. A thrown exception is recorded as evidence and propagated
        UNCHANGED — never converted into an occurrence or a result. The SPU
        result is consumed internally; it is never returned to Stage as if it
        were the StepExecutionResult.
        """
        if type(flow_result) is not StepCompositionFlowResult:
            raise TypeError(
                "flow_result must be StepCompositionFlowResult, got "
                f"{type(flow_result).__name__}"
            )
        if type(spu_identity) is not SPUIdentity:
            raise TypeError(f"spu_identity must be SPUIdentity, got {type(spu_identity).__name__}")
        if not isinstance(spu, StepProcessingUnit):
            raise TypeError(
                f"spu must be a StepProcessingUnit, got {type(spu).__name__}"
            )
        result: SPUExecutionResult
        try:
            result = spu.execute(input)
        except BaseException as exc:  # noqa: BLE001 — recorded, then re-raised unchanged
            flow_result.record_exception(exc, phase="component_invocation")
            raise
        if type(result) is not SPUExecutionResult:
            contract = TypeError(
                "the SPU must return exactly SPUExecutionResult, got "
                f"{type(result).__name__}"
            )
            flow_result.record_exception(contract, phase="component_result_contract")
            raise contract
        flow_result.record_component_invocation(spu_identity, result)
        return result

    def record_supporting_result(
        self,
        flow_result: StepCompositionFlowResult,
        category: str,
        value: Any,
        *,
        source: SPUIdentity | None = None,
    ) -> CustodyEntry:
        """Accept a produced supporting result into Step custody.

        Creates a release obligation: the value is either assembled into the
        StepExecutionResult or explicitly released. Acceptance does not
        decide success/failure and does not include the value in any result.
        """
        if type(flow_result) is not StepCompositionFlowResult:
            raise TypeError(
                "flow_result must be StepCompositionFlowResult, got "
                f"{type(flow_result).__name__}"
            )
        return flow_result.take_into_custody(category, value, source=source)

    def assemble_step_result(
        self,
        invocation: StepInvocation[Any],
        flow_result: StepCompositionFlowResult,
        *,
        processing_artifact: OptionalResultSlot[Any],
    ) -> StepExecutionResult[Any, Any, Any, Any]:
        """Assemble the Stage-facing ``StepExecutionResult`` for one invocation.

        Copies the identity/correlation fields UNCHANGED from the accepted
        invocation. Builds the typed contribution bundle from custody: each
        baseline category contributes its (single) outstanding accepted value
        as ``Present`` — the Step-level aggregate, not per-unit results — and
        stays ``Absent`` when nothing was accepted. All consumed custody
        obligations are released by the assembly; a value is included only
        after production AND acceptance into custody; nothing is fabricated.
        """
        if type(invocation) is not StepInvocation:
            raise TypeError(
                f"invocation must be StepInvocation, got {type(invocation).__name__}"
            )
        if type(flow_result) is not StepCompositionFlowResult:
            raise TypeError(
                "flow_result must be StepCompositionFlowResult, got "
                f"{type(flow_result).__name__}"
            )
        if not isinstance(processing_artifact, (Absent, Present)):
            raise TypeError(
                "processing_artifact must be an OptionalResultSlot (Absent or "
                f"Present), got {type(processing_artifact).__name__}"
            )

        outstanding = flow_result.outstanding_custody
        by_category: dict[str, CustodyEntry] = {}
        for entry in outstanding:
            if entry.category in by_category:
                raise ValueError(
                    f"multiple outstanding custody entries for category "
                    f"{entry.category!r}; the Step-level slot carries exactly "
                    "ONE aggregate — supersede or release the earlier value "
                    "before assembly"
                )
            by_category[entry.category] = entry

        contributions = OptionalResultContributions(
            validator_result=(
                Present(by_category["validator_result"].value)
                if "validator_result" in by_category
                else ABSENT
            ),
            error_result=(
                Present(by_category["error_result"].value) if "error_result" in by_category else ABSENT
            ),
            error_handler_result=(
                Present(by_category["error_handler_result"].value)
                if "error_handler_result" in by_category
                else ABSENT
            ),
        )
        flow_result.release_all(reason="assembled into StepExecutionResult")

        return StepExecutionResult(
            step_identity=invocation.step_identity,
            step_invocation_identity=invocation.step_invocation_identity,
            owning_stage_identity=invocation.owning_stage_identity,
            parent_stage_invocation_identity=invocation.parent_stage_invocation_identity,
            pipeline_invocation_identity=invocation.pipeline_invocation_identity,
            processing_artifact=processing_artifact,
            optional_result_contributions=contributions,
        )

    # -- settlement --------------------------------------------------------

    def settle(
        self, invocation: StepInvocation[Any], flow_result: StepCompositionFlowResult
    ) -> StepSettlementReport:
        """Invocation-scoped settlement: seal the evidence, report custody.

        Called by the Step aggregate AFTER its specialization produced the
        result and BEFORE the invocation is marked complete in admission. An
        incomplete report (outstanding custody) signals a concrete-Step
        contract violation; exceptions recorded during execution are evidence
        here but do NOT by themselves make settlement incomplete — a failed
        execution never reaches settlement because the Step re-raises.
        """
        if type(flow_result) is not StepCompositionFlowResult:
            raise TypeError(
                "flow_result must be StepCompositionFlowResult, got "
                f"{type(flow_result).__name__}"
            )
        flow_result.seal()
        outstanding = flow_result.outstanding_custody
        return StepSettlementReport(
            step_identity=self._step_identity,
            step_invocation_identity=invocation.step_invocation_identity,
            unsettled_invocations=(),
            outstanding_custody=len(outstanding),
            unsealed_flow_results=0,
        )

    def settle_overall(
        self, unsettled_invocations: tuple[Any, ...]
    ) -> StepSettlementReport:
        """Step-wide settlement report for the lifecycle request path.

        ``unsettled_invocations`` is the admission boundary's accepted-but-
        unsettled snapshot taken at closure; the composition contributes the
        unsealed flow results and outstanding custody of every invocation it
        ever opened.
        """
        with self._lock:
            flows = tuple(self._flow_results)
        outstanding = sum(len(flow.outstanding_custody) for flow in flows)
        unsealed = sum(1 for flow in flows if not flow.sealed)
        return StepSettlementReport(
            step_identity=self._step_identity,
            step_invocation_identity=None,
            unsettled_invocations=tuple(unsettled_invocations),
            outstanding_custody=outstanding,
            unsealed_flow_results=unsealed,
        )
