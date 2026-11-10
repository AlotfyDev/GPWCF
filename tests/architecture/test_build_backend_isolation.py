"""Build backend isolation tests (Task 10.D).

Verifies:
  - pyproject.toml declares setuptools==84.2.1 as the isolated build backend
  - Build-system dependencies are isolated from runtime dependencies
  - Core-only installation works without Prefect (metadata inspection)
  - Prefect extra is declared as prefect==3.9.2
"""

import ast
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = PROJECT_ROOT / "pyproject.toml"


def _parse_pyproject():
    import tomllib

    with open(PYPROJECT, "rb") as f:
        return tomllib.load(f)


def test_pyproject_exists():
    """pyproject.toml exists at project root."""
    assert PYPROJECT.is_file(), "pyproject.toml is missing"


def test_build_backend_is_setuptools_pinned():
    """[build-system] requires setuptools==84.2.1 exact pin."""
    data = _parse_pyproject()
    requires = data["build-system"]["requires"]
    assert "setuptools==84.2.1" in requires, (
        f"build-system requires must contain setuptools==84.2.1, got {requires}"
    )
    assert data["build-system"]["build-backend"] == "setuptools.build_meta"


def test_build_backend_isolated_from_runtime():
    """Build-system requires contains only setuptools; no runtime deps in [build-system]."""
    data = _parse_pyproject()
    requires = data["build-system"]["requires"]
    for req in requires:
        # Build requirements should not include prefect, pygccxml, or any runtime dep
        name = req.split("==")[0].split(">=")[0].split("<")[0].split("!=")[0].strip()
        assert name not in ("prefect", "pygccxml"), (
            f"build-system requires contains runtime dep: {req}"
        )


def test_core_runtime_dependencies_empty():
    """[project].dependencies is empty (Core is stdlib-only)."""
    data = _parse_pyproject()
    assert data["project"]["dependencies"] == [], (
        f"Core runtime dependencies must be empty, got {data['project']['dependencies']}"
    )


def test_prefect_extra_declared():
    """[project.optional-dependencies] prefect = [prefect==3.9.2]."""
    data = _parse_pyproject()
    optional = data["project"]["optional-dependencies"]
    assert "prefect" in optional, f"prefect extra missing from optional-dependencies: {optional}"
    assert optional["prefect"] == ["prefect==3.9.2"], (
        f"prefect extra must be [prefect==3.9.2], got {optional['prefect']}"
    )


def test_no_prefect_in_core_dependencies():
    """Prefect does not appear in core [project].dependencies."""
    data = _parse_pyproject()
    deps = data["project"]["dependencies"]
    for dep in deps:
        name = dep.split("==")[0].split(">=")[0].split("<")[0].strip()
        assert name != "prefect", f"Prefect must not be in core dependencies: {dep}"


def test_pyproject_has_required_metadata_fields():
    """[project] contains required PEP 621 fields."""
    data = _parse_pyproject()
    required = ["name", "version", "description", "readme", "requires-python", "dependencies"]
    for field in required:
        assert field in data["project"], f"[project] missing required field: {field}"


def test_package_discovery_uses_src_layout():
    """Package discovery is rooted at src with gpwcf* include."""
    data = _parse_pyproject()
    find = data["tool"]["setuptools"]["packages"]["find"]
    assert "src" in find["where"], f"Package discovery where must include src: {find['where']}"
    assert "gpwcf*" in find["include"], f"Package discovery include must include gpwcf*: {find['include']}"


def test_package_dir_is_src():
    """[tool.setuptools] package-dir maps root package to src."""
    data = _parse_pyproject()
    pd = data["tool"]["setuptools"]["package-dir"]
    assert pd == {"": "src"}, f"package-dir must be {{'': 'src'}}, got {pd}"


def test_py_typed_included():
    """py.typed is included in package data."""
    data = _parse_pyproject()
    pkg_data = data["tool"]["setuptools"]["package-data"]["gpwcf"]
    assert "py.typed" in pkg_data, f"py.typed must be in package-data: {pkg_data}"


def test_core_public_api_importable_without_prefect():
    """Core Public API imports successfully without Prefect (import isolation)."""
    # Fresh subprocess to guarantee clean import state
    import subprocess

    probe = (
        "import sys; "
        "baseline = set(sys.modules); "
        "from gpwcf.public_api.core import Stage, Step, StageResult, StepExecutionResult; "
        "added = {m.split('.')[0] for m in set(sys.modules) - baseline}; "
        "third_party = sorted(added - set(sys.stdlib_module_names) - {'gpwcf'}); "
        "print('|'.join(third_party))"
    )
    import os

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
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


def test_prefect_extra_is_opt_in_not_base():
    """prefect==3.9.2 is only in optional-dependencies, never in base dependencies."""
    data = _parse_pyproject()
    base = data["project"]["dependencies"]
    optional = data["project"]["optional-dependencies"]
    for dep in base:
        assert "prefect" not in dep.lower(), f"Prefect must not be in base dependencies: {dep}"
    assert "prefect" in optional
    assert optional["prefect"] == ["prefect==3.9.2"]
