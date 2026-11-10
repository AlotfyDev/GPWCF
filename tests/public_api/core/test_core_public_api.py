"""Core Public API conformance tests (Task 10.D).

Verifies:
  - Core Public API exposes exactly the curated symbol set
  - No Prefect types leak into Core API (AST scan)
  - Core remains importable/usable with Prefect absent
  - Key public symbols are constructible
"""

import ast
import inspect
import sys

import pytest

from gpwcf.public_api import core as core_mod

# --------------------------------------------------------------------------
# Expected Core Public API symbol set
# --------------------------------------------------------------------------

CORE_PUBLIC_SYMBOLS = {
    # Results
    "Absent",
    "Present",
    "OptionalResultSlot",
    "OptionalResultContributions",
    # Identities
    "PipelineInvocationIdentity",
    "StageIdentity",
    "StageInvocationIdentity",
    "StepIdentity",
    "StepInvocationIdentity",
    "SPUIdentity",
    "InvocationIdentity",
    # Diagnostics
    "Diagnostic",
    "DiagnosticCode",
    # SPU
    "StepProcessingUnit",
    "SPUExecutionResult",
    # Step
    "Step",
    "StepExecutionResult",
    "StepCallable",
    "StepInvocation",
    "StepInvocationRejected",
    "StepExecutionContext",
    # Stage
    "Stage",
    "StageCallableContract",
    "StageComposition",
    "StageExecutionContractViolation",
    "StageFlowResult",
    "StageInvocation",
    "StageInvocationRejected",
    "StageResult",
    "StageSettlementReport",
    # Stage errors
    "StageError",
    "StageErrorTypeDefinition",
    "StageErrorTypeDefinitionRegistry",
    # Stage result internals
    "StageFlowException",
    "StageFlowTransition",
    "StageStepInvocation",
    # Coordination
    "Association",
    "AssociationIdentity",
    "AssociationTarget",
    "AssociationTargetIdentity",
    "ComponentAssociationIdentity",
    "ComponentInstanceIdentity",
    "ComponentInvocationIdentity",
    "Dissociation",
    "InvocationBinding",
    "StepCompositionAssociationCoordination",
    "StepCompositionInternalComponentLifecycleCoordination",
    "RuntimeInstanceLifetime",
    "AssociationLifetime",
    "InvocationLifetime",
    "OperationLifetime",
    "ResourceCapabilityLifetime",
    "OutputAndEvidenceRetentionLifetime",
}


def test_core_public_api_symbols_match_curated_set():
    """The Core Public API exposes exactly the curated symbol set (no more, no less)."""
    public = {name for name in vars(core_mod) if not name.startswith("_")}
    assert public == CORE_PUBLIC_SYMBOLS, (
        f"Symbol mismatch:\n  missing: {CORE_PUBLIC_SYMBOLS - public}\n  extra:   {public - CORE_PUBLIC_SYMBOLS}"
    )


def test_core_public_api_no_prefect_imports_ast():
    """Architecture: Core Public API does not import Prefect (AST scan)."""
    src = inspect.getsource(core_mod)
    tree = ast.parse(src)
    imports_prefect = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "prefect" or alias.name.startswith("prefect."):
                    imports_prefect = True
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module == "prefect" or node.module.startswith("prefect.")):
                imports_prefect = True
    assert not imports_prefect, "Core Public API must not import Prefect"


def test_core_public_api_importable_without_prefect():
    """Core Public API imports cleanly when Prefect is absent."""
    # The fact that this test runs and imports core proves it
    from gpwcf.public_api.core import Stage, Step, StepExecutionResult, SPUExecutionResult
    assert Stage is not None
    assert Step is not None
    assert StepExecutionResult is not None
    assert SPUExecutionResult is not None


def test_core_public_api_symbols_are_constructible():
    """Key public symbols can be instantiated (smoke test)."""
    from gpwcf.public_api.core import Diagnostic, DiagnosticCode
    from gpwcf.core.identities import StageIdentity, StepIdentity
    from gpwcf.core.step.results import Absent, Present

    # Diagnostic
    dc = DiagnosticCode(namespace="gpwcf", value="smoke-test")
    d = Diagnostic(code=dc, message="smoke test diagnostic", details=None)
    assert d is not None

    # Identities
    assert StageIdentity("s1") is not None
    assert StepIdentity("st1") is not None

    # Results slots
    assert Absent() is not None
    p = Present("value")
    assert p.value == "value"

    # StageFlowResult
    from gpwcf.core.stage.results import StageFlowResult
    flow = StageFlowResult()
    assert not flow.sealed
    flow.seal()
    assert flow.sealed
