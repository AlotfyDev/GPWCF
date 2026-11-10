"""Contract tests for the SPU Validator Unit pattern (task 05).

Covers (Step_Supporting_Validator_Unit_{Behavioral,Association,Lifecycle}_Contract.json):
  - SPUValidatorResult: full invocation/association provenance, domain-outcome
    semantics (negative conclusions are NOT invocation failures), independently
    optional evidence, invocation distinguishability, provenance stability
  - ValidatorUnitAssociation: association identity distinct from participant
    identities; applicability-only; stability; dissociation keeps history
  - ValidatorUnitLifecycle: milestones provisioned→prepared→ready→admitted→
    available/in-use→quiescing→retained-for-reuse→released; admission gating;
    quiescence blocks new invocations; release outcome recorded distinctly
    (failed/uncertain release is never labelled Released)
  - ValidatorUnitAssociations: Step-Composition-owned establishment (admitted
    instance required), identity uniqueness/no-reuse, multi-association
    cardinality freedom, dissociation-not-release
  - SPUValidatorUnit: invocation boundary (exact association binding, target
    from the association, no fabricated result on exception)
"""

import dataclasses

import pytest

from gpwcf.core.supporting_patterns.validation import (
    AssociationTargetIdentity,
    AssociationTargetScopeKind,
    SPUValidatorResult,
    SPUValidatorUnit,
    ValidatorInvocationIdentity,
    ValidatorUnitAssociation,
    ValidatorUnitAssociationIdentity,
    ValidatorUnitAssociations,
    ValidatorUnitIdentity,
    ValidatorUnitLifecycle,
    ValidatorUnitLifecyclePhase,
    ValidatorUnitReleaseOutcome,
)

STEP_ID = "step-instance-1"


def a_unit_identity(name: str = "validator-unit-1") -> ValidatorUnitIdentity:
    return ValidatorUnitIdentity(name)


def a_target(name: str = "spu-1") -> AssociationTargetIdentity:
    return AssociationTargetIdentity(AssociationTargetScopeKind.SPU, name)


def an_admitted_lifecycle(
    identity: ValidatorUnitIdentity | None = None,
) -> ValidatorUnitLifecycle:
    lifecycle = ValidatorUnitLifecycle(identity or a_unit_identity())
    lifecycle.provision()
    lifecycle.mark_prepared()
    lifecycle.determine_ready()
    lifecycle.admit()
    return lifecycle


def an_association_book(
    identity: ValidatorUnitIdentity | None = None,
    lifecycle: ValidatorUnitLifecycle | None = None,
) -> ValidatorUnitAssociations:
    unit_identity = identity or a_unit_identity()
    return ValidatorUnitAssociations(
        unit_identity,
        lifecycle or an_admitted_lifecycle(unit_identity),
        step_instance_identity=STEP_ID,
    )


class _NeverMatchingValidator(
    SPUValidatorUnit[str, str, str, str]
):
    """Concrete specialization: outcome IS the joined input (no pass/fail)."""

    def __init__(
        self,
        identity: ValidatorUnitIdentity,
        *,
        outcome: str = "shape-conforms",
        evidence: str | None = "dimensions-checked",
        raises: Exception | None = None,
    ) -> None:
        super().__init__(identity)
        self._outcome = outcome
        self._evidence = evidence
        self._raises = raises
        self.evaluation_count = 0

    def evaluate(
        self, validation_input: str, target_context: str | None
    ) -> tuple[str, str | None]:
        self.evaluation_count += 1
        if self._raises is not None:
            raise self._raises
        return self._outcome, self._evidence


# --------------------------------------------------------------------------
# identities: nominal separation
# --------------------------------------------------------------------------


def test_identity_types_are_nominal_and_never_conflatable():
    unit = ValidatorUnitIdentity("x-1")
    association = ValidatorUnitAssociationIdentity("x-1")
    invocation = ValidatorInvocationIdentity("x-1")

    # the same underlying string in different identity types never compares
    # equal: each identity names a DIFFERENT architectural fact
    assert unit != association
    assert unit != invocation
    assert association != invocation
    assert unit == ValidatorUnitIdentity("x-1")
    assert hash(unit) != hash(association)


