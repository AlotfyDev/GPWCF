"""Step public lifecycle boundary: admission, disposition, settlement.

Implementation task: 02_Step
Related diagrams:
  class: 03_Diagrams_Codes_Files/02_Step.dot
  sequence: B_Sequencial_Diagram_Code/05_Step_Execution_Sequence.puml
  dependency: D_Architectural_Dependency_Diagram_Code/02_Architectural_Level_Dependency_Graph.dot

Contract basis:
  - Step_Contract.json (``pipeline.step.contract``) — public lifecycle boundary
  - Step_Termination_Integration_Review.md — termination/lifecycle integration

Ownership split (Stage Composition owns the OUTER decision; Step owns the
ordering): Stage Composition requests a disposition — retention for reuse or
terminal retirement — through the public Step boundary; the Step Aggregate
Root owns the ordering between ``execute`` admission and terminal-retirement
admission closure, and remains accountable for never CONFIRMING a disposition
while accepted work is unsettled.

Linearizability: ONE lock guards ``admit`` / ``close`` / ``settle`` / snapshot
so admission ordering is linearizable. ``close`` returns the accepted-but-
unsettled snapshot atomically with closure — that snapshot is exactly the
drain set (nothing can be admitted after closure; work admitted before
closure either settles afterwards or stays unsettled).

Identity discipline: the ever-accepted ledger retains every admitted
invocation identity permanently. The same ``step_invocation_identity`` is
never admitted twice — not even after its invocation settled, and not after
reuse reopens admission. A candidate value can never be silently reused for a
different invocation.

Failure discipline: an execution exception leaves its invocation accepted but
UNSETTLED — retirement can never confirm over it; the disposition outcome is
FAILED (incomplete settlement) or INDETERMINATE (settlement could not be
determined), the Step phase becomes QUARANTINED, and only a terminal-
retirement re-request may be re-attempted from quarantine. Lifecycle outcomes
are recorded distinctly from any ``StepExecutionResult`` — they are the
result of a separate public interaction, never a Step execution result.
"""

from __future__ import annotations

import enum
import threading
from typing import Callable

from gpwcf.core.identities import StepIdentity, StepInvocationIdentity
from gpwcf.core.step.composition import StepSettlementReport
from gpwcf.core.step.invocation import StepInvocationRejected

__all__ = [
    "StepAdmissionBoundary",
    "StepLifecycle",
    "StepLifecycleDisposition",
    "StepLifecycleError",
    "StepLifecycleOutcome",
    "StepLifecycleStatus",
]


class StepLifecycleError(RuntimeError):
    """A lifecycle transition was requested outside its valid phase."""


class StepLifecycleStatus(enum.Enum):
    """Phase of the Step's public lifecycle boundary.

    - IN_SERVICE: normal operation; execute admission is open.
    - DRAINING_FOR_REUSE: retention requested; admission closed; accepted
      work settling; admission stays closed until reuse readiness is
      explicitly confirmed.
    - RETAINED_FOR_REUSE: retention confirmed; admission remains CLOSED
      until ``confirm_reuse_readiness`` reopens it.
    - DRAINING_FOR_RETIREMENT: terminal retirement requested; admission
      closed; accepted work settling.
    - QUARANTINED: a disposition attempt failed or was indeterminate; the
      Step must not be reused; only a terminal-retirement re-request may be
      re-attempted.
    - TERMINALLY_RETIRED: terminal retirement confirmed; admission is
      permanently closed and can never reopen.
    """

    IN_SERVICE = "in-service"
    DRAINING_FOR_REUSE = "draining-for-reuse"
    RETAINED_FOR_REUSE = "retained-for-reuse"
    DRAINING_FOR_RETIREMENT = "draining-for-retirement"
    QUARANTINED = "quarantined"
    TERMINALLY_RETIRED = "terminally-retired"


class StepLifecycleOutcome(enum.Enum):
    """Recorded outcome of a disposition request — deliberately distinct
    from ``StepExecutionResult`` and from any SPU/supporting result."""

    CONFIRMED = "confirmed"
    FAILED = "failed"
    INDETERMINATE = "indeterminate"


class StepLifecycleDisposition(enum.Enum):
    """Stage-requested disposition for the Step's current use."""

    RETAIN_FOR_REUSE = "retain-for-reuse"
    RETIRE_TERMINALLY = "retire-terminally"


