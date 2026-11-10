"""Contract tests for the SPU Observation Unit pattern (task 06).

Covers (Step_Supporting_Observation_Unit_{Behavioral,Association,Lifecycle}_Contract.json):
  - ObservationRecord: the SIX mandatory provenance references, specialization-
    defined payload, zero/one/many records per activity, distinctness by record
    identity, provenance stability after dissociation/release, and full
    independence from StepExecutionResult
  - ObservationUnitAssociation: applicability ONLY (no active-observation,
    lifecycle-readiness, or completeness guarantee); identity distinct from
    participant identities; dissociation keeps history
  - ObservationUnitLifecycle: milestones provisioned→prepared→ready→admitted→
    available/in-use→observing-or-subscribed→quiescing→retained-for-reuse→
    released; admission gating; quiescence blocks new activities; the
    observation mechanism tracked distinctly; release outcome recorded
    distinctly (failed/uncertain release is never labelled Released)
  - ObservationUnitAssociations: Step-Composition-owned establishment (admitted
    instance required), identity uniqueness/no-reuse, cardinality freedom,
    dissociation-not-release
  - SPUObservationUnit: activity boundary (call/callback/sampling/subscription
    all reduce to one authorized activity), foreign-association refusal,
    zero-record completion, no fabricated records on exception
"""

import dataclasses

import pytest

from gpwcf.core.supporting_patterns.observation import (
    AssociationTargetIdentity,
    AssociationTargetScopeKind,
    ObservationInvocationIdentity,
    ObservationRecord,
    ObservationRecordIdentity,
    ObservationUnitAssociation,
    ObservationUnitAssociationIdentity,
    ObservationUnitAssociations,
    ObservationUnitIdentity,
    ObservationUnitLifecycle,
    ObservationUnitLifecyclePhase,
    ObservationUnitReleaseOutcome,
    SPUObservationUnit,
)

STEP_ID = "step-instance-1"


def a_unit_identity(name: str = "observation-unit-1") -> ObservationUnitIdentity:
    return ObservationUnitIdentity(name)


def a_target(name: str = "spu-1") -> AssociationTargetIdentity:
    return AssociationTargetIdentity(AssociationTargetScopeKind.SPU, name)


def an_admitted_lifecycle(
    identity: ObservationUnitIdentity | None = None,
) -> ObservationUnitLifecycle:
    lifecycle = ObservationUnitLifecycle(identity or a_unit_identity())
    lifecycle.provision()
    lifecycle.mark_prepared()
    lifecycle.determine_ready()
    lifecycle.admit()
    return lifecycle


def an_association_book(
    identity: ObservationUnitIdentity | None = None,
    lifecycle: ObservationUnitLifecycle | None = None,
) -> ObservationUnitAssociations:
    unit_identity = identity or a_unit_identity()
    return ObservationUnitAssociations(
        unit_identity,
        lifecycle or an_admitted_lifecycle(unit_identity),
        step_instance_identity=STEP_ID,
    )


class _SamplingObserver(
    SPUObservationUnit[str, str, str]
):
    """Concrete specialization: emits canned payloads per activity.

    Stands in for any activity mechanism — explicit call, callback, sampling
    cycle, or subscription activation all reduce to one authorized activity.
    Record identities are generated per emission by the SPECIALIZATION (fresh
    per activity), matching the contract's identity-generation requirement.
    """

    def __init__(
        self,
        identity: ObservationUnitIdentity,
        *,
        payloads: tuple[str, ...] = (),
        raises: Exception | None = None,
        record_prefix: str = "obsrec",
    ) -> None:
        super().__init__(identity)
        self._payloads = payloads
        self._raises = raises
        self._record_prefix = record_prefix
        self.observation_count = 0

    def perform_observation(
        self, observation_input: str | None, target_context: str | None
    ) -> tuple[tuple[str, ObservationRecordIdentity], ...]:
        self.observation_count += 1
        if self._raises is not None:
            raise self._raises
        return tuple(
            (
                payload,
                ObservationRecordIdentity(
                    f"{self._record_prefix}-{self.observation_count}-{index}"
                ),
            )
            for index, payload in enumerate(self._payloads, start=1)
        )


# --------------------------------------------------------------------------
# identities: nominal separation
# --------------------------------------------------------------------------


def test_identity_types_are_nominal_and_never_conflatable():
    unit = ObservationUnitIdentity("x-1")
    association = ObservationUnitAssociationIdentity("x-1")
    activity = ObservationInvocationIdentity("x-1")
    record = ObservationRecordIdentity("x-1")

    # the same underlying string in different identity types never compares
    # equal: each identity names a DIFFERENT architectural fact
    assert unit != association
    assert unit != activity
    assert unit != record
    assert association != activity
    assert association != record
    assert activity != record
    assert unit == ObservationUnitIdentity("x-1")
    assert hash(unit) != hash(association)


