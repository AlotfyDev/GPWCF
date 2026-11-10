"""Unit tests for the Step aggregate root (task 02_Step).

Implementation task: 02_Step
Related diagrams:
  class: 03_Diagrams_Codes_Files/02_Step.dot
  sequence: B_Sequencial_Diagram_Code/05_Step_Execution_Sequence.puml
  association: C_Association_Diagram_Code/02_Step_Associations.puml

Tests cover:
  - execute(invocation) -> StepExecutionResult: happy path, identity copying,
    SPUExecutionResult consumed internally (never returned as the Step result)
  - OptionalResultSlot semantics: Present(None) vs Absent, all-absent bundle,
    raw values refused, closed supporting-result categories
  - Rejection paths: StepInvocationRejected (no fabricated result, no silent
    identity reuse, foreign identity scope)
  - Exception paths: propagation unchanged, invocation stays unsettled,
    earlier evidence retained, SPU result contract violations
  - Custody/settlement: leak is a contract violation; identity mismatch is a
    contract violation
  - Public lifecycle through the Step boundary (retain/reuse/retire)
  - 05/06 cross-check: the concrete Step drives ValidatorUnitAssociations /
    ObservationUnitAssociations as the Step-Composition authority; observation
    records stay OUT of the StepExecutionResult
"""

from __future__ import annotations

import itertools
from typing import Never, Sequence

import pytest

from gpwcf.core.identities import (
    PipelineInvocationIdentity,
    SPUIdentity,
    StageIdentity,
    StageInvocationIdentity,
    StepIdentity,
    StepInvocationIdentity,
)
from gpwcf.core.processing_units.spu import (
    SPUErrorTypeDefinitionRegistry,
    SPUErrorTypeDefinitionRegistryIdentity,
    SPUExecutionResult,
    StepProcessingUnit,
)
from gpwcf.core.step import (
    ABSENT,
    Absent,
    OptionalResultContributions,
    Present,
    Step,
    StepCompositionFlowResult,
    StepExecutionContractViolation,
    StepExecutionResult,
    StepExecutionContext,
    StepInvocation,
    StepInvocationRejected,
    StepLifecycleDisposition,
    StepLifecycleError,
    StepLifecycleOutcome,
    StepLifecycleStatus,
)
from gpwcf.core.supporting_patterns.observation import (
    AssociationTargetIdentity as ObservationTargetIdentity,
    AssociationTargetScopeKind as ObservationTargetScopeKind,
    ObservationInvocationIdentity,
    ObservationRecord,
    ObservationRecordIdentity,
    ObservationUnitAssociationIdentity,
    ObservationUnitAssociations,
    ObservationUnitIdentity,
    ObservationUnitLifecycle,
    SPUObservationUnit,
)
from gpwcf.core.supporting_patterns.validation import (
    AssociationTargetIdentity as ValidatorTargetIdentity,
    AssociationTargetScopeKind as ValidatorTargetScopeKind,
    SPUValidatorResult,
    SPUValidatorUnit,
    ValidatorInvocationIdentity,
    ValidatorUnitAssociationIdentity,
    ValidatorUnitAssociations,
    ValidatorUnitIdentity,
    ValidatorUnitLifecycle,
)

STEP_IDENTITY = StepIdentity("step-1")
STAGE_IDENTITY = StageIdentity("stage-1")
STAGE_INVOCATION_IDENTITY = StageInvocationIdentity("stage-inv-1")
SPU_IDENTITY = SPUIdentity("spu-1")

_invocation_counter = itertools.count(1)


# --------------------------------------------------------------------------
# Fixtures: stub SPU and concrete Steps
# --------------------------------------------------------------------------


def a_registry() -> SPUErrorTypeDefinitionRegistry:
    return SPUErrorTypeDefinitionRegistry(
        SPUErrorTypeDefinitionRegistryIdentity("registry-1"), SPU_IDENTITY
    )


class _UpperCaserSPU(StepProcessingUnit[str, str]):
    """Concrete SPU: actual processing; models documented failure flows."""

    def __init__(self) -> None:
        super().__init__(a_registry())

    def execute(self, input: str) -> SPUExecutionResult[str, dict]:
        if input == "explode":
            raise _ExplodeError("spu prevented execute from returning")
        if input == "wrong-type":
            return "not an SPUExecutionResult"  # type: ignore[return-value]
        return SPUExecutionResult(processing_artifact=input.upper())


