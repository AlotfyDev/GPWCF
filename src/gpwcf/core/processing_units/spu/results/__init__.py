"""SPUExecutionResult[TOutput] — structured result of one SPU invocation.

Implementation task: 01_SPU_Step_Processing_Unit
Related diagrams:
  class: 03_Diagrams_Codes_Files/01_SPU_Step_Processing_Unit.dot
  sequence: B_Sequencial_Diagram_Code/01_SPU_Execution_Sequence.puml
  dependency: D_Architectural_Dependency_Diagram_Code/02_Architectural_Level_Dependency_Graph.dot

Contract basis:
  - SPUExecutionResult_Contract.json (``pipeline.spu-execution-result.contract``)

Carries the processing artifact and SPU-invocation-scoped results/evidence of
one normally completed Step Processing Unit invocation. Produced by the
concrete SPU; consumed by the owning Step Composition.

Deliberately NOT represented here:

  - Not the aggregate result of the complete Step (``StepExecutionResult`` is a
    distinct Stage-facing contract assembled by Step Composition).
  - No universal SPU success boolean or status: absence of an element is NOT a
    success/failure status — the concrete Step defines applicability and
    interpretation.
  - No Stage/Pipeline status and no Step-level flow control.
  - No universal conversion from thrown exceptions: an exception that prevents
    ``execute`` from returning is not an ``SPUExecutionResult`` and no
    occurrence is synthesized for it.

Optionality: all three elements are independently optional; every element
actually produced must be preserved in the returned result (a later internal
failure must not discard an earlier result element — build incrementally with
``dataclasses.replace`` and return once, or return the produced subset).
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from gpwcf.core.processing_units.spu.errors import SPUError

__all__ = ["SPUExecutionResult"]


@dataclass(frozen=True)
class SPUExecutionResult[TOutput, TErrorOccurrenceContext = object]:
    """Immutable, invocation-scoped result of one SPU ``execute`` invocation.

    Type parameters:
        TOutput: The SPU-specific processing artifact type, when one is
            produced. Selected by the concrete SPU; not automatically the
            Step's final output.
        TErrorOccurrenceContext: The SPU-specialized context type carried by
            the ``SPUError`` occurrences made available in this result.

    Elements (independently optional; absent = ``None`` and absence is not a
    success/failure status):

        processing_artifact: The artifact produced by this SPU invocation,
            when present conforming exactly to the SPU's TOutput
            specialization.
        spu_error_occurrences: Original ``SPUError`` occurrences created by
            this SPU for errors arising within its own processing
            responsibility. Each occurrence preserves its occurrence identity
            and exact error-type-definition reference.
        validator_result: The validation result associated specifically with
            this SPU invocation, when the Step's design assigns such
            validation to this SPU scope. The concrete ``SPUValidatorResult``
            type arrives with the Validator Unit task (05); the field accepts
            any object at runtime and is deliberately annotated as a forward
            reference only — no runtime dependency is created.
    """

    processing_artifact: TOutput | None = None
    spu_error_occurrences: Collection[SPUError[TErrorOccurrenceContext]] | None = None
    validator_result: SPUValidatorResult | None = None

    def __post_init__(self) -> None:
        occurrences = self.spu_error_occurrences
        if occurrences is None:
            return
        if isinstance(occurrences, (str, bytes)) or not isinstance(
            occurrences, Collection
        ):
            raise TypeError(
                "spu_error_occurrences must be a Collection of SPUError or None"
            )
        for occurrence in occurrences:
            if not isinstance(occurrence, SPUError):
                raise TypeError(
                    "spu_error_occurrences must contain only SPUError instances, "
                    f"got {type(occurrence).__name__}"
                )
