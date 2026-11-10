"""SPU Validator Unit — working protocol for the optional validation pattern.

Implementation task: 05_Validator_Unit
Related diagrams:
  class: 03_Diagrams_Codes_Files/01_SPU_Step_Processing_Unit.dot
  sequence: B_Sequencial_Diagram_Code/03_Validator_Unit_Sequence.puml
  association: C_Association_Diagram_Code/05_Validator_Unit_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/04_Supporting_Pattern_Optional_Dependency.dot

Contract basis:
  - Step_Supporting_Validator_Unit_Contract.json (behavioral: invocation
    boundary, result semantics, custody, failure boundary)
  - Step_Supporting_Validator_Unit_Association_Contract.json (association
    identity, target binding, applicability, dissociation)
  - Step_Supporting_Validator_Unit_Lifecycle_Contract.json (instance
    lifecycle milestones, admission, quiescence, release)
  - Common/Step_Composition_Association_Coordination_Contract.json and
    Common/Step_Composition_Internal_Component_Lifecycle_Coordination_Contract.json
    (specialized here with validator-specific identity names and mechanics)

Dependency boundary (``04_Supporting_Pattern_Optional_Dependency.dot``):
``ValidatorUnit -> Core : NO dependency``; ``ValidatorUnit -> Prefect : NO
dependency``. This package imports NOTHING from ``gpwcf`` (stdlib only).

What this module provides (the reusable protocol shape a concrete Step owns
and coordinates — NOT a universal validation algorithm and not a universal
Supporting Unit base type):

  - :class:`SPUValidatorResult` — the structured result of one normally
    completed validator invocation, with the mandatory invocation/association
    provenance. Its ``validation_outcome`` is the SPECIALIZATION-defined
    domain conclusion: a negative conclusion (rejection, invalidity,
    non-compliance) is still a normally produced result — NEVER an automatic
    invocation failure, and no universal pass/fail boolean or severity model
    is defined here. Carried independently in the optional ``validatorResult``
    slot of ``SPUExecutionResult`` (task 01 forward reference) — this result is
    distinct from SPUExecutionResult, StepExecutionResult, StepValidatorResult,
    ErrorResult, and ErrorHandlerResult.
  - :class:`ValidatorUnitAssociation` — the identity-bearing relationship
    between one validator-unit instance and ONE Step-owned target scope. The
    association identity is distinct from both participant identities
    (nominal types make conflation unrepresentable). One validator-unit
    instance associated with three target scopes is one validatorUnitIdentity
    plus three association identities.
  - :class:`ValidatorUnitLifecycle` (with :class:`ValidatorUnitLifecyclePhase`
    and :class:`ValidatorUnitReleaseOutcome`) — the Step-Composition-coordinated
    instance lifecycle milestones: provisioned → prepared → ready → admitted →
    available/in-use → quiescing → retained-for-reuse / released. Milestones
    are conceptual (the contract does not mandate a fixed state machine);
    admission, quiescence, reuse, and release decisions are recorded here when
    the owning Step Composition makes them. Release completion, failure, and
    uncertain outcomes are recorded DISTINCTLY — an attempted release is never
    silently labelled Released.
  - :class:`ValidatorUnitAssociations` — the Step-Composition-owned
    association book for ONE validator-unit instance: establishment (only for
    an admitted instance; identity unique and never reused while retained
    evidence may still be observable), dissociation (does not release the
    instance, does not erase historical provenance, does not end the unit's
    other associations), and invocation-usability checks.
  - :class:`SPUValidatorUnit` — the abstract base for concrete validator
    specializations. The concrete subclass defines WHAT is validated, the
    meaning of its outcome, and its evidence structure via :meth:`evaluate`;
    the shared :meth:`validate` boundary enforces the invocation contract:
    invocation under exactly one authorized association context, target taken
    from that association (never inferred from the validation input), full
    provenance on every normally completed invocation, and NO fabricated
    result when evaluation throws (an exception is an invocation failure, not
    a validation outcome; it never revokes a result handed off earlier).

Explicit non-goals (per contract ``explicitNonGoals``): no mandatory validator
for any Step, no one-validator-per-SPU or one-validator-per-Step rule, no
universal validation algorithm/status taxonomy/evidence schema, no association
or lifecycle authority for the validator unit or the SPU target, no Step flow
control, no automatic conversion of outcomes or exceptions into SPU/Step
errors, no global registry or central mediator.
"""