class _ExplodeError(RuntimeError):
    """Dedicated exception so 1:1 propagation is provable by exact type."""


class _PipelineStep(Step[str, str, str, Never, Never]):
    """Concrete Step: drives one SPU; optional validator contribution."""

    def __init__(
        self,
        *,
        spu: StepProcessingUnit | None = None,
        validator_contribution: object | None = None,
        record_validator: bool = False,
        artifact_present: bool = True,
    ) -> None:
        super().__init__(STEP_IDENTITY, STAGE_IDENTITY)
        self._spu = spu if spu is not None else _UpperCaserSPU()
        self._validator_contribution = validator_contribution
        self._record_validator = record_validator
        self._artifact_present = artifact_present

    def _perform_invocation(
        self, invocation: StepInvocation[str], flow: StepCompositionFlowResult
    ) -> StepExecutionResult[str, str, Never, Never]:
        composition = self._composition_for_subclasses
        spu_result = composition.invoke_spu(flow, SPU_IDENTITY, self._spu, invocation.input)
        if self._record_validator:
            composition.record_supporting_result(
                flow, "validator_result", self._validator_contribution
            )
        artifact: Absent | Present[str] = (
            Present(spu_result.processing_artifact) if self._artifact_present else Absent()
        )
        return composition.assemble_step_result(invocation, flow, processing_artifact=artifact)


class _LeakCustodyStep(_PipelineStep):
    """Concrete Step that accepts custody AFTER assembling (contract violation)."""

    def _perform_invocation(
        self, invocation: StepInvocation[str], flow: StepCompositionFlowResult
    ) -> StepExecutionResult[str, str, Never, Never]:
        result = super()._perform_invocation(invocation, flow)
        self._composition_for_subclasses.record_supporting_result(
            flow, "error_result", "accepted too late"
        )
        return result


class _ForgedIdentityStep(_PipelineStep):
    """Concrete Step that returns a result with a mismatched invocation identity."""

    def _perform_invocation(
        self, invocation: StepInvocation[str], flow: StepCompositionFlowResult
    ) -> StepExecutionResult[str, str, Never, Never]:
        forged = StepExecutionResult(
            step_identity=invocation.step_identity,
            step_invocation_identity=StepInvocationIdentity("someone-elses-invocation"),
            owning_stage_identity=invocation.owning_stage_identity,
            parent_stage_invocation_identity=invocation.parent_stage_invocation_identity,
            pipeline_invocation_identity=invocation.pipeline_invocation_identity,
            processing_artifact=Present("forged"),
            optional_result_contributions=OptionalResultContributions.all_absent(),
        )
        return forged


def an_invocation(
    input: str = "hello",
    *,
    step_identity: StepIdentity = STEP_IDENTITY,
    owning_stage_identity: StageIdentity = STAGE_IDENTITY,
    invocation_identity: StepInvocationIdentity | None = None,
    pipeline_invocation_identity: PipelineInvocationIdentity | None = None,
    execution_context: StepExecutionContext | None = None,
) -> StepInvocation[str]:
    return StepInvocation(
        step_identity=step_identity,
        step_invocation_identity=(
            invocation_identity
            if invocation_identity is not None
            else StepInvocationIdentity(f"inv-{next(_invocation_counter)}")
        ),
        owning_stage_identity=owning_stage_identity,
        parent_stage_invocation_identity=STAGE_INVOCATION_IDENTITY,
        input=input,
        execution_context=execution_context if execution_context is not None else StepExecutionContext(),
        pipeline_invocation_identity=pipeline_invocation_identity,
    )


# --------------------------------------------------------------------------
# Happy path and identity copying
# --------------------------------------------------------------------------


def test_execute_returns_exactly_step_execution_result():
    step = _PipelineStep()
    result = step.execute(an_invocation())
    assert type(result) is StepExecutionResult


def test_result_copies_identity_fields_unchanged_from_invocation():
    pipeline_identity = PipelineInvocationIdentity("pipeline-run-7")
    invocation = an_invocation(pipeline_invocation_identity=pipeline_identity)
    result = _PipelineStep().execute(invocation)
    assert result.step_identity == STEP_IDENTITY
    assert result.step_invocation_identity == invocation.step_invocation_identity
    assert result.owning_stage_identity == STAGE_IDENTITY
    assert result.parent_stage_invocation_identity == STAGE_INVOCATION_IDENTITY
    assert result.pipeline_invocation_identity == pipeline_identity