class StepAdmissionBoundary:
    """Linearizable admission boundary for ONE Step's ``execute`` calls.

    One lock guards admit/close/settle/snapshot. The ever-accepted ledger
    keeps every admitted invocation identity; the active set keeps accepted-
    but-unsettled ones.
    """

    def __init__(self, step_identity: StepIdentity) -> None:
        if type(step_identity) is not StepIdentity:
            raise TypeError(
                f"step_identity must be StepIdentity, got {type(step_identity).__name__}"
            )
        self._step_identity = step_identity
        self._lock = threading.Lock()
        self._ever_accepted: set[StepInvocationIdentity] = set()
        self._active: set[StepInvocationIdentity] = set()
        self._closed = False
        self._terminally_closed = False

    @property
    def step_identity(self) -> StepIdentity:
        return self._step_identity

    @property
    def closed(self) -> bool:
        """Whether execute admission is currently closed."""
        with self._lock:
            return self._closed

    @property
    def terminally_closed(self) -> bool:
        """Whether admission is terminally closed (never reopens)."""
        with self._lock:
            return self._terminally_closed

    def admit(self, step_invocation_identity: StepInvocationIdentity) -> None:
        """Atomically accept one candidate invocation identity.

        Raises :class:`StepInvocationRejected` when admission is closed, when
        the identity was EVER accepted (no silent identity reuse — even after
        settlement), or when the value is not a ``StepInvocationIdentity``.
        """
        if type(step_invocation_identity) is not StepInvocationIdentity:
            raise StepInvocationRejected(
                "step_invocation_identity must be StepInvocationIdentity, got "
                f"{type(step_invocation_identity).__name__}"
            )
        with self._lock:
            if self._closed:
                if self._terminally_closed:
                    raise StepInvocationRejected(
                        "execute admission is terminally closed: the Step has "
                        "confirmed terminal retirement"
                    )
                raise StepInvocationRejected(
                    "execute admission is closed: the Step's current use is "
                    "draining or retained for reuse"
                )
            if step_invocation_identity in self._ever_accepted:
                raise StepInvocationRejected(
                    "step_invocation_identity was already accepted for another "
                    "invocation; an invocation identity is never silently "
                    "reused, even after its invocation settled"
                )
            self._ever_accepted.add(step_invocation_identity)
            self._active.add(step_invocation_identity)

    def settle(self, step_invocation_identity: StepInvocationIdentity) -> None:
        """Mark one accepted invocation complete (result produced/returned).

        Called by the Step aggregate only after the result was produced and
        its identity consistency verified. Unknown or already-settled
        identities are rejected — nothing is settled silently.
        """
        if type(step_invocation_identity) is not StepInvocationIdentity:
            raise StepInvocationRejected(
                "step_invocation_identity must be StepInvocationIdentity, got "
                f"{type(step_invocation_identity).__name__}"
            )
        with self._lock:
            if step_invocation_identity not in self._active:
                if step_invocation_identity not in self._ever_accepted:
                    raise StepInvocationRejected(
                        "cannot settle an invocation identity that was never "
                        "admitted by this Step"
                    )
                raise StepInvocationRejected(
                    "cannot settle the same invocation identity twice"
                )
            self._active.discard(step_invocation_identity)

    def close(self, *, terminal: bool) -> tuple[StepInvocationIdentity, ...]:
        """Close admission; return the accepted-but-unsettled drain set.

        Atomic with the snapshot: the returned identities are exactly the
        accepted work that admission closure must drain. ``terminal=True``
        closes admission permanently (no reopen, ever).
        """
        with self._lock:
            if terminal:
                self._closed = True
                self._terminally_closed = True
            else:
                self._closed = True
            return tuple(self._active)

    def reopen(self) -> None:
        """Reopen execute admission after confirmed retention for reuse.

        Refused for a terminally closed boundary — confirmed terminal
        retirement is irreversible.
        """
        with self._lock:
            if self._terminally_closed:
                raise StepInvocationRejected(
                    "admission cannot reopen after confirmed terminal retirement"
                )
            if not self._closed:
                raise StepLifecycleError("admission is not closed; nothing to reopen")
            self._closed = False

    def unsettled_identities(self) -> tuple[StepInvocationIdentity, ...]:
        """Snapshot of accepted-but-unsettled invocation identities."""
        with self._lock:
            return tuple(self._active)