from __future__ import annotations

import enum
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .identities import (
    AssociationTargetIdentity,
    AssociationTargetScopeKind,
    ValidatorInvocationIdentity,
    ValidatorUnitAssociationIdentity,
    ValidatorUnitIdentity,
)

__all__ = [
    "SPUValidatorResult",
    "ValidatorUnitAssociation",
    "ValidatorUnitLifecyclePhase",
    "ValidatorUnitReleaseOutcome",
    "ValidatorUnitLifecycle",
    "ValidatorUnitAssociations",
    "SPUValidatorUnit",
]


# --------------------------------------------------------------------------
# SPUValidatorResult
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SPUValidatorResult[TValidationOutcome, TValidationEvidence = object]:
    """Structured result of ONE normally completed validator invocation.

    Produced by the invoked Validator Unit instance; handed off to Step
    Composition for custody, retention, and Step-specific consumption. Carried
    independently in the optional ``validatorResult`` slot of
    ``SPUExecutionResult`` — it is never merged into, and never mutates, any
    execution result, and it is distinct from StepValidatorResult, ErrorResult,
    and ErrorHandlerResult.

    Semantics (per the behavioral contract):

    - ``validation_outcome`` is the specialization-defined DOMAIN conclusion.
      Its type and interpretation are not standardized here: no universal
      pass/fail boolean, no severity taxonomy, no Prescribed/Failed naming. An
      outcome expressing rejection, invalidity, or non-compliance is still a
      normally produced validation result — NOT an invocation failure and NOT a
      Step flow-control decision.
    - ``validation_evidence`` is INDEPENDENTLY optional: absence of evidence is
      not a success/failure status. Evidence never rewrites the outcome.
    - Provenance invariants: the result identifies exactly ONE validator
      invocation; ``validator_unit_identity`` identifies the instance that
      actually performed it; association/target provenance matches the
      association context bound to that invocation and is NEVER rewritten when
      the association later changes or ends; two results from two different
      invocations remain distinguishable even with identical outcomes under the
      same association.
    """

    step_instance_identity: str
    validator_unit_identity: ValidatorUnitIdentity
    validator_unit_association_identity: ValidatorUnitAssociationIdentity
    association_target_identity: AssociationTargetIdentity
    validator_invocation_identity: ValidatorInvocationIdentity
    validation_outcome: TValidationOutcome
    validation_evidence: TValidationEvidence | None = None
    validation_subject_reference: str | None = None
    completion_metadata: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.step_instance_identity, str) or (
            self.step_instance_identity == "" or self.step_instance_identity.isspace()
        ):
            raise ValueError(
                "step_instance_identity must be a non-empty, non-blank string"
            )
        _require_type(
            "validator_unit_identity", self.validator_unit_identity, ValidatorUnitIdentity
        )
        _require_type(
            "validator_unit_association_identity",
            self.validator_unit_association_identity,
            ValidatorUnitAssociationIdentity,
        )
        _require_type(
            "association_target_identity",
            self.association_target_identity,
            AssociationTargetIdentity,
        )
        _require_type(
            "validator_invocation_identity",
            self.validator_invocation_identity,
            ValidatorInvocationIdentity,
        )
        for name in ("validation_subject_reference", "completion_metadata"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, str) or value == "" or value.isspace()
            ):
                raise ValueError(f"{name} must be a non-empty string or None")


def _require_type(name: str, value: object, expected: type) -> None:
    if type(value) is not expected:
        raise TypeError(
            f"{name} must be {expected.__name__}, got {type(value).__name__}"
        )