def test_identities_reject_invalid_values():
    for identity_type in (
        ValidatorUnitIdentity,
        ValidatorUnitAssociationIdentity,
        ValidatorInvocationIdentity,
    ):
        with pytest.raises(TypeError):
            identity_type(123)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            identity_type("")
        with pytest.raises(ValueError):
            identity_type("   ")


def test_association_target_identity_requires_scope_kind_and_instance():
    target = AssociationTargetIdentity(AssociationTargetScopeKind.SPU, "spu-9")
    assert target.scope_kind is AssociationTargetScopeKind.SPU
    assert target.instance_identity == "spu-9"
    assert target == AssociationTargetIdentity(AssociationTargetScopeKind.SPU, "spu-9")
    assert target != AssociationTargetIdentity(
        AssociationTargetScopeKind.STEP, "spu-9"
    )
    # a bare SPU identity string can never stand in for a target identity
    with pytest.raises(TypeError):
        AssociationTargetIdentity("spu-9")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        AssociationTargetIdentity(AssociationTargetScopeKind.SPU, 9)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        AssociationTargetIdentity(AssociationTargetScopeKind.STEP, "  ")


# --------------------------------------------------------------------------
# SPUValidatorResult
# --------------------------------------------------------------------------


def a_result(
    *,
    invocation: str = "vinv-1",
    unit: ValidatorUnitIdentity | None = None,
    association: str = "assoc-1",
    target: AssociationTargetIdentity | None = None,
    outcome: str = "shape-conforms",
    evidence: str | None = "dimensions-checked",
) -> SPUValidatorResult[str, str]:
    return SPUValidatorResult[str, str](
        step_instance_identity=STEP_ID,
        validator_unit_identity=unit or a_unit_identity(),
        validator_unit_association_identity=ValidatorUnitAssociationIdentity(association),
        association_target_identity=target or a_target(),
        validator_invocation_identity=ValidatorInvocationIdentity(invocation),
        validation_outcome=outcome,
        validation_evidence=evidence,
    )


def test_result_carries_the_full_required_provenance():
    result = a_result()

    assert result.step_instance_identity == STEP_ID
    assert result.validator_unit_identity == a_unit_identity()
    assert result.validator_unit_association_identity == (
        ValidatorUnitAssociationIdentity("assoc-1")
    )
    assert result.association_target_identity == a_target()
    assert result.validator_invocation_identity == ValidatorInvocationIdentity("vinv-1")
    assert result.validation_outcome == "shape-conforms"


def test_validation_evidence_is_independently_optional():
    with_evidence = a_result()
    without_evidence = a_result(evidence=None)

    assert with_evidence.validation_evidence == "dimensions-checked"
    # absence of evidence is NOT a success/failure status
    assert without_evidence.validation_evidence is None
    assert without_evidence.validation_outcome == "shape-conforms"


def test_negative_validation_conclusion_is_still_a_normally_produced_result():
    """A rejection/invalidity outcome is a domain conclusion — never an
    exception, never an automatic invocation failure, never a flow decision."""
    result = a_result(
        outcome="noncompliant:tolerance-exceeded",
        evidence="measured=12.4 allowed=10.0",
    )

    # constructing/holding it requires nothing special; no status field exists
    assert result.validation_outcome == "noncompliant:tolerance-exceeded"
    field_names = {field.name for field in dataclasses.fields(result)}
    assert not field_names & {"passed", "failed", "success", "status", "valid"}


def test_results_from_different_invocations_remain_distinguishable():
    same_association = ValidatorUnitAssociationIdentity("assoc-1")
    first = a_result(invocation="vinv-1", association="assoc-1")
    second = a_result(invocation="vinv-2", association="assoc-1")

    # identical outcomes under the same association are still distinct results
    assert first.validation_outcome == second.validation_outcome
    assert first.validator_unit_association_identity == (
        second.validator_unit_association_identity
    )
    assert first != second
    assert (
        first.validator_invocation_identity != second.validator_invocation_identity
    )


