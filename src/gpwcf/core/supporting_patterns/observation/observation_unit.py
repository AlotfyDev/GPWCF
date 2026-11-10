"""SPU Observation Unit — working protocol for the optional observation pattern.

Implementation task: 06_Observation_Unit
Related diagrams:
  class: 03_Diagrams_Codes_Files/01_SPU_Step_Processing_Unit.dot
  sequence: B_Sequencial_Diagram_Code/04_Observation_Unit_Sequence.puml
  association: C_Association_Diagram_Code/06_Observation_Unit_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/04_Supporting_Pattern_Optional_Dependency.dot

Contract basis:
  - Step_Supporting_Observation_Unit_Contract.json (behavioral: activity
    boundary, record semantics, output/custody, failure boundary)
  - Step_Supporting_Observation_Unit_Association_Contract.json (association
    identity, target binding, applicability, dissociation, historical
    provenance)
  - Step_Supporting_Observation_Unit_Lifecycle_Contract.json (instance
    lifecycle milestones, admission, quiescence, reuse, release, record
    independence)
  - Common/Step_Composition_Association_Coordination_Contract.json and
    Common/Step_Composition_Internal_Component_Lifecycle_Coordination_Contract.json
    (specialized here with observation-specific identity names and mechanics)

Dependency boundary (``04_Supporting_Pattern_Optional_Dependency.dot``):
``ObservationUnit -> Core : NO dependency``; ``ObservationUnit -> Prefect : NO
dependency``. This package imports NOTHING from ``gpwcf`` (stdlib only).

What this module provides (the reusable protocol shape a concrete Step owns
and coordinates — NOT a universal telemetry system and not a universal
Supporting Unit base type):

  - :class:`ObservationRecord` — one independently identifiable fact,
    measurement, event, or diagnostic observation, typed
    ``ObservationRecord[TObservationPayload]``. The payload is wholly
    specialization-defined; no universal event schema, timestamp format,
    measurement unit, or severity is imposed. Every record carries the SIX
    mandatory provenance references (step instance, observation unit,
    association, target scope, activity, record) and remains fully independent
    of SPUExecutionResult, StepValidatorResult, ErrorResult,
    ErrorHandlerResult, and StepExecutionResult — observation output is never
    merged into a Step result by default and never implies the observed
    operation succeeded or failed.
  - :class:`ObservationUnitAssociation` — the identity-bearing relationship
    between one observation-unit instance and ONE Step-owned target scope.
    Association = APPLICABILITY ONLY: not ownership, not an activity, not a
    record, not a lifecycle state, and explicitly NOT a guarantee that
    observation is currently active, that the unit is lifecycle-ready, or that
    every event or fact about the target will be observed.
  - :class:`ObservationUnitLifecycle` (with :class:`ObservationUnitLifecyclePhase`
    and :class:`ObservationUnitReleaseOutcome`) — the Step-Composition-coordinated
    instance lifecycle milestones: provisioned → prepared → ready → admitted →
    available/in-use → observing-or-subscribed → quiescing →
    retained-for-reuse / released. Milestones are conceptual (the contract does
    not mandate a fixed state machine); admission, quiescence, reuse, and
    release decisions are recorded here when the owning Step Composition makes
    them. Release completion, failure, and uncertain outcomes are recorded
    DISTINCTLY — an attempted release is never silently labelled Released.
  - :class:`ObservationUnitAssociations` — the Step-Composition-owned
    association book for ONE observation-unit instance: establishment (only
    for an admitted instance; identity unique and never reused while retained
    records may still be observable), dissociation (does not release the
    instance, does not erase historical provenance, does not end the unit's
    other associations), and activity-usability checks.
  - :class:`SPUObservationUnit` — the abstract base for concrete observation
    specializations. The concrete subclass defines WHAT it observes, the
    activity mechanism (call, callback, sampling, subscription, or another
    explicit model), the payload structure, and identity generation via
    :meth:`perform_observation`; the shared :meth:`observe` boundary enforces
    the activity contract: one activity under exactly one authorized
    association context, target taken from that association (never inferred
    from the observation input), zero/one/many records per activity each with
    its own record identity, and NO fabricated record when the mechanism
    throws (an exception is an activity failure, not an observation; it never
    revokes records accepted earlier).

Explicit non-goals (per contract ``explicitNonGoals``): no mandatory Observation
Unit for any Step or SPU, no universal execute signature or request/response
object, no single-result-per-activity assumption, no universal event schema or
telemetry protocol, no mandatory central logger/event bus/broker/database/
collector/observation manager, no validation verdict or error classification or
Step flow-control authority, no association or lifecycle authority for the unit
or the SPU target, no default inclusion of records in StepExecutionResult, no
universal synchronous/asynchronous/periodic/streaming/subscription model.
"""

