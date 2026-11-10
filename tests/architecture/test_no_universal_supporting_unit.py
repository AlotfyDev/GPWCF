"""Architecture tests for task 08_Common_Coordination.

Enforces the framework's structural non-negotiables across all of ``src\\gpwcf``:

  - No universal Supporting Unit / universal runtime component base type is
    defined anywhere (no ``SupportingUnit`` base class, no ``Component`` root,
    no universal ``ExecutionContext``).
  - No universal registry/manager/lifecycle-machine abstractions.
  - Coordination contracts depend on nothing above ``core.identities``
    (plus their own package).
  - Dependency direction: SPU never imports Step/Stage/supporting patterns;
    supporting patterns never import Step/Stage/SPU modules.
"""

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"
GPWCF_DIR = SRC / "gpwcf"

# Universal abstractions explicitly forbidden by the architecture documents.
_FORBIDDEN_CLASS_NAMES = {
    "SupportingUnit",
    "GenericSupportingUnit",
    "UniversalSupportingUnit",
    "SupportingUnitBase",
    "ExecutionContext",
    "UniversalExecutionContext",
    "Component",
    "UniversalComponent",
    "RuntimeComponent",
    "RuntimeComponentBase",
    "ComponentBase",
    "LifecycleManager",
    "AssociationRegistry",
    "ComponentRegistry",
    "IdentityRegistry",
    "IdentityGenerator",
}


def _python_files():
    return sorted(GPWCF_DIR.rglob("*.py"))


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


def _class_definitions(path: Path) -> list[ast.ClassDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]


def _offending_files() -> list[str]:
    offenders = []
    for py_file in _python_files():
        for class_def in _class_definitions(py_file):
            if class_def.name in _FORBIDDEN_CLASS_NAMES:
                offenders.append(f"{py_file}: class {class_def.name}")
                continue
            for base in class_def.bases:
                base_name = (
                    base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)
                )
                if base_name in _FORBIDDEN_CLASS_NAMES:
                    offenders.append(f"{py_file}: {class_def.name} inherits {base_name}")
    return offenders


def test_no_universal_supporting_unit_or_component_base_anywhere():
    """No Generic Supporting Unit / universal runtime component type in src\\gpwcf."""
    offenders = _offending_files()
    assert not offenders, f"universal abstractions defined: {offenders}"


def test_no_universal_registry_manager_or_lifecycle_machine_types():
    """Coordination stays a contract; Step Composition owns the actual state."""
    offenders = _offending_files()
    assert not offenders, f"universal manager/registry types defined: {offenders}"


def test_coordination_depends_on_nothing_above_core_identities():
    """Coordination modules import only stdlib, core.identities, or their own package."""
    coordination_dir = GPWCF_DIR / "core" / "coordination"
    allowed_prefixes = ("gpwcf.core.identities", "gpwcf.core.coordination")
    offenders = []
    for py_file in sorted(coordination_dir.rglob("*.py")):
        for module in _imported_modules(py_file):
            if module.split(".")[0] == "gpwcf" and not module.startswith(allowed_prefixes):
                offenders.append(f"{py_file}: {module}")
    assert not offenders, f"coordination exceeded its dependency boundary: {offenders}"


def test_spu_never_imports_step_stage_or_supporting_patterns():
    """Dependency direction: SPU must never import Step/Stage/supporting patterns."""
    spu_dir = GPWCF_DIR / "core" / "processing_units"
    forbidden_prefixes = (
        "gpwcf.core.step",
        "gpwcf.core.stage",
        "gpwcf.core.supporting_patterns",
    )
    offenders = []
    for py_file in sorted(spu_dir.rglob("*.py")):
        for module in _imported_modules(py_file):
            if module.startswith(forbidden_prefixes):
                offenders.append(f"{py_file}: {module}")
    assert not offenders, f"SPU imports a higher layer: {offenders}"


def test_supporting_patterns_never_import_step_stage_or_processing_units():
    """Supporting patterns stay independent of Step/Stage and of the SPU layer."""
    patterns_dir = GPWCF_DIR / "core" / "supporting_patterns"
    forbidden_prefixes = (
        "gpwcf.core.step",
        "gpwcf.core.stage",
        "gpwcf.core.processing_units",
    )
    offenders = []
    for py_file in sorted(patterns_dir.rglob("*.py")):
        for module in _imported_modules(py_file):
            if module.startswith(forbidden_prefixes):
                offenders.append(f"{py_file}: {module}")
    assert not offenders, f"supporting pattern imports a forbidden layer: {offenders}"