def test_result_enforces_provenance_types_and_immutability():
    with pytest.raises(TypeError):
        SPUValidatorResult[str, str](
            step_instance_identity=STEP_ID,
            validator_unit_identity="validator-unit-1",  # type: ignore[arg-type]
            validator_unit_association_identity=(
                ValidatorUnitAssociationIdentity("assoc-1")
            ),
            association_target_identity=a_target(),
            validator_invocation_identity=ValidatorInvocationIdentity("vinv-1"),
            validation_outcome="ok",
        )
    with pytest.raises(ValueError):
        SPUValidatorResult[str, str](
            step_instance_identity="   ",
            validator_unit_identity=a_unit_identity(),
            validator_unit_association_identity=(
                ValidatorUnitAssociationIdentity("assoc-1")
            ),
            association_target_identity=a_target(),
            validator_invocation_identity=ValidatorInvocationIdentity("vinv-1"),
            validation_outcome="ok",
        )

    result = a_result()
    with pytest.raises(AttributeError):
        result.validation_outcome = "rewritten"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        result.validator_invocation_identity = (  # type: ignore[misc]
            ValidatorInvocationIdentity("vinv-9")
        )


def test_result_provenance_is_never_rewritten_when_association_ends():
    """Provenance stability: retained results keep their association identity
    even after the association ends (tested end-to-end with the book below)."""
    book = an_association_book()
    association = book.establish(
        ValidatorUnitAssociationIdentity("assoc-1"), a_target("spu-1")
    )
    unit = _NeverMatchingValidator(book.validator_unit_identity)
    result = unit.validate(
        association=association,
        validator_invocation_identity=ValidatorInvocationIdentity("vinv-1"),
        step_instance_identity=STEP_ID,
        validation_input="input",
    )
    book.end(ValidatorUnitAssociationIdentity("assoc-1"))

    # the retained result still names the ended association and target
    assert result.validator_unit_association_identity == (
        ValidatorUnitAssociationIdentity("assoc-1")
    )
    assert result.association_target_identity == a_target("spu-1")
    assert book.usable_for_invocation(ValidatorUnitAssociationIdentity("assoc-1")) is False


# --------------------------------------------------------------------------
# ValidatorUnitAssociation
# --------------------------------------------------------------------------


def test_association_identity_is_distinct_from_participant_identities():
    association = ValidatorUnitAssociation(
        association_identity=ValidatorUnitAssociationIdentity("assoc-1"),
        validator_unit_identity=ValidatorUnitIdentity("validator-unit-1"),
        association_target_identity=a_target("spu-1"),
        step_instance_identity=STEP_ID,
    )

    assert association.association_identity != association.validator_unit_identity
    assert association.association_identity != association.association_target_identity
    assert association.validator_unit_identity != association.association_target_identity


def test_association_records_step_target_and_scope_kind():
    association = ValidatorUnitAssociation(
        association_identity=ValidatorUnitAssociationIdentity("assoc-1"),
        validator_unit_identity=a_unit_identity(),
        association_target_identity=AssociationTargetIdentity(
            AssociationTargetScopeKind.STEP_INTERNAL, "stage-input-gate"
        ),
        step_instance_identity=STEP_ID,
    )
    assert association.step_instance_identity == STEP_ID
    assert association.target_scope_kind is AssociationTargetScopeKind.STEP_INTERNAL


def test_association_rejects_conflated_or_invalid_participants():
    with pytest.raises(TypeError):
        ValidatorUnitAssociation(
            association_identity=ValidatorUnitAssociationIdentity("assoc-1"),
            validator_unit_identity=ValidatorUnitIdentity("v-1"),
            # the target is not an AssociationTargetIdentity (conflation)
            association_target_identity=ValidatorUnitIdentity("spu-1"),  # type: ignore[arg-type]
            step_instance_identity=STEP_ID,
        )
    with pytest.raises(ValueError):
        ValidatorUnitAssociation(
            association_identity=ValidatorUnitAssociationIdentity("assoc-1"),
            validator_unit_identity=a_unit_identity(),
            association_target_identity=a_target(),
            step_instance_identity="   ",
        )


# --------------------------------------------------------------------------
# ValidatorUnitLifecycle
# --------------------------------------------------------------------------


