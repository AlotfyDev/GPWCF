"""Unit tests for core.identities (task 11_Core_Identities_Diagnostics).

Covers:
  - The five nominal identity value types and their shared value contract
  - Validation (opaque non-empty string values, consumer-owned; no generator)
  - Value semantics within one type (equality + hash)
  - Nominal type distinction: cross-type equality and implicit conversion prohibited
  - Immutability
"""

import dataclasses

import pytest

from gpwcf.core import identities
from gpwcf.core.identities import (
    InvocationIdentity,
    PipelineInvocationIdentity,
    SPUIdentity,
    StageIdentity,
    StageInvocationIdentity,
    StepIdentity,
    StepInvocationIdentity,
)

IDENTITY_TYPES = [
    PipelineInvocationIdentity,
    StageIdentity,
    StageInvocationIdentity,
    StepIdentity,
    StepInvocationIdentity,
    SPUIdentity,
    InvocationIdentity,
]


@pytest.mark.parametrize("identity_type", IDENTITY_TYPES)
class TestIdentityValueContract:
    def test_construction_and_opaque_value(self, identity_type):
        ident = identity_type("abc-123")
        assert ident.value == "abc-123"
        assert str(ident) == "abc-123"
        assert repr(ident) == f"{identity_type.__name__}('abc-123')"

    def test_rejects_empty_and_blank_values(self, identity_type):
        with pytest.raises(ValueError):
            identity_type("")
        with pytest.raises(ValueError):
            identity_type("   ")

    def test_rejects_non_string_values(self, identity_type):
        with pytest.raises(TypeError):
            identity_type(123)  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            identity_type(None)  # type: ignore[arg-type]

    def test_value_semantics_within_type(self, identity_type):
        first = identity_type("x1")
        same_value = identity_type("x1")
        other_value = identity_type("x2")
        assert first == same_value
        assert hash(first) == hash(same_value)
        assert first != other_value
        assert len({first, same_value, other_value}) == 2

    def test_usable_as_dict_key(self, identity_type):
        mapping = {identity_type("k"): "payload"}
        assert mapping[identity_type("k")] == "payload"

    def test_immutable(self, identity_type):
        ident = identity_type("keep")
        with pytest.raises(AttributeError):
            ident.value = "changed"  # type: ignore[misc]
        with pytest.raises(AttributeError):
            del ident.value  # type: ignore[misc]
        assert ident.value == "keep"
        assert not dataclasses.is_dataclass(ident)


def test_module_exports_exactly_the_seven_identity_types():
    """Nominal identity value types only; no generator/registry/service surface."""
    assert set(identities.__all__) == {
        "PipelineInvocationIdentity",
        "StageIdentity",
        "StageInvocationIdentity",
        "StepIdentity",
        "StepInvocationIdentity",
        "SPUIdentity",
        "InvocationIdentity",
    }
    public = {name for name in vars(identities) if not name.startswith("_")}
    assert public == set(identities.__all__)


def test_no_identity_generator_registry_or_service():
    """The module provides no identity generator, registry, service, or lifecycle manager."""
    for identity_type in IDENTITY_TYPES:
        for forbidden in ("new", "generate", "create", "register", "resolve", "next"):
            assert not hasattr(identity_type, forbidden), forbidden
    for forbidden_module_name in ("registry", "generator", "provider", "manager", "service"):
        assert not hasattr(identities, forbidden_module_name)


def test_cross_type_equality_and_implicit_conversion_prohibited():
    pipeline = PipelineInvocationIdentity("same-value")
    stage = StageIdentity("same-value")
    stage_inv = StageInvocationIdentity("same-value")
    step = StepIdentity("same-value")
    step_inv = StepInvocationIdentity("same-value")
    spu = SPUIdentity("same-value")
    invocation = InvocationIdentity("same-value")

    assert pipeline != stage
    assert stage != stage_inv
    assert stage_inv != step
    assert step != step_inv
    assert step_inv != spu
    assert spu != invocation
    assert pipeline != invocation

    # no implicit conversion to the raw string value
    assert stage != "same-value"
    assert not (stage == "same-value")

    # distinct types remain distinct members in a set despite equal values
    assert len({pipeline, stage, stage_inv, step, step_inv, spu, invocation}) == 7


def test_identity_types_are_distinct_nominal_types():
    for identity_type in IDENTITY_TYPES:
        assert type(identity_type("v")) is identity_type
    for left in IDENTITY_TYPES:
        for right in IDENTITY_TYPES:
            if left is not right:
                assert not issubclass(left, right)
                assert not issubclass(right, left)