def test_result_without_pipeline_identity_carries_none():
    result = _PipelineStep().execute(an_invocation())
    assert result.pipeline_invocation_identity is None


def test_processing_artifact_is_present_and_spu_result_consumed_internally():
    result = _PipelineStep().execute(an_invocation(input="hello"))
    assert isinstance(result.processing_artifact, Present)
    assert result.processing_artifact.value == "HELLO"


def test_optional_contributions_structurally_present_all_slots_absent_by_default():
    result = _PipelineStep().execute(an_invocation())
    bundle = result.optional_result_contributions
    assert type(bundle) is OptionalResultContributions
    assert isinstance(bundle.validator_result, Absent)
    assert isinstance(bundle.error_result, Absent)
    assert isinstance(bundle.error_handler_result, Absent)


def test_step_is_abstract_and_owns_composition_privately():
    assert getattr(Step, "__abstractmethods__", set()), "Step must remain abstract"
    step = _PipelineStep()
    assert not hasattr(step, "composition"), "the composition stays hidden"
    assert type(step._composition).__name__ == "StepComposition"
    assert step.step_identity == STEP_IDENTITY
    assert step.owning_stage_identity == STAGE_IDENTITY


# --------------------------------------------------------------------------
# OptionalResultSlot semantics
# --------------------------------------------------------------------------


def test_validator_contribution_becomes_present_others_stay_absent():
    result = _PipelineStep(
        record_validator=True, validator_contribution="validation aggregate"
    ).execute(an_invocation())
    bundle = result.optional_result_contributions
    assert isinstance(bundle.validator_result, Present)
    assert bundle.validator_result.value == "validation aggregate"
    assert isinstance(bundle.error_result, Absent)
    assert isinstance(bundle.error_handler_result, Absent)


def test_present_none_is_distinct_from_absent():
    result = _PipelineStep(record_validator=True, validator_contribution=None).execute(
        an_invocation()
    )
    validator_slot = result.optional_result_contributions.validator_result
    assert isinstance(validator_slot, Present)
    assert not isinstance(validator_slot, Absent)
    assert validator_slot.value is None
    assert validator_slot != ABSENT


def test_processing_artifact_can_be_absent():
    result = _PipelineStep(artifact_present=False).execute(an_invocation())
    assert isinstance(result.processing_artifact, Absent)
    assert not isinstance(result.processing_artifact, Present)


def test_raw_values_are_refused_as_slot_states():
    with pytest.raises(TypeError, match="OptionalResultSlot"):
        OptionalResultContributions(
            validator_result="raw", error_result=ABSENT, error_handler_result=ABSENT
        )
    with pytest.raises(TypeError, match="OptionalResultSlot"):
        OptionalResultContributions(
            validator_result=ABSENT, error_result=None, error_handler_result=ABSENT
        )


def test_unknown_supporting_result_category_is_refused():
    step = _PipelineStep()
    invocation = an_invocation()
    flow = step._composition_for_subclasses.new_flow_result()
    with pytest.raises(ValueError, match="closed"):
        step._composition_for_subclasses.record_supporting_result(
            flow, "observation_records", "telemetry never enters the result"
        )


def test_duplicate_category_at_assembly_is_refused():
    step = _PipelineStep(record_validator=True, validator_contribution="first")
    invocation = an_invocation()

    class _DoubleValidatorStep(_PipelineStep):
        def _perform_invocation(self, invocation, flow):
            composition = self._composition_for_subclasses
            spu_result = composition.invoke_spu(flow, SPU_IDENTITY, self._spu, invocation.input)
            composition.record_supporting_result(flow, "validator_result", "first")
            composition.record_supporting_result(flow, "validator_result", "second")
            return composition.assemble_step_result(
                invocation, flow, processing_artifact=Present(spu_result.processing_artifact)
            )

    with pytest.raises(ValueError, match="ONE aggregate"):
        _DoubleValidatorStep().execute(invocation)


# --------------------------------------------------------------------------
# Rejection paths: StepInvocationRejected, no fabricated result
# --------------------------------------------------------------------------


def test_execute_rejects_a_non_invocation_argument():
    with pytest.raises(StepInvocationRejected, match="StepInvocation"):
        _PipelineStep().execute("bare input")  # type: ignore[arg-type]


