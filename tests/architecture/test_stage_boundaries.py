"""Architecture boundary tests for Stage (Task 03 DoD).

Enforces:
  - Core not permitted to import Prefect (placeholder until task 09, then enforced for real)
  - Stage Composition does not import SPUs or supporting units directly — only Steps
  - Stage sees only Step's public contract and StepExecutionResult
"""

import ast
import sys

import pytest

from gpwcf.core.stage import Stage, StageResult


def _module_source_tree(mod):
    """Return the set of top-level import module names used by a module."""
    import inspect

    src = inspect.getsource(mod)
    tree = ast.parse(src)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    return imports


def test_core_stage_module_does_not_import_prefect():
    """Architecture boundary: gpwcf.core.stage must not import Prefect (task 09 gate).

    Prefect may only appear under gpwcf.integrations.prequad and must be an
    optional import there. Core remains standard-library-only.
    """
    import gpwcf.core.stage as stage_mod
    import gpwcf.core.stage.composition as comp_mod
    import gpwcf.core.stage.results as results_mod
    import gpwcf.core.stage.errors as errors_mod

    modules = [stage_mod, comp_mod, results_mod, errors_mod]
    for mod in modules:
        imports = _module_source_tree(mod)
        assert "prefect" not in imports, f"{mod.__name__} imports Prefect: {imports}"


def test_stage_composition_does_not_import_spu_directly():
    """Stage Composition must not import core.processing_units.spu (Stage->Step->SPU direction)."""
    import gpwcf.core.stage.composition as comp_mod

    imports = _module_source_tree(comp_mod)
    assert "processing_units" not in imports, f"composition imports processing_units: {imports}"
    assert "spu" not in imports, f"composition imports spu: {imports}"


def test_stage_sees_only_step_public_contract():
    """Stage Composition references Step and StepExecutionResult only (public boundary)."""
    import gpwcf.core.stage.composition as comp_mod

    src = inspect_getsource_safe(comp_mod)
    assert "from gpwcf.core.step import" in src
    assert "StepExecutionResult" in src
    assert "StepInvocation" in src


def inspect_getsource_safe(mod):
    import inspect

    return inspect.getsource(mod)


def test_stage_result_is_not_prefect_state():
    """StageResult has no Prefect State attributes — Prefect State is operational evidence, not a domain result."""
    result = StageResult(
        stage_identity=__import__("gpwcf.core.identities", fromlist=["StageIdentity"]).StageIdentity("stage-1"),
        stage_invocation_identity=__import__("gpwcf.core.identities", fromlist=["StageInvocationIdentity"]).StageInvocationIdentity("inv-1"),
        owning_pipeline_invocation_identity=None,
        parent_stage_invocation_identity=None,
        processing_artifact=__import__("gpwcf.core.step.results", fromlist=["Present"]).Present("x"),
        stage_outputs=__import__("gpwcf.core.step.results", fromlist=["Absent"]).Absent(),
        stage_flow_result=__import__("gpwcf.core.stage.results", fromlist=["StageFlowResult"]).StageFlowResult(),
        domain_outcome=__import__("gpwcf.core.step.results", fromlist=["Absent"]).Absent(),
    )
    for attr in ("state", "run_id", "flow_run_id", "task_run_id", "deployment_id"):
        assert not hasattr(result, attr), f"StageResult must not expose Prefect operational attribute {attr}"


def test_stage_callable_contract_is_proper_abc():
    """StageCallableContract is an abstract base class (cannot be instantiated)."""
    import abc
    from gpwcf.core.stage import StageCallableContract

    assert abc.ABC in StageCallableContract.__mro__
    with pytest.raises(TypeError):
        StageCallableContract()  # type: ignore[abstract]