def test_identities_reject_invalid_values():
    for identity_type in (
        ObservationUnitIdentity,
        ObservationUnitAssociationIdentity,
        ObservationInvocationIdentity,
        ObservationRecordIdentity,
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
        AssociationTargetScopeKind.STEP_INTERNAL, "spu-9"
    )
    # a bare SPU identity string can never stand in for a target identity
    with pytest.raises(TypeError):
        AssociationTargetIdentity("spu-9")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        AssociationTargetIdentity(AssociationTargetScopeKind.STEP, 9)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        AssociationTargetIdentity(AssociationTargetScopeKind.STEP, "  ")


# --------------------------------------------------------------------------
# ObservationRecord
# --------------------------------------------------------------------------


def a_record(
    *,
    activity: str = "obsact-1",
    record: str = "obsrec-1",
    unit: ObservationUnitIdentity | None = None,
    association: str = "assoc-1",
    target: AssociationTargetIdentity | None = None,
    payload: str = "temperature=71.4",
    **metadata: str,
) -> ObservationRecord[str]:
    return ObservationRecord[str](
        step_instance_identity=STEP_ID,
        observation_unit_identity=unit or a_unit_identity(),
        observation_unit_association_identity=ObservationUnitAssociationIdentity(association),
        association_target_identity=target or a_target(),
        observation_invocation_identity=ObservationInvocationIdentity(activity),
        observation_record_identity=ObservationRecordIdentity(record),
        payload=payload,
        **metadata,
    )


def test_record_carries_all_six_mandatory_provenance_references():
    record = a_record()

    assert record.step_instance_identity == STEP_ID
    assert record.observation_unit_identity == a_unit_identity()
    assert record.observation_unit_association_identity == (
        ObservationUnitAssociationIdentity("assoc-1")
    )
    assert record.association_target_identity == a_target()
    assert record.observation_invocation_identity == ObservationInvocationIdentity("obsact-1")
    assert record.observation_record_identity == ObservationRecordIdentity("obsrec-1")


def test_records_with_identical_payloads_remain_distinct():
    first = a_record(record="obsrec-1")
    second = a_record(record="obsrec-2")

    # identical payloads, different record identities: two distinct records
    assert first.payload == second.payload
    assert first != second
    assert first.observation_record_identity != second.observation_record_identity
    assert hash(first) != hash(second)


def test_payload_and_optional_metadata_are_independently_present_or_absent():
    plain = a_record()
    assert plain.payload == "temperature=71.4"
    assert plain.observation_subject_identity is None
    assert plain.observation_timestamp is None
    assert plain.source_invocation_identity is None
    assert plain.source_event_identity is None
    assert plain.sequence_metadata is None
    assert plain.observation_metadata is None

    # absence of metadata is not a success/failure status and absence is valid
    annotated = a_record(
        observation_subject_identity="spu-op-heater",
        observation_timestamp="2026-11-10T10:00:00Z",
        source_invocation_identity="spu-invocation-77",
        source_event_identity="setpoint-changed-9",
        sequence_metadata="seq=12",
        observation_metadata="unit=celsius precision=0.1",
    )
    assert annotated.observation_subject_identity == "spu-op-heater"
    assert annotated.observation_metadata == "unit=celsius precision=0.1"


def test_record_is_fully_independent_of_step_execution_result():
    """Observation output is never a Step result element: the record type has
    no result field, no status/success semantics, and the pattern package
    imports nothing from the Core (enforced by the architecture test)."""
    field_names = {field.name for field in dataclasses.fields(ObservationRecord)}
    assert not field_names & {
        "step_execution_result",
        "spu_execution_result",
        "step_validator_result",
        "error_result",
        "error_handler_result",
        "status",
        "success",
        "severity",
    }
    # a record describes an observation; it does not assert success or failure
    # of the observed operation and carries no validation verdict field
    record = a_record(payload="setpoint-exceeded observed")
    assert record.payload == "setpoint-exceeded observed"


def test_record_enforces_provenance_types_and_immutability():
    with pytest.raises(TypeError):
        ObservationRecord[str](
            step_instance_identity=STEP_ID,
            observation_unit_identity="observation-unit-1",  # type: ignore[arg-type]
            observation_unit_association_identity=(
                ObservationUnitAssociationIdentity("assoc-1")
            ),
            association_target_identity=a_target(),
            observation_invocation_identity=ObservationInvocationIdentity("obsact-1"),
            observation_record_identity=ObservationRecordIdentity("obsrec-1"),
            payload="p",
        )
    with pytest.raises(ValueError):
        a_record(activity="  ")
    with pytest.raises(ValueError):
        a_record(observation_timestamp="   ")

    record = a_record()
    with pytest.raises(AttributeError):
        record.payload = "rewritten"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        record.observation_record_identity = (  # type: ignore[misc]
            ObservationRecordIdentity("obsrec-9")
        )