def test_execute_rejects_foreign_step_identity_without_consuming_the_identity():
    step = _PipelineStep()
    foreign = an_invocation(step_identity=StepIdentity("step-2"))
    with pytest.raises(StepInvocationRejected, match="redirected"):
        step.execute(foreign)
    # The rejection happened before admission: the candidate identity is
    # still fresh and usable against the right Step instance — but only when
    # re-issued targeting the right Step (not the same foreign invocation).
    right_foreign = StepInvocation(
        step_identity=STEP_IDENTITY,
        step_invocation_identity=foreign.step_invocation_identity,
        owning_stage_identity=STAGE_IDENTITY,
        parent_stage_invocation_identity=STAGE_INVOCATION_IDENTITY,
        input=foreign.input,
        execution_context=foreign.execution_context,
        pipeline_invocation_identity=foreign.pipeline_invocation_identity,
    )
    right_step = _PipelineStep()
    result = right_step.execute(right_foreign)
    assert result.step_invocation_identity == foreign.step_invocation_identity


def test_execute_rejects_foreign_owning_stage_identity():
    foreign = an_invocation(owning_stage_identity=StageIdentity("stage-2"))
    with pytest.raises(StepInvocationRejected, match="owned"):
        _PipelineStep().execute(foreign)


def test_reused_invocation_identity_is_rejected():
    step = _PipelineStep()
    identity = StepInvocationIdentity("inv-reused")
    step.execute(an_invocation(invocation_identity=identity))
    with pytest.raises(StepInvocationRejected, match="never silently reused"):
        step.execute(an_invocation(invocation_identity=identity))


def test_reused_identity_rejected_even_after_reuse_reopens_admission():
    step = _PipelineStep()
    identity = StepInvocationIdentity("inv-then-reuse")
    step.execute(an_invocation(invocation_identity=identity))
    assert (
        step.request_lifecycle(StepLifecycleDisposition.RETAIN_FOR_REUSE)
        is StepLifecycleOutcome.CONFIRMED
    )
    step.confirm_reuse_readiness()
    with pytest.raises(StepInvocationRejected, match="never silently reused"):
        step.execute(an_invocation(invocation_identity=identity))


def test_rejected_invocation_fabricates_no_result_and_leaves_no_side_effects():
    step = _PipelineStep()
    with pytest.raises(StepInvocationRejected):
        step.execute(an_invocation(step_identity=StepIdentity("step-other")))
    # No flow result was opened, nothing is unsettled: clean retirement confirms.
    assert (
        step.request_lifecycle(StepLifecycleDisposition.RETIRE_TERMINALLY)
        is StepLifecycleOutcome.CONFIRMED
    )


# --------------------------------------------------------------------------
# Exception paths
# --------------------------------------------------------------------------


def test_spu_exception_propagates_unchanged_and_is_never_a_result():
    step = _PipelineStep(spu=_UpperCaserSPU())
    with pytest.raises(_ExplodeError) as caught:
        step.execute(an_invocation(input="explode"))
    # Exact type: the boundary neither wrapped nor converted the exception.
    assert type(caught.value) is _ExplodeError
    assert not isinstance(caught.value, StepExecutionResult)
    assert not isinstance(caught.value, StepInvocationRejected)


    step = _PipelineStep(spu=_UpperCaserSPU())
    with pytest.raises(RuntimeError):
        step.execute(an_invocation(input="explode"))
    outcome = step.request_lifecycle(StepLifecycleDisposition.RETIRE_TERMINALLY)
    assert outcome is StepLifecycleOutcome.FAILED
    assert step.lifecycle_status is StepLifecycleStatus.QUARANTINED


def test_exception_keeps_all_earlier_evidence_in_the_flow_result():
    step = _PipelineStep(spu=_UpperCaserSPU())
    with pytest.raises(RuntimeError):
        step.execute(an_invocation(input="explode"))
    flows = step._composition_for_subclasses._flow_results
    assert len(flows) == 1
    flow = flows[0]
    assert flow.exceptions, "the exception is retained as invocation evidence"
    assert flow.exceptions[0].phase == "component_invocation"
    assert flow.exceptions[-1].phase == "step_invocation"
    assert not flow.sealed


def test_spu_returning_a_non_result_is_recorded_and_refused():
    step = _PipelineStep(spu=_UpperCaserSPU())
    with pytest.raises(TypeError, match="exactly SPUExecutionResult"):
        step.execute(an_invocation(input="wrong-type"))
    flow = step._composition_for_subclasses._flow_results[0]
    assert flow.exceptions[0].phase == "component_result_contract"
    assert flow.exceptions[-1].phase == "step_invocation"