from __future__ import annotations

import enum
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from collections.abc import Sequence

from .identities import (
    AssociationTargetIdentity,
    AssociationTargetScopeKind,
    ObservationInvocationIdentity,
    ObservationRecordIdentity,
    ObservationUnitAssociationIdentity,
    ObservationUnitIdentity,
)

__all__ = [
    "ObservationRecord",
    "ObservationUnitAssociation",
    "ObservationUnitLifecyclePhase",
    "ObservationUnitReleaseOutcome",
    "ObservationUnitLifecycle",
    "ObservationUnitAssociations",
    "SPUObservationUnit",
]


def _require_type(name: str, value: object, expected: type) -> None:
    if type(value) is not expected:
        raise TypeError(
            f"{name} must be {expected.__name__}, got {type(value).__name__}"
        )


def _require_optional_text(name: str, value: str | None) -> None:
    if value is not None and (not isinstance(value, str) or value == "" or value.isspace()):
        raise ValueError(f"{name} must be a non-empty string or None")


# --------------------------------------------------------------------------
# ObservationRecord
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ObservationRecord[TObservationPayload]:
    """One independently identifiable fact, measurement, or diagnostic record.

    Produced by the Observation Unit instance (or a specialization-defined
    capture mechanism operating under its identity) during ONE authorized
    observation activity; handed off to the destination defined by the
    specialization. Deliberately independent of SPUExecutionResult,
    StepValidatorResult, ErrorResult, ErrorHandlerResult, and
    StepExecutionResult: observation output is never a default Step result
    field, never a validation verdict, never an error classification, and it
    does not imply that the observed operation succeeded or failed.

    Semantics (per the record contract):

    - The payload (``TObservationPayload``) is defined by the concrete
      specialization — a measurement, event fact, sampled value, timing datum,
      state snapshot, or other observation content. No universal event schema
      is imposed here.
    - One observation ACTIVITY may emit zero, one, or multiple records; every
      separately identifiable record carries its OWN
      ``observation_record_identity``. Two records with identical payloads
      remain distinct when their record identities differ.
    - Provenance invariants: all SIX mandatory references are present on every
      record; the record names exactly ONE activity; association/target
      provenance matches the association context bound to that activity and is
      NEVER rewritten when the association later changes, ends, or the
      instance is released — records outlive both.
    - Optional metadata is independently present/absent: the observation
      subject (when it differs from the association target), timestamp or
      monotonic measurement time, correlation with a distinct source activity
      or event, sequence/order metadata, and specialization-defined quality,
      precision, units, sampling, or diagnostic metadata. Absence of metadata
      is not a success/failure status.
    """

    step_instance_identity: str
    observation_unit_identity: ObservationUnitIdentity
    observation_unit_association_identity: ObservationUnitAssociationIdentity
    association_target_identity: AssociationTargetIdentity
    observation_invocation_identity: ObservationInvocationIdentity
    observation_record_identity: ObservationRecordIdentity
    payload: TObservationPayload
    observation_subject_identity: str | None = None
    observation_timestamp: str | None = None
    source_invocation_identity: str | None = None
    source_event_identity: str | None = None
    sequence_metadata: str | None = None
    observation_metadata: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.step_instance_identity, str) or (
            self.step_instance_identity == "" or self.step_instance_identity.isspace()
        ):
            raise ValueError(
                "step_instance_identity must be a non-empty, non-blank string"
            )
        _require_type(
            "observation_unit_identity",
            self.observation_unit_identity,
            ObservationUnitIdentity,
        )
        _require_type(
            "observation_unit_association_identity",
            self.observation_unit_association_identity,
            ObservationUnitAssociationIdentity,
        )
        _require_type(
            "association_target_identity",
            self.association_target_identity,
            AssociationTargetIdentity,
        )
        _require_type(
            "observation_invocation_identity",
            self.observation_invocation_identity,
            ObservationInvocationIdentity,
        )
        _require_type(
            "observation_record_identity",
            self.observation_record_identity,
            ObservationRecordIdentity,
        )
        for name in (
            "observation_subject_identity",
            "observation_timestamp",
            "source_invocation_identity",
            "source_event_identity",
            "sequence_metadata",
            "observation_metadata",
        ):
            _require_optional_text(name, getattr(self, name))