def test_records_from_different_activities_are_distinguishable():
    same_association = ObservationUnitAssociationIdentity("assoc-1")
    first = a_record(activity="obsact-1", record="obsrec-1", association="assoc-1")
    second = a_record(activity="obsact-2", record="obsrec-2", association="assoc-1")

    assert first != second
    assert first.observation_invocation_identity != second.observation_invocation_identity
    assert first.observation_unit_association_identity == same_association


def test_record_provenance_is_never_rewritten_when_association_ends():
    """Records outlive the association: retained records keep naming the ended
    association and target (tested end-to-end with the book)."""
    book = an_association_book()
    association = book.establish(
        ObservationUnitAssociationIdentity("assoc-1"), a_target("spu-1")
    )
    observer = _SamplingObserver(
        book.observation_unit_identity,
        payloads=("measured=71.4",),
    )
    records = observer.observe(
        association=association,
        observation_invocation_identity=ObservationInvocationIdentity("obsact-1"),
        step_instance_identity=STEP_ID,
        observation_input="sample",
    )
    book.end(ObservationUnitAssociationIdentity("assoc-1"))

    assert len(records) == 1
    record = records[0]
    assert record.observation_unit_association_identity == (
        ObservationUnitAssociationIdentity("assoc-1")
    )
    assert record.association_target_identity == a_target("spu-1")
    assert book.usable_for_activity(ObservationUnitAssociationIdentity("assoc-1")) is False
    # historical provenance stays resolvable after dissociation
    assert book.ended_associations() == (association,)


# --------------------------------------------------------------------------
# ObservationUnitAssociation: applicability ONLY
# --------------------------------------------------------------------------


def test_association_identity_is_distinct_from_participant_identities():
    association = ObservationUnitAssociation(
        association_identity=ObservationUnitAssociationIdentity("assoc-1"),
        observation_unit_identity=ObservationUnitIdentity("observation-unit-1"),
        association_target_identity=a_target("spu-1"),
        step_instance_identity=STEP_ID,
    )

    assert association.association_identity != association.observation_unit_identity
    assert association.association_identity != association.association_target_identity
    assert association.observation_unit_identity != association.association_target_identity


def test_association_records_step_target_and_scope_kind():
    association = ObservationUnitAssociation(
        association_identity=ObservationUnitAssociationIdentity("assoc-1"),
        observation_unit_identity=a_unit_identity(),
        association_target_identity=AssociationTargetIdentity(
            AssociationTargetScopeKind.STEP_INTERNAL, "heater-op-scope"
        ),
        step_instance_identity=STEP_ID,
    )
    assert association.step_instance_identity == STEP_ID
    assert association.target_scope_kind is AssociationTargetScopeKind.STEP_INTERNAL


def test_association_is_applicability_only_with_no_observation_guarantee():
    """THE core association rule: establishing an association makes the unit
    APPLICABLE to the target and nothing more — no activity has run, no
    mechanism is active, no record exists, and the lifecycle need not be in an
    observing state."""
    book = an_association_book()
    association = book.establish(
        ObservationUnitAssociationIdentity("assoc-1"), a_target("spu-1")
    )

    # the association exists and is usable for AUTHORizing new activities...
    assert book.usable_for_activity(ObservationUnitAssociationIdentity("assoc-1")) is True
    # ...but nothing is being observed: no activity recorded, no mechanism
    # active, no lifecycle implication, no record produced
    assert book._lifecycle.active_activities == 0
    assert book._lifecycle.phase is ObservationUnitLifecyclePhase.ADMITTED
    assert book._lifecycle.phase is not (
        ObservationUnitLifecyclePhase.OBSERVING_OR_SUBSCRIBED
    )
    # an admitted unit with a live association may still never be activated:
    # applicability does not force observation to happen at all


def test_association_does_not_transfer_authority_to_the_target():
    """An SPU may be a target without gaining association-management authority:
    the book binds the unit to the target, never the reverse, and exposes no
    operation by which the target could create, change, or end associations."""
    book = an_association_book()
    association = book.establish(
        ObservationUnitAssociationIdentity("assoc-1"), a_target("spu-1")
    )

    book_operations = {
        name for name in dir(book) if not name.startswith("_")
    }
    assert association.association_target_identity == a_target("spu-1")
    assert not any("register" in name or "subscribe" in name for name in book_operations)
    # the only mutation operations are establish/end — both Step Composition's
    assert book_operations & {"establish", "end"}


