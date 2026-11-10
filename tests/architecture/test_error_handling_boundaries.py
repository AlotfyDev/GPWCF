"""Architecture tests for task 04_Error_Handling.

Enforces the Error Handling pattern structural boundaries across
``src\\gpwcf\\core\\supporting_patterns\\error_handling``:

  - NO Core dependency: the pattern package imports nothing from ``gpwcf`` at
    all (``ErrorHandlingUnit -> Core : NO dependency``; stdlib + pattern-local
    identities only), and never imports Prefect or any integration package.
  - ``ErrorHandlerResult`` carries exactly the aggregate fields and contains no
    ``ErrorResult`` containment of any kind.
  - ``ErrorHandlingUnit`` exposes the contract ``execute`` (returns None) and no
    competing entries-collection API.
  - Cross-layer identities travel as opaque validated string values.
"""

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"
PATTERN_DIR = SRC / "gpwcf" / "core" / "supporting_patterns" / "error_handling"

FORBIDDEN_ROOTS = ("gpwcf", "prefect", "prefectextras")


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


def test_error_handling_pattern_has_no_core_or_prefect_dependency():
    """``ErrorHandlingUnit -> Core : NO dependency`` — stdlib only."""
    offenders = []
    for py_file in sorted(PATTERN_DIR.rglob("*.py")):
        for module in _imported_modules(py_file):
            root = module.split(".")[0]
            if root in FORBIDDEN_ROOTS or module.startswith(
                ("gpwcf.", "prefect.", "integrations.")
            ):
                offenders.append(f"{py_file.name}: {module}")
    assert not offenders, f"pattern modules import a forbidden layer: {offenders}"


def test_error_handler_result_aggregates_entries_and_never_error_result():
    """ErrorHandlerResult has exactly the two aggregate fields and no
    ErrorResult containment in code (docstrings excluded)."""
    unit_file = PATTERN_DIR / "error_handling_unit.py"
    tree = ast.parse(unit_file.read_text(encoding="utf-8"), filename=str(unit_file))

    cls = None
    unit_cls = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if node.name == "ErrorHandlerResult":
                cls = node
            elif node.name == "ErrorHandlingUnit":
                unit_cls = node
    assert cls is not None, "ErrorHandlerResult is missing"

    assigned = [
        statement.target.id
        for statement in cls.body
        if isinstance(statement, ast.AnnAssign)
    ]
    assert assigned == ["operation_entries", "error_handling_context"]

    # no ErrorResult symbol is referenced in executable code of the class
    for node in ast.walk(cls):
        if isinstance(node, ast.Name) and "ErrorResult" in node.id:
            raise AssertionError(f"ErrorHandlerResult references {node.id}")
        if isinstance(node, ast.Attribute) and "ErrorResult" in node.attr:
            raise AssertionError(f"ErrorHandlerResult references .{node.attr}")

    # no occurrence-resolution assertion API
    for method in ("resolve_occurrences", "assert_resolved", "error_result"):
        assert not any(
            isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
            and member.name == method
            for member in cls.body
        ), method


def test_error_handling_unit_executes_and_never_collects_entries():
    """execute(input, operationEntryPublisher) -> None; no entries-collection
    API on the Unit (the Publisher is the authoritative delivery path)."""
    unit_file = PATTERN_DIR / "error_handling_unit.py"
    tree = ast.parse(unit_file.read_text(encoding="utf-8"), filename=str(unit_file))

    unit_cls = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ErrorHandlingUnit":
            unit_cls = node
    assert unit_cls is not None, "ErrorHandlingUnit is missing"

    methods = {
        member.name: member
        for member in unit_cls.body
        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    execute = methods.get("execute")
    assert execute is not None, "ErrorHandlingUnit.execute is missing"
    positional = [arg.arg for arg in execute.args.posonlyargs + execute.args.args]
    assert positional == ["self", "input", "operation_entry_publisher"], positional
    returns_none = (
        execute.returns is None or ast.unparse(execute.returns) == "None"
    )
    assert returns_none, "execute must return None, not a collection of entries"

    for forbidden in ("accepted_entries", "get_entries", "operation_entries", "drain"):
        assert forbidden not in methods, forbidden


def test_cross_layer_identities_travel_as_opaque_string_values():
    """Step/Association/target/SPU-occurrence identities are opaque non-empty
    string VALUES (validated); pattern-owned identities are nominal types."""
    unit_file = PATTERN_DIR / "error_handling_unit.py"
    source = unit_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(unit_file))

    entry_cls = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ErrorHandlingOperationEntry":
            entry_cls = node
    assert entry_cls is not None, "ErrorHandlingOperationEntry is missing"

    string_fields = {
        statement.target.id
        for statement in entry_cls.body
        if isinstance(statement, ast.AnnAssign)
        and isinstance(statement.annotation, ast.Name)
        and statement.annotation.id == "str"
    }
    assert string_fields == {
        "step_instance_identity",
        "error_handling_unit_association_identity",
        "association_target_identity",
    }
    # opaque values are validated non-empty
    assert "_require_opaque_identity" in source
    # the pattern defines its own nominal identity types (local replica of the
    # core value-type pattern; the first test already proves no gpwcf import)
    identities_file = PATTERN_DIR / "identities.py"
    identities_tree = ast.parse(
        identities_file.read_text(encoding="utf-8"), filename=str(identities_file)
    )
    defined = {
        node.name
        for node in ast.walk(identities_tree)
        if isinstance(node, ast.ClassDef)
    }
    assert {
        "ErrorHandlingUnitIdentity",
        "ErrorHandlingInvocationIdentity",
        "HandlingOperationAttemptIdentity",
        "HandlingOperationIdentity",
        "OperationEntryPublisherIdentity",
        "PublicationReservationIdentity",
    } <= defined


# --------------------------------------------------------------------------
# task 07 — the specialization surface is fully implemented (no TBDs)
# --------------------------------------------------------------------------


_MARKERS = ("TODO", "TBD", "FIXME", "XXX", "to be decided", "not implemented")


def _is_abstract_stub(function: ast.AST) -> bool:
    """``@abstractmethod`` bodies raising NotImplementedError are contracts,
    not unfinished work."""
    if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    decorators = {
        ast.unparse(decorator) for decorator in function.decorator_list
    }
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


def test_publication_specialization_has_no_tbd_or_unimplemented_code():
    """The Single Step Publication Specialization surface (publisher +
    recovery module) is concrete: no NotImplementedError raises and no
    TODO/TBD/FIXME markers anywhere in the Error Handling pattern — the only
    permitted raise is an ``@abstractmethod`` stub body."""
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
            for marker in _MARKERS:
                if marker in line:
                    offenders.append(f"{py_file.name}:{index}: {marker!r}")
                    break

    assert not offenders, f"unfinished publication specialization code: {offenders}"
