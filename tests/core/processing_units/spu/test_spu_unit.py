"""Contract tests for the SPU / Step Processing Unit (task 01_SPU_Step_Processing_Unit).

Covers:
  - execute(input: TInput) -> SPUExecutionResult[TOutput] success path with a
    concrete SPU performing actual (non-delegation) processing
  - SPUExecutionResult elements independently optional; absence is not status
  - Preservation invariant: earlier produced elements survive later failures
  - SPU error family: definitions registered through the Pipeline-assigned
    registry; occurrences reference exactly one registered definition
  - Registry scoping: one owning SPU, no silent overwrite, no cross-registry
    resolution on equal identity values, no occurrence storage
  - Exception boundary: exceptions are not converted into SPUError/results
  - SPUExecutionResult distinct from StepExecutionResult (placeholder-tolerant)
"""

import dataclasses

import pytest

from gpwcf.core.identities import SPUIdentity
from gpwcf.core.processing_units.spu import (
    SPUError,
    SPUErrorOccurrenceIdentity,
    SPUErrorTypeDefinition,
    SPUErrorTypeDefinitionIdentity,
    SPUErrorTypeDefinitionReference,
    SPUErrorTypeDefinitionRegistry,
    SPUErrorTypeDefinitionRegistryIdentity,
    SPUExecutionResult,
    StepProcessingUnit,
)

REGISTRY_IDENTITY = SPUErrorTypeDefinitionRegistryIdentity("registry-1")
SPU_IDENTITY = SPUIdentity("spu-1")
REJECTED_INPUT_DEFINITION = SPUErrorTypeDefinitionIdentity("rejected-input")


def a_registry() -> SPUErrorTypeDefinitionRegistry:
    return SPUErrorTypeDefinitionRegistry(REGISTRY_IDENTITY, SPU_IDENTITY)


def a_definition() -> SPUErrorTypeDefinition[str, str]:
    return SPUErrorTypeDefinition(
        definition_identity=REJECTED_INPUT_DEFINITION,
        error_content="input did not conform to the SPU's TInput contract",
        handling_action="reject the invocation and report the occurrence",
    )


class _UpperCaserSPU(StepProcessingUnit[str, str]):
    """Concrete SPU: performs actual processing; models the documented flows."""

    def __init__(self, error_type_definitions):
        super().__init__(error_type_definitions)
        self.error_type_definitions.register(a_definition())

    def execute(self, input: str) -> SPUExecutionResult[str, dict]:
        if input == "defined-error":
            occurrence = self.error_type_definitions.create_occurrence(
                REJECTED_INPUT_DEFINITION,
                SPUErrorOccurrenceIdentity("occ-1"),
                {"rejected_input": input},
            )
            return SPUExecutionResult[str, dict](spu_error_occurrences=(occurrence,))
        if input == "explode":
            raise RuntimeError("prevents execute from returning")
        return SPUExecutionResult[str, dict](processing_artifact=input.upper())


def a_spu() -> _UpperCaserSPU:
    return _UpperCaserSPU(a_registry())


# --------------------------------------------------------------------------
# execute contract
# --------------------------------------------------------------------------


def test_execute_success_returns_spu_execution_result():
    spu = a_spu()
    result = spu.execute("hello")

    assert isinstance(result, SPUExecutionResult)
    assert result.processing_artifact == "HELLO"
    assert result.spu_error_occurrences is None
    assert result.validator_result is None


def test_execute_is_one_execution_attempt_per_invocation():
    spu = a_spu()
    first = spu.execute("a")
    second = spu.execute("b")
    assert first.processing_artifact == "A"
    assert second.processing_artifact == "B"


def test_generic_specialization_by_concrete_spu():
    """TInput/TOutput are bound independently by the concrete SPU."""
    assert issubclass(_UpperCaserSPU, StepProcessingUnit)
    spu = a_spu()
    assert isinstance(spu, StepProcessingUnit)
    # subscripting works for both the ABC and the result aggregate
    assert StepProcessingUnit[str, str] is not None
    assert SPUExecutionResult[str, dict] is not None
    assert SPUExecutionResult[str].__class__ is not None  # single-arg alias valid


def test_spu_is_the_actual_processing_unit_not_a_delegation_wrapper():
    """The base cannot be instantiated without implementing execute."""
    with pytest.raises(TypeError):
        StepProcessingUnit(a_registry())  # abstract execute