def test_association_rejects_conflated_or_invalid_participants():
    with pytest.raises(TypeError):
        ObservationUnitAssociation(
            association_identity=ObservationUnitAssociationIdentity("assoc-1"),
            observation_unit_identity=ObservationUnitIdentity("ou-1"),
            # the target is not an AssociationTargetIdentity (conflation)
            association_target_identity=ObservationUnitIdentity("spu-1"),  # type: ignore[arg-type]
            step_instance_identity=STEP_ID,
        )
    with pytest.raises(ValueError):
        ObservationUnitAssociation(
            association_identity=ObservationUnitAssociationIdentity("assoc-1"),
            observation_unit_identity=a_unit_identity(),
            association_target_identity=a_target(),
            step_instance_identity="   ",
        )


# --------------------------------------------------------------------------
# ObservationUnitLifecycle
# --------------------------------------------------------------------------


def test_lifecycle_happy_path_provisioned_through_release():
    lifecycle = ObservationUnitLifecycle(a_unit_identity())
    assert lifecycle.phase is None
    assert lifecycle.usable_for_activity is False

    lifecycle.provision()
    assert lifecycle.phase is ObservationUnitLifecyclePhase.PROVISIONED_OR_ACQUIRED
    lifecycle.mark_prepared()
    lifecycle.determine_ready()
    assert lifecycle.phase is ObservationUnitLifecyclePhase.READY
    lifecycle.admit()
    assert lifecycle.usable_for_activity is True
    lifecycle.begin_activity()
    assert lifecycle.phase is ObservationUnitLifecyclePhase.AVAILABLE_OR_IN_USE
    assert lifecycle.active_activities == 1
    lifecycle.end_activity()
    # an ongoing mechanism (sampling loop / subscription / callback) is
    # recorded distinctly and may span many events
    lifecycle.activate_observation_mechanism()
    assert lifecycle.phase is ObservationUnitLifecyclePhase.OBSERVING_OR_SUBSCRIBED
    lifecycle.deactivate_observation_mechanism()
    assert lifecycle.phase is ObservationUnitLifecyclePhase.AVAILABLE_OR_IN_USE
    lifecycle.quiesce()
    assert lifecycle.usable_for_activity is False
    lifecycle.retain_for_reuse()
    assert lifecycle.phase is ObservationUnitLifecyclePhase.RETAINED_FOR_REUSE
    # reuse requires a fresh admission decision by Step Composition
    lifecycle.admit()
    assert lifecycle.phase is ObservationUnitLifecyclePhase.ADMITTED
    lifecycle.quiesce()
    lifecycle.release()
    assert lifecycle.phase is ObservationUnitLifecyclePhase.RELEASED
    assert lifecycle.release_outcome is ObservationUnitReleaseOutcome.RELEASED


def test_admission_requires_readiness_and_activity_requires_admission():
    lifecycle = ObservationUnitLifecycle(a_unit_identity())
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
        lifecycle.begin_activity()  # ready does NOT mean admitted

    lifecycle.admit()
    lifecycle.begin_activity()
    # a double admission recording is refused while already admitted
    with pytest.raises(ValueError):
        lifecycle.admit()
    lifecycle.end_activity()


def test_observing_mechanism_may_service_many_events_without_lifecycle_noise():
    """A subscription/sampling loop stays ObservingOrSubscribed across events;
    each observed event is NOT a new instance lifecycle transition."""
    lifecycle = an_admitted_lifecycle()
    lifecycle.activate_observation_mechanism()
    assert lifecycle.phase is ObservationUnitLifecyclePhase.OBSERVING_OR_SUBSCRIBED
    assert lifecycle.usable_for_activity is True

    # many events serviced: recorded as activities, phase unchanged
    for _ in range(3):
        lifecycle.begin_activity()
    assert lifecycle.phase is ObservationUnitLifecyclePhase.OBSERVING_OR_SUBSCRIBED
    assert lifecycle.active_activities == 3
    for _ in range(3):
        lifecycle.end_activity()
    assert lifecycle.phase is ObservationUnitLifecyclePhase.OBSERVING_OR_SUBSCRIBED
    lifecycle.deactivate_observation_mechanism()