def test_lifecycle_happy_path_provisioned_through_release():
    lifecycle = ValidatorUnitLifecycle(a_unit_identity())
    assert lifecycle.phase is None
    assert lifecycle.usable_for_invocation is False

    lifecycle.provision()
    assert lifecycle.phase is ValidatorUnitLifecyclePhase.PROVISIONED_OR_ACQUIRED
    lifecycle.mark_prepared()
    lifecycle.determine_ready()
    assert lifecycle.phase is ValidatorUnitLifecyclePhase.READY
    lifecycle.admit()
    assert lifecycle.usable_for_invocation is True
    lifecycle.begin_invocation()
    assert lifecycle.phase is ValidatorUnitLifecyclePhase.AVAILABLE_OR_IN_USE
    assert lifecycle.active_invocations == 1
    lifecycle.end_invocation()
    lifecycle.quiesce()
    assert lifecycle.usable_for_invocation is False
    lifecycle.retain_for_reuse()
    assert lifecycle.phase is ValidatorUnitLifecyclePhase.RETAINED_FOR_REUSE
    # reuse requires a fresh admission decision by Step Composition
    lifecycle.admit()
    assert lifecycle.phase is ValidatorUnitLifecyclePhase.ADMITTED
    lifecycle.quiesce()
    lifecycle.release()
    assert lifecycle.phase is ValidatorUnitLifecyclePhase.RELEASED
    assert lifecycle.release_outcome is ValidatorUnitReleaseOutcome.RELEASED


def test_admission_requires_readiness_and_invocation_requires_admission():
    lifecycle = ValidatorUnitLifecycle(a_unit_identity())
    with pytest.raises(ValueError):
        lifecycle.admit()  # not even provisioned

    lifecycle.provision()
    with pytest.raises(ValueError):
        lifecycle.admit()  # provisioned but not prepared/ready
    lifecycle.mark_prepared()
    with pytest.raises(ValueError):
        lifecycle.admit()  # prepared but not determined ready
    lifecycle.determine_ready()
    with pytest.raises(ValueError):
        lifecycle.begin_invocation()  # ready does NOT mean admitted

    lifecycle.admit()
    lifecycle.begin_invocation()
    # a double admission recording is refused while already admitted
    with pytest.raises(ValueError):
        lifecycle.admit()
    lifecycle.end_invocation()


def test_quiescence_blocks_new_invocations_but_lets_active_work_drain():
    lifecycle = an_admitted_lifecycle()
    lifecycle.begin_invocation()
    lifecycle.quiesce()

    with pytest.raises(ValueError):
        lifecycle.begin_invocation()
    assert lifecycle.usable_for_invocation is False
    lifecycle.end_invocation()  # active work drains
    assert lifecycle.active_invocations == 0
    # results already produced are not erased by quiescence (nothing to clear)
    assert lifecycle.phase is ValidatorUnitLifecyclePhase.QUIESCING


def test_release_requires_no_active_invocations():
    lifecycle = an_admitted_lifecycle()
    lifecycle.begin_invocation()
    with pytest.raises(ValueError):
        lifecycle.release()
    assert lifecycle.phase is ValidatorUnitLifecyclePhase.AVAILABLE_OR_IN_USE

    lifecycle.end_invocation()
    lifecycle.release()
    assert lifecycle.phase is ValidatorUnitLifecyclePhase.RELEASED


def test_failed_or_uncertain_release_is_never_labelled_released():
    for bad_outcome in (
        ValidatorUnitReleaseOutcome.RELEASE_FAILED,
        ValidatorUnitReleaseOutcome.RELEASE_OUTCOME_UNCERTAIN,
    ):
        lifecycle = an_admitted_lifecycle()
        lifecycle.quiesce()
        lifecycle.release(bad_outcome)
        assert lifecycle.phase is ValidatorUnitLifecyclePhase.QUIESCING
        assert lifecycle.release_outcome is bad_outcome
        assert lifecycle.phase is not ValidatorUnitLifecyclePhase.RELEASED
        assert lifecycle.usable_for_invocation is False


def test_release_before_provisioning_is_refused():
    lifecycle = ValidatorUnitLifecycle(a_unit_identity())
    with pytest.raises(ValueError):
        lifecycle.release()


