"""StepExecutionResult[TOutput] — the Stage-facing Step aggregate result.

Implementation task: 02_Step
Related diagrams:
  class: 03_Diagrams_Codes_Files/02_Step.dot
  sequence: B_Sequencial_Diagram_Code/05_Step_Execution_Sequence.puml
  association: C_Association_Diagram_Code/02_Step_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/02_Architectural_Level_Dependency_Graph.dot

Contract basis:
  - StepExecutionResult_Contract.json (``pipeline.step-execution-result.contract``)
  - 04.00_Step_Callable.json (result identity/correlation fields)
  - 05.00_Step_Execution_Result.json (typed envelope, OptionalResultSlot)
  - 06.00_Optional_Result_Contributions.json (typed closed contribution bundle,
    Absent | Present[T] discriminated presence model)

The structured result of ONE accepted Step invocation, returned to its owning
Stage. Produced by the concrete Step / Step Composition; consumed by Stage
Composition.

Deliberately NOT represented here:

  - Not the result of an individual SPU invocation (``SPUExecutionResult`` is
    an internal per-SPU result consumed by Step Composition; the two types are
    never interchangeable and Step never wraps or re-exports one as the other).
  - Not ``StepCompositionFlowResult`` (internal invocation-scoped evidence).
  - Not a lifecycle settlement outcome (retention/retirement results are a
    separate public Step interaction).
  - No universal success boolean, status, or severity: absence of an element is
    NOT a success/failure status — the concrete Step defines outcome semantics.
  - No Observation Unit records/events/telemetry: observation output stays
    outside the common result contract by default.
  - No Prefect State or native runtime identifiers: those are operational
    evidence, never the domain result.

Optional result presence: each slot is ``Absent | Present[T]`` — a dedicated
discriminated representation, NOT ``None``. ``Absent`` and ``Present(None)``
are distinct values, because a specialized domain result type may itself
permit ``None``. The ``OptionalResultContributions`` bundle is structurally
present in every StepExecutionResult while each of its three slots is
independently present/absent; the bundle's existence implies nothing about
which optional patterns were selected, attempted, or successful.

Dependency boundary: this package imports only ``core.identities`` value types
and the standard library. It must NOT import concrete optional Supporting
Pattern packages (Validator/Error Handling/Observation), the Generator Common
Error Model, or Prefect — optional pattern result types enter ONLY as generic
type arguments selected by the concrete Step; unselected capabilities use
``typing.Never`` and their slot is statically constrained to Absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Never

from gpwcf.core.identities import (
    PipelineInvocationIdentity,
    StageIdentity,
    StageInvocationIdentity,
    StepIdentity,
    StepInvocationIdentity,
)

__all__ = [
    "Absent",
    "Present",
    "OptionalResultSlot",
    "OptionalResultContributions",
    "StepExecutionResult",
]


# --------------------------------------------------------------------------
# OptionalResultSlot: discriminated presence model
# --------------------------------------------------------------------------


@dataclass(frozen=True, repr=False)
class Absent:
    """No value of this result category is included in this slot.

    Deliberately NOT ``None``: absence is a dedicated discriminated variant so
    that a specialized domain result type permitting ``None`` can still be
    carried as ``Present(None)`` without losing presence information.

    Invariants: absence is not a success/failure status; absence does not by
    itself prove that the corresponding capability was not selected or not
    executed; a slot specialized to ``typing.Never`` must always be Absent.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return "Absent"


#: The canonical Absent value (all Absent values compare equal regardless).
ABSENT = Absent()


@dataclass(frozen=True)
class Present[T]:
    """A value of the declared type was produced, accepted into Step custody,
    and is included in this slot.

    The wrapped value may itself be ``None`` when the concrete ``T`` contract
    permits ``None`` — ``Present(None)`` remains distinct from ``Absent``.
    Presence does not imply that the represented domain outcome is successful
    (a negative validation conclusion, for example, is a normally produced
    result).
    """

    value: T


type OptionalResultSlot[T] = Absent | Present[T]