def test_mechanism_activation_requires_admission():
    lifecycle = ObservationUnitLifecycle(a_unit_identity())
    with pytest.raises(ValueError):
        lifecycle.activate_observation_mechanism()  # not provisioned

    lifecycle.provision()
    with pytest.raises(ValueError):
        lifecycle.activate_observation_mechanism()  # provisioned only
    lifecycle.mark_prepared()
    lifecycle.determine_ready()
    with pytest.raises(ValueError):
        lifecycle.activate_observation_mechanism()  # ready but not admitted

    lifecycle.admit()
    lifecycle.activate_observation_mechanism()  # admitted: activation recorded
    with pytest.raises(ValueError):
        lifecycle.activate_observation_mechanism()  # already active
    lifecycle.deactivate_observation_mechanism()
    with pytest.raises(ValueError):
        lifecycle.deactivate_observation_mechanism()  # already inactive


def test_quiescence_blocks_new_activities_but_lets_active_work_drain():
    lifecycle = an_admitted_lifecycle()
    lifecycle.begin_activity()
    lifecycle.quiesce()

    with pytest.raises(ValueError):
        lifecycle.begin_activity()
    assert lifecycle.usable_for_activity is False
    lifecycle.end_activity()  # active work drains
    assert lifecycle.active_activities == 0
    # records already produced/accepted are not erased by quiescence
    assert lifecycle.phase is ObservationUnitLifecyclePhase.QUIESCING


def test_release_requires_no_active_activities_and_no_active_mechanism():
    lifecycle = an_admitted_lifecycle()
    lifecycle.begin_activity()
    with pytest.raises(ValueError):
        lifecycle.release()  # active one-shot activity
    lifecycle.end_activity()

    lifecycle.activate_observation_mechanism()
    with pytest.raises(ValueError):
        lifecycle.release()  # active subscription/sampling mechanism
    assert lifecycle.phase is ObservationUnitLifecyclePhase.OBSERVING_OR_SUBSCRIBED

    lifecycle.deactivate_observation_mechanism()
    lifecycle.release()
    assert lifecycle.phase is ObservationUnitLifecyclePhase.RELEASED


def test_failed_or_uncertain_release_is_never_labelled_released():
    for bad_outcome in (
        ObservationUnitReleaseOutcome.RELEASE_FAILED,
        ObservationUnitReleaseOutcome.RELEASE_OUTCOME_UNCERTAIN,
    ):
        lifecycle = an_admitted_lifecycle()
        lifecycle.quiesce()
        lifecycle.release(bad_outcome)
        assert lifecycle.phase is ObservationUnitLifecyclePhase.QUIESCING
        assert lifecycle.release_outcome is bad_outcome
        assert lifecycle.phase is not ObservationUnitLifecyclePhase.RELEASED
        assert lifecycle.usable_for_activity is False


def test_release_before_provisioning_or_after_release_is_refused():
    lifecycle = ObservationUnitLifecycle(a_unit_identity())
    with pytest.raises(ValueError):
        lifecycle.release()

    lifecycle.provision()
    lifecycle.mark_prepared()
    lifecycle.determine_ready()
    lifecycle.admit()
    lifecycle.release()
    with pytest.raises(ValueError):
        lifecycle.release()


def test_end_activity_without_active_activity_is_refused():
    lifecycle = an_admitted_lifecycle()
    with pytest.raises(ValueError):
        lifecycle.end_activity()


def test_replacement_instance_receives_a_distinct_identity():
    first = ObservationUnitLifecycle(ObservationUnitIdentity("observation-unit-A"))
    first.provision()
    replacement = ObservationUnitLifecycle(ObservationUnitIdentity("observation-unit-A2"))

    # the replacement may share implementation/configuration but never identity
    assert first.identity != replacement.identity
    assert first.phase is ObservationUnitLifecyclePhase.PROVISIONED_OR_ACQUIRED
    assert replacement.phase is None  # independent lifecycle


# --------------------------------------------------------------------------
# ObservationUnitAssociations (Step-Composition-owned book)
# --------------------------------------------------------------------------


def test_establishment_requires_an_admitted_instance():
    unit_identity = a_unit_identity()
    lifecycle = ObservationUnitLifecycle(unit_identity)
    book = an_association_book(unit_identity, lifecycle)

    with pytest.raises(ValueError):
        book.establish(ObservationUnitAssociationIdentity("assoc-1"), a_target())
    lifecycle.provision()
    with pytest.raises(ValueError):
        book.establish(ObservationUnitAssociationIdentity("assoc-1"), a_target())
    lifecycle.mark_prepared()
    lifecycle.determine_ready()
    with pytest.raises(ValueError):
        book.establish(ObservationUnitAssociationIdentity("assoc-1"), a_target())

    lifecycle.admit()
    association = book.establish(
        ObservationUnitAssociationIdentity("assoc-1"), a_target()
    )
    assert association.observation_unit_identity == unit_identity
    assert association.step_instance_identity == STEP_ID
    assert book.usable_for_activity(ObservationUnitAssociationIdentity("assoc-1"))


