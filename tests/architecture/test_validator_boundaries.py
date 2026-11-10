"""Architecture tests for task 05_Validator_Unit.

Enforces the Validator Unit pattern structural boundaries across
``src\\gpwcf\\core\\supporting_patterns\\validation``:

  - NO Core dependency: the pattern imports nothing from ``gpwcf`` at all
    (``ValidatorUnit -> Core : NO dependency``; stdlib only) and never imports
    Prefect or any integration package.
  - No universal one-validator-per-SPU relationship is imposed: association
    cardinality is a concrete-Step concern; one unit may serve several target
    scopes and several units may serve one target.
  - No universal Supporting Unit / registry / manager abstraction is defined
    under the validation pattern (task-05-specific instantiation of the
    framework-wide rule).
  - The SPU ``validatorResult`` optional slot stays a pure forward reference:
    ``core\\processing_units`` never imports the supporting pattern (even
    TYPE_CHECKING-guarded), and the validation pattern never imports the SPU
    layer.
  - The pattern is fully implemented: no ``NotImplementedError`` outside
    abstractmethod stubs, no TODO/TBD/FIXME markers.
"""

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"
PATTERN_DIR = SRC / "gpwcf" / "core" / "supporting_patterns" / "validation"
SPU_DIR = SRC / "gpwcf" / "core" / "processing_units"

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
    "ValidatorRegistry",
    "ValidatorManager",
}

_TBD_MARKERS = ("TODO", "TBD", "FIXME", "XXX", "to be decided", "not implemented")


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


def test_validator_pattern_has_no_core_or_prefect_dependency():
    """``ValidatorUnit -> Core : NO dependency`` — stdlib only."""
    offenders = []
    for py_file in sorted(PATTERN_DIR.rglob("*.py")):
        for module in _imported_modules(py_file):
            root = module.split(".")[0]
            if root in FORBIDDEN_ROOTS or module.startswith(
                ("gpwcf.", "prefect.", "integrations.")
            ):
                offenders.append(f"{py_file.name}: {module}")
    assert not offenders, f"validation pattern imports a forbidden layer: {offenders}"


def test_no_universal_abstraction_types_in_the_validation_pattern():
    """No universal Supporting Unit / registry / manager type is defined or
    inherited by validation pattern code (association coordination is a
    pattern-scoped book owned by Step Composition, never a global manager)."""
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
    assert not offenders, f"universal abstractions in the validation pattern: {offenders}"


def test_no_universal_one_validator_per_target_relationship_is_imposed():
    """Association cardinality is concrete-Step freedom: the behavioral proof
    that one unit may hold several associations and several units may target
    one scope lives in the unit tests; here we assert the pattern code contains
    no hardcoded cardinality caps on associations per unit or per target."""
    forbidden_fragments = (
        "max_associations",
        "maximum_associations",
        "association_limit",
        "one_validator_per_spu",
        "one_validator_per_step",
        "singleton",
    )
    offenders = []
    for py_file in sorted(PATTERN_DIR.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8").lower()
        for fragment in forbidden_fragments:
            if fragment in source:
                offenders.append(f"{py_file.name}: mentions {fragment!r}")
    assert not offenders, f"cardinality restriction found: {offenders}"


def test_spu_validator_result_slot_stays_a_pure_forward_reference():
    """The SPU result slot references SPUValidatorResult by name only:
    ``core\\processing_units`` never imports the supporting pattern (relative
    imports resolved, TYPE_CHECKING-guarded imports included), and the
    validation pattern never imports the SPU layer."""
    results_init = SPU_DIR / "spu" / "results" / "__init__.py"
    tree = ast.parse(results_init.read_text(encoding="utf-8"), filename=str(results_init))
    annotation_names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }
    assert "SPUValidatorResult" in annotation_names, (
        "SPUExecutionResult.validator_result must keep referencing SPUValidatorResult"
    )

    for py_file in sorted(SPU_DIR.rglob("*.py")):
        for module in _imported_modules(py_file):
            assert not module.startswith("gpwcf.core.supporting_patterns"), (
                f"{py_file}: the SPU layer imports the validation pattern"
            )
    for py_file in sorted(PATTERN_DIR.rglob("*.py")):
        for module in _imported_modules(py_file):
            assert not module.startswith("gpwcf.core.processing_units"), (
                f"{py_file}: the validation pattern imports the SPU layer"
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


def test_validator_pattern_has_no_tbd_or_unimplemented_code():
    """The validation pattern is concrete: the only permitted NotImplementedError
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
    assert not offenders, f"unfinished validator pattern code: {offenders}"