def test_end_invocation_without_active_invocation_is_refused():
    lifecycle = an_admitted_lifecycle()
    with pytest.raises(ValueError):
        lifecycle.end_invocation()


def test_replacement_instance_receives_a_distinct_identity():
    first = ValidatorUnitLifecycle(ValidatorUnitIdentity("validator-unit-A"))
    first.provision()
    replacement = ValidatorUnitLifecycle(ValidatorUnitIdentity("validator-unit-A2"))

    # the replacement may share implementation/configuration but never identity
    assert first.identity != replacement.identity
    assert first.phase is ValidatorUnitLifecyclePhase.PROVISIONED_OR_ACQUIRED
    assert replacement.phase is None  # independent lifecycle


# --------------------------------------------------------------------------
# ValidatorUnitAssociations (Step-Composition-owned book)
# --------------------------------------------------------------------------


def test_establishment_requires_an_admitted_instance():
    unit_identity = a_unit_identity()
    lifecycle = ValidatorUnitLifecycle(unit_identity)
    book = an_association_book(unit_identity, lifecycle)

    with pytest.raises(ValueError):
        book.establish(ValidatorUnitAssociationIdentity("assoc-1"), a_target())
    lifecycle.provision()
    with pytest.raises(ValueError):
        book.establish(ValidatorUnitAssociationIdentity("assoc-1"), a_target())
    lifecycle.mark_prepared()
    lifecycle.determine_ready()
    with pytest.raises(ValueError):
        book.establish(ValidatorUnitAssociationIdentity("assoc-1"), a_target())

    lifecycle.admit()
    association = book.establish(ValidatorUnitAssociationIdentity("assoc-1"), a_target())
    assert association.validator_unit_identity == unit_identity
    assert association.step_instance_identity == STEP_ID
    assert book.usable_for_invocation(ValidatorUnitAssociationIdentity("assoc-1"))


def test_one_unit_may_serve_multiple_target_scopes():
    """No universal one-validator-per-SPU rule: three associations, one unit."""
    book = an_association_book()
    unit_identity = book.validator_unit_identity
    first = book.establish(ValidatorUnitAssociationIdentity("assoc-1"), a_target("spu-1"))
    second = book.establish(
        ValidatorUnitAssociationIdentity("assoc-2"), a_target("spu-2")
    )
    third = book.establish(
        ValidatorUnitAssociationIdentity("assoc-3"),
        AssociationTargetIdentity(AssociationTargetScopeKind.STEP, STEP_ID),
    )

    assert len(book.live_associations()) == 3
    for association in (first, second, third):
        # one validatorUnitIdentity, three DISTINCT association identities
        assert association.validator_unit_identity == unit_identity
        assert association.association_identity in {
            ValidatorUnitAssociationIdentity("assoc-1"),
            ValidatorUnitAssociationIdentity("assoc-2"),
            ValidatorUnitAssociationIdentity("assoc-3"),
        }
    assert book.associations_for_target(a_target("spu-1")) == (first,)
    assert book.associations_for_target(a_target("spu-2")) == (second,)


def test_one_target_may_be_served_by_multiple_validator_units():
    """No universal one-SPU-per-validator rule either: two units, one target."""
    book_1 = an_association_book(a_unit_identity("validator-unit-1"))
    book_2 = an_association_book(a_unit_identity("validator-unit-2"))

    association_1 = book_1.establish(
        ValidatorUnitAssociationIdentity("assoc-U1"), a_target("spu-shared")
    )
    association_2 = book_2.establish(
        ValidatorUnitAssociationIdentity("assoc-U2"), a_target("spu-shared")
    )

    assert association_1.association_target_identity == (
        association_2.association_target_identity
    )
    assert association_1.validator_unit_identity != association_2.validator_unit_identity
    assert association_1.association_identity != association_2.association_identity


def test_lifecycle_identity_must_match_the_book():
    lifecycle = an_admitted_lifecycle(a_unit_identity("validator-unit-1"))
    with pytest.raises(ValueError):
        ValidatorUnitAssociations(
            a_unit_identity("validator-unit-OTHER"),
            lifecycle,
            step_instance_identity=STEP_ID,
        )


