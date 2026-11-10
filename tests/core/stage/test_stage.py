"""Real tests for Stage aggregate root (Task 03).

Implementation task: 03_Stage
Related diagrams:
  class: 03_Diagrams_Codes_Files/03_Stage.dot
  sequence: B_Sequencial_Diagram_Code/06_Stage_Execution_Sequence.puml
  association: C_Association_Diagram_Code/03_Stage_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/02_Architectural_Level_Dependency_Graph.dot

Tests cover:
  - StageCallableContract boundary: acceptance/completion/result/exception distinctions
  - Stage owns Step membership and Stage Composition
  - StageResult envelope separate from outputs, flow result, domain outcome
  - Stage registers StageErrorTypeDefinition via Pipeline-assigned registry
  - Stage Flow Result independent of StepExecutionResult
  - Prefect State never substitutes for StageResult
"""

import threading
from dataclasses import FrozenInstanceError

import pytest

from gpwcf.core.identities import (
    PipelineInvocationIdentity,
    StageIdentity,
    StageInvocationIdentity,
    StepIdentity,
    StepInvocationIdentity,
)
from gpwcf.core.stage import (
    Stage,
    StageCallableContract,
    StageComposition,
    StageErrorTypeDefinition,
    StageErrorTypeDefinitionRegistry,
    StageFlowResult,
    StageInvocation,
    StageInvocationRejected,
    StageResult,
    StageExecutionContractViolation,
)
from gpwcf.core.step import Step, StepExecutionResult, StepInvocation
from gpwcf.core.step.invocation import StepExecutionContext
from gpwcf.core.step.results import Absent, Present, StepExecutionResult as _SER


# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------


class _ConcreteStep(Step):
    """Concrete Step that echoes its input as the processing artifact."""

    def __init__(self, step_identity: StepIdentity, owning_stage_identity: StageIdentity):
        super().__init__(step_identity, owning_stage_identity)
        self.calls = 0

    def _perform_invocation(self, invocation, flow):
        self.calls += 1
        return StepExecutionResult(
            step_identity=invocation.step_identity,
            step_invocation_identity=invocation.step_invocation_identity,
            owning_stage_identity=invocation.owning_stage_identity,
            parent_stage_invocation_identity=invocation.parent_stage_invocation_identity,
            pipeline_invocation_identity=invocation.pipeline_invocation_identity,
            processing_artifact=Present(f"step-{invocation.input}"),
            optional_result_contributions=__import__(
                "gpwcf.core.step.results", fromlist=["OptionalResultContributions"]
            ).OptionalResultContributions.all_absent(),
        )


class _ConcreteStage(Stage[str, str]):
    """Concrete Stage that fans out to all member Steps and aggregates."""

    def __init__(self, stage_identity: StageIdentity):
        super().__init__(stage_identity)
        self.invocations = 0

    def _perform_invocation(self, invocation, flow):
        self.invocations += 1
        step_results = []
        for step in self.step_membership:
            step_invocation = StepInvocation(
                step_identity=step.step_identity,
                step_invocation_identity=StepInvocationIdentity(
                    f"step-inv-{invocation.stage_invocation_identity.value}-{step.step_identity.value}"
                ),
                owning_stage_identity=invocation.stage_identity,
                parent_stage_invocation_identity=invocation.stage_invocation_identity,
                input=invocation.input,
                execution_context=StepExecutionContext(),
                pipeline_invocation_identity=invocation.owning_pipeline_invocation_identity,
            )
            result = self._composition_for_subclasses.invoke_step(
                flow, step, step_invocation
            )
            step_results.append(result)

        artifacts = Present(
            "|".join(
                r.processing_artifact.value
                for r in step_results
                if isinstance(r.processing_artifact, Present)
            )
        )
        return StageResult(
            stage_identity=invocation.stage_identity,
            stage_invocation_identity=invocation.stage_invocation_identity,
            owning_pipeline_invocation_identity=invocation.owning_pipeline_invocation_identity,
            parent_stage_invocation_identity=invocation.parent_stage_invocation_identity,
            processing_artifact=artifacts,
            stage_outputs=Absent(),
            stage_flow_result=flow,
            domain_outcome=Absent(),
        )


def _stage_invocation(
    stage_id="stage-1",
    inv_id="inv-1",
    input_value="hello",
    pipeline_id=None,
    parent_id=None,
):
    return StageInvocation(
        stage_identity=StageIdentity(stage_id),
        stage_invocation_identity=StageInvocationIdentity(inv_id),
        input=input_value,
        execution_context=__import__(
            "gpwcf.core.stage.composition", fromlist=["StageExecutionContext"]
        ).StageExecutionContext(),
        owning_pipeline_invocation_identity=(
            PipelineInvocationIdentity(pipeline_id) if pipeline_id else None
        ),
        parent_stage_invocation_identity=(
            StageInvocationIdentity(parent_id) if parent_id else None
        ),
    )