# --------------------------------------------------------------------------
# ValidatorUnitAssociation
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidatorUnitAssociation:
    """Identity-bearing relationship: one validator unit ↔ one target scope.

    Association = APPLICABILITY ONLY. It is not ownership of the validator
    unit, not an invocation, not a validation result, not a lifecycle
    operation, and not a flow-control decision. It does not transfer
    association-management authority to the target (an SPU target acquires no
    authority over the validator merely by being targeted).

    Identity rules (association contract):

    - ``association_identity`` identifies THIS relationship instance — distinct
      from the validator-unit identity and the target identity (each is a
      different nominal type; conflation is unrepresentable).
    - Every association belongs to exactly one owning Step instance and
      identifies exactly one target scope.
    - The identity is stable for the association's lifetime; ending this
      association does not end the validator unit's other associations, does
      not release the validator-unit instance, and does not erase validation
      results or provenance already produced under it.
    """

    association_identity: ValidatorUnitAssociationIdentity
    validator_unit_identity: ValidatorUnitIdentity
    association_target_identity: AssociationTargetIdentity
    step_instance_identity: str

    def __post_init__(self) -> None:
        _require_type(
            "association_identity", self.association_identity, ValidatorUnitAssociationIdentity
        )
        _require_type(
            "validator_unit_identity", self.validator_unit_identity, ValidatorUnitIdentity
        )
        _require_type(
            "association_target_identity",
            self.association_target_identity,
            AssociationTargetIdentity,
        )
        if (
            not isinstance(self.step_instance_identity, str)
            or self.step_instance_identity == ""
            or self.step_instance_identity.isspace()
        ):
            raise ValueError(
                "step_instance_identity must be a non-empty, non-blank string"
            )

    @property
    def target_scope_kind(self) -> AssociationTargetScopeKind:
        """The kind of Step-owned scope this association targets."""
        return self.association_target_identity.scope_kind


# --------------------------------------------------------------------------
# Validator Unit Lifecycle
# --------------------------------------------------------------------------


class ValidatorUnitLifecyclePhase(enum.Enum):
    """Conceptual lifecycle milestones for a Validator Unit instance.

    Milestones, not a mandatory enum state machine and not a requirement that
    every implementation materialize each phase: the concrete Step defines the
    actual lifecycle policy consistent with the lifecycle contract. The
    instance lifecycle is INDEPENDENT of association lifetimes and of
    validation-evidence retention lifetimes.
    """

    PROVISIONED_OR_ACQUIRED = "provisioned-or-acquired"
    PREPARED = "prepared"
    READY = "ready"
    ADMITTED = "admitted"
    AVAILABLE_OR_IN_USE = "available-or-in-use"
    QUIESCING = "quiescing"
    RETAINED_FOR_REUSE = "retained-for-reuse"
    RELEASED = "released"


class ValidatorUnitReleaseOutcome(enum.Enum):
    """Recorded outcome of the instance release operation.

    ``RELEASED``: the required release procedure completed successfully.
    ``RELEASE_FAILED``: the release procedure failed; the instance is not
    Released and the concrete Step defines quarantine/reconciliation.
    ``RELEASE_OUTCOME_UNCERTAIN``: the release outcome could not be determined;
    the instance is not Released and must be reconciled.
    """

    RELEASED = "released"
    RELEASE_FAILED = "release-failed"
    RELEASE_OUTCOME_UNCERTAIN = "release-outcome-uncertain"


_INVOCATION_ELIGIBLE = (
    ValidatorUnitLifecyclePhase.ADMITTED,
    ValidatorUnitLifecyclePhase.AVAILABLE_OR_IN_USE,
)