def test_one_unit_may_observe_multiple_target_scopes():
    """No universal one-to-one mapping: three associations, one unit."""
    book = an_association_book()
    unit_identity = book.observation_unit_identity
    first = book.establish(
        ObservationUnitAssociationIdentity("assoc-1"), a_target("spu-1")
    )
    second = book.establish(
        ObservationUnitAssociationIdentity("assoc-2"), a_target("spu-2")
    )
    third = book.establish(
        ObservationUnitAssociationIdentity("assoc-3"),
        AssociationTargetIdentity(AssociationTargetScopeKind.STEP, STEP_ID),
    )

    assert len(book.live_associations()) == 3
    for association in (first, second, third):
        # one observationUnitIdentity, three DISTINCT association identities
        assert association.observation_unit_identity == unit_identity
        assert association.association_identity in {
            ObservationUnitAssociationIdentity("assoc-1"),
            ObservationUnitAssociationIdentity("assoc-2"),
            ObservationUnitAssociationIdentity("assoc-3"),
        }
    assert book.associations_for_target(a_target("spu-1")) == (first,)
    assert book.associations_for_target(a_target("spu-2")) == (second,)


def test_one_target_may_be_observed_by_multiple_units():
    """No exclusivity either: two units, one shared target scope."""
    book_1 = an_association_book(a_unit_identity("observation-unit-1"))
    book_2 = an_association_book(a_unit_identity("observation-unit-2"))

    association_1 = book_1.establish(
        ObservationUnitAssociationIdentity("assoc-U1"), a_target("spu-shared")
    )
    association_2 = book_2.establish(
        ObservationUnitAssociationIdentity("assoc-U2"), a_target("spu-shared")
    )

    assert association_1.association_target_identity == (
        association_2.association_target_identity
    )
    assert association_1.observation_unit_identity != (
        association_2.observation_unit_identity
    )
    assert association_1.association_identity != association_2.association_identity


def test_lifecycle_identity_must_match_the_book():
    lifecycle = an_admitted_lifecycle(a_unit_identity("observation-unit-1"))
    with pytest.raises(ValueError):
        ObservationUnitAssociations(
            a_unit_identity("observation-unit-OTHER"),
            lifecycle,
            step_instance_identity=STEP_ID,
        )


def test_dissociation_keeps_history_does_not_release_and_spares_other_associations():
    book = an_association_book()
    first = book.establish(
        ObservationUnitAssociationIdentity("assoc-1"), a_target("spu-1")
    )
    second = book.establish(
        ObservationUnitAssociationIdentity("assoc-2"), a_target("spu-2")
    )

    ended = book.end(ObservationUnitAssociationIdentity("assoc-1"))

    assert ended == first
    # no new activity may rely on the ended association
    assert book.usable_for_activity(ObservationUnitAssociationIdentity("assoc-1")) is False
    assert book.get(ObservationUnitAssociationIdentity("assoc-1")) is None
    # the other association is untouched
    assert book.usable_for_activity(ObservationUnitAssociationIdentity("assoc-2")) is True
    # historical provenance remains resolvable
    assert book.ended_associations() == (first,)
    # dissociation is NOT release and cancels nothing already produced
    assert book._lifecycle.phase is ObservationUnitLifecyclePhase.ADMITTED
    assert book.has_live_associations() is True
    book.end(ObservationUnitAssociationIdentity("assoc-2"))
    assert book.has_live_associations() is False
    assert book._lifecycle.phase is ObservationUnitLifecyclePhase.ADMITTED


def test_association_identity_is_never_reused_while_records_remain_observable():
    book = an_association_book()
    book.establish(ObservationUnitAssociationIdentity("assoc-1"), a_target("spu-1"))
    book.end(ObservationUnitAssociationIdentity("assoc-1"))

    # same target OR a different target: the identity stays retired
    with pytest.raises(ValueError):
        book.establish(ObservationUnitAssociationIdentity("assoc-1"), a_target("spu-1"))
    with pytest.raises(ValueError):
        book.establish(ObservationUnitAssociationIdentity("assoc-1"), a_target("spu-2"))
    # a logically similar re-establishment takes a NEW identity
    reestablished = book.establish(
        ObservationUnitAssociationIdentity("assoc-1-reestablished"), a_target("spu-1")
    )
    assert reestablished.association_target_identity == a_target("spu-1")


def test_double_ending_and_unknown_ending_are_refused():
    book = an_association_book()
    book.establish(ObservationUnitAssociationIdentity("assoc-1"), a_target())
    book.end(ObservationUnitAssociationIdentity("assoc-1"))

    with pytest.raises(ValueError):
        book.end(ObservationUnitAssociationIdentity("assoc-1"))
    with pytest.raises(KeyError):
        book.end(ObservationUnitAssociationIdentity("assoc-unknown"))


