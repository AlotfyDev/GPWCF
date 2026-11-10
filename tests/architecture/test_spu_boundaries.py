"""Architecture tests for task 01_SPU_Step_Processing_Unit.

Enforces the SPU structural boundaries across ``src\\gpwcf``:

  - No reverse dependency: nothing under ``core\\processing_units`` imports
    ``core.step``, ``core.stage``, or ``core.supporting_patterns`` (relative
    imports resolved, ``TYPE_CHECKING``-guarded imports included).
  - The SPU layer never imports Prefect or any integration package; Prefect
    State is operational evidence, never a substitute for the domain result.
  - ``StepProcessingUnit`` exposes exactly the generic ``execute`` operation
    (no universal execution-context parameter).
  - ``SPUExecutionResult`` carries exactly the three independently optional
    contract elements and no universal success/status field.
"""

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"
SPU_DIR = SRC / "gpwcf" / "core" / "processing_units"

FORBIDDEN_IMPORT_PREFIXES = (
    "gpwcf.core.step",
    "gpwcf.core.stage",
    "gpwcf.core.supporting_patterns",
    "gpwcf.integrations",
    "prefect",
)


def _package_parts(path: Path) -> tuple[str, ...]:
    return tuple(path.relative_to(SRC).with_suffix("").parts[:-1])


def _resolve_import(path: Path, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module
    package = _package_parts(path)
    base = package[: len(package) - (node.level - 1)]
    if not node.module:
        return ".".join(base)
    return ".".join([*base, node.module])


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve_import(path, node)
            if resolved:
                modules.append(resolved)
    return modules


def test_no_reverse_dependency_from_spu_to_step_stage_or_supporting_patterns():
    """SPU -> Step [FORBIDDEN (reverse)]; SPU never imports higher layers."""
    offenders = []
    for py_file in sorted(SPU_DIR.rglob("*.py")):
        for module in _imported_modules(py_file):
            if module.startswith(FORBIDDEN_IMPORT_PREFIXES):
                offenders.append(f"{py_file}: {module}")
    assert not offenders, f"SPU modules import a forbidden layer: {offenders}"


def test_prefect_state_never_enters_the_spu_domain_result():
    """The SPU result family must not reference Prefect State in any form."""
    offenders = []
    for py_file in sorted(SPU_DIR.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        for module in _imported_modules(py_file):
            if module.split(".")[0] == "prefect":
                offenders.append(f"{py_file}: import {module}")
        for forbidden_symbol in ("PrefectState", "prefect.states", "State["):
            if forbidden_symbol in source:
                offenders.append(f"{py_file}: references {forbidden_symbol}")
    assert not offenders, f"Prefect operational state leaked into SPU layer: {offenders}"


def test_step_processing_unit_exposes_exactly_the_generic_execute_operation():
    """execute(input: TInput) -> SPUExecutionResult[TOutput]; no ExecutionContext."""
    spu_unit = SPU_DIR / "spu" / "spu_unit.py"
    tree = ast.parse(spu_unit.read_text(encoding="utf-8"), filename=str(spu_unit))

    execute = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "StepProcessingUnit":
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and member.name == "execute":
                    execute = member
    assert execute is not None, "StepProcessingUnit.execute is missing"

    positional = [arg.arg for arg in execute.args.posonlyargs + execute.args.args]
    assert positional == ["self", "input"], positional
    assert not execute.args.kwonlyargs
    assert not execute.args.kwarg
    source = ast.unparse(execute)
    assert "ExecutionContext" not in source, (
        "no universal execution-context parameter may be introduced"
    )


def test_spu_execution_result_carries_exactly_the_three_optional_elements():
    """Three independently optional elements; no universal success/status field."""
    results_init = SPU_DIR / "spu" / "results" / "__init__.py"
    tree = ast.parse(results_init.read_text(encoding="utf-8"), filename=str(results_init))

    fields = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "SPUExecutionResult":
            fields = [
                statement
                for statement in node.body
                if isinstance(statement, ast.AnnAssign)
            ]
    assert fields is not None, "SPUExecutionResult is missing"
    field_names = [statement.target.id for statement in fields]
    assert field_names == [
        "processing_artifact",
        "spu_error_occurrences",
        "validator_result",
    ]
