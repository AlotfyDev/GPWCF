"""Architecture tests for task 06_Observation_Unit.

Enforces the Observation Unit pattern structural boundaries across
``src\\\\gpwcf\\\\core\\\\supporting_patterns\\\\observation``:

  - NO Core dependency: the pattern imports nothing from ``gpwcf`` at all
    (``ObservationUnit -> Core : NO dependency``; stdlib only) and never imports
    Prefect or any integration package.
  - No universal Supporting Unit / registry / manager / telemetry-hub
    abstraction is defined or inherited under the observation pattern (the
    task-06-specific instantiation of the framework-wide rule).
  - No universal one-observation-unit-per-target relationship or cardinality
    cap is imposed: association cardinality is a concrete-Step concern.
  - ``ObservationRecord`` is fully independent of ``StepExecutionResult`` and
    every other result contract: its fields are exactly the six mandatory
    provenance references plus payload and optional metadata — no result,
    status, or severity field; and no layer imports the observation pattern
    into the Step/SPU result contracts (checked in both directions).
  - The pattern is fully implemented: no ``NotImplementedError`` outside
    abstractmethod stubs, no TODO/TBD/FIXME markers.
"""

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"
PATTERN_DIR = SRC / "gpwcf" / "core" / "supporting_patterns" / "observation"
SPU_DIR = SRC / "gpwcf" / "core" / "processing_units"
STEP_DIR = SRC / "gpwcf" / "core" / "step"

FORBIDDEN_ROOTS = ("gpwcf", "prefect", "prefectextras")

_UNIVERSAL_ABSTRACTION_NAMES = {
    "SupportingUnit",
    "UniversalSupportingUnit",
    "SupportingUnitBase",
    "ExecutionContext",
    "UniversalExecutionContext",
    "LifecycleManager",
    "AssociationRegistry",
    "IdentityRegistry",
    "IdentityGenerator",
    "ObservationManager",
    "ObservationRegistry",
    "TelemetryHub",
    "EventBus",
}

_CARDINALITY_FRAGMENTS = (
    "max_associations",
    "maximum_associations",
    "association_limit",
    "one_observation_unit_per_spu",
    "one_observation_unit_per_step",
    "exclusive_binding",
    "singleton",
)

_TBD_MARKERS = ("TODO", "TBD", "FIXME", "XXX", "to be decided", "not implemented")

_SIX_PROVENANCE_FIELDS = {
    "step_instance_identity",
    "observation_unit_identity",
    "observation_unit_association_identity",
    "association_target_identity",
    "observation_invocation_identity",
    "observation_record_identity",
}

_FORBIDDEN_RECORD_FIELD_FRAGMENTS = (
    "execution_result",
    "validator_result",
    "error_result",
    "handler_result",
    "status",
    "success",
    "severity",
    "verdict",
)


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                continue  # relative imports stay inside the pattern package
            if node.module:
                modules.append(node.module)
    return modules


def test_observation_pattern_has_no_core_or_prefect_dependency():
    """``ObservationUnit -> Core : NO dependency`` — stdlib only."""
    offenders = []
    for py_file in sorted(PATTERN_DIR.rglob("*.py")):
        for module in _imported_modules(py_file):
            root = module.split(".")[0]
            if root in FORBIDDEN_ROOTS or module.startswith(
                ("gpwcf.", "prefect.", "integrations.")
            ):
                offenders.append(f"{py_file.name}: {module}")
    assert not offenders, f"observation pattern imports a forbidden layer: {offenders}"


def test_no_universal_abstraction_types_in_the_observation_pattern():
    """No universal Supporting Unit / registry / manager / telemetry-hub type is
    defined or inherited by observation pattern code (association coordination
    is a pattern-scoped book owned by Step Composition, never a global
    manager, and no central collector is required)."""
    offenders = []
    for py_file in sorted(PATTERN_DIR.rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if node.name in _UNIVERSAL_ABSTRACTION_NAMES:
                    offenders.append(f"{py_file.name}: class {node.name}")
                for base in node.bases:
                    base_name = (
                        base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)
                    )
                    if base_name in _UNIVERSAL_ABSTRACTION_NAMES:
                        offenders.append(
                            f"{py_file.name}: {node.name} inherits {base_name}"
                        )
    assert not offenders, f"universal abstractions in the observation pattern: {offenders}"