def test_step_execution_result_is_distinct_from_spu_execution_result():
    step = _PipelineStep()
    result = step.execute(an_invocation())
    assert type(result) is not SPUExecutionResult
    assert not isinstance(result, SPUExecutionResult)
    assert not issubclass(StepExecutionResult, SPUExecutionResult)
    assert not issubclass(SPUExecutionResult, StepExecutionResult)


# --------------------------------------------------------------------------
# Custody/settlement contract violations
# --------------------------------------------------------------------------


def test_custody_accepted_after_assembly_is_a_settlement_violation():
    step = _LeakCustodyStep(record_validator=True, validator_contribution="late custody")
    with pytest.raises(StepExecutionContractViolation, match="incomplete"):
        step.execute(an_invocation())
    # The invocation stays unsettled: no disposition can confirm over the leak.
    assert (
        step.request_lifecycle(StepLifecycleDisposition.RETIRE_TERMINALLY)
        is StepLifecycleOutcome.FAILED
    )


def test_result_with_mismatched_invocation_identity_is_a_contract_violation():
    step = _ForgedIdentityStep()
    with pytest.raises(StepExecutionContractViolation, match="never generates or replaces"):
        step.execute(an_invocation())
    flows = step._composition_for_subclasses._flow_results
    assert not flows[-1].sealed, "a violating invocation never settles"


# --------------------------------------------------------------------------
# Public lifecycle through the Step boundary
# --------------------------------------------------------------------------


def test_retain_confirms_but_keeps_admission_closed():
    step = _PipelineStep()
    assert (
        step.request_lifecycle(StepLifecycleDisposition.RETAIN_FOR_REUSE)
        is StepLifecycleOutcome.CONFIRMED
    )
    assert step.lifecycle_status is StepLifecycleStatus.RETAINED_FOR_REUSE
    with pytest.raises(StepInvocationRejected, match="draining or retained"):
        step.execute(an_invocation())


def test_reuse_readiness_reopens_admission_for_new_invocations():
    step = _PipelineStep()
    step.request_lifecycle(StepLifecycleDisposition.RETAIN_FOR_REUSE)
    step.confirm_reuse_readiness()
    assert step.lifecycle_status is StepLifecycleStatus.IN_SERVICE
    result = step.execute(an_invocation())
    assert isinstance(result, StepExecutionResult)


def test_retire_confirms_terminally_and_reopen_is_refused():
    step = _PipelineStep()
    assert (
        step.request_lifecycle(StepLifecycleDisposition.RETIRE_TERMINALLY)
        is StepLifecycleOutcome.CONFIRMED
    )
    assert step.lifecycle_status is StepLifecycleStatus.TERMINALLY_RETIRED
    with pytest.raises(StepInvocationRejected, match="terminally closed"):
        step.execute(an_invocation())
    with pytest.raises(StepLifecycleError, match="reuse readiness"):
        step.confirm_reuse_readiness()


def test_confirmed_disposition_rereads_are_idempotent():
    step = _PipelineStep()
    assert (
        step.request_lifecycle(StepLifecycleDisposition.RETIRE_TERMINALLY)
        is StepLifecycleOutcome.CONFIRMED
    )
    assert (
        step.request_lifecycle(StepLifecycleDisposition.RETIRE_TERMINALLY)
        is StepLifecycleOutcome.CONFIRMED
    )
    reused_step = _PipelineStep()
    reused_step.request_lifecycle(StepLifecycleDisposition.RETAIN_FOR_REUSE)
    assert (
        reused_step.request_lifecycle(StepLifecycleDisposition.RETAIN_FOR_REUSE)
        is StepLifecycleOutcome.CONFIRMED
    )


def test_lifecycle_outcome_is_a_distinct_interaction_from_step_result():
    step = _PipelineStep()
    outcome = step.request_lifecycle(StepLifecycleDisposition.RETIRE_TERMINALLY)
    assert type(outcome) is StepLifecycleOutcome
    assert not isinstance(outcome, StepExecutionResult)
    assert outcome is not StepLifecycleOutcome.CONFIRMED or outcome.value == "confirmed"


# --------------------------------------------------------------------------
# 05/06 cross-check: Step Composition is the association authority
# --------------------------------------------------------------------------


class _CaseValidatorUnit(SPUValidatorUnit[str, None, str, str]):
    def evaluate(self, validation_input, target_context):
        return ("conforms" if validation_input.isupper() else "does-not-conform"), "evidence"


