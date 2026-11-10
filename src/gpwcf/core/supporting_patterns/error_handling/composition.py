"""Step-specific Error Handling Composition — working aggregation machinery.

Implementation task: 04_Error_Handling
Related diagrams:
  class: 03_Diagrams_Codes_Files/04_Error_Handling.dot
  sequence: B_Sequencial_Diagram_Code/02_Error_Handling_Sequence.puml
  association: C_Association_Diagram_Code/04_Error_Handling_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/04_Supporting_Pattern_Optional_Dependency.dot

Contract basis:
  - ErrorHandlerResult_Contract.json (composition-side aggregation role)
  - OperationEntryPublisher_Contract.json (``relationships``: the Composition
    owns the Publisher and assumes retention responsibility at atomic
    acceptance; ``invocationClosure``: closure preconditions)

The Step-specific Error Handling Composition is the Step-owned component that:

  - owns the ``OperationEntryPublisher`` and supplies it to each Error Handling
    Unit invocation under the Step-specific lifecycle contract;
  - assumes retention responsibility for every accepted entry at the atomic
    acceptance point and retains it for the duration required by collection and
    ErrorHandlerResult aggregation;
  - assembles the ``ErrorHandlerResult`` from accepted entries when the Step's
    design selects them, preserving the entries as given (no merging, no
    reordering, no deduplication, no interpretation of the operation results);
  - checks the invocation-closure preconditions (every granted reservation
    Consumed or Released; nothing unresolved) before representing the
    invocation as normally and completely closed.

It does NOT execute handling operations, schedule them, impose semantic
ordering, define error-handling policy, or decide Step flow transitions. The
per-Step publication specialization (no-fail transfer strategy evidence, status
retention/expiry, custody traces, named recovery procedure) is task 07: this
module participates with the retention-reclamation convenience
``retire_publication_records`` — an explicit Composition decision that reclaims
terminal status records (tombstoned) only after aggregation.
"""

from __future__ import annotations

from .error_handling_unit import (
    ErrorHandlingOperationEntry,
    ErrorHandlerResult,
)
from .identities import (
    ErrorHandlingInvocationIdentity,
    ErrorHandlingUnitIdentity,
    OperationEntryPublisherIdentity,
)
from .operation_entry_publisher import (
    OperationEntryPublisher,
    PublicationReservation,
)

__all__ = ["ErrorHandlingComposition"]


class ErrorHandlingComposition[THandlingOperationResult, TErrorHandlingContext = object]:
    """Composition-side aggregation and publisher ownership (working machinery).

    Generic over the concrete entry's operation-result type and the optional
    Step-specialized error-handling context. Stateless: the concrete Step
    selects when to aggregate, which accepted entries to include, and which
    context (if any) to attach.
    """

    def create_publisher(
        self,
        identity: OperationEntryPublisherIdentity,
        *,
        invocation_identity: ErrorHandlingInvocationIdentity,
        error_handling_unit_identity: ErrorHandlingUnitIdentity,
        step_instance_identity: str,
        error_handling_unit_association_identity: str,
        association_target_identity: str,
        total_capacity: int,
    ) -> OperationEntryPublisher[THandlingOperationResult]:
        """Create the invocation-bound Publisher this Composition owns.

        Encodes ``owns-and-supplies-per-invocation``: the Publisher is bound at
        creation to the exact invocation, Unit instance, Step instance,
        Association, and association target selected by Step Composition.
        """
        return OperationEntryPublisher[THandlingOperationResult](
            identity,
            invocation_identity=invocation_identity,
            error_handling_unit_identity=error_handling_unit_identity,
            step_instance_identity=step_instance_identity,
            error_handling_unit_association_identity=(
                error_handling_unit_association_identity
            ),
            association_target_identity=association_target_identity,
            total_capacity=total_capacity,
        )

    def collect_accepted_entries(
        self, publisher: OperationEntryPublisher[THandlingOperationResult]
    ) -> tuple[ErrorHandlingOperationEntry[THandlingOperationResult], ...]:
        """Snapshot the entries the Publisher accepted (retention responsibility
        transferred to this Composition at each atomic acceptance point)."""
        return publisher.accepted_entries()

    @staticmethod
    def retire_publication_records(
        publisher: OperationEntryPublisher[THandlingOperationResult],
        reservations: tuple[PublicationReservation, ...]
        | list[PublicationReservation],
    ) -> int:
        """Reclaim terminal publication-status records (explicit Composition
        decision; task 07 retention rules).

        Permitted ONLY for Consumed/Released reservations whose accepted
        entries were already collected (``collect_accepted_entries``) and
        aggregated, and whose retry observers have left scope. Reserved
        records are never removed. Each reclaimed record keeps a tombstone so
        stale capabilities stay rejected, late status queries report EXPIRED
        (never definitely-not-accepted), and identity reuse can never make a
        stale query resolve to a different publication. Returns the number of
        records reclaimed.
        """
        return publisher.retire_terminal_records(reservations)

    def assemble(
        self,
        operation_entries: tuple[ErrorHandlingOperationEntry[THandlingOperationResult], ...],
        error_handling_context: TErrorHandlingContext | None = None,
    ) -> ErrorHandlerResult[
        ErrorHandlingOperationEntry[THandlingOperationResult], TErrorHandlingContext
    ]:
        """Assemble the ErrorHandlerResult from selected ACCEPTED entries.

        Entries are preserved exactly as given — no merging, no reordering, no
        deduplication, and no interpretation of their operation results. An
        empty selection is not an ErrorHandlerResult (ValueError); absence of
        the optional context is not a success/failure status. The aggregate
        contains no ErrorResult and does not assert occurrence resolution.
        """
        return ErrorHandlerResult[
            ErrorHandlingOperationEntry[THandlingOperationResult], TErrorHandlingContext
        ](
            operation_entries=operation_entries,
            error_handling_context=error_handling_context,
        )

    @staticmethod
    def unresolved_reservations(
        publisher: OperationEntryPublisher[THandlingOperationResult],
    ) -> tuple[PublicationReservation, ...]:
        """Granted reservations not yet Consumed or Released.

        A non-empty result means the invocation cannot be represented as
        normally and completely closed: the Step-specific Composition records
        the unresolved condition and applies its own exception/flow policy
        (outstanding reservations are never automatically released).
        """
        return publisher.outstanding_reservations()