# --------------------------------------------------------------------------
# ObservationUnitAssociation
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ObservationUnitAssociation:
    """Identity-bearing relationship: one observation unit ↔ one target scope.

    Association = APPLICABILITY ONLY. Per the association contract it is NOT:

    - ownership of the Observation Unit instance by the target,
    - a transfer of association-management authority to the Observation Unit
      or the target SPU,
    - an observation activity, a record, or an observation destination,
    - a guarantee that observation is currently active or that the unit is
      lifecycle-ready,
    - a guarantee that every event or fact about the target will be observed.

    Identity rules (association contract):

    - ``association_identity`` identifies THIS relationship instance — distinct
      from the observation-unit identity and the target identity (each is a
      different nominal type; conflation is unrepresentable).
    - Every association belongs to exactly one owning Step instance and
      identifies exactly one target scope.
    - The identity is stable for the association's lifetime; ending this
      association does not end the unit's other associations, does not release
      the observation-unit instance, does not cancel or erase records already
      produced, and does not decide the disposition of pending records.
    """

    association_identity: ObservationUnitAssociationIdentity
    observation_unit_identity: ObservationUnitIdentity
    association_target_identity: AssociationTargetIdentity
    step_instance_identity: str

    def __post_init__(self) -> None:
        _require_type(
            "association_identity",
            self.association_identity,
            ObservationUnitAssociationIdentity,
        )
        _require_type(
            "observation_unit_identity",
            self.observation_unit_identity,
            ObservationUnitIdentity,
        )
        _require_type(
            "association_target_identity",
            self.association_target_identity,
            AssociationTargetIdentity,
        )
        _require_optional_text("step_instance_identity", self.step_instance_identity)
        if self.step_instance_identity is None:
            raise ValueError("step_instance_identity is required")

    @property
    def target_scope_kind(self) -> AssociationTargetScopeKind:
        """The kind of Step-owned scope this association targets."""
        return self.association_target_identity.scope_kind


# --------------------------------------------------------------------------
# Observation Unit Lifecycle
# --------------------------------------------------------------------------


class ObservationUnitLifecyclePhase(enum.Enum):
    """Conceptual lifecycle milestones for an Observation Unit instance.

    Milestones, not a mandatory enum state machine and not a requirement that
    every implementation materialize each phase: the concrete Step defines the
    actual lifecycle policy consistent with the lifecycle contract. The
    instance lifecycle is INDEPENDENT of association lifetimes, of activity or
    subscription-activation lifetimes, and of observation-record retention
    lifetimes. A subscription or ongoing observer may remain active across
    multiple observed events without treating each event as a new lifecycle
    transition.
    """

    PROVISIONED_OR_ACQUIRED = "provisioned-or-acquired"
    PREPARED = "prepared"
    READY = "ready"
    ADMITTED = "admitted"
    AVAILABLE_OR_IN_USE = "available-or-in-use"
    OBSERVING_OR_SUBSCRIBED = "observing-or-subscribed"
    QUIESCING = "quiescing"
    RETAINED_FOR_REUSE = "retained-for-reuse"
    RELEASED = "released"


class ObservationUnitReleaseOutcome(enum.Enum):
    """Recorded outcome of the instance release operation.

    ``RELEASED``: the required release procedure completed successfully.
    ``RELEASE_FAILED``: the release procedure failed; the instance is not
    Released and the concrete Step defines quarantine/reconciliation.
    ``RELEASE_OUTCOME_UNCERTAIN``: the release outcome could not be determined;
    the instance is not Released, must not be reused without an explicit
    safety determination, and must be reconciled.
    """

    RELEASED = "released"
    RELEASE_FAILED = "release-failed"
    RELEASE_OUTCOME_UNCERTAIN = "release-outcome-uncertain"


_ACTIVITY_ELIGIBLE = (
    ObservationUnitLifecyclePhase.ADMITTED,
    ObservationUnitLifecyclePhase.AVAILABLE_OR_IN_USE,
    ObservationUnitLifecyclePhase.OBSERVING_OR_SUBSCRIBED,
)