def test_dissociation_keeps_history_does_not_release_and_spares_other_associations():
    book = an_association_book()
    first = book.establish(ValidatorUnitAssociationIdentity("assoc-1"), a_target("spu-1"))
    second = book.establish(ValidatorUnitAssociationIdentity("assoc-2"), a_target("spu-2"))

    ended = book.end(ValidatorUnitAssociationIdentity("assoc-1"))

    assert ended == first
    # no new invocation may rely on the ended association
    assert book.usable_for_invocation(ValidatorUnitAssociationIdentity("assoc-1")) is False
    assert book.get(ValidatorUnitAssociationIdentity("assoc-1")) is None
    # the other association is untouched
    assert book.usable_for_invocation(ValidatorUnitAssociationIdentity("assoc-2")) is True
    # historical provenance remains resolvable
    assert book.ended_associations() == (first,)
    # dissociation is NOT release: the instance lifecycle is untouched
    assert book._lifecycle.phase is ValidatorUnitLifecyclePhase.ADMITTED
    assert book.has_live_associations() is True
    book.end(ValidatorUnitAssociationIdentity("assoc-2"))
    assert book.has_live_associations() is False
    assert book._lifecycle.phase is ValidatorUnitLifecyclePhase.ADMITTED


def test_association_identity_is_never_reused_while_evidence_remains_observable():
    book = an_association_book()
    book.establish(ValidatorUnitAssociationIdentity("assoc-1"), a_target("spu-1"))
    book.end(ValidatorUnitAssociationIdentity("assoc-1"))

    # same target OR a different target: the identity stays retired
    with pytest.raises(ValueError):
        book.establish(ValidatorUnitAssociationIdentity("assoc-1"), a_target("spu-1"))
    with pytest.raises(ValueError):
        book.establish(ValidatorUnitAssociationIdentity("assoc-1"), a_target("spu-2"))
    # a logically similar re-establishment takes a NEW identity
    reestablished = book.establish(
        ValidatorUnitAssociationIdentity("assoc-1-reestablished"), a_target("spu-1")
    )
    assert reestablished.association_target_identity == a_target("spu-1")


def test_double_ending_and_unknown_ending_are_refused():
    book = an_association_book()
    book.establish(ValidatorUnitAssociationIdentity("assoc-1"), a_target())
    book.end(ValidatorUnitAssociationIdentity("assoc-1"))

    with pytest.raises(ValueError):
        book.end(ValidatorUnitAssociationIdentity("assoc-1"))
    with pytest.raises(KeyError):
        book.end(ValidatorUnitAssociationIdentity("assoc-unknown"))


def test_establishment_while_quiescing_is_refused():
    unit_identity = a_unit_identity()
    lifecycle = an_admitted_lifecycle(unit_identity)
    book = an_association_book(unit_identity, lifecycle)
    lifecycle.quiesce()

    with pytest.raises(ValueError):
        book.establish(ValidatorUnitAssociationIdentity("assoc-1"), a_target())


# --------------------------------------------------------------------------
# SPUValidatorUnit invocation boundary
# --------------------------------------------------------------------------


def a_bound_association(
    book: ValidatorUnitAssociations, name: str, target: AssociationTargetIdentity
) -> ValidatorUnitAssociation:
    return book.establish(ValidatorUnitAssociationIdentity(name), target)


def test_validate_produces_result_with_authoritative_provenance():
    book = an_association_book()
    association = a_bound_association(book, "assoc-1", a_target("spu-1"))
    validator = _NeverMatchingValidator(book.validator_unit_identity)

    result = validator.validate(
        association=association,
        validator_invocation_identity=ValidatorInvocationIdentity("vinv-1"),
        step_instance_identity=STEP_ID,
        validation_input="input-payload",
        target_context="live-target-context",
        validation_subject_reference="subject-42",
        completion_metadata="after-phase-2",
    )

    assert isinstance(result, SPUValidatorResult)
    assert result.validator_unit_identity == validator.identity
    assert result.validator_unit_association_identity == (
        ValidatorUnitAssociationIdentity("assoc-1")
    )
    # the target comes from the ASSOCIATION, never inferred from the input
    assert result.association_target_identity == a_target("spu-1")
    assert result.validation_outcome == "shape-conforms"
    assert result.validation_evidence == "dimensions-checked"
    assert result.validation_subject_reference == "subject-42"
    assert result.completion_metadata == "after-phase-2"
    assert validator.evaluation_count == 1


