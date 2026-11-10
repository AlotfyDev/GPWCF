"""StepProcessingUnit[TInput,TOutput] — the SPU generic callable contract.

Implementation task: 01_SPU_Step_Processing_Unit
Related diagrams:
  class: 03_Diagrams_Codes_Files/01_SPU_Step_Processing_Unit.dot
  sequence: B_Sequencial_Diagram_Code/01_SPU_Execution_Sequence.puml
  dependency: D_Architectural_Dependency_Diagram_Code/02_Architectural_Level_Dependency_Graph.dot

Contract basis:
  - Step_Processing_Unit_SPU_Contract.json (``pipeline.step-processing-unit.contract``)

The actual specialized processing unit that performs the processing
responsibility assigned to its owning Step — not a delegation-only wrapper and
not the Step Aggregate.

Boundary (enforced structurally and by architecture tests):

  - The SPU returns ONLY its own ``SPUExecutionResult``; it does NOT assemble
    ``StepExecutionResult`` and does NOT decide Step-level flow transitions.
    Step Composition consumes the result and decides its contribution.
  - ``SPUExecutionResult`` is the domain result of this invocation. Prefect
    State (or any native runtime state) is operational evidence and never
    substitutes for it; nothing here imports or depends on a runtime engine.
  - No reverse dependency: an SPU never imports Step, Stage, or supporting
    pattern modules. It cooperates with supporting units only where the
    concrete Step composition contract assigns that interaction.
  - Exceptions that prevent ``execute`` from returning are NOT converted into
    ``SPUError`` occurrences and are not an ``SPUExecutionResult`` (exception
    boundary); they remain distinct from returned structured results.

Generic contract: ``execute(input: TInput) -> SPUExecutionResult[TOutput]`` —
one invocation is one execution attempt. Each concrete SPU binds TInput and
TOutput independently; no common concrete input/output type is imposed, and no
universal execution-context parameter is introduced.

Error ownership: the concrete SPU defines and registers its own
``SPUErrorTypeDefinition`` instances through the registry instance assigned to
it by the Pipeline (this base receives that instance; the SPU never creates
its own registry) and creates ``SPUError`` occurrences for errors arising
within its own processing responsibility. No registration lifecycle is
mandated per ``execute`` invocation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from gpwcf.core.processing_units.spu.errors import SPUErrorTypeDefinitionRegistry
from gpwcf.core.processing_units.spu.results import SPUExecutionResult

__all__ = ["StepProcessingUnit"]


class StepProcessingUnit[TInput, TOutput](ABC):
    """Generic callable contract of one Step Processing Unit (SPU).

    Subclasses bind ``TInput``/``TOutput`` to their own Step responsibility
    and implement :meth:`execute` as the actual specialized processing.

    The constructor receives the ``SPUErrorTypeDefinitionRegistry`` instance
    assigned to this SPU by the Pipeline (exactly one dedicated instance per
    SPU; the Pipeline retains exclusive ownership). The SPU never creates its
    own registry — construction fails without an assigned instance.
    """

    def __init__(self, error_type_definitions: SPUErrorTypeDefinitionRegistry) -> None:
        if not isinstance(error_type_definitions, SPUErrorTypeDefinitionRegistry):
            raise TypeError(
                "error_type_definitions must be the SPUErrorTypeDefinitionRegistry "
                "instance assigned to this SPU by the Pipeline, got "
                f"{type(error_type_definitions).__name__}"
            )
        self._error_type_definitions = error_type_definitions

    @property
    def error_type_definitions(self) -> SPUErrorTypeDefinitionRegistry:
        """The Pipeline-assigned registry for this SPU's error type definitions."""
        return self._error_type_definitions

    @abstractmethod
    def execute(self, input: TInput) -> SPUExecutionResult[TOutput]:
        """Perform this SPU's assigned processing responsibility.

        One invocation represents one execution attempt. A normally completed
        invocation returns one ``SPUExecutionResult[TOutput]`` preserving every
        result element actually produced; a later internal failure must not
        discard an earlier produced element. Thrown exceptions are not
        converted into structured results or occurrences.
        """
        raise NotImplementedError