class StepLifecycle:
    """The Step public lifecycle state machine (disposition + settlement).

    The Stage Composition requests a disposition; the lifecycle closes
    admission FIRST (close-then-settle), evaluates settlement over the drain
    snapshot through the caller-supplied ``settlement_provider``, and records
    the outcome distinctly. It never confirms while accepted work is
    unsettled, and a failed/indeterminate attempt quarantines the Step.
    """

    def __init__(self, step_identity: StepIdentity, admission: StepAdmissionBoundary) -> None:
        if type(step_identity) is not StepIdentity:
            raise TypeError(
                f"step_identity must be StepIdentity, got {type(step_identity).__name__}"
            )
        if not isinstance(admission, StepAdmissionBoundary):
            raise TypeError(
                f"admission must be StepAdmissionBoundary, got {type(admission).__name__}"
            )
        self._step_identity = step_identity
        self._admission = admission
        self._lock = threading.Lock()
        self._status = StepLifecycleStatus.IN_SERVICE
        self._confirmed_outcome: StepLifecycleOutcome | None = None

    @property
    def status(self) -> StepLifecycleStatus:
        """Current lifecycle phase (idempotent re-read)."""
        with self._lock:
            return self._status

    @property
    def confirmed_outcome(self) -> StepLifecycleOutcome | None:
        """The outcome recorded for the last CONFIRMED disposition, if any."""
        with self._lock:
            return self._confirmed_outcome

    def request(
        self,
        disposition: StepLifecycleDisposition,
        settlement_provider: Callable[[tuple[StepInvocationIdentity, ...]], StepSettlementReport],
    ) -> StepLifecycleOutcome:
        """Stage-requested disposition through the public Step boundary.

        Ordering: admission closes FIRST; the drain snapshot is taken
        atomically with closure; settlement is then evaluated over that
        snapshot via ``settlement_provider``. CONFIRMED requires the provider
        to report complete settlement (no unsettled accepted work, no
        outstanding custody, no unsealed flow results). Incomplete settlement
        → FAILED; a provider that raises → INDETERMINATE; both leave the Step
        QUARANTINED. Retention keeps admission closed until an explicit
        ``confirm_reuse_readiness`` reopens it.

        Re-reading an already-confirmed disposition is idempotent: it returns
        the recorded outcome without re-running settlement or changing state.
        """
        if not isinstance(disposition, StepLifecycleDisposition):
            raise TypeError(
                "disposition must be StepLifecycleDisposition, got "
                f"{type(disposition).__name__}"
            )
        if not callable(settlement_provider):
            raise TypeError("settlement_provider must be callable")

        with self._lock:
            status = self._status
            # Idempotent re-read of a confirmed disposition.
            if disposition is StepLifecycleDisposition.RETIRE_TERMINALLY:
                if status is StepLifecycleStatus.TERMINALLY_RETIRED:
                    return StepLifecycleOutcome.CONFIRMED
            else:
                if status is StepLifecycleStatus.RETAINED_FOR_REUSE:
                    return StepLifecycleOutcome.CONFIRMED
            # Valid source phases per disposition.
            if disposition is StepLifecycleDisposition.RETIRE_TERMINALLY:
                if status not in (
                    StepLifecycleStatus.IN_SERVICE,
                    StepLifecycleStatus.RETAINED_FOR_REUSE,
                    StepLifecycleStatus.QUARANTINED,
                ):
                    raise StepLifecycleError(
                        f"terminal retirement requested while {status.value}; "
                        "a concurrent disposition request is already draining"
                    )
            else:
                if status is not StepLifecycleStatus.IN_SERVICE:
                    raise StepLifecycleError(
                        f"retention for reuse is permitted only while in "
                        f"service (phase {status.value})"
                    )

        # Close-then-settle: closure and drain snapshot are atomic.
        drain_set = self._admission.close(
            terminal=disposition is StepLifecycleDisposition.RETIRE_TERMINALLY
        )
        draining_status = (
            StepLifecycleStatus.DRAINING_FOR_RETIREMENT
            if disposition is StepLifecycleDisposition.RETIRE_TERMINALLY
            else StepLifecycleStatus.DRAINING_FOR_REUSE
        )
        with self._lock:
            self._status = draining_status

        try:
            report = settlement_provider(drain_set)
        except BaseException:
            with self._lock:
                self._status = StepLifecycleStatus.QUARANTINED
            return StepLifecycleOutcome.INDETERMINATE

        if not isinstance(report, StepSettlementReport):
            with self._lock:
                self._status = StepLifecycleStatus.QUARANTINED
            raise StepLifecycleError(
                "settlement_provider must return a StepSettlementReport, got "
                f"{type(report).__name__}"
            )

        if report.complete:
            confirmed_status = (
                StepLifecycleStatus.TERMINALLY_RETIRED
                if disposition is StepLifecycleDisposition.RETIRE_TERMINALLY
                else StepLifecycleStatus.RETAINED_FOR_REUSE
            )
            with self._lock:
                self._status = confirmed_status
                self._confirmed_outcome = StepLifecycleOutcome.CONFIRMED
            return StepLifecycleOutcome.CONFIRMED

        with self._lock:
            self._status = StepLifecycleStatus.QUARANTINED
        return StepLifecycleOutcome.FAILED

    def confirm_reuse_readiness(self) -> None:
        """Explicitly confirm reuse readiness and reopen execute admission.

        Valid only in the RETAINED_FOR_REUSE phase: retention keeps admission
        closed until the owning Stage Composition makes this explicit call.
        A terminally retired Step can never reopen.
        """
        with self._lock:
            if self._status is not StepLifecycleStatus.RETAINED_FOR_REUSE:
                raise StepLifecycleError(
                    f"reuse readiness is confirmed only after a confirmed "
                    f"retention for reuse (phase {self._status.value})"
                )
        self._admission.reopen()
        with self._lock:
            self._status = StepLifecycleStatus.IN_SERVICE