# --------------------------------------------------------------------------
# OptionalResultContributions: the typed closed bundle
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class OptionalResultContributions[TValidatorResult, TErrorResult, TErrorHandlerResult]:
    """Closed, typed bundle of the three baseline optional Step-level results.

    Groups the Step-specialized ``StepValidatorResult``, ``ErrorResult``, and
    ``ErrorHandlerResult`` aggregates for transport through the Step result.
    It does NOT redefine their meaning: each slot retains the semantic
    ownership and schema defined by its specialized contract, and the concrete
    Step supplies the result types as generic parameters (``typing.Never``
    when the capability is not selected — that slot is then statically
    constrained to Absent).

    Independence rules:

    - Each slot is independently present or absent; the presence of one
      category never determines another.
    - ``error_result`` and ``error_handler_result`` remain distinct values
      with distinct semantics; neither contains, mutates, removes, or subsumes
      the other.
    - ``validator_result`` carries the Step-level aggregate, not an individual
      validator-unit result by default; a negative validation conclusion is a
      normally produced result, and a thrown validator invocation exception
      never fabricates a value here.
    - The bundle excludes SPUExecutionResult, StepCompositionFlowResult,
      Observation output, generic diagnostics, and Prefect State.
    - The baseline set is CLOSED: a new category requires an explicit reviewed
      contract revision — no extras dictionary, no string-keyed map, no
      runtime registry.
    """

    validator_result: OptionalResultSlot[TValidatorResult]
    error_result: OptionalResultSlot[TErrorResult]
    error_handler_result: OptionalResultSlot[TErrorHandlerResult]

    def __post_init__(self) -> None:
        for name in ("validator_result", "error_result", "error_handler_result"):
            slot = getattr(self, name)
            if not isinstance(slot, (Absent, Present)):
                raise TypeError(
                    f"{name} must be an OptionalResultSlot (Absent or Present), "
                    f"got {type(slot).__name__}; a raw domain value or None is "
                    "not a valid slot state"
                )

    @classmethod
    def all_absent(cls) -> "OptionalResultContributions[Never, Never, Never]":
        """A bundle with all three slots Absent (no contributions included)."""
        return cls(Absent(), Absent(), Absent())


# --------------------------------------------------------------------------
# StepExecutionResult: the Stage-facing envelope
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class StepExecutionResult[TOutput, TValidatorResult, TErrorResult, TErrorHandlerResult]:
    """Structured result of ONE accepted Step invocation, returned to Stage.

    Generic parameters (all selected by the concrete Step specialization):

        TOutput: the Step-level output artifact type exposed to Stage. It is
            NOT automatically the output type of any one SPU.
        TValidatorResult: the Step-level validation aggregate type (the
            StepValidatorResult specialization), or ``Never`` when the Step
            does not select a validator contribution.
        TErrorResult: the Step Error Model's ErrorResult specialization, or
            ``Never`` when the Step does not select a Step Error Model.
        TErrorHandlerResult: the ErrorHandlerResult aggregate type, or
            ``Never`` when the Step does not select error handling.

    Elements:

        Identity/correlation (copied UNCHANGED from the accepted StepInvocation
        — Step Composition never generates or replaces them):

        - ``step_identity``: the Step instance that produced the result.
        - ``step_invocation_identity``: the accepted invocation — the primary
          correlation key for this result.
        - ``owning_stage_identity``: the Stage owning the Step membership.
        - ``parent_stage_invocation_identity``: the Stage invocation whose
          Stage Composition invoked this Step.
        - ``pipeline_invocation_identity``: consumer-owned correlation,
          propagated unchanged when supplied, absent (None) otherwise.

        Result content:

        - ``processing_artifact``: ``OptionalResultSlot[TOutput]`` — the
          Step-level output derived from zero or more SPU artifacts and other
          internal results per the concrete Step's aggregation rules. Distinct
          from any individual SPU's processing artifact unless the Step
          explicitly forwards one.
        - ``optional_result_contributions``: the typed bundle above —
          structurally present on every result; its slots are independently
          present/absent.

    Custody invariants: every result required by the concrete Step's result
    contract that was actually produced and accepted into Step custody is
    retained here — including results produced before a later internal
    failure; a value is included only as ``Present`` after production AND
    acceptance into Step custody; no value is fabricated for an operation
    that did not produce one; a result already returned to Stage remains
    valid independently of later Step reuse or retirement.
    """

    step_identity: StepIdentity
    step_invocation_identity: StepInvocationIdentity
    owning_stage_identity: StageIdentity
    parent_stage_invocation_identity: StageInvocationIdentity
    pipeline_invocation_identity: PipelineInvocationIdentity | None
    processing_artifact: OptionalResultSlot[TOutput]
    optional_result_contributions: OptionalResultContributions[
        TValidatorResult, TErrorResult, TErrorHandlerResult
    ]

    def __post_init__(self) -> None:
        _require_exact("step_identity", self.step_identity, StepIdentity)
        _require_exact(
            "step_invocation_identity",
            self.step_invocation_identity,
            StepInvocationIdentity,
        )
        _require_exact("owning_stage_identity", self.owning_stage_identity, StageIdentity)
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
        if not isinstance(self.processing_artifact, (Absent, Present)):
            raise TypeError(
                "processing_artifact must be an OptionalResultSlot (Absent or "
                f"Present), got {type(self.processing_artifact).__name__}"
            )
        if type(self.optional_result_contributions) is not OptionalResultContributions:
            raise TypeError(
                "optional_result_contributions must be OptionalResultContributions, "
                f"got {type(self.optional_result_contributions).__name__}"
            )


def _require_exact(name: str, value: object, expected: type) -> None:
    if type(value) is not expected:
        raise TypeError(f"{name} must be {expected.__name__}, got {type(value).__name__}")
