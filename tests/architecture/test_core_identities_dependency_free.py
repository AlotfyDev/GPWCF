"""Architecture tests for task 11_Core_Identities_Diagnostics.

Covers:
  - core.identities is dependency-free (stdlib allowlist only, no gpwcf imports)
  - core.diagnostics is independent (no gpwcf imports; no Error Model taxonomy defined)
  - Importing both modules in a clean interpreter loads no third-party modules
  - Core (all of src/gpwcf/core) imports no Prefect (day-one guard; full scan
    enforcement lands with task 09)
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"
CORE_DIR = SRC / "gpwcf" / "core"
IDENTITIES_DIR = CORE_DIR / "identities"
DIAGNOSTICS_DIR = CORE_DIR / "diagnostics"

# stdlib modules these two narrow modules are allowed to use
_ALLOWED_STDLIB = {"__future__", "dataclasses", "typing"}


def _imported_modules(path: Path) -> list[str]:
    """All imported modules (absolute roots plus full dotted names) in one file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import: first-party by definition
                modules.append("gpwcf")
            elif node.module:
                modules.append(node.module)
    return modules


def _defined_class_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]


def test_core_identities_is_dependency_free():
    """core.identities: stdlib allowlist only; nothing from gpwcf; nothing third-party."""
    assert list(IDENTITIES_DIR.glob("*.py")), "identities module files missing"
    for py_file in IDENTITIES_DIR.glob("*.py"):
        for module in _imported_modules(py_file):
            root = module.split(".")[0]
            assert root != "gpwcf", f"{py_file.name} imports {module} (first-party forbidden)"
            assert root in _ALLOWED_STDLIB, (
                f"{py_file.name} imports {module}; allowed stdlib: {sorted(_ALLOWED_STDLIB)}"
            )


def test_core_identities_defines_only_nominal_identity_types():
    """Pinned class set. Task 02 (04.00_Step_Callable.json) requires
    StepInvocationIdentity and StageInvocationIdentity here: the Step callable
    consumes these nominal value types from the canonical dependency-free
    identities module — still identity value types ONLY, no generators."""
    classes = _defined_class_names(IDENTITIES_DIR / "__init__.py")
    assert set(classes) == {
        "_IdentityValue",
        "PipelineInvocationIdentity",
        "StageIdentity",
        "StageInvocationIdentity",
        "StepIdentity",
        "StepInvocationIdentity",
        "SPUIdentity",
        "InvocationIdentity",
    }


def test_core_diagnostics_is_independent():
    """core.diagnostics imports no gpwcf package and no third-party package (DIAG-008)."""
    assert list(DIAGNOSTICS_DIR.glob("*.py")), "diagnostics module files missing"
    for py_file in DIAGNOSTICS_DIR.glob("*.py"):
        for module in _imported_modules(py_file):
            root = module.split(".")[0]
            assert root != "gpwcf", f"{py_file.name} imports {module} (first-party forbidden)"
            assert root in _ALLOWED_STDLIB, (
                f"{py_file.name} imports {module}; allowed stdlib: {sorted(_ALLOWED_STDLIB)}"
            )


def test_core_diagnostics_defines_no_error_model_taxonomy():
    """No Error/Failure/Outcome/Severity taxonomy classes may exist here (DIAG-005, DIAG-009)."""
    classes = _defined_class_names(DIAGNOSTICS_DIR / "__init__.py")
    assert set(classes) == {"DiagnosticCode", "Diagnostic"}


def test_importing_both_modules_loads_no_third_party_package():
    """Clean-interpreter proof: import adds only stdlib and gpwcf modules."""
    probe = (
        "import sys; baseline = set(sys.modules); "
        "import gpwcf.core.identities, gpwcf.core.diagnostics; "
        "added = {m.split('.')[0] for m in set(sys.modules) - baseline}; "
        "third_party = sorted(added - set(sys.stdlib_module_names) - {'gpwcf'}); "
        "print('|'.join(third_party))"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    result = subprocess.run(
        [sys.executable, "-s", "-c", probe],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
        check=True,
    )
    assert result.stdout.strip() == "", f"third-party modules loaded: {result.stdout}"


def test_core_does_not_import_prefect():
    """No module under src/gpwcf/core may import Prefect (Core stays runtime-free)."""
    offenders = []
    for py_file in CORE_DIR.rglob("*.py"):
        for module in _imported_modules(py_file):
            if module.split(".")[0] == "prefect":
                offenders.append(f"{py_file}: {module}")
    assert not offenders, f"Core must not import Prefect: {offenders}"