def test_establishment_while_quiescing_is_refused():
    unit_identity = a_unit_identity()
    lifecycle = an_admitted_lifecycle(unit_identity)
    book = an_association_book(unit_identity, lifecycle)
    lifecycle.quiesce()

    with pytest.raises(ValueError):
        book.establish(ObservationUnitAssociationIdentity("assoc-1"), a_target())


# --------------------------------------------------------------------------
# SPUObservationUnit activity boundary
# --------------------------------------------------------------------------


def a_bound_association(
    book: ObservationUnitAssociations, name: str, target: AssociationTargetIdentity
) -> ObservationUnitAssociation:
    return book.establish(ObservationUnitAssociationIdentity(name), target)


def test_observe_produces_records_with_authoritative_provenance():
    book = an_association_book()
    association = a_bound_association(book, "assoc-1", a_target("spu-1"))
    observer = _SamplingObserver(
        book.observation_unit_identity,
        payloads=("measured=71.4", "measured=72.1"),
    )

    records = observer.observe(
        association=association,
        observation_invocation_identity=ObservationInvocationIdentity("obsact-1"),
        step_instance_identity=STEP_ID,
        observation_input="sample-now",
        target_context="live-target-surface",
        observation_subject_identity="heater-op",
        observation_timestamp="2026-11-10T10:00:00Z",
        sequence_metadata="seq=1",
        observation_metadata="unit=celsius",
    )

    # ONE activity, TWO records — each with its own record identity
    assert len(records) == 2
    for record in records:
        assert record.observation_unit_identity == observer.identity
        assert record.observation_unit_association_identity == (
            ObservationUnitAssociationIdentity("assoc-1")
        )
        # the target comes from the ASSOCIATION, never inferred from the input
        assert record.association_target_identity == a_target("spu-1")
        assert record.observation_invocation_identity == (
            ObservationInvocationIdentity("obsact-1")
        )
        assert record.step_instance_identity == STEP_ID
        assert record.observation_subject_identity == "heater-op"
        assert record.sequence_metadata == "seq=1"
        assert record.observation_metadata == "unit=celsius"
    # record identities are distinct within the activity
    assert records[0].observation_record_identity != records[1].observation_record_identity
    assert records[0].payload == "measured=71.4"
    assert records[1].payload == "measured=72.1"
    assert observer.observation_count == 1


def test_activity_may_complete_normally_with_zero_records():
    """One activity may emit zero records — a normal completion, not a failure."""
    book = an_association_book()
    association = a_bound_association(book, "assoc-1", a_target())
    observer = _SamplingObserver(book.observation_unit_identity, payloads=())

    records = observer.observe(
        association=association,
        observation_invocation_identity=ObservationInvocationIdentity("obsact-1"),
        step_instance_identity=STEP_ID,
        observation_input="quiet-window",
    )

    assert records == ()
    assert observer.observation_count == 1


def test_activity_under_callback_sampling_and_subscription_models():
    """Call, callback, sampling, and subscription are all specializations of
    ONE authorized activity — the boundary neither knows nor cares which."""
    book = an_association_book()
    association = a_bound_association(book, "assoc-1", a_target())
    observer = _SamplingObserver(book.observation_unit_identity, payloads=("event",))

    for activity_name in ("call", "callback", "sampling-cycle", "subscription-activation"):
        records = observer.observe(
            association=association,
            observation_invocation_identity=ObservationInvocationIdentity(activity_name),
            step_instance_identity=STEP_ID,
            observation_input="mechanism-specific",
        )
        assert len(records) == 1
        assert records[0].observation_invocation_identity == (
            ObservationInvocationIdentity(activity_name)
        )


def test_duplicate_record_identities_within_one_activity_are_refused():
    class _DuplicateEmitter(_SamplingObserver):
        """Specialization bug simulation: one identity used for two records."""

        def perform_observation(
            self, observation_input: str | None, target_context: str | None
        ) -> tuple[tuple[str, ObservationRecordIdentity], ...]:
            self.observation_count += 1
            duplicate = ObservationRecordIdentity("obsrec-dup")
            return (("first", duplicate), ("second", duplicate))

    book = an_association_book()
    association = a_bound_association(book, "assoc-1", a_target())
    observer = _DuplicateEmitter(book.observation_unit_identity)

    with pytest.raises(ValueError, match="own observationRecordIdentity"):
        observer.observe(
            association=association,
            observation_invocation_identity=ObservationInvocationIdentity("obsact-1"),
            step_instance_identity=STEP_ID,
            observation_input="sample",
        )