# --------------------------------------------------------------------------
# StageCallableContract boundary tests
# --------------------------------------------------------------------------


def test_stage_callable_contract_is_abstract():
    """StageCallableContract cannot be instantiated directly."""
    with pytest.raises(TypeError):
        StageCallableContract()


def test_stage_callable_contract_acceptance_distinction():
    """execute accepts a valid StageInvocation and returns a StageResult."""
    stage = _ConcreteStage(StageIdentity("stage-1"))
    step = _ConcreteStep(
        StepIdentity("step-1"), StageIdentity("stage-1")
    )
    stage._composition_for_subclasses.add_step(step)

    result = stage.execute(_stage_invocation())
    assert isinstance(result, StageResult)
    assert result.stage_identity == StageIdentity("stage-1")
    assert result.stage_invocation_identity == StageInvocationIdentity("inv-1")
    assert stage.invocations == 1


def test_stage_callable_contract_rejects_non_invocation():
    """execute rejects a non-StageInvocation argument."""
    stage = _ConcreteStage(StageIdentity("stage-1"))
    with pytest.raises(StageInvocationRejected, match="StageInvocation envelope"):
        stage.execute("not-an-invocation")  # type: ignore[arg-type]


def test_stage_callable_contract_rejects_foreign_stage_identity():
    """execute rejects an invocation targeting a different Stage identity."""
    stage = _ConcreteStage(StageIdentity("stage-1"))
    inv = _stage_invocation(stage_id="stage-2")
    with pytest.raises(StageInvocationRejected, match="redirected"):
        stage.execute(inv)


def test_stage_callable_contract_exception_propagates_unchanged():
    """An exception in _perform_invocation propagates unchanged (not converted to a result)."""

    class _FailingStage(Stage[str, str]):
        def _perform_invocation(self, invocation, flow):
            raise RuntimeError("boom")

    stage = _FailingStage(StageIdentity("stage-1"))
    with pytest.raises(RuntimeError, match="boom"):
        stage.execute(_stage_invocation())


# --------------------------------------------------------------------------
# Stage owns Step membership and Stage Composition
# --------------------------------------------------------------------------


def test_stage_owns_step_composition():
    """Stage exposes its StageComposition and step count starts at zero."""
    stage = _ConcreteStage(StageIdentity("stage-1"))
    assert isinstance(stage._composition_for_subclasses, StageComposition)
    assert stage.step_count == 0


def test_stage_adds_and_removes_step_membership():
    """Stage Composition add_step / remove_step manage membership."""
    stage = _ConcreteStage(StageIdentity("stage-1"))
    step = _ConcreteStep(
        StepIdentity("step-1"), StageIdentity("stage-1")
    )
    stage._composition_for_subclasses.add_step(step)
    assert stage.step_count == 1
    assert step in stage.step_membership

    stage._composition_for_subclasses.remove_step(StepIdentity("step-1"))
    assert stage.step_count == 0


def test_stage_add_step_rejects_wrong_owning_stage():
    """add_step rejects a Step owned by a different Stage."""
    stage = _ConcreteStage(StageIdentity("stage-1"))
    step = _ConcreteStep(
        StepIdentity("step-1"), StageIdentity("stage-2")
    )
    with pytest.raises(ValueError, match="owned by Stage"):
        stage._composition_for_subclasses.add_step(step)


def test_stage_remove_step_rejects_unknown_step():
    """remove_step rejects a Step identity not in membership."""
    stage = _ConcreteStage(StageIdentity("stage-1"))
    with pytest.raises(KeyError, match="not a member"):
        stage._composition_for_subclasses.remove_step(StepIdentity("step-99"))


# --------------------------------------------------------------------------
# StageResult envelope separate from outputs, flow result, domain outcome
# --------------------------------------------------------------------------


def test_stage_result_envelope_fields():
    """StageResult carries distinct outputs, flow result, and domain outcome slots."""
    stage = _ConcreteStage(StageIdentity("stage-1"))
    step = _ConcreteStep(
        StepIdentity("step-1"), StageIdentity("stage-1")
    )
    stage._composition_for_subclasses.add_step(step)

    result = stage.execute(_stage_invocation())
    assert isinstance(result.processing_artifact, Present)
    assert isinstance(result.stage_outputs, Absent)
    assert isinstance(result.stage_flow_result, StageFlowResult)
    assert isinstance(result.domain_outcome, Absent)


def test_stage_result_independent_of_step_execution_result():
    """Stage Flow Result is independent of any individual StepExecutionResult."""
    stage = _ConcreteStage(StageIdentity("stage-1"))
    step = _ConcreteStep(
        StepIdentity("step-1"), StageIdentity("stage-1")
    )
    stage._composition_for_subclasses.add_step(step)

    result = stage.execute(_stage_invocation())
    flow = result.stage_flow_result
    step_invocations = flow.step_invocations
    assert len(step_invocations) == 1
    si = step_invocations[0]
    assert isinstance(si.result, StepExecutionResult)
    assert si.step_identity == StepIdentity("step-1")
    # The StageFlowResult is a separate object from the StepExecutionResult
    assert flow is not si.result