class ObservationUnitLifecycle:
    """Step-Composition-coordinated lifecycle of ONE observation-unit instance.

    The owning Step Composition is authoritative for admission, availability,
    activation, reuse, quiescence, and release: the methods below RECORD the
    Step Composition's decisions and enforce the contract's safety
    preconditions — they do not transfer lifecycle authority to the
    observation unit or to an SPU association target.

    Safety rules enforced here:

    - Admission is recorded only for a Ready (or RetainedForReuse) instance.
      Admission is distinct from technical readiness and from association with
      any target; an instance may be admitted with no active association or
      activity where the concrete Step permits it.
    - New activities are recorded only while the instance is admitted; a
      quiescing or released instance never accepts new activities (Step
      Composition has withdrawn authorization).
    - An active observation mechanism (sampling loop, subscription, callback
      registration) is recorded distinctly from one-shot activities and may
      span many observed events without a lifecycle transition per event.
    - Release is recorded only when no active activities remain AND no active
      mechanism remains; completion, failure, and uncertain outcomes are
      recorded DISTINCTLY — an attempted release is never silently labelled
      Released, and an indeterminate release leaves identity/status unresolved
      until reconciled.
    - Releasing, ending associations, and retaining records are independent
      concerns; this machine never implies any of them from the others, and
      release never erases records already accepted by their destination.
    """

    def __init__(self, identity: ObservationUnitIdentity) -> None:
        _require_type("identity", identity, ObservationUnitIdentity)
        self._identity = identity
        self._lock = threading.Lock()
        self._phase: ObservationUnitLifecyclePhase | None = None
        self._active_activities = 0
        self._release_outcome: ObservationUnitReleaseOutcome | None = None

    @property
    def identity(self) -> ObservationUnitIdentity:
        """The stable identity of the lifecycle-coordinated instance."""
        return self._identity

    @property
    def phase(self) -> ObservationUnitLifecyclePhase | None:
        """The current milestone, or None before provisioning."""
        with self._lock:
            return self._phase

    @property
    def active_activities(self) -> int:
        """Currently active (in-flight) observation activities."""
        with self._lock:
            return self._active_activities

    @property
    def release_outcome(self) -> ObservationUnitReleaseOutcome | None:
        """The recorded release outcome, or None before/at an attempted release."""
        with self._lock:
            return self._release_outcome

    @property
    def usable_for_activity(self) -> bool:
        """Whether the instance currently admits new activity authorization."""
        with self._lock:
            return self._phase in _ACTIVITY_ELIGIBLE

    def _transition(
        self,
        expected: tuple[ObservationUnitLifecyclePhase, ...],
        next_phase: ObservationUnitLifecyclePhase,
        action: str,
    ) -> None:
        with self._lock:
            if self._phase not in expected:
                raise ValueError(
                    f"cannot {action}: instance phase is "
                    f"{self._phase.value if self._phase else 'not-provisioned'}, "
                    f"expected one of {[phase.value for phase in expected]}"
                )
            self._phase = next_phase

    # -- milestone recording (each records a Step Composition decision) ----

    def provision(self) -> None:
        """Record acquisition/provisioning of the concrete runtime instance."""
        with self._lock:
            if self._phase is not None:
                raise ValueError(
                    "cannot provision: the instance lifecycle already started "
                    f"at {self._phase.value}"
                )
            self._phase = ObservationUnitLifecyclePhase.PROVISIONED_OR_ACQUIRED

    def mark_prepared(self) -> None:
        """Record that specialization-required preparation completed.

        Configuration, dependencies, capture resources, and observation
        interfaces are prepared. Partial or failed preparation must not be
        treated as readiness.
        """
        self._transition(
            (ObservationUnitLifecyclePhase.PROVISIONED_OR_ACQUIRED,),
            ObservationUnitLifecyclePhase.PREPARED,
            "mark prepared",
        )

    def determine_ready(self) -> None:
        """Record that the declared technical readiness conditions are satisfied.

        Ready does NOT mean admitted, associated, or currently observing.
        """
        self._transition(
            (ObservationUnitLifecyclePhase.PREPARED,),
            ObservationUnitLifecyclePhase.READY,
            "determine ready",
        )

    def admit(self) -> None:
        """Record Step Composition's admission decision.

        Admission authorizes the instance for use within the owning Step and
        makes it eligible for association and observation activity; it is
        distinct from association with any target and does not require
        immediate activity.
        """
        self._transition(
            (
                ObservationUnitLifecyclePhase.READY,
                ObservationUnitLifecyclePhase.RETAINED_FOR_REUSE,
            ),
            ObservationUnitLifecyclePhase.ADMITTED,
            "admit",
        )

    def begin_activity(self) -> None:
        """Record one authorized observation activity beginning.

        One-shot calls, callbacks, and sampling cycles are tracked as
        activities. A persistent mechanism is recorded separately via
        :meth:`activate_observation_mechanism`.
        """
        with self._lock:
            if self._phase not in _ACTIVITY_ELIGIBLE:
                raise ValueError(
                    "cannot begin activity: the instance is not admitted "
                    f"(phase {self._phase.value if self._phase else 'not-provisioned'})"
                )
            self._active_activities += 1
            if self._phase is ObservationUnitLifecyclePhase.ADMITTED:
                self._phase = ObservationUnitLifecyclePhase.AVAILABLE_OR_IN_USE

    def end_activity(self) -> None:
        """Record one observation activity completing (draining allowed while quiescing)."""
        with self._lock:
            if self._active_activities == 0:
                raise ValueError(
                    "cannot end activity: no active activity is recorded"
                )
            self._active_activities -= 1

    def activate_observation_mechanism(self) -> None:
        """Record an ongoing mechanism: sampling loop, subscription, callback.

        The mechanism may remain active across many observed events without a
        lifecycle transition per event. Activation is a Step-Composition
        coordination decision recorded here; it is distinct from association
        existence (an association may exist with no active mechanism, and an
        active mechanism is not implied by association).
        """
        self._transition(
            (
                ObservationUnitLifecyclePhase.ADMITTED,
                ObservationUnitLifecyclePhase.AVAILABLE_OR_IN_USE,
            ),
            ObservationUnitLifecyclePhase.OBSERVING_OR_SUBSCRIBED,
            "activate the observation mechanism",
        )

    def deactivate_observation_mechanism(self) -> None:
        """Record that the ongoing mechanism was stopped/detached."""
        self._transition(
            (ObservationUnitLifecyclePhase.OBSERVING_OR_SUBSCRIBED,),
            ObservationUnitLifecyclePhase.AVAILABLE_OR_IN_USE,
            "deactivate the observation mechanism",
        )

    def quiesce(self) -> None:
        """Record that new activities are stopped while active work reconciles.

        Quiescence coordinates termination or reconciliation of active
        observation work and pending emissions; it does not erase
        already-produced or already-accepted records.
        """
        self._transition(
            (
                ObservationUnitLifecyclePhase.ADMITTED,
                ObservationUnitLifecyclePhase.AVAILABLE_OR_IN_USE,
                ObservationUnitLifecyclePhase.OBSERVING_OR_SUBSCRIBED,
                ObservationUnitLifecyclePhase.RETAINED_FOR_REUSE,
            ),
            ObservationUnitLifecyclePhase.QUIESCING,
            "quiesce",
        )

    def retain_for_reuse(self) -> None:
        """Record the explicit choice to retain the idle instance for reuse.

        Retention for reuse is NOT an automatic consequence of ending an
        association, and it is distinct from retaining observation records.
        Reuse requires the concrete Step's reset, isolation, and readiness
        requirements; prior activity provenance is never attributed to a later
        activity.
        """
        self._transition(
            (
                ObservationUnitLifecyclePhase.ADMITTED,
                ObservationUnitLifecyclePhase.AVAILABLE_OR_IN_USE,
                ObservationUnitLifecyclePhase.OBSERVING_OR_SUBSCRIBED,
                ObservationUnitLifecyclePhase.QUIESCING,
            ),
            ObservationUnitLifecyclePhase.RETAINED_FOR_REUSE,
            "retain for reuse",
        )

    def release(
        self,
        outcome: ObservationUnitReleaseOutcome = ObservationUnitReleaseOutcome.RELEASED,
    ) -> None:
        """Record the release operation outcome.

        Preconditions enforced: no active activities, and no active observation
        mechanism (deactivate it first). The release outcome is recorded
        distinctly; only ``RELEASED`` moves the instance to the Released
        milestone. A failed or indeterminate release is NEVER labelled
        Released: the instance stays quiescing (unusable for new activities)
        and the concrete Step defines reconciliation — an indeterminate release
        must not be retried blindly where retry could duplicate or corrupt
        release effects.

        Association ending is Step Composition's separate duty: ensure every
        association that could authorize new activities has been ended,
        deactivated, or otherwise rendered unusable
        (``ObservationUnitAssociations.has_live_associations``) BEFORE recording
        a successful release. Release does not erase records already accepted
        by their destination and does not require retaining the runtime
        instance merely because historical records reference the instance
        identity.
        """
        _require_type("outcome", outcome, ObservationUnitReleaseOutcome)
        with self._lock:
            if self._phase in (
                None,
                ObservationUnitLifecyclePhase.PROVISIONED_OR_ACQUIRED,
                ObservationUnitLifecyclePhase.PREPARED,
                ObservationUnitLifecyclePhase.READY,
            ):
                raise ValueError(
                    "cannot release: instance phase is "
                    f"{self._phase.value if self._phase else 'not-provisioned'}"
                )
            if self._phase is ObservationUnitLifecyclePhase.RELEASED:
                raise ValueError("cannot release: the instance is already released")
            if self._active_activities != 0:
                raise ValueError(
                    "cannot release: active activities must be completed, "
                    "cancelled, or reconciled before release"
                )
            if self._phase is ObservationUnitLifecyclePhase.OBSERVING_OR_SUBSCRIBED:
                raise ValueError(
                    "cannot release: the observation mechanism (sampling loop, "
                    "subscription, callback) must be deactivated or reconciled "
                    "before release"
                )
            self._release_outcome = outcome
            if outcome is ObservationUnitReleaseOutcome.RELEASED:
                self._phase = ObservationUnitLifecyclePhase.RELEASED
            else:
                # Failed/uncertain: quarantine as quiescing; not Released.
                self._phase = ObservationUnitLifecyclePhase.QUIESCING