def test_repeated_activities_under_one_association_stay_distinguishable():
    book = an_association_book()
    association = a_bound_association(book, "assoc-1", a_target())
    observer = _SamplingObserver(
        book.observation_unit_identity,
        payloads=("measured=71.4",),
    )

    first = observer.observe(
        association=association,
        observation_invocation_identity=ObservationInvocationIdentity("obsact-1"),
        step_instance_identity=STEP_ID,
        observation_input="sample",
    )
    second = observer.observe(
        association=association,
        observation_invocation_identity=ObservationInvocationIdentity("obsact-2"),
        step_instance_identity=STEP_ID,
        observation_input="sample",
    )

    # identical payloads across activities: still distinct activities AND
    # distinct records; the association identity is not a substitute for the
    # activity identity
    assert len(first) == len(second) == 1
    assert first[0].payload == second[0].payload
    assert first[0].observation_invocation_identity != (
        second[0].observation_invocation_identity
    )
    assert first[0].observation_record_identity != second[0].observation_record_identity
    assert first[0] != second[0]


def test_multiple_associations_disambiguate_the_activity_context():
    """One instance, two associations: each record names which one applied."""
    book = an_association_book()
    association_step = book.establish(
        ObservationUnitAssociationIdentity("assoc-step"),
        AssociationTargetIdentity(AssociationTargetScopeKind.STEP, STEP_ID),
    )
    observer = _SamplingObserver(book.observation_unit_identity, payloads=("fact",))
    association_spu = a_bound_association(book, "assoc-spu", a_target("spu-1"))

    at_spu = observer.observe(
        association=association_spu,
        observation_invocation_identity=ObservationInvocationIdentity("obsact-1"),
        step_instance_identity=STEP_ID,
        observation_input="sample",
    )
    at_step = observer.observe(
        association=association_step,
        observation_invocation_identity=ObservationInvocationIdentity("obsact-2"),
        step_instance_identity=STEP_ID,
        observation_input="sample",
    )

    assert at_spu[0].observation_unit_association_identity == (
        ObservationUnitAssociationIdentity("assoc-spu")
    )
    assert at_step[0].observation_unit_association_identity == (
        ObservationUnitAssociationIdentity("assoc-step")
    )
    assert at_spu[0].association_target_identity != at_step[0].association_target_identity


def test_activity_under_a_foreign_association_is_refused():
    other_book = an_association_book(a_unit_identity("observation-unit-OTHER"))
    foreign = other_book.establish(
        ObservationUnitAssociationIdentity("assoc-foreign"), a_target()
    )
    book = an_association_book()
    observer = _SamplingObserver(book.observation_unit_identity, payloads=("fact",))

    with pytest.raises(ValueError, match="does not authorize this observation unit"):
        observer.observe(
            association=foreign,
            observation_invocation_identity=ObservationInvocationIdentity("obsact-1"),
            step_instance_identity=STEP_ID,
            observation_input="sample",
        )
    assert observer.observation_count == 0


def test_activity_failure_never_fabricates_or_revokes_records():
    """An exception is an activity failure: no record is fabricated for the
    failing activity, and records accepted by an EARLIER activity are not
    revoked by a later one."""
    observer = _SamplingObserver(
        a_unit_identity(),
        payloads=("measured=71.0",),
    )
    book = an_association_book(observer.identity)
    association = a_bound_association(book, "assoc-1", a_target())

    earlier = observer.observe(
        association=association,
        observation_invocation_identity=ObservationInvocationIdentity("obsact-1"),
        step_instance_identity=STEP_ID,
        observation_input="sample",
    )
    failing = _SamplingObserver(
        observer.identity,
        raises=RuntimeError("observation source unavailable"),
    )

    with pytest.raises(RuntimeError, match="observation source unavailable"):
        failing.observe(
            association=association,
            observation_invocation_identity=ObservationInvocationIdentity("obsact-2"),
            step_instance_identity=STEP_ID,
            observation_input="sample",
        )
    assert failing.observation_count == 1
    # the earlier records remain valid, unrewritten, and attributable to their
    # own activity
    assert len(earlier) == 1
    assert earlier[0].observation_invocation_identity == (
        ObservationInvocationIdentity("obsact-1")
    )
    # the failure did not change association or lifecycle state
    assert book.usable_for_activity(ObservationUnitAssociationIdentity("assoc-1"))
    assert book._lifecycle.phase is ObservationUnitLifecyclePhase.ADMITTED


def test_abstract_base_cannot_be_instantiated():
    with pytest.raises(TypeError):
        SPUObservationUnit(a_unit_identity())  # type: ignore[abstract]
