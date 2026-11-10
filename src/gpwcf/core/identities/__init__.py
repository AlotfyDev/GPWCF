"""Core identities: nominal, immutable identity value types.

Implementation task: 11_Core_Identities_Diagnostics
Related diagrams:
  class: 03_Diagrams_Codes_Files/11_Core_Identities_Diagnostics.dot
  association: C_Association_Diagram_Code/11_Core_Identities_Diagnostics_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/01_Package_Module_Dependency_Graph.dot

Contract basis:
  - 03.00_Pipeline_Invocation.json (gpwcf.architecture-closure.wave1.pipeline-invocation)
  - 14,00_Dependency.json ("8_Core_Identities_Module" entity note)

This module is deliberately dependency-free: standard library only, no imports
from other ``gpwcf`` packages, no third-party packages. It contains nominal
identity value types ONLY and provides no identity generator, registry,
service, or lifecycle manager. Identity values are created and owned by the
consumer / owner of the corresponding aggregate; GPWCF only carries and
preserves them. The value representation is opaque; no UUID/ULID/integer/text
encoding is mandated by the framework.

Cross-type equality and implicit conversion between identity types are
prohibited: equal opaque values of different identity types are not equal.
"""

__all__ = [
    "PipelineInvocationIdentity",
    "StageIdentity",
    "StageInvocationIdentity",
    "StepIdentity",
    "StepInvocationIdentity",
    "SPUIdentity",
    "InvocationIdentity",
]


def _validated(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("identity value must be a str")
    if value == "" or value.isspace():
        raise ValueError("identity value must be a non-empty, non-blank string")
    return value


class _IdentityValue:
    """Immutable nominal identity value; equal only within its own type."""

    __slots__ = ("_value",)

    def __new__(cls, value: str) -> "_IdentityValue":
        if cls is _IdentityValue:
            raise TypeError("use a concrete identity type, not _IdentityValue")
        return super().__new__(cls)

    def __init__(self, value: str) -> None:
        object.__setattr__(self, "_value", _validated(value))

    @property
    def value(self) -> str:
        """The opaque, owner-assigned identity value."""
        return self._value

    def __setattr__(self, name: str, object: object) -> None:  # noqa: A002
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        return self._value == other._value  # type: ignore[attr-defined]

    def __hash__(self) -> int:
        return hash((type(self), self._value))

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._value!r})"


class PipelineInvocationIdentity(_IdentityValue):
    """Opaque identity of one logical consumer-owned pipeline invocation.

    Consumer-created and consumer-owned; GPWCF carries it as an optional
    correlation identity across Stage invocations. Its existence does not
    establish a Pipeline Root Entity or any GPWCF orchestration responsibility.
    """

    __slots__ = ()


class StageIdentity(_IdentityValue):
    """Nominal identity of one Stage instance.

    Semantic issuance/ownership remains with the Stage Aggregate; the value
    is opaque and not interchangeable with Step, SPU, or invocation identities.
    """

    __slots__ = ()


class StepIdentity(_IdentityValue):
    """Nominal identity of one Step instance.

    Issued by the owning Stage/Stage Composition; opaque value; distinct
    nominal type from Stage, SPU, and invocation identities.
    """

    __slots__ = ()


class StepInvocationIdentity(_IdentityValue):
    """Nominal identity of one proposed/accepted Step invocation.

    Contract basis: 04.00_Step_Callable.json (``stepInvocation``). The caller
    (Stage Composition or its integration binding) supplies a candidate value
    before calling ``execute``; the Step public boundary validates it against
    the Step identity scope and atomically accepts or rejects the invocation.
    A distinct value is required for each distinct admitted invocation; the
    Step must not accept the same value for two distinct concurrent
    invocations unless an explicit idempotency/replay contract authorizes it,
    and a candidate value can never be silently reused for a different
    invocation.
    """

    __slots__ = ()


class StageInvocationIdentity(_IdentityValue):
    """Nominal identity of one Stage invocation.

    Contract basis: 04.00_Step_Callable.json (``parent_stage_invocation_identity``).
    Identifies the Stage invocation whose Stage Composition invokes a Step;
    semantic issuance/ownership remains with the Stage Aggregate. Distinct
    nominal type from Stage, Step, and invocation identities.
    """

    __slots__ = ()


class SPUIdentity(_IdentityValue):
    """Nominal identity of one Step Processing Unit instance.

    Correlation of SPU identity is maintained across invocation and (when an
    external runtime is used) native subworkflow boundaries; it remains
    distinct from Step/Stage identities and native runtime identities.
    """

    __slots__ = ()


class InvocationIdentity(_IdentityValue):
    """Nominal identity of one authorized invocation of a component.

    Used to correlate one execution attempt across callable boundaries and
    operational evidence; the value is owner-assigned and opaque.
    """

    __slots__ = ()
