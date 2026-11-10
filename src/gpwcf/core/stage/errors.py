"""StageError types — Stage-level error type definitions, registry, and occurrences.

Implementation task: 03_Stage
Related diagrams:
  class: 03_Diagrams_Codes_Files/03_Stage.dot
  association: C_Association_Diagram_Code/03_Stage_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/02_Architectural_Level_Dependency_Graph.dot

Contract basis:
  - Stage_Level_Architecture.json
  - Common/Error_Model.json

StageErrorTypeDefinition[TErrorContent, THandlingAction] defines one Stage-level
error type. StageErrorTypeDefinitionRegistry is the Pipeline-assigned registry
for exactly one owning Stage — the Pipeline retains exclusive ownership.
StageError[TErrorOccurrenceContext] is a Stage error occurrence created when an
error arises within a Stage-owned responsibility.

Stage-level error types are DISTINCT programmatic types from SPU-level ones
— neither alias nor subtype. Stage errors are created by Stage-owned
components; SPU errors are created by SPUs.

Dependency boundary: this package imports only core.identities value types
and the standard library. It must NOT import concrete Supporting Pattern
packages, core.stage (no reverse dependency), or Prefect.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gpwcf.core.identities import StageIdentity

__all__ = [
    "StageError",
    "StageErrorTypeDefinition",
    "StageErrorTypeDefinitionRegistry",
]


@dataclass(frozen=True, repr=False)
class StageErrorTypeDefinition[TErrorContent, THandlingAction]:
    """One Stage-level error type definition.

    Defined and owned by the concrete Stage for its Stage-level error domain.
    Registered through the StageErrorTypeDefinitionRegistry instance assigned
    to the Stage by the Pipeline.

    Type parameters:

        TErrorContent: the error content/payload type carried by occurrences
            of this type.
        THandlingAction: the handling action type associated with this type.
    """

    error_type_identity: str
    error_content_type: type[TErrorContent]
    handling_action_type: type[THandlingAction]
    stage_identity: StageIdentity

    def __post_init__(self) -> None:
        if not isinstance(self.error_type_identity, str) or self.error_type_identity == "":
            raise ValueError("error_type_identity must be a non-empty string")
        if not isinstance(self.error_content_type, type):
            raise TypeError(
                f"error_content_type must be a type, got {type(self.error_content_type).__name__}"
            )
        if not isinstance(self.handling_action_type, type):
            raise TypeError(
                f"handling_action_type must be a type, got "
                f"{type(self.handling_action_type).__name__}"
            )
        if type(self.stage_identity) is not StageIdentity:
            raise TypeError(
                f"stage_identity must be StageIdentity, got "
                f"{type(self.stage_identity).__name__}"
            )

    def __repr__(self) -> str:
        return (
            f"StageErrorTypeDefinition({self.error_type_identity!r}, "
            f"{self.error_content_type.__name__}, "
            f"{self.handling_action_type.__name__})"
        )


class StageErrorTypeDefinitionRegistry:
    """Stage-level registry that stores and resolves StageErrorTypeDefinition
    instances for exactly one owning Stage.

    Exclusively owned and allocated by the Pipeline per Stage. The Stage
    registers its StageErrorTypeDefinition instances through this registry;
    the Pipeline retains exclusive ownership of that Registry Instance.
    """

    def __init__(self, stage_identity: StageIdentity) -> None:
        if type(stage_identity) is not StageIdentity:
            raise TypeError(
                f"stage_identity must be StageIdentity, got {type(stage_identity).__name__}"
            )
        self._stage_identity = stage_identity
        self._definitions: dict[str, StageErrorTypeDefinition[Any, Any]] = {}

    @property
    def stage_identity(self) -> StageIdentity:
        return self._stage_identity

    def register(self, definition: StageErrorTypeDefinition[Any, Any]) -> None:
        """Register one StageErrorTypeDefinition with this registry."""
        if not isinstance(definition, StageErrorTypeDefinition):
            raise TypeError(
                f"definition must be StageErrorTypeDefinition, got "
                f"{type(definition).__name__}"
            )
        if definition.stage_identity != self._stage_identity:
            raise ValueError(
                f"definition targets Stage {definition.stage_identity.value!r}, "
                f"but this registry belongs to Stage {self._stage_identity.value!r}"
            )
        self._definitions[definition.error_type_identity] = definition

    def resolve(self, error_type_identity: str) -> StageErrorTypeDefinition[Any, Any]:
        """Resolve one registered StageErrorTypeDefinition by identity."""
        if error_type_identity not in self._definitions:
            raise KeyError(
                f"no StageErrorTypeDefinition registered for identity "
                f"{error_type_identity!r} on Stage {self._stage_identity.value!r}"
            )
        return self._definitions[error_type_identity]

    @property
    def definitions(self) -> tuple[StageErrorTypeDefinition[Any, Any], ...]:
        return tuple(self._definitions.values())


@dataclass(frozen=True)
class StageError[TErrorOccurrenceContext]:
    """One Stage error occurrence.

    Created when an error arises within a Stage-owned responsibility. Preserves
    the producing Stage's identity, the error type definition reference, and
    the occurrence context. Distinct from SPUError (different nominal type,
    different scope).
    """

    error_type_definition: StageErrorTypeDefinition[Any, Any]
    occurrence_identity: str
    stage_identity: StageIdentity
    error_occurrence_context: TErrorOccurrenceContext

    def __post_init__(self) -> None:
        if not isinstance(self.error_type_definition, StageErrorTypeDefinition):
            raise TypeError(
                f"error_type_definition must be StageErrorTypeDefinition, got "
                f"{type(self.error_type_definition).__name__}"
            )
        if not isinstance(self.occurrence_identity, str) or self.occurrence_identity == "":
            raise ValueError("occurrence_identity must be a non-empty string")
        if type(self.stage_identity) is not StageIdentity:
            raise TypeError(
                f"stage_identity must be StageIdentity, got "
                f"{type(self.stage_identity).__name__}"
            )