def test_no_universal_cardinality_or_exclusivity_is_imposed():
    """Association cardinality is concrete-Step freedom: one unit may hold
    several associations and several units may observe one target (proven
    behaviorally in the unit tests); here we assert the pattern code contains
    no hardcoded cardinality cap, exclusivity rule, or singleton binding."""
    offenders = []
    for py_file in sorted(PATTERN_DIR.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8").lower()
        for fragment in _CARDINALITY_FRAGMENTS:
            if fragment in source:
                offenders.append(f"{py_file.name}: mentions {fragment!r}")
    assert not offenders, f"cardinality restriction found: {offenders}"


def test_observation_record_is_independent_of_every_result_contract():
    """The record type's fields are exactly the six mandatory provenance
    references plus payload and optional metadata — no StepExecutionResult /
    SPUExecutionResult / validation / error / status / severity field exists,
    and no Core layer direction imports the pattern into a result contract."""
    unit_file = PATTERN_DIR / "observation_unit.py"
    tree = ast.parse(unit_file.read_text(encoding="utf-8"), filename=str(unit_file))

    record_class = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "ObservationRecord"
        ),
        None,
    )
    assert record_class is not None, "ObservationRecord must be defined"

    field_names = {
        node.target.id
        for node in record_class.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    # all SIX mandatory provenance references are present on every record
    assert _SIX_PROVENANCE_FIELDS <= field_names, (
        f"missing provenance fields: {_SIX_PROVENANCE_FIELDS - field_names}"
    )
    assert "payload" in field_names, "the payload element is missing"
    # no result contract or status semantics leaks onto the record
    for fragment in _FORBIDDEN_RECORD_FIELD_FRAGMENTS:
        assert not any(fragment in name for name in field_names), (
            f"ObservationRecord carries a forbidden {fragment!r} field"
        )

    # both directions: no Core layer imports the observation pattern
    for layer_dir in (SPU_DIR, STEP_DIR):
        for py_file in sorted(layer_dir.rglob("*.py")):
            for module in _imported_modules(py_file):
                assert not module.startswith("gpwcf.core.supporting_patterns"), (
                    f"{py_file}: a Core layer imports the observation pattern"
                )


def _is_abstract_stub(function: ast.AST) -> bool:
    if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    decorators = {ast.unparse(decorator) for decorator in function.decorator_list}
    if "abstractmethod" not in decorators:
        return False
    body = [
        statement
        for statement in function.body
        if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant))
    ]
    return (
        len(body) == 1
        and isinstance(body[0], ast.Raise)
        and body[0].exc is not None
        and ast.unparse(body[0].exc) == "NotImplementedError"
    )


def test_observation_pattern_has_no_tbd_or_unimplemented_code():
    """The observation pattern is concrete: the only permitted NotImplementedError
    is an ``@abstractmethod`` stub body; no TODO/TBD/FIXME markers anywhere."""
    offenders: list[str] = []
    for py_file in sorted(PATTERN_DIR.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if _is_abstract_stub(node):
                continue
            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.Raise)
                    and inner.exc is not None
                    and ast.unparse(inner.exc) == "NotImplementedError"
                ):
                    offenders.append(
                        f"{py_file.name}:{inner.lineno}: raise NotImplementedError"
                    )
        for index, line in enumerate(source.splitlines(), start=1):
            for marker in _TBD_MARKERS:
                if marker in line:
                    offenders.append(f"{py_file.name}:{index}: {marker!r}")
                    break
    assert not offenders, f"unfinished observation pattern code: {offenders}"
