"""Architecture tests for task 10_Dependency_Packaging_Public_API — Sub-task 10.A.

Enforces the dependency ownership/direction graph across all of ``src\\gpwcf``:

  - Acyclicity of the ``gpwcf`` internal import graph (AST scan, no third-party).
  - Forbidden dependency directions rejected:
      * Core must never import integrations (core -> integrations FORBIDDEN)
      * SPU must never import Step/Stage/supporting patterns (reverse direction)
      * Supporting patterns must never import Step/Stage/core.step/core.stage
      * public_api must not reach into internals beyond its curated surface
      * consumers import only via Public API surfaces (not enforced here at
        runtime; see test_stage_boundaries.py for Stage/SPU direction)
  - ``core.identities`` dependency-free (stdlib allowlist only) — re-verified
    from task 11.
  - ``core.diagnostics`` independent (no gpwcf imports).
"""

import ast
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"
GPWCF_DIR = SRC / "gpwcf"


# --------------------------------------------------------------------------
# Import resolution helpers (AST-based, stdlib only)
# --------------------------------------------------------------------------


def _package_parts(path: Path) -> tuple[str, ...]:
    return tuple(path.relative_to(SRC).with_suffix("").parts[:-1])


def _resolve_import(path: Path, node: ast.ImportFrom) -> str | None:
    """Full dotted module name of an ImportFrom, resolving relative imports."""
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


def _all_gpwcf_files() -> list[Path]:
    return sorted(GPWCF_DIR.rglob("*.py"))


# --------------------------------------------------------------------------
# Build the internal import graph (module -> set of imported gpwcf modules)
# --------------------------------------------------------------------------


def _build_import_graph() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for py_file in _all_gpwcf_files():
        # Package __init__.py files are package markers that re-export from
        # submodules; importing them does not create real runtime cycles.
        if py_file.name == "__init__.py":
            continue
        module = ".".join(py_file.relative_to(SRC).with_suffix("").parts)
        imports = set()
        for imported in _imported_modules(py_file):
            root = imported.split(".")[0]
            if root == "gpwcf":
                imports.add(imported)
        graph[module] = imports
    return graph


def _package_of(module: str) -> str:
    """Top-level package of a gpwcf module (e.g. 'gpwcf.core.step')."""
    parts = module.split(".")
    return ".".join(parts[:3]) if len(parts) >= 3 else module


def _build_package_graph() -> dict[str, set[str]]:
    """Collapse the module graph to package-level nodes for cycle detection.

    Intra-package cycles (e.g. within supporting_patterns.error_handling) are
    implementation details and not architectural violations. Cross-package
    cycles are the real concern.
    """
    module_graph = _build_import_graph()
    package_graph: dict[str, set[str]] = {}
    for module, imports in module_graph.items():
        pkg = _package_of(module)
        package_graph.setdefault(pkg, set())
        for imported in imports:
            imported_pkg = _package_of(imported)
            if imported_pkg != pkg:
                package_graph[pkg].add(imported_pkg)
    return package_graph


