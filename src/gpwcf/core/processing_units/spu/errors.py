"""SPU error model family: definitions, per-SPU registry, and occurrences.

Implementation task: 01_SPU_Step_Processing_Unit
Related diagrams:
  class: 03_Diagrams_Codes_Files/01_SPU_Step_Processing_Unit.dot
  sequence: B_Sequencial_Diagram_Code/01_SPU_Execution_Sequence.puml
  dependency: D_Architectural_Dependency_Diagram_Code/02_Architectural_Level_Dependency_Graph.dot

Contract basis:
  - Step_Processing_Unit_SPU_Contract.json (``errorOwnershipAndProduction``)
  - Error_Model.json (SPU-level family: SPUErrorTypeDefinition, SPUError,
    SPUErrorTypeDefinitionRegistry)
  - Step_Error_Model_Contract.json (Step-level aggregation consumes occurrences)

Ownership rules (Error Model):

  - Each concrete SPU owns and defines its own ``SPUErrorTypeDefinition``
    instances and registers them through its assigned registry.
  - The Pipeline exclusively creates/owns every
    ``SPUErrorTypeDefinitionRegistry`` instance and allocates/assigns exactly
    one dedicated instance per participating SPU; a registry is never shared
    as the registry of another unit.
  - The SPU creates ``SPUError`` occurrences for errors arising within its own
    processing responsibility; each occurrence references exactly one
    registered definition through the assigned registry. The registry does not
    own or store occurrences.
  - A thrown exception that prevents ``execute`` from returning remains
    distinct from ``SPUError`` and is never automatically converted into an
    occurrence or a result element.

Registry rules (Error Model):

  - Definition identity is unique within its owning registry; a conflicting
    registration must not silently overwrite the existing definition.
  - Lookup is scoped to the registry instance: an Error Type Definition
    identity alone is not a globally sufficient lookup key, and a reference
    from one unit's registry must not be resolved against another unit's
    registry merely because identity values are equal. A definition reference
    therefore carries BOTH the registry instance identity and the definition
    identity.

Identity values are nominal value types reusing the ``core.identities``
pattern; no generation mechanism is provided (values are owner-assigned).
"""

from dataclasses import dataclass
from typing import Any

from gpwcf.core.identities import SPUIdentity, _IdentityValue

__all__ = [
    "SPUErrorOccurrenceIdentity",
    "SPUErrorTypeDefinitionIdentity",
    "SPUErrorTypeDefinitionRegistryIdentity",
    "SPUErrorTypeDefinitionReference",
    "SPUErrorTypeDefinition",
    "SPUErrorTypeDefinitionRegistry",
    "SPUError",
]


def _require_exact_type(field: str, value: object, expected: type) -> None:
    """Exact-type check: nominal identity roles must never collapse."""
    if type(value) is not expected:
        raise TypeError(
            f"{field} must be exactly {expected.__name__}, got {type(value).__name__}"
        )


class SPUErrorOccurrenceIdentity(_IdentityValue):
    """Identifies one error occurrence within the producing SPU's occurrence
    scope. Paired with the producer SPU identity when referenced at Step level
    (producerSPUIdentity + occurrenceIdentity per the Error Model).
    """

    __slots__ = ()


class SPUErrorTypeDefinitionIdentity(_IdentityValue):
    """Identifies an SPU error kind within the scope of its owning registry.

    Must be unique within its owning registry; it is NOT a globally sufficient
    lookup key on its own.
    """

    __slots__ = ()


class SPUErrorTypeDefinitionRegistryIdentity(_IdentityValue):
    """Identifies one dedicated ``SPUErrorTypeDefinitionRegistry`` instance.

    Registry instance identity and unit assignment are maintained by the
    owning Pipeline for the lifetime of the Pipeline.
    """

    __slots__ = ()


@dataclass(frozen=True)
class SPUErrorTypeDefinitionReference:
    """Reference to exactly one registered SPU error type definition.

    Carries BOTH the registry instance identity and the definition identity;
    a reference resolves only when both designate the same registered
    definition within that registry instance. Equal definition-identity
    values in a different unit's registry never resolve.
    """

    registry_identity: SPUErrorTypeDefinitionRegistryIdentity
    definition_identity: SPUErrorTypeDefinitionIdentity

    def __post_init__(self) -> None:
        _require_exact_type(
            "registry_identity", self.registry_identity,
            SPUErrorTypeDefinitionRegistryIdentity,
        )
        _require_exact_type(
            "definition_identity", self.definition_identity,
            SPUErrorTypeDefinitionIdentity,
        )


@dataclass(frozen=True)
class SPUErrorTypeDefinition[TErrorContent, THandlingAction]:
    """Definition of one SPU-specific error kind, owned by the concrete SPU.

    Fields:
        definition_identity: Identity of this error kind within its owning
            registry (unique there; conflicting registration is rejected).
        error_content: The SPU-specialized error content description
            (``TErrorContent``); semantics defined by the concrete SPU.
        handling_action: The SPU-specialized handling-action description
            (``THandlingAction``); semantics defined by the concrete SPU.

    A definition must be registered in the registry assigned to its owning
    SPU before an occurrence can reference it through that registry.
    """

    definition_identity: SPUErrorTypeDefinitionIdentity
    error_content: TErrorContent
    handling_action: THandlingAction

    def __post_init__(self) -> None:
        _require_exact_type(
            "definition_identity", self.definition_identity,
            SPUErrorTypeDefinitionIdentity,
        )