class ValidatorUnitLifecycle:
    """Step-Composition-coordinated lifecycle of ONE validator-unit instance.

    The owning Step Composition is authoritative for admission, availability,
    reuse, quiescence, and release: the methods below RECORD the Step
    Composition's decisions and enforce the contract's safety preconditions —
    they do not transfer lifecycle authority to the validator unit or to an SPU
    association target.

    Safety rules enforced here:

    - Admission is recorded only for a Ready (or RetainedForReuse) instance.
    - New invocations are recorded only while the instance is admitted; a
      quiescing or released instance never accepts new invocations.
    - Release is recorded only when no active invocations remain; completion,
      failure, and uncertain outcomes are recorded DISTINCTLY — an attempted
      release is never silently labelled Released.
    - Ending associations, retaining evidence, and releasing the instance are
      independent concerns; this machine never implies any of them from the
      others.
    """

    def __init__(self, identity: ValidatorUnitIdentity) -> None:
        _require_type("identity", identity, ValidatorUnitIdentity)
        self._identity = identity
        self._lock = threading.Lock()
        self._phase: ValidatorUnitLifecyclePhase | None = None
        self._active_invocations = 0
        self._release_outcome: ValidatorUnitReleaseOutcome | None = None

    @property
    def identity(self) -> ValidatorUnitIdentity:
        """The stable identity of the lifecycle-coordinated instance."""
        return self._identity

    @property
    def phase(self) -> ValidatorUnitLifecyclePhase | None:
        """The current milestone, or None before provisioning."""
        with self._lock:
            return self._phase

    @property
    def active_invocations(self) -> int:
        """Currently active (in-flight) invocations tracked for safe release."""
        with self._lock:
            return self._active_invocations

    @property
    def release_outcome(self) -> ValidatorUnitReleaseOutcome | None:
        """The recorded release outcome, or None before/at an attempted release."""
        with self._lock:
            return self._release_outcome

    @property
    def usable_for_invocation(self) -> bool:
        """Whether the instance currently admits new invocation authorization."""
        with self._lock:
            return self._phase in _INVOCATION_ELIGIBLE

    def _transition(self, expected: tuple[ValidatorUnitLifecyclePhase, ...], next_phase: ValidatorUnitLifecyclePhase, action: str) -> None:
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
            self._phase = ValidatorUnitLifecyclePhase.PROVISIONED_OR_ACQUIRED

    def mark_prepared(self) -> None:
        """Record that implementation-specific preparation completed.

        Partial or failed preparation must not be treated as readiness: only a
        provisioned instance can be marked prepared.
        """
        self._transition(
            (ValidatorUnitLifecyclePhase.PROVISIONED_OR_ACQUIRED,),
            ValidatorUnitLifecyclePhase.PREPARED,
            "mark prepared",
        )

    def determine_ready(self) -> None:
        """Record that the Step's readiness criteria are satisfied.

        Ready does NOT mean admitted, associated, or currently executing.
        """
        self._transition(
            (ValidatorUnitLifecyclePhase.PREPARED,),
            ValidatorUnitLifecyclePhase.READY,
            "determine ready",
        )

    def admit(self) -> None:
        """Record Step Composition's admission decision.

        Admission makes the instance eligible for association and invocation;
        it is distinct from association with any target and does not require
        immediate invocation.
        """
        self._transition(
            (
                ValidatorUnitLifecyclePhase.READY,
                ValidatorUnitLifecyclePhase.RETAINED_FOR_REUSE,
            ),
            ValidatorUnitLifecyclePhase.ADMITTED,
            "admit",
        )

    def begin_invocation(self) -> None:
        """Record one authorized invocation beginning (eligibility enforced)."""
        with self._lock:
            if self._phase not in _INVOCATION_ELIGIBLE:
                raise ValueError(
                    "cannot begin invocation: the instance is not admitted "
                    f"(phase {self._phase.value if self._phase else 'not-provisioned'})"
                )
            self._active_invocations += 1
            self._phase = ValidatorUnitLifecyclePhase.AVAILABLE_OR_IN_USE

    def end_invocation(self) -> None:
        """Record one invocation completing (draining is allowed while quiescing)."""
        with self._lock:
            if self._active_invocations == 0:
                raise ValueError(
                    "cannot end invocation: no active invocation is recorded"
                )
            self._active_invocations -= 1

    def quiesce(self) -> None:
        """Record that new invocations are stopped while active work reconciles.

        Quiescence does not erase already-produced results or evidence.
        """
        self._transition(
            (
                ValidatorUnitLifecyclePhase.ADMITTED,
                ValidatorUnitLifecyclePhase.AVAILABLE_OR_IN_USE,
                ValidatorUnitLifecyclePhase.RETAINED_FOR_REUSE,
            ),
            ValidatorUnitLifecyclePhase.QUIESCING,
            "quiesce",
        )

    def retain_for_reuse(self) -> None:
        """Record the explicit choice to retain the idle instance for reuse.

        Retention for reuse is NOT an automatic consequence of ending an
        association, and it is distinct from retaining validation evidence.
        """
        self._transition(
            (
                ValidatorUnitLifecyclePhase.ADMITTED,
                ValidatorUnitLifecyclePhase.AVAILABLE_OR_IN_USE,
                ValidatorUnitLifecyclePhase.QUIESCING,
            ),
            ValidatorUnitLifecyclePhase.RETAINED_FOR_REUSE,
            "retain for reuse",
        )

    def release(self, outcome: ValidatorUnitReleaseOutcome = ValidatorUnitReleaseOutcome.RELEASED) -> None:
        """Record the release operation outcome.

        Preconditions enforced: no active invocations (active work must be
        completed, cancelled, drained, or otherwise reconciled first). The
        release outcome is recorded distinctly; only ``RELEASED`` moves the
        instance to the Released milestone. A failed or uncertain release is
        NEVER labelled Released: the instance stays quiescing (unusable for new
        invocations) and the concrete Step defines quarantine/reconciliation.

        Association ending is Step Composition's separate duty: ensure every
        association involving the instance has been ended or invalidated
        (``ValidatorUnitAssociations.has_live_associations``) BEFORE recording
        a successful release.
        """
        _require_type("outcome", outcome, ValidatorUnitReleaseOutcome)
        with self._lock:
            if self._phase not in (
                ValidatorUnitLifecyclePhase.ADMITTED,
                ValidatorUnitLifecyclePhase.AVAILABLE_OR_IN_USE,
                ValidatorUnitLifecyclePhase.QUIESCING,
                ValidatorUnitLifecyclePhase.RETAINED_FOR_REUSE,
            ):
                raise ValueError(
                    "cannot release: instance phase is "
                    f"{self._phase.value if self._phase else 'not-provisioned'}"
                )
            if self._active_invocations != 0:
                raise ValueError(
                    "cannot release: active invocations must be completed, "
                    "cancelled, or drained before release"
                )
            self._release_outcome = outcome
            if outcome is ValidatorUnitReleaseOutcome.RELEASED:
                self._phase = ValidatorUnitLifecyclePhase.RELEASED
            else:
                # Failed/uncertain: quarantine as quiescing; not Released.
                self._phase = ValidatorUnitLifecyclePhase.QUIESCING