# --------------------------------------------------------------------------
# Association book (Step-Composition-owned)
# --------------------------------------------------------------------------


class ObservationUnitAssociations:
    """Association book for ONE observation unit, owned by Step Composition.

    Encodes the association contract's coordination rules so the concrete Step
    Composition (task 02 finalizes the wiring) can remain the SOLE authority
    for creating, activating, changing, rebinding, and ending associations:

    - Establishment is permitted ONLY while the instance is admitted to the
      owning Step (association existence is distinct from activation: an
      established association does not by itself start observation).
    - Association identities are unique among live AND ended associations —
      historical association identity is never reused in a way that makes
      prior records ambiguous, and an association identity is never reused for
      a relationship to a different target.
    - Dissociation records the association's end WITHOUT erasing it: the ended
      descriptor remains resolvable as historical provenance (record retention
      does not require the runtime instance, target object, callback,
      subscription handle, or any other resource to be retained).
    - Ending one association never ends the unit's other associations, and
      dissociation never releases the lifecycle instance.
    - No cardinality is imposed: one instance may observe several target
      scopes and several instances may observe one target where the concrete
      Step permits it.

    This book holds NO observation records and is NOT a global registry: it is
    the per-unit coordination surface the owning Step Composition drives.
    """

    def __init__(
        self,
        observation_unit_identity: ObservationUnitIdentity,
        lifecycle: ObservationUnitLifecycle,
        *,
        step_instance_identity: str,
    ) -> None:
        _require_type(
            "observation_unit_identity", observation_unit_identity, ObservationUnitIdentity
        )
        _require_type("lifecycle", lifecycle, ObservationUnitLifecycle)
        _require_optional_text("step_instance_identity", step_instance_identity)
        if step_instance_identity is None:
            raise ValueError("step_instance_identity is required")
        if lifecycle.identity != observation_unit_identity:
            raise ValueError(
                "the lifecycle does not belong to this observation unit instance"
            )
        self._observation_unit_identity = observation_unit_identity
        self._lifecycle = lifecycle
        self._step_instance_identity = step_instance_identity
        self._lock = threading.Lock()
        self._live: dict[ObservationUnitAssociationIdentity, ObservationUnitAssociation] = {}
        # Ended associations remain resolvable as historical provenance while
        # retained records/evidence may still reference them.
        self._ended: dict[ObservationUnitAssociationIdentity, ObservationUnitAssociation] = {}

    @property
    def observation_unit_identity(self) -> ObservationUnitIdentity:
        """The observation-unit instance this book coordinates associations for."""
        return self._observation_unit_identity

    @property
    def step_instance_identity(self) -> str:
        """The owning Step instance within which every association is valid."""
        return self._step_instance_identity

    def establish(
        self,
        association_identity: ObservationUnitAssociationIdentity,
        association_target_identity: AssociationTargetIdentity,
    ) -> ObservationUnitAssociation:
        """Establish one association to one Step-owned target scope.

        Requires the observation-unit instance to be admitted. The association
        identity must be unused among live AND ended associations (identity
        stability/no-ambiguity rule). A change that alters the target or the
        unit participant is modeled as ending the previous association and
        establishing a NEW one under a NEW identity — historical identity is
        never silently mutated. Establishment makes the unit APPLICABLE to the
        target; it does not activate observation (activation is a separate
        Step-Composition decision recorded on the lifecycle).
        """
        _require_type(
            "association_identity", association_identity, ObservationUnitAssociationIdentity
        )
        _require_type(
            "association_target_identity",
            association_target_identity,
            AssociationTargetIdentity,
        )
        with self._lock:
            if not self._lifecycle.usable_for_activity:
                # Only an admitted instance may be associated; Ready-but-not-
                # admitted, quiescing, released, and unprovisioned all refuse.
                raise ValueError(
                    "association establishment is permitted only for an "
                    f"admitted observation-unit instance (phase "
                    f"{self._lifecycle.phase.value if self._lifecycle.phase else 'not-provisioned'})"
                )
            if association_identity in self._live:
                raise ValueError(
                    f"association identity {association_identity.value!r} is "
                    "already in use; an association identity is stable for the "
                    "association's lifetime and never reused"
                )
            if association_identity in self._ended:
                raise ValueError(
                    f"association identity {association_identity.value!r} was "
                    "already used by an ended association and remains "
                    "referable by retained records; establishing a logically "
                    "similar association creates a NEW association identity"
                )
            association = ObservationUnitAssociation(
                association_identity=association_identity,
                observation_unit_identity=self._observation_unit_identity,
                association_target_identity=association_target_identity,
                step_instance_identity=self._step_instance_identity,
            )
            self._live[association_identity] = association
            return association

    def end(
        self, association_identity: ObservationUnitAssociationIdentity
    ) -> ObservationUnitAssociation:
        """Dissociate: end exactly this association (Step Composition decision).

        From the effective end point the association can no longer authorize
        new observation activities. The ended descriptor is retained as
        historical provenance; records produced under the association are NOT
        erased or rewritten; the unit's other associations and its instance
        lifecycle are untouched (dissociation is not release and does not
        decide the disposition of pending records).
        """
        _require_type(
            "association_identity", association_identity, ObservationUnitAssociationIdentity
        )
        with self._lock:
            association = self._live.pop(association_identity, None)
            if association is None:
                if association_identity in self._ended:
                    raise ValueError(
                        f"association {association_identity.value!r} is already "
                        "ended; the ended association is retained as historical "
                        "provenance"
                    )
                raise KeyError(
                    f"no live association {association_identity.value!r} for "
                    f"observation unit {self._observation_unit_identity.value!r}"
                )
            self._ended[association_identity] = association
            return association

    def get(
        self, association_identity: ObservationUnitAssociationIdentity
    ) -> ObservationUnitAssociation | None:
        """The live association, or None (unknown or ended: not usable)."""
        _require_type(
            "association_identity", association_identity, ObservationUnitAssociationIdentity
        )
        with self._lock:
            return self._live.get(association_identity)

    def usable_for_activity(
        self, association_identity: ObservationUnitAssociationIdentity
    ) -> bool:
        """Whether the association is live and may authorize new activities.

        An ended association remains identifiable as historical provenance but
        can never authorize a new activity — even while the observation unit
        itself stays admitted and ready. A True result is STILL only
        applicability: it does not mean observation is currently active.
        """
        _require_type(
            "association_identity", association_identity, ObservationUnitAssociationIdentity
        )
        with self._lock:
            return association_identity in self._live

    def has_live_associations(self) -> bool:
        """Whether any live association remains for this observation unit.

        Step Composition checks this BEFORE recording a successful instance
        release: every association that could authorize new activities must
        have been ended, deactivated, or otherwise rendered unusable first.
        """
        with self._lock:
            return bool(self._live)

    def live_associations(self) -> tuple[ObservationUnitAssociation, ...]:
        """All live associations of this observation unit."""
        with self._lock:
            return tuple(self._live.values())

    def ended_associations(self) -> tuple[ObservationUnitAssociation, ...]:
        """Ended associations retained as historical provenance descriptors.

        Historical identity/provenance remains interpretable for as long as
        retained records or other evidence require it; retention does not
        extend the observation-unit instance lifetime or keep it callable.
        """
        with self._lock:
            return tuple(self._ended.values())

    def associations_for_target(
        self, association_target_identity: AssociationTargetIdentity
    ) -> tuple[ObservationUnitAssociation, ...]:
        """The live associations targeting one Step-owned scope.

        Deliberately unconstrained in cardinality: a target may have multiple
        observation associations and a unit may serve multiple targets when
        the concrete Step permits it — no universal one-to-one mapping is
        imposed here.
        """
        with self._lock:
            return tuple(
                association
                for association in self._live.values()
                if association.association_target_identity == association_target_identity
            )