def test_repeated_invocations_under_one_association_stay_distinguishable():
    book = an_association_book()
    association = a_bound_association(book, "assoc-1", a_target())
    validator = _NeverMatchingValidator(book.validator_unit_identity)

    first = validator.validate(
        association=association,
        validator_invocation_identity=ValidatorInvocationIdentity("vinv-1"),
        step_instance_identity=STEP_ID,
        validation_input="input",
    )
    second = validator.validate(
        association=association,
        validator_invocation_identity=ValidatorInvocationIdentity("vinv-2"),
        step_instance_identity=STEP_ID,
        validation_input="input",
    )

    # the association identity is NOT a substitute for the invocation identity
    assert first != second
    assert first.validator_invocation_identity != second.validator_invocation_identity
    assert first.validator_unit_association_identity == (
        second.validator_unit_association_identity
    )


def test_multiple_associations_disambiguate_the_invocation_context():
    """One instance, two associations: the result names which one applied."""
    book = an_association_book()
    association_spu = a_bound_association(book, "assoc-spu", a_target("spu-1"))
    association_step = book.establish(
        ValidatorUnitAssociationIdentity("assoc-step"),
        AssociationTargetIdentity(AssociationTargetScopeKind.STEP, STEP_ID),
    )
    validator = _NeverMatchingValidator(book.validator_unit_identity)

    at_spu = validator.validate(
        association=association_spu,
        validator_invocation_identity=ValidatorInvocationIdentity("vinv-1"),
        step_instance_identity=STEP_ID,
        validation_input="input",
    )
    at_step = validator.validate(
        association=association_step,
        validator_invocation_identity=ValidatorInvocationIdentity("vinv-2"),
        step_instance_identity=STEP_ID,
        validation_input="input",
    )

    assert at_spu.validator_unit_association_identity == (
        ValidatorUnitAssociationIdentity("assoc-spu")
    )
    assert at_step.validator_unit_association_identity == (
        ValidatorUnitAssociationIdentity("assoc-step")
    )
    assert at_spu.association_target_identity != at_step.association_target_identity


def test_invocation_under_a_foreign_association_is_refused():
    other_book = an_association_book(a_unit_identity("validator-unit-OTHER"))
    foreign = other_book.establish(
        ValidatorUnitAssociationIdentity("assoc-foreign"), a_target()
    )
    book = an_association_book()
    validator = _NeverMatchingValidator(book.validator_unit_identity)

    with pytest.raises(ValueError, match="does not authorize this validator unit"):
        validator.validate(
            association=foreign,
            validator_invocation_identity=ValidatorInvocationIdentity("vinv-1"),
            step_instance_identity=STEP_ID,
            validation_input="input",
        )
    assert validator.evaluation_count == 0


def test_invocation_failure_never_fabricates_a_validation_result():
    validator = _NeverMatchingValidator(
        a_unit_identity(),
        raises=RuntimeError("target context unavailable"),
    )
    book = an_association_book(validator.identity)
    association = a_bound_association(book, "assoc-1", a_target())

    # the invocation failure propagates; no result is produced
    with pytest.raises(RuntimeError, match="target context unavailable"):
        validator.validate(
            association=association,
            validator_invocation_identity=ValidatorInvocationIdentity("vinv-1"),
            step_instance_identity=STEP_ID,
            validation_input="input",
        )
    assert validator.evaluation_count == 1
    # the failure did not change association or lifecycle state
    assert book.usable_for_invocation(ValidatorUnitAssociationIdentity("assoc-1"))
    assert book._lifecycle.phase is ValidatorUnitLifecyclePhase.ADMITTED


def test_abstract_base_cannot_be_instantiated():
    with pytest.raises(TypeError):
        SPUValidatorUnit(a_unit_identity())  # type: ignore[abstract]