def test_spu_receives_pipeline_assigned_registry_and_never_creates_one():
    registry = a_registry()
    spu = _UpperCaserSPU(registry)
    assert spu.error_type_definitions is registry
    assert spu.error_type_definitions.owner_spu_identity == SPU_IDENTITY

    # construction without the Pipeline-assigned registry fails
    with pytest.raises(TypeError):
        _UpperCaserSPU(None)  # type: ignore[arg-type]

    # the SPU has no factory to create its own registry
    for forbidden in ("create_registry", "new_registry", "build_registry"):
        assert not hasattr(StepProcessingUnit, forbidden), forbidden


# --------------------------------------------------------------------------
# Result optionality and preservation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "present"),
    [
        ({"processing_artifact": "x"}, "processing_artifact"),
        ({"spu_error_occurrences": ()}, "spu_error_occurrences"),
        ({"validator_result": object()}, "validator_result"),
    ],
    ids=["artifact-only", "occurrences-only", "validator-only"],
)
def test_result_elements_are_independently_optional(kwargs, present):
    result = SPUExecutionResult[str, dict](**kwargs)
    field_names = {field.name for field in dataclasses.fields(result)}
    assert field_names == {
        "processing_artifact",
        "spu_error_occurrences",
        "validator_result",
    }
    for name in field_names:
        value = getattr(result, name)
        if name == present:
            assert value is not None
        else:
            assert value is None, f"{name} must be independently absent"


def test_absence_is_not_a_success_or_failure_status():
    """No universal success boolean/status exists on the result type."""
    for forbidden in ("success", "succeeded", "failed", "status", "outcome", "state"):
        assert not hasattr(SPUExecutionResult, forbidden), forbidden
    # an all-absent result is constructible and carries no status meaning
    empty = SPUExecutionResult[str, dict]()
    assert empty.processing_artifact is None
    assert empty.spu_error_occurrences is None
    assert empty.validator_result is None


def test_result_rejects_non_spuerror_occurrence_items():
    with pytest.raises(TypeError):
        SPUExecutionResult[str, dict](spu_error_occurrences=("not-an-occurrence",))
    with pytest.raises(TypeError):
        SPUExecutionResult[str, dict](spu_error_occurrences="not-a-collection")


def test_preservation_invariant_later_failure_keeps_earlier_elements():
    """A later failure must not discard an earlier produced result element."""
    result = SPUExecutionResult[str, dict](processing_artifact="partial")
    occurrence = SPUError(
        occurrence_identity=SPUErrorOccurrenceIdentity("occ-late"),
        definition_reference=SPUErrorTypeDefinitionReference(
            REGISTRY_IDENTITY, REJECTED_INPUT_DEFINITION
        ),
        context={"stage": "post-processing"},
    )
    # the SPU adds the later evidence without discarding the earlier artifact
    updated = dataclasses.replace(result, spu_error_occurrences=(occurrence,))
    assert updated.processing_artifact == "partial"
    assert updated.spu_error_occurrences == (occurrence,)
    # the original snapshot is untouched (immutable evidence)
    assert result.spu_error_occurrences is None


