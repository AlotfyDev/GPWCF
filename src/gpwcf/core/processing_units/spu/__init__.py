"""SPU package: StepProcessingUnit[TInput,TOutput], SPUExecutionResult, SPU error family.

Implementation task: 01_SPU_Step_Processing_Unit
Related diagrams:
  class: 03_Diagrams_Codes_Files/01_SPU_Step_Processing_Unit.dot
  sequence: B_Sequencial_Diagram_Code/01_SPU_Execution_Sequence.puml
  dependency: D_Architectural_Dependency_Diagram_Code/02_Architectural_Level_Dependency_Graph.dot

The SPU performs one assigned processing responsibility inside its owning Step
and returns its own invocation-level result. It must NOT assemble
``StepExecutionResult``, decide Step flow transitions, or import Step/Stage/
supporting-pattern modules (reverse dependency forbidden).
"""

from gpwcf.core.processing_units.spu.errors import (
    SPUError,
    SPUErrorOccurrenceIdentity,
    SPUErrorTypeDefinition,
    SPUErrorTypeDefinitionIdentity,
    SPUErrorTypeDefinitionReference,
    SPUErrorTypeDefinitionRegistry,
    SPUErrorTypeDefinitionRegistryIdentity,
)
from gpwcf.core.processing_units.spu.results import SPUExecutionResult
from gpwcf.core.processing_units.spu.spu_unit import StepProcessingUnit

__all__ = [
    "StepProcessingUnit",
    "SPUExecutionResult",
    "SPUError",
    "SPUErrorOccurrenceIdentity",
    "SPUErrorTypeDefinition",
    "SPUErrorTypeDefinitionIdentity",
    "SPUErrorTypeDefinitionReference",
    "SPUErrorTypeDefinitionRegistry",
    "SPUErrorTypeDefinitionRegistryIdentity",
]