@dataclass(frozen=True)
class SPUError[TErrorOccurrenceContext = object]:
    """One error occurrence created by the concrete SPU for an error arising
    within its own processing responsibility.

    Fields:
        occurrence_identity: Identity of this occurrence within the producing
            SPU's occurrence scope.
        definition_reference: Reference resolving (within the SPU's assigned
            registry) to exactly one registered ``SPUErrorTypeDefinition``.
        context: The SPU-specialized occurrence context
            (``TErrorOccurrenceContext``); semantics defined by the concrete
            SPU. Not an exception, not an error result, and never synthesized
            from a thrown exception.

    Occurrences are made available to the owning Step Composition (carried on
    the SPU invocation's ``SPUExecutionResult``); the producing SPU identity
    is associated with each occurrence when incorporated into Step-level
    aggregation or references. Occurrences are immutable evidence values.
    """

    occurrence_identity: SPUErrorOccurrenceIdentity
    definition_reference: SPUErrorTypeDefinitionReference
    context: TErrorOccurrenceContext

    def __post_init__(self) -> None:
        _require_exact_type(
            "occurrence_identity", self.occurrence_identity,
            SPUErrorOccurrenceIdentity,
        )
        _require_exact_type(
            "definition_reference", self.definition_reference,
            SPUErrorTypeDefinitionReference,
        )


class SPUErrorTypeDefinitionRegistry[TErrorTypeDefinition = SPUErrorTypeDefinition[Any]]:
    """Per-SPU registry that stores and resolves SPU error type definitions.

    Exclusively created, owned, and managed by the Pipeline; one dedicated
    instance is assigned to exactly one owning SPU and is never shared as the
    registry of another unit. The SPU uses its assigned instance to register
    and resolve its own definitions — usage authority does not transfer
    ownership.

    Operations (Error Model): ``register`` (register a definition belonging to
    the owning unit), ``resolve`` (resolve a definition reference within this
    registry), ``definitions`` (expose registered definitions to authorized
    consumers). ``create_occurrence`` builds an occurrence whose definition
    reference is guaranteed to resolve within THIS registry.

    The registry does not own or store occurrences.
    """

    def __init__(
        self,
        identity: SPUErrorTypeDefinitionRegistryIdentity,
        owner_spu_identity: SPUIdentity,
    ) -> None:
        _require_exact_type("identity", identity, SPUErrorTypeDefinitionRegistryIdentity)
        _require_exact_type("owner_spu_identity", owner_spu_identity, SPUIdentity)
        object.__setattr__(self, "_identity", identity)
        object.__setattr__(self, "_owner_spu_identity", owner_spu_identity)
        object.__setattr__(self, "_definitions", {})

    @property
    def identity(self) -> SPUErrorTypeDefinitionRegistryIdentity:
        """Identity of this registry instance (Pipeline-maintained)."""
        return self._identity

    @property
    def owner_spu_identity(self) -> SPUIdentity:
        """The exactly-one owning SPU this dedicated instance is assigned to."""
        return self._owner_spu_identity

    def register(self, definition: TErrorTypeDefinition) -> None:
        """Register a definition belonging to the owning SPU.

        Accepts only ``SPUErrorTypeDefinition`` instances. A registration
        conflicting with an existing definition identity must not silently
        overwrite the existing definition and raises ``ValueError``.
        """
        if not isinstance(definition, SPUErrorTypeDefinition):
            raise TypeError(
                "registry accepts only SPUErrorTypeDefinition instances, got "
                f"{type(definition).__name__}"
            )
        identity = definition.definition_identity
        if identity in self._definitions:
            raise ValueError(
                f"definition identity {str(identity)!r} is already registered in "
                "this registry; identities must be unique within the owning "
                "registry and must not be silently overwritten"
            )
        self._definitions[identity] = definition

    def resolve(
        self, reference: SPUErrorTypeDefinitionReference
    ) -> SPUErrorTypeDefinition[Any]:
        """Resolve a definition reference to the registered definition.

        Scoped to this registry instance: a reference naming a different
        registry instance is rejected (``ValueError``) even if definition
        identity values are equal; an unregistered definition identity raises
        ``KeyError``.
        """
        if not isinstance(reference, SPUErrorTypeDefinitionReference):
            raise TypeError("reference must be an SPUErrorTypeDefinitionReference")
        if reference.registry_identity != self._identity:
            raise ValueError(
                "definition reference names a different registry instance; a "
                "reference from one unit's registry must not be resolved against "
                "another unit's registry"
            )
        try:
            return self._definitions[reference.definition_identity]
        except KeyError:
            raise KeyError(
                f"definition identity {str(reference.definition_identity)!r} is not "
                "registered in this registry"
            ) from None

    def create_occurrence(
        self,
        definition_identity: SPUErrorTypeDefinitionIdentity,
        occurrence_identity: SPUErrorOccurrenceIdentity,
        context: object,
    ) -> SPUError:
        """Create one occurrence referencing a definition registered HERE.

        Enforces the registration rule structurally: the occurrence is built
        only after the definition reference resolves within this registry
        (``KeyError`` otherwise). The registry does not retain the occurrence.
        """
        reference = SPUErrorTypeDefinitionReference(
            registry_identity=self._identity, definition_identity=definition_identity
        )
        self.resolve(reference)
        return SPUError(
            occurrence_identity=occurrence_identity,
            definition_reference=reference,
            context=context,
        )

    def definitions(self) -> tuple[SPUErrorTypeDefinition[Any], ...]:
        """Expose the definitions registered in this registry (read-only view)."""
        return tuple(self._definitions.values())

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return (
            f"{type(self).__name__}(identity={str(self._identity)!r}, "
            f"owner_spu_identity={str(self._owner_spu_identity)!r}, "
            f"definitions={len(self._definitions)})"
        )