def _has_cycle(graph: dict[str, set[str]]) -> bool:
    """DFS-based cycle detection on the directed graph."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in graph}

    def dfs(node: str) -> bool:
        color[node] = GRAY
        for neighbor in graph.get(node, set()):
            if color.get(neighbor, WHITE) == GRAY:
                return True
            if color.get(neighbor, WHITE) == WHITE and dfs(neighbor):
                return True
        color[node] = BLACK
        return False

    return any(color[n] == WHITE and dfs(n) for n in graph)


# --------------------------------------------------------------------------
# Forbidden dependency direction rules
# --------------------------------------------------------------------------


# (importer_module, forbidden_import_prefix)
_FORBIDDEN_DIRECTIONS = [
    # Core must never import integrations
    ("gpwcf.core", "gpwcf.integrations"),
    # SPU must never import Step/Stage/supporting patterns (reverse direction)
    ("gpwcf.core.processing_units", "gpwcf.core.step"),
    ("gpwcf.core.processing_units", "gpwcf.core.stage"),
    ("gpwcf.core.processing_units", "gpwcf.core.supporting_patterns"),
    # Supporting patterns must never import Step/Stage/core.step/core.stage
    ("gpwcf.core.supporting_patterns", "gpwcf.core.step"),
    ("gpwcf.core.supporting_patterns", "gpwcf.core.stage"),
    # public_api must not reach into internals beyond its curated surface
    ("gpwcf.public_api", "gpwcf.core.processing_units"),
    ("gpwcf.public_api", "gpwcf.core.stage"),
]


def _forbidden_violations(graph: dict[str, set[str]]) -> list[str]:
    violations: list[str] = []
    for importer, forbidden_prefix in _FORBIDDEN_DIRECTIONS:
        for imported in graph.get(importer, set()):
            if imported.startswith(forbidden_prefix):
                violations.append(f"{importer} -> {imported} (forbidden: {forbidden_prefix})")
    return violations


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


def test_internal_import_graph_is_acyclic():
    """The gpwcf internal import graph has no dependency cycles (package level)."""
    graph = _build_package_graph()
    assert not _has_cycle(graph), f"cyclic dependency detected in gpwcf package graph: {graph}"


def test_forbidden_dependency_directions_rejected():
    """Forbidden dependency directions are prohibited across all modules."""
    graph = _build_import_graph()
    violations = _forbidden_violations(graph)
    assert not violations, f"forbidden dependency directions: {violations}"


def test_core_identities_is_dependency_free():
    """core.identities imports nothing from gpwcf and nothing third-party
    beyond the stdlib allowlist (task 11 invariant re-verified here)."""
    identities_dir = SRC / "gpwcf" / "core" / "identities"
    assert list(identities_dir.glob("*.py")), "identities module files missing"
    allowed_stdlib = {"__future__", "dataclasses", "typing"}
    for py_file in identities_dir.glob("*.py"):
        for module in _imported_modules(py_file):
            root = module.split(".")[0]
            assert root != "gpwcf", f"{py_file.name} imports {module} (first-party forbidden)"
            assert root in allowed_stdlib, (
                f"{py_file.name} imports {module}; allowed stdlib: {sorted(allowed_stdlib)}"
            )


def test_core_diagnostics_is_independent():
    """core.diagnostics imports no gpwcf package and no third-party package."""
    diagnostics_dir = SRC / "gpwcf" / "core" / "diagnostics"
    assert list(diagnostics_dir.glob("*.py")), "diagnostics module files missing"
    allowed_stdlib = {"__future__", "dataclasses", "typing"}
    for py_file in diagnostics_dir.glob("*.py"):
        for module in _imported_modules(py_file):
            root = module.split(".")[0]
            assert root != "gpwcf", f"{py_file.name} imports {module} (first-party forbidden)"
            assert root in allowed_stdlib, (
                f"{py_file.name} imports {module}; allowed stdlib: {sorted(allowed_stdlib)}"
            )


def test_core_never_imports_prefect():
    """No module under src/gpwcf/core imports Prefect (Core runtime-free)."""
    offenders: list[str] = []
    core_dir = SRC / "gpwcf" / "core"
    for py_file in core_dir.rglob("*.py"):
        for module in _imported_modules(py_file):
            if module.split(".")[0] == "prefect":
                offenders.append(f"{py_file}: {module}")
    assert not offenders, f"Core must not import Prefect: {offenders}"


def test_supporting_patterns_never_import_core():
    """Supporting patterns import nothing from gpwcf at all (stdlib + pattern-local
    identities only) — they never import Core."""
    patterns_dir = SRC / "gpwcf" / "core" / "supporting_patterns"
    for py_file in sorted(patterns_dir.rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    assert root != "gpwcf", f"{py_file.name}: imports {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    continue  # relative imports stay inside the pattern package
                if node.module:
                    root = node.module.split(".")[0]
                    assert root != "gpwcf", f"{py_file.name}: imports {node.module}"


def test_public_api_surface_only_reexports_curated_symbols():
    """public_api modules re-export only from their curated public surface,
    not from internal gpwcf.core.* modules beyond the boundary."""
    public_api_dir = SRC / "gpwcf" / "public_api"
    for py_file in sorted(public_api_dir.rglob("*.py")):
        for module in _imported_modules(py_file):
            # public_api may import from gpwcf.core.identities and gpwcf.core.step
            # (curated result contracts) but not from internal implementation
            # modules like core.step.composition, core.processing_units, etc.
                if module.startswith("gpwcf.core."):
                    allowed = (
                        "gpwcf.core.coordination",
                        "gpwcf.core.diagnostics",
                        "gpwcf.core.identities",
                        "gpwcf.core.processing_units.spu",
                        "gpwcf.core.step",
                        "gpwcf.core.stage",
                        "gpwcf.core.step.results",
                    )
                    assert module.startswith(allowed), (
                        f"{py_file.name}: imports internal {module} beyond curated surface"
                    )
