"""Core diagnostics: narrow, typed, descriptive, optional Diagnostic value contract.

Implementation task: 11_Core_Identities_Diagnostics
Related diagrams:
  class: 03_Diagrams_Codes_Files/11_Core_Identities_Diagnostics.dot
  association: C_Association_Diagram_Code/11_Core_Identities_Diagnostics_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/01_Package_Module_Dependency_Graph.dot

Contract basis:
  - 09.00_Generic_Diagnostics.json (gpwcf.architecture-closure.wave4.generic-diagnostics),
    selected option DIAGNOSTICS-D "NarrowOptionalDiagnosticValue",
    conformance requirements DIAG-001..DIAG-010.

A Diagnostic is descriptive evidence that helps explain or inspect a condition,
observation, protocol event, or contract violation. It is deliberately distinct
from the Error Model, Failure taxonomy, execution outcome, and control-flow
policy:

  - It does not decide success, failure, retry, resolution, or flow transition
    (DIAG-001).
  - It is not an Error Type Definition, Error Occurrence, ErrorResult, Failure,
    Exception, or domain Outcome (DIAG-005).
  - It deliberately omits identity, severity, retryability, resolution status,
    timestamp, origin identity, and cause chain; the parent specialized record
    owns provenance, identity, retention, and custody (DIAG-006).
  - It has no behavior (no execute/classify/retry/resolve/publish/transition).

The module is optional and independently importable (DIAG-004), standard
library only, and must not depend on Error Handling, Stage, Step, SPU, Prefect,
or consumer packages (DIAG-008). No global diagnostic registry, logger,
collector, event bus, or storage service is introduced (DIAG-002, DIAG-010).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

__all__ = ["Diagnostic", "DiagnosticCode"]

TDetails = TypeVar("TDetails")


def _non_empty(field: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a str")
    if value == "" or value.isspace():
        raise ValueError(f"{field} must be a non-empty, non-blank string")
    return value


@dataclass(frozen=True)
class DiagnosticCode:
    """Producer-owned, namespaced machine-readable diagnostic code (DIAG-002).

    The producer owns the code namespace and its stability; no global
    diagnostic-code registry exists. Equality is scoped by BOTH namespace and
    value. A code is descriptive and must not silently encode a universal
    severity, retry, resolution, or flow-control policy.
    """

    namespace: str
    value: str

    def __post_init__(self) -> None:
        _non_empty("namespace", self.namespace)
        _non_empty("value", self.value)


@dataclass(frozen=True)
class Diagnostic(Generic[TDetails]):
    """Immutable descriptive evidence value (DIAG-001).

    Fields:
        code: Producer-owned namespaced :class:`DiagnosticCode`.
        message: Human-readable explanation; never a machine control
            instruction.
        details: Producer/consumer-specialized typed detail payload. Use
            ``None`` as the ``TDetails`` value when no additional structured
            details are needed; do not use an untyped dictionary (DIAG-003).
            Core does not inspect or interpret ``TDetails``.

    Deliberately omitted (see module docstring): diagnostic identity, severity,
    retryability, resolution status, timestamp, origin identity, cause chain.
    The containing occurrence/result/protocol record owns correlation identity,
    retention, and custody (DIAG-006). No result envelope
    (``StageResult``/``StepExecutionResult``/``SPUExecutionResult``/
    ``OptionalResultContributions``) acquires a mandatory diagnostics field
    (DIAG-007).
    """

    code: DiagnosticCode
    message: str
    details: TDetails

    def __post_init__(self) -> None:
        if not isinstance(self.code, DiagnosticCode):
            raise TypeError("code must be a DiagnosticCode")
        _non_empty("message", self.message)