# --------------------------------------------------------------------------
# Abstract Observation Unit
# --------------------------------------------------------------------------


class SPUObservationUnit[
    TObservationInput, TTargetContext, TObservationPayload
](ABC):
    """Abstract base for ONE concrete Observation Unit specialization.

    Optional supporting pattern selected by a concrete Step for observation
    responsibilities. This is the OBSERVATION PATTERN's own activity contract —
    deliberately NOT a universal Supporting Unit base type: the concrete
    subclass defines what is observed, the activity mechanism (explicit call,
    callback, event-driven capture, sampling, subscription, or another defined
    model), the payload structure, and record-identity generation via
    :meth:`perform_observation`.

    Responsibilities (behavioral contract):

    - Perform the observation, measurement, capture, or recording capability
      defined by the concrete specialization, using the supplied input and
      target context.
    - Treat the supplied association context as the authorization scope; never
      select or substitute another association or target, and never infer the
      target identity from the observation input when an authoritative
      association target identity is supplied.
    - Preserve the distinction between the observed fact and any interpretation
      or decision made by Step Composition or another consumer.
    - Emit zero, one, or many records per activity, each with its own record
      identity, preserving full provenance until the defined handoff/acceptance
      point.

    Non-responsibilities: association management, instance lifecycle policy,
    activity timing/ordering policy, validation judgments, business meaning or
    acceptability of observed facts, creating error occurrences merely because
    a fact is noteworthy, choosing Step flow transitions, assembling or
    mutating any execution result.
    """

    def __init__(self, identity: ObservationUnitIdentity) -> None:
        _require_type("identity", identity, ObservationUnitIdentity)
        self._identity = identity

    @property
    def identity(self) -> ObservationUnitIdentity:
        """The concrete runtime instance identity of this observation unit."""
        return self._identity

    def observe(
        self,
        *,
        association: ObservationUnitAssociation,
        observation_invocation_identity: ObservationInvocationIdentity,
        step_instance_identity: str,
        observation_input: TObservationInput | None = None,
        target_context: TTargetContext | None = None,
        observation_subject_identity: str | None = None,
        observation_timestamp: str | None = None,
        source_invocation_identity: str | None = None,
        source_event_identity: str | None = None,
        sequence_metadata: str | None = None,
        observation_metadata: str | None = None,
    ) -> tuple[ObservationRecord[TObservationPayload], ...]:
        """Run one authorized observation activity and wrap its emitted records.

        Activity contract enforced at this boundary:

        - The activity is correlated with EXACTLY ONE association context —
          the one supplied by Step Composition. Observing under a foreign
          association (a different observation unit's) is refused: the
          activity must never be silently redirected.
        - The target provenance comes from the association's
          ``association_target_identity``, never from the observation input.
        - The activity identity identifies THIS activity; repeated activities
          under the same association receive distinct activity identities.
        - :meth:`perform_observation` carries the specialization semantics and
          returns zero, one, or many ``(payload, record_identity)`` emissions;
          each is wrapped into a fully-provenanced :class:`ObservationRecord`.
          An activity that emits nothing completes normally.
        - If the mechanism THROWS, the exception propagates as an activity
          failure and NO record is fabricated; records already produced by
          this activity are not revoked (they remain subject to their custody
          contracts). A noteworthy or negative observed fact is never an
          automatic failure — only the specialization classifies failures.
        """
        _require_type("association", association, ObservationUnitAssociation)
        _require_type(
            "observation_invocation_identity",
            observation_invocation_identity,
            ObservationInvocationIdentity,
        )
        _require_optional_text("step_instance_identity", step_instance_identity)
        if step_instance_identity is None:
            raise ValueError("step_instance_identity is required")
        for name, value in (
            ("observation_subject_identity", observation_subject_identity),
            ("observation_timestamp", observation_timestamp),
            ("source_invocation_identity", source_invocation_identity),
            ("source_event_identity", source_event_identity),
            ("sequence_metadata", sequence_metadata),
            ("observation_metadata", observation_metadata),
        ):
            _require_optional_text(name, value)
        if association.observation_unit_identity != self._identity:
            raise ValueError(
                "the supplied association does not authorize this observation "
                f"unit: association binds observation unit "
                f"{association.observation_unit_identity.value!r}, invoked "
                f"{self._identity.value!r}; an activity must not be silently "
                "redirected to another association"
            )

        emissions = self.perform_observation(observation_input, target_context)

        records: list[ObservationRecord[TObservationPayload]] = []
        seen_record_identities: set[ObservationRecordIdentity] = set()
        for emission in emissions:
            payload, record_identity = emission
            _require_type(
                "record_identity", record_identity, ObservationRecordIdentity
            )
            if record_identity in seen_record_identities:
                raise ValueError(
                    f"record identity {record_identity.value!r} was emitted twice "
                    "by one activity; every separately identifiable record must "
                    "carry its own observationRecordIdentity"
                )
            seen_record_identities.add(record_identity)
            records.append(
                ObservationRecord[TObservationPayload](
                    step_instance_identity=step_instance_identity,
                    observation_unit_identity=self._identity,
                    observation_unit_association_identity=association.association_identity,
                    association_target_identity=association.association_target_identity,
                    observation_invocation_identity=observation_invocation_identity,
                    observation_record_identity=record_identity,
                    payload=payload,
                    observation_subject_identity=observation_subject_identity,
                    observation_timestamp=observation_timestamp,
                    source_invocation_identity=source_invocation_identity,
                    source_event_identity=source_event_identity,
                    sequence_metadata=sequence_metadata,
                    observation_metadata=observation_metadata,
                )
            )
        return tuple(records)

    @abstractmethod
    def perform_observation(
        self,
        observation_input: TObservationInput | None,
        target_context: TTargetContext | None,
    ) -> Sequence[tuple[TObservationPayload, ObservationRecordIdentity]]:
        """Perform the concrete observation; return zero or more emissions.

        Each emission is a ``(payload, record_identity)`` pair: the payload is
        the specialization-defined observation content, and the record identity
        is the specialization-generated identity of THAT emitted record (the
        specialization defines generation and uniqueness scope). Return an
        empty sequence when the activity legitimately observes nothing — an
        empty emission is a NORMAL completion, not a failure. Raise only for
        activity inability or implementation-level failure (source access,
        measurement, record construction, delivery per the specialization),
        never to express that an observed fact is noteworthy.
        """
        raise NotImplementedError