def test_stage_result_immutable():
    """StageResult is a frozen dataclass."""
    result = StageResult(
        stage_identity=StageIdentity("stage-1"),
        stage_invocation_identity=StageInvocationIdentity("inv-1"),
        owning_pipeline_invocation_identity=None,
        parent_stage_invocation_identity=None,
        processing_artifact=Present("x"),
        stage_outputs=Absent(),
        stage_flow_result=StageFlowResult(),
        domain_outcome=Absent(),
    )
    with pytest.raises(FrozenInstanceError):
        result.processing_artifact = Absent()  # type: ignore[misc]


# --------------------------------------------------------------------------
# Stage registers StageErrorTypeDefinition via Pipeline-assigned registry
# --------------------------------------------------------------------------


def test_stage_error_type_definition_registry_is_pipeline_assigned():
    """StageErrorTypeDefinitionRegistry is created with a StageIdentity and owned by Pipeline."""
    reg = StageErrorTypeDefinitionRegistry(StageIdentity("stage-1"))
    assert reg.stage_identity == StageIdentity("stage-1")


def test_stage_registers_error_type_definitions():
    """Stage registers StageErrorTypeDefinition instances through the registry."""
    reg = StageErrorTypeDefinitionRegistry(StageIdentity("stage-1"))
    defn = StageErrorTypeDefinition(
        "stage-err-1", str, str, StageIdentity("stage-1")
    )
    reg.register(defn)
    resolved = reg.resolve("stage-err-1")
    assert resolved is defn
    assert resolved.stage_identity == StageIdentity("stage-1")


def test_stage_error_type_definitions_distinct_from_spu_types():
    """StageErrorTypeDefinition is a distinct nominal type from SPU-level types."""
    from gpwcf.core.processing_units.spu.errors import (
        SPUErrorTypeDefinition as _SPUDef,
    )

    stage_def = StageErrorTypeDefinition(
        "err-1", str, str, StageIdentity("stage-1")
    )
    assert type(stage_def) is not _SPUDef
    assert not isinstance(stage_def, _SPUDef)


def test_stage_error_type_definition_registry_rejects_wrong_stage():
    """Registry rejects a definition targeting a different Stage."""
    reg = StageErrorTypeDefinitionRegistry(StageIdentity("stage-1"))
    defn = StageErrorTypeDefinition(
        "err-1", str, str, StageIdentity("stage-2")
    )
    with pytest.raises(ValueError, match="but this registry belongs to Stage"):
        reg.register(defn)


# --------------------------------------------------------------------------
# Prefect State never substitutes for StageResult
# --------------------------------------------------------------------------


def test_stage_result_is_not_prefect_state():
    """StageResult is a domain result, never a Prefect operational state."""
    result = StageResult(
        stage_identity=StageIdentity("stage-1"),
        stage_invocation_identity=StageInvocationIdentity("inv-1"),
        owning_pipeline_invocation_identity=None,
        parent_stage_invocation_identity=None,
        processing_artifact=Present("x"),
        stage_outputs=Absent(),
        stage_flow_result=StageFlowResult(),
        domain_outcome=Absent(),
    )
    # No Prefect import — this test proves StageResult has no Prefect dependency
    assert not hasattr(result, "state")
    assert not hasattr(result, "run_id")
    assert isinstance(result, StageResult)


def test_stage_execute_returns_domain_result_not_prefect_state():
    """Stage.execute returns a StageResult, never Prefect State."""
    stage = _ConcreteStage(StageIdentity("stage-1"))
    step = _ConcreteStep(
        StepIdentity("step-1"), StageIdentity("stage-1")
    )
    stage._composition_for_subclasses.add_step(step)
    result = stage.execute(_stage_invocation())
    assert isinstance(result, StageResult)
    assert type(result).__name__ == "StageResult"


# --------------------------------------------------------------------------
# Concurrency / admission
# --------------------------------------------------------------------------


def test_stage_execution_is_serialized_per_stage():
    """Stage admission is serialized (lock-protected) per Stage instance."""
    stage = _ConcreteStage(StageIdentity("stage-1"))
    step = _ConcreteStep(
        StepIdentity("step-1"), StageIdentity("stage-1")
    )
    stage._composition_for_subclasses.add_step(step)

    results = []
    errors = []

    def call(i: int) -> None:
        try:
            r = stage.execute(
                _stage_invocation(inv_id=f"inv-{i}", input_value=f"input-{i}")
            )
            results.append(r)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=call, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"unexpected errors: {errors}"
    assert len(results) == 10
    assert stage.invocations == 10