def test_step_composition_drives_validator_unit_associations_end_to_end():
    """The concrete Step (via Step Composition authority) establishes the
    validator association, authorizes one validation invocation, and its
    StepValidatorResult travels the optional contribution slot."""
    unit_identity = ValidatorUnitIdentity("validator-1")
    lifecycle = ValidatorUnitLifecycle(unit_identity)
    lifecycle.provision()
    lifecycle.mark_prepared()
    lifecycle.determine_ready()
    lifecycle.admit()
    book = ValidatorUnitAssociations(
        unit_identity, lifecycle, step_instance_identity=STEP_IDENTITY.value
    )
    association_identity = ValidatorUnitAssociationIdentity("assoc-1")
    association = book.establish(
        association_identity, ValidatorTargetIdentity(ValidatorTargetScopeKind.STEP, "target-scope-1")
    )
    assert book.usable_for_invocation(association_identity)

    unit = _CaseValidatorUnit(unit_identity)
    step = _PipelineStep()

    class _ValidatingStep(_PipelineStep):
        def _perform_invocation(self, invocation, flow):
            composition = self._composition_for_subclasses
            spu_result = composition.invoke_spu(flow, SPU_IDENTITY, self._spu, invocation.input)
            validator_result = unit.validate(
                association=association,
                validator_invocation_identity=ValidatorInvocationIdentity("vinv-1"),
                step_instance_identity=STEP_IDENTITY.value,
                validation_input=invocation.input,
            )
            assert isinstance(validator_result, SPUValidatorResult)
            composition.record_supporting_result(
                flow, "validator_result", validator_result
            )
            return composition.assemble_step_result(
                invocation, flow, processing_artifact=Present(spu_result.processing_artifact)
            )

    result = _ValidatingStep().execute(an_invocation(input="HELLO"))
    validator_slot = result.optional_result_contributions.validator_result
    assert isinstance(validator_slot, Present)
    assert type(validator_slot.value) is SPUValidatorResult
    assert validator_slot.value.validation_outcome == "conforms"
    assert (
        validator_slot.value.validator_unit_association_identity == association_identity
    )
    # The association authorizes further invocations until Step Composition ends it.
    assert book.usable_for_invocation(association_identity)


class _CounterObservationUnit(SPUObservationUnit[str, None, str]):
    def perform_observation(self, observation_input, target_context):
        return [("observed:" + str(observation_input), ObservationRecordIdentity("rec-1"))]


def test_step_composition_drives_observation_associations_and_records_stay_out_of_result():
    """Observation applicability is established by Step Composition authority;
    the records are retained OUTSIDE the StepExecutionResult contract."""
    unit_identity = ObservationUnitIdentity("observer-1")
    lifecycle = ObservationUnitLifecycle(unit_identity)
    lifecycle.provision()
    lifecycle.mark_prepared()
    lifecycle.determine_ready()
    lifecycle.admit()
    book = ObservationUnitAssociations(
        unit_identity, lifecycle, step_instance_identity=STEP_IDENTITY.value
    )
    association_identity = ObservationUnitAssociationIdentity("obs-assoc-1")
    association = book.establish(
        association_identity, ObservationTargetIdentity(ObservationTargetScopeKind.STEP, "observed-scope-1")
    )
    assert book.usable_for_activity(association_identity)

    unit = _CounterObservationUnit(unit_identity)
    captured: list[ObservationRecord[str]] = []

    class _ObservingStep(_PipelineStep):
        def _perform_invocation(self, invocation, flow):
            composition = self._composition_for_subclasses
            spu_result = composition.invoke_spu(flow, SPU_IDENTITY, self._spu, invocation.input)
            records = unit.observe(
                association=association,
                observation_invocation_identity=ObservationInvocationIdentity("oinv-1"),
                step_instance_identity=STEP_IDENTITY.value,
                observation_input=invocation.input,
            )
            captured.extend(records)
            return composition.assemble_step_result(
                invocation, flow, processing_artifact=Present(spu_result.processing_artifact)
            )

    result = _ObservingStep().execute(an_invocation(input="hello"))
    assert len(captured) == 1
    assert type(captured[0]) is ObservationRecord
    assert captured[0].payload == "observed:hello"
    # Observation records stay OUT of the Step result: no slot, no attribute.
    assert not hasattr(result, "observation_records")
    bundle = result.optional_result_contributions
    assert isinstance(bundle.validator_result, Absent)
    assert isinstance(bundle.error_result, Absent)
    assert isinstance(bundle.error_handler_result, Absent)