def test_result_is_immutable():
    result = SPUExecutionResult[str, dict](processing_artifact="x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.processing_artifact = "y"


# --------------------------------------------------------------------------
# Error family: definitions, registry, occurrences
# --------------------------------------------------------------------------


def test_definition_carries_identity_content_and_handling_action():
    definition = a_definition()
    assert definition.definition_identity == REJECTED_INPUT_DEFINITION
    assert definition.error_content.startswith("input did not conform")
    assert definition.handling_action.startswith("reject the invocation")


def test_error_occurrence_creation_references_exactly_one_registered_definition():
    registry = a_registry()
    registry.register(a_definition())
    occurrence = registry.create_occurrence(
        REJECTED_INPUT_DEFINITION,
        SPUErrorOccurrenceIdentity("occ-1"),
        {"rejected_input": "boom"},
    )

    assert isinstance(occurrence, SPUError)
    assert occurrence.occurrence_identity == SPUErrorOccurrenceIdentity("occ-1")
    assert occurrence.definition_reference.registry_identity == REGISTRY_IDENTITY
    assert occurrence.definition_reference.definition_identity == REJECTED_INPUT_DEFINITION
    assert occurrence.context == {"rejected_input": "boom"}

    # the reference resolves back to the exact registered definition
    assert registry.resolve(occurrence.definition_reference) == a_definition()


def test_occurrence_requires_definition_registered_in_the_assigned_registry():
    registry = a_registry()
    with pytest.raises(KeyError):
        registry.create_occurrence(
            REJECTED_INPUT_DEFINITION,
            SPUErrorOccurrenceIdentity("occ-1"),
            None,
        )


def test_registry_rejects_duplicate_definition_identity_without_overwrite():
    registry = a_registry()
    registry.register(a_definition())
    conflicting = SPUErrorTypeDefinition(
        definition_identity=REJECTED_INPUT_DEFINITION,
        error_content="different content",
        handling_action="different action",
    )
    with pytest.raises(ValueError):
        registry.register(conflicting)
    # the original definition is preserved
    assert registry.resolve(
        SPUErrorTypeDefinitionReference(REGISTRY_IDENTITY, REJECTED_INPUT_DEFINITION)
    ) == a_definition()


def test_registry_lookup_is_scoped_to_the_registry_instance():
    """Equal definition identities in another unit's registry never cross-resolve."""
    first = a_registry()
    first.register(a_definition())
    other_registry = SPUErrorTypeDefinitionRegistry(
        SPUErrorTypeDefinitionRegistryIdentity("registry-2"), SPUIdentity("spu-2")
    )

    foreign_reference = SPUErrorTypeDefinitionReference(
        other_registry.identity, REJECTED_INPUT_DEFINITION
    )
    with pytest.raises(ValueError):
        first.resolve(foreign_reference)
    with pytest.raises(KeyError):
        other_registry.resolve(
            SPUErrorTypeDefinitionReference(other_registry.identity, REJECTED_INPUT_DEFINITION)
        )


def test_registry_is_dedicated_to_exactly_one_owning_spu():
    registry = a_registry()
    assert registry.identity == REGISTRY_IDENTITY
    assert registry.owner_spu_identity == SPU_IDENTITY
    with pytest.raises(TypeError):
        SPUErrorTypeDefinitionRegistry("not-an-identity", SPU_IDENTITY)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        SPUErrorTypeDefinitionRegistry(REGISTRY_IDENTITY, "not-an-spu-identity")  # type: ignore[arg-type]


def test_registry_does_not_own_or_store_occurrences():
    registry = a_registry()
    registry.register(a_definition())
    registry.create_occurrence(
        REJECTED_INPUT_DEFINITION, SPUErrorOccurrenceIdentity("occ-1"), None
    )
    # only definitions are exposed; no occurrence storage exists
    assert registry.definitions() == (a_definition(),)
    for forbidden in ("occurrences", "add_occurrence", "store_occurrence"):
        assert not hasattr(registry, forbidden), forbidden


def test_registry_rejects_non_definition_registrations():
    registry = a_registry()
    with pytest.raises(TypeError):
        registry.register("not-a-definition")  # type: ignore[arg-type]


def test_spu_error_occurrences_flow_to_step_composition_via_result():
    """Occurrences created by the SPU are made available on its result."""
    result = a_spu().execute("defined-error")
    occurrences = result.spu_error_occurrences
    assert occurrences is not None and len(occurrences) == 1
    occurrence = occurrences[0]
    assert occurrence.definition_reference.definition_identity == REJECTED_INPUT_DEFINITION


# --------------------------------------------------------------------------
# Exception boundary
# --------------------------------------------------------------------------


def test_exception_boundary_exceptions_are_not_converted():
    """An exception preventing execute from returning stays distinct from
    SPUError and is not an SPUExecutionResult."""
    spu = a_spu()
    with pytest.raises(RuntimeError) as exc_info:
        spu.execute("explode")

    thrown = exc_info.value
    assert not isinstance(thrown, SPUError)
    assert not isinstance(thrown, SPUExecutionResult)
    assert isinstance(thrown, RuntimeError)  # propagates as-is, unconverted


# --------------------------------------------------------------------------
# Distinctness from the Step-level result (integration-oriented)
# --------------------------------------------------------------------------


def test_spu_execution_result_distinct_from_step_execution_result():
    """SPUExecutionResult is scoped to one SPU invocation and is a distinct type
    from the Stage-facing StepExecutionResult (assembled only by Step
    Composition, task 02). Skips deep checks while StepExecutionResult is a
    placeholder."""
    from gpwcf.core.step.step import StepExecutionResult

    assert SPUExecutionResult is not StepExecutionResult
    assert not issubclass(SPUExecutionResult, StepExecutionResult)
    assert not issubclass(StepExecutionResult, SPUExecutionResult)

    if not hasattr(StepExecutionResult, "__dataclass_fields__"):
        pytest.skip("StepExecutionResult is still a placeholder (task 02)")
    # once task 02 lands: the SPU result must never carry Step-level fields
    spu_fields = {field.name for field in dataclasses.fields(SPUExecutionResult)}
    step_fields = {field.name for field in dataclasses.fields(StepExecutionResult)}
    assert "spu_error_occurrences" not in step_fields or step_fields != spu_fields
