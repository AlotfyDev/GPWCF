"""Contract tests for core.diagnostics (task 11_Core_Identities_Diagnostics).

Covers:
  - DiagnosticCode: producer-owned namespaced code; equality scoped by namespace AND value
  - Diagnostic[TDetails]: narrow, typed, descriptive, optional value (DIAG-001..DIAG-004)
  - Semantic distinction from Error Occurrence / Failure / Exception / Outcome (DIAG-005)
  - Descriptive only: no severity/retry/resolution/outcome fields or behavior
"""

import dataclasses

import pytest

from gpwcf.core.diagnostics import Diagnostic, DiagnosticCode

CODE = DiagnosticCode("smrb.test", "invariant-hint")


class _SpecializedDetails:
    """Producer-specialized typed details payload (TDetails)."""


def test_diagnostic_code_namespaced_equality():
    assert DiagnosticCode("ns", "code") == DiagnosticCode("ns", "code")
    assert hash(DiagnosticCode("ns", "code")) == hash(DiagnosticCode("ns", "code"))
    # equality is scoped by BOTH namespace and value
    assert DiagnosticCode("ns1", "code") != DiagnosticCode("ns2", "code")


def test_diagnostic_code_validation():
    with pytest.raises(ValueError):
        DiagnosticCode("", "code")
    with pytest.raises(ValueError):
        DiagnosticCode("ns", "  ")
    with pytest.raises(TypeError):
        DiagnosticCode("ns", 7)  # type: ignore[arg-type]


def test_diagnostic_construction_without_details():
    """``None`` is the TDetails value when no structured details are needed."""
    diagnostic = Diagnostic(CODE, "capability reference was invalid", None)
    assert diagnostic.code == CODE
    assert diagnostic.message == "capability reference was invalid"
    assert diagnostic.details is None


def test_diagnostic_typed_details_payload():
    details = _SpecializedDetails()
    diagnostic = Diagnostic(CODE, "publication status query unavailable", details)
    assert diagnostic.details is details


def test_diagnostic_validation():
    with pytest.raises(TypeError):
        Diagnostic("not-a-code", "message", None)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Diagnostic(CODE, "", None)
    with pytest.raises(ValueError):
        Diagnostic(CODE, "   ", None)
    with pytest.raises(TypeError):
        Diagnostic(CODE, 42, None)  # type: ignore[arg-type]


def test_diagnostic_immutable_value_semantics():
    first = Diagnostic(CODE, "message", None)
    second = Diagnostic(DiagnosticCode("smrb.test", "invariant-hint"), "message", None)
    assert first == second
    assert hash(first) == hash(second)
    assert first != Diagnostic(CODE, "different message", None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.message = "mutated"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.details = "mutated"  # type: ignore[misc]


def test_diagnostic_is_not_an_exception_or_error_model_type():
    """DIAG-005: not an Error Occurrence, Failure, Exception, or domain Outcome."""
    assert not issubclass(Diagnostic, BaseException)
    assert not issubclass(DiagnosticCode, BaseException)
    # Diagnostic is not part of any identity hierarchy either
    from gpwcf.core import identities

    for identity_type in (
        identities.PipelineInvocationIdentity,
        identities.StageIdentity,
        identities.StepIdentity,
        identities.SPUIdentity,
        identities.InvocationIdentity,
    ):
        assert not issubclass(Diagnostic, identity_type)
        assert not issubclass(identity_type, Diagnostic)


def test_diagnostic_has_no_error_model_semantics_or_behavior():
    """DIAG-001/DIAG-010: descriptive only; no severity/retry/resolution/outcome surface."""
    for forbidden_attribute in (
        "severity",
        "level",
        "retryable",
        "retriable",
        "resolution",
        "resolved",
        "outcome",
        "status",
        "state",
        "timestamp",
        "origin",
        "cause",
        "error_result",
        "errorresult",
    ):
        assert not hasattr(Diagnostic, forbidden_attribute), forbidden_attribute
    for forbidden_behavior in (
        "execute",
        "classify",
        "retry",
        "resolve",
        "publish",
        "transition",
        "handle",
        "attach",
    ):
        assert not hasattr(Diagnostic, forbidden_behavior), forbidden_behavior


def test_module_exports_exactly_the_diagnostic_contract():
    import gpwcf.core.diagnostics as diagnostics_module

    assert set(diagnostics_module.__all__) == {"Diagnostic", "DiagnosticCode"}
    for name in diagnostics_module.__all__:
        assert hasattr(diagnostics_module, name)