# --------------------------------------------------------------------------
# Association book (Step-Composition-owned)
# --------------------------------------------------------------------------


class ValidatorUnitAssociations:
    """Association book for ONE validator unit, owned by Step Composition.

    Encodes the association contract's coordination rules so the concrete Step
    Composition (task 02 finalizes the wiring) can remain the SOLE authority
    for establishing, changing, and ending associations:

    - Establishment is permitted ONLY while the instance is admitted to the
      owning Step.
    - Association identities are unique among live AND ended associations —
      identity reuse while retained evidence may still be observable is
      refused, and an association identity is never reused for a relationship
      to a different target.
    - Dissociation records the association's end WITHOUT erasing it: the ended
      descriptor remains resolvable as historical provenance (result retention
      does not require the validator runtime instance to remain alive).
    - Ending one association never ends the unit's other associations, and
      dissociation never releases the lifecycle instance.

    This book holds NO validation results and is NOT a global registry: it is
    the per-unit coordination surface the owning Step Composition drives.
    """

    def __init__(
        self,
        validator_unit_identity: ValidatorUnitIdentity,
        lifecycle: ValidatorUnitLifecycle,
        *,
        step_instance_identity: str,
    ) -> None:
        _require_type(
            "validator_unit_identity", validator_unit_identity, ValidatorUnitIdentity
        )
        _require_type("lifecycle", lifecycle, ValidatorUnitLifecycle)
        if (
            not isinstance(step_instance_identity, str)
            or step_instance_identity == ""
            or step_instance_identity.isspace()
        ):
            raise ValueError(
                "step_instance_identity must be a non-empty, non-blank string"
            )
        if lifecycle.identity != validator_unit_identity:
            raise ValueError(
                "the lifecycle does not belong to this validator unit instance"
            )
        self._validator_unit_identity = validator_unit_identity
        self._lifecycle = lifecycle
        self._step_instance_identity = step_instance_identity
        self._lock = threading.Lock()
        self._live: dict[ValidatorUnitAssociationIdentity, ValidatorUnitAssociation] = {}
        # Ended associations remain resolvable as historical provenance while
        # retained results/evidence may still reference them.
        self._ended: dict[ValidatorUnitAssociationIdentity, ValidatorUnitAssociation] = {}

    @property
    def validator_unit_identity(self) -> ValidatorUnitIdentity:
        """The validator-unit instance this book coordinates associations for."""
        return self._validator_unit_identity

    @property
    def step_instance_identity(self) -> str:
        """The owning Step instance within which every association is valid."""
        return self._step_instance_identity

    def establish(
        self,
        association_identity: ValidatorUnitAssociationIdentity,
        association_target_identity: AssociationTargetIdentity,
    ) -> ValidatorUnitAssociation:
        """Establish one association to one Step-owned target scope.

        Requires the validator-unit instance to be admitted. The association
        identity must be unused among live AND ended associations (identity
        stability/no-reuse rule). A change that alters the target or validator
        participant is modeled as ending the previous association and
        establishing a NEW one under a NEW identity.
        """
        _require_type(
            "association_identity", association_identity, ValidatorUnitAssociationIdentity
        )
        _require_type(
            "association_target_identity",
            association_target_identity,
            AssociationTargetIdentity,
        )
        with self._lock:
            if not self._lifecycle.usable_for_invocation:
                # Only an admitted instance may be associated; Ready-but-not-
                # admitted, quiescing, released, and unprovisioned all refuse.
                raise ValueError(
                    "association establishment is permitted only for an "
                    f"admitted validator-unit instance (phase "
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
                    "referable by retained evidence; establishing a logically "
                    "similar association creates a NEW association identity"
                )
            association = ValidatorUnitAssociation(
                association_identity=association_identity,
                validator_unit_identity=self._validator_unit_identity,
                association_target_identity=association_target_identity,
                step_instance_identity=self._step_instance_identity,
            )
            self._live[association_identity] = association
            return association

    def end(self, association_identity: ValidatorUnitAssociationIdentity) -> ValidatorUnitAssociation:
        """Dissociate: end exactly this association (Step Composition decision).

        From the effective end point no new validator invocation may rely on
        the association. The ended descriptor is retained as historical
        provenance; validation results produced under the association are NOT
        erased or rewritten; the validator unit's other associations and its
        instance lifecycle are untouched (dissociation is not release).
        """
        _require_type(
            "association_identity", association_identity, ValidatorUnitAssociationIdentity
        )
        with self._lock:
            association = self._live.pop(association_identity, None)
            if association is None:
                if association_identity in self._ended:
                    raise ValueError(
                        f"association {association_identity.value!r} is already "
                        "ended; dissociation is idempotent-unfriendly: the ended "
                        "association is retained as historical provenance"
                    )
                raise KeyError(
                    f"no live association {association_identity.value!r} for "
                    f"validator unit {self._validator_unit_identity.value!r}"
                )
            self._ended[association_identity] = association
            return association

    def get(self, association_identity: ValidatorUnitAssociationIdentity) -> ValidatorUnitAssociation | None:
        """The live association, or None (unknown or ended: not usable)."""
        _require_type(
            "association_identity", association_identity, ValidatorUnitAssociationIdentity
        )
        with self._lock:
            return self._live.get(association_identity)

    def usable_for_invocation(
        self, association_identity: ValidatorUnitAssociationIdentity
    ) -> bool:
        """Whether the association is live and may authorize new invocations.

        An ended association remains identifiable as historical provenance but
        can never authorize a new invocation — even while the validator unit
        itself stays admitted and ready.
        """
        _require_type(
            "association_identity", association_identity, ValidatorUnitAssociationIdentity
        )
        with self._lock:
            return association_identity in self._live

    def has_live_associations(self) -> bool:
        """Whether any live association remains for this validator unit.

        Step Composition checks this BEFORE recording a successful instance
        release: every association involving the instance must have been ended
        or invalidated for future invocation first.
        """
        with self._lock:
            return bool(self._live)

    def live_associations(self) -> tuple[ValidatorUnitAssociation, ...]:
        """All live associations of this validator unit."""
        with self._lock:
            return tuple(self._live.values())

    def ended_associations(self) -> tuple[ValidatorUnitAssociation, ...]:
        """Ended associations retained as historical provenance descriptors.

        Historical identity/provenance remains referable for as long as
        retained results or evidence require it; retention does not extend the
        validator-unit instance lifetime or keep it callable.
        """
        with self._lock:
            return tuple(self._ended.values())

    def associations_for_target(
        self, association_target_identity: AssociationTargetIdentity
    ) -> tuple[ValidatorUnitAssociation, ...]:
        """The live associations targeting one Step-owned scope.

        Deliberately unconstrained in cardinality: a target may have multiple
        validator associations and a unit may serve multiple targets when the
        concrete Step permits it — no universal one-validator-per-SPU rule is
        imposed here.
        """
        with self._lock:
            return tuple(
                association
                for association in self._live.values()
                if association.association_target_identity == association_target_identity
            )


# --------------------------------------------------------------------------
# Abstract Validator Unit
# --------------------------------------------------------------------------


class SPUValidatorUnit[
    TValidationInput, TTargetContext, TValidationOutcome, TValidationEvidence
](ABC):
    """Abstract base for ONE concrete Validator Unit specialization.

    Optional supporting pattern selected by a concrete Step for validation
    responsibilities. This is the VALIDATOR PATTERN's own callable contract —
    deliberately NOT a universal Supporting Unit base type: the concrete
    subclass defines what is validated, the meaning of its outcome, its
    evidence structure, and its validation rules via :meth:`evaluate`.

    Responsibilities (behavioral contract):

    - Apply the validation rules of the concrete specialization using only the
      supplied validation input and target context.
    - Treat the supplied association context as the authorization scope; never
      select or substitute another association or target, and never infer the
      target identity from the validation input when an authoritative
      association target identity is supplied.
    - Produce a structured :class:`SPUValidatorResult` for each invocation that
      completes normally, with full invocation and association provenance.

    Non-responsibilities: association management, instance lifecycle policy,
    invocation timing/ordering, Step flow control, aggregation into
    StepValidatorResult, construction of StepExecutionResult, and creating
    errors merely because an outcome is a negative domain conclusion.
    """

    def __init__(self, identity: ValidatorUnitIdentity) -> None:
        _require_type("identity", identity, ValidatorUnitIdentity)
        self._identity = identity

    @property
    def identity(self) -> ValidatorUnitIdentity:
        """The concrete runtime instance identity of this validator unit."""
        return self._identity

    def validate(
        self,
        *,
        association: ValidatorUnitAssociation,
        validator_invocation_identity: ValidatorInvocationIdentity,
        step_instance_identity: str,
        validation_input: TValidationInput,
        target_context: TTargetContext | None = None,
        validation_subject_reference: str | None = None,
        completion_metadata: str | None = None,
    ) -> SPUValidatorResult[TValidationOutcome, TValidationEvidence]:
        """Run one authorized validation invocation and wrap its conclusion.

        Invocation contract enforced at this boundary:

        - The invocation is correlated with EXACTLY ONE association context —
          the one supplied by Step Composition. Invoking under a foreign
          association (a different validator unit's) is refused: the
          invocation must never be silently redirected.
        - The target provenance comes from the association's
          ``association_target_identity``, never from the validation input.
        - The invocation identity identifies THIS attempt; repeated invocations
          under the same association receive distinct invocation identities and
          produce distinguishable results.
        - :meth:`evaluate` carries the specialization semantics; if it THROWS,
          the exception propagates as an invocation failure and NO validation
          result is fabricated. An exception never revokes a result handed off
          before it.
        """
        _require_type("association", association, ValidatorUnitAssociation)
        _require_type(
            "validator_invocation_identity",
            validator_invocation_identity,
            ValidatorInvocationIdentity,
        )
        if (
            not isinstance(step_instance_identity, str)
            or step_instance_identity == ""
            or step_instance_identity.isspace()
        ):
            raise ValueError(
                "step_instance_identity must be a non-empty, non-blank string"
            )
        if association.validator_unit_identity != self._identity:
            raise ValueError(
                "the supplied association does not authorize this validator "
                f"unit: association binds validator unit "
                f"{association.validator_unit_identity.value!r}, invoked "
                f"{self._identity.value!r}; an invocation must not be silently "
                "redirected to another association"
            )

        outcome, evidence = self.evaluate(validation_input, target_context)

        return SPUValidatorResult[
            TValidationOutcome, TValidationEvidence
        ](
            step_instance_identity=step_instance_identity,
            validator_unit_identity=self._identity,
            validator_unit_association_identity=association.association_identity,
            association_target_identity=association.association_target_identity,
            validator_invocation_identity=validator_invocation_identity,
            validation_outcome=outcome,
            validation_evidence=evidence,
            validation_subject_reference=validation_subject_reference,
            completion_metadata=completion_metadata,
        )

    @abstractmethod
    def evaluate(
        self,
        validation_input: TValidationInput,
        target_context: TTargetContext | None,
    ) -> tuple[TValidationOutcome, TValidationEvidence | None]:
        """Apply the concrete validation semantics; return (outcome, evidence).

        The outcome is the specialization-defined domain conclusion — its type
        and interpretation are the specialization's own. Returning a negative
        conclusion is a NORMAL completion: raise only for invocation inability
        or implementation-level failure, never to express a validation
        conclusion. Evidence is optional (return None when absent).
        """
        raise NotImplementedError
