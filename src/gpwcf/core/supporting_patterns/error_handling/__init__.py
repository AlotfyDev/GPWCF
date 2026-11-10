"""Error Handling pattern: Unit, operation entries, publication protocol, escrow.

Implementation tasks: 04_Error_Handling (working machinery), 07_Publication
(Single Step Publication Specialization surface).
Related diagrams:
  class: 03_Diagrams_Codes_Files/04_Error_Handling.dot
  sequence: B_Sequencial_Diagram_Code/02_Error_Handling_Sequence.puml
           B_Sequencial_Diagram_Code/08_Publication_Specialization_Sequence.puml
  association: C_Association_Diagram_Code/04_Error_Handling_Associations.puml
  dependency: D_Architectural_Dependency_Diagram_Code/04_Supporting_Pattern_Optional_Dependency.dot

Step-owned optional Error Handling pattern with NO Core dependency (stdlib
only): pattern-local identities, the Error Handling Unit callable, complete
operation entries, the ErrorHandlerResult aggregate, the OperationEntryPublisher
reserve/publish/status/release protocol with atomic acceptance, and the
Recovery Owner escrow. Task 07 adds the per-Step publication specialization
surface: correlated protocol envelopes, the derived AcceptedEntryIdentity, the
no-fail preallocated-envelope transfer, publication sequence/identity/retention
policies, the full status-query envelope, retention tombstones, and the
Recovery Owner recovery procedure with the ambiguous-acceptance escrow and the
end-to-end custody trace (``recovery``).
"""

from .identities import (
    AcceptedEntryIdentity,
    ErrorHandlingInvocationIdentity,
    ErrorHandlingUnitIdentity,
    HandlingOperationAttemptIdentity,
    HandlingOperationIdentity,
    OperationEntryPublisherIdentity,
    PublicationReservationIdentity,
)
from .error_handling_unit import (
    ErrorHandlingOperationEntry,
    ErrorHandlingUnit,
    ErrorHandlerResult,
    HandledErrorOccurrenceReference,
    RecoveryEscrowRecord,
    RecoveryOwner,
)
from .operation_entry_publisher import (
    AcceptanceKnowledge,
    OperationEntryPublisher,
    PreallocatedEntryEnvelope,
    PublicationAcknowledgement,
    PublicationIdentityPolicy,
    PublicationOutcome,
    PublicationRejection,
    PublicationReservation,
    PublicationSequencePolicy,
    PublicationStatus,
    PublicationStatusQuery,
    PublicationStatusRetentionPolicy,
    PublisherContractViolation,
    ReleaseAcknowledgement,
    ReservationGrant,
    StatusQueryOutcome,
    derive_accepted_entry_identity,
)
from .recovery import (
    AmbiguousAcceptanceEscrow,
    AmbiguousAcceptanceEscrowRecord,
    CustodyDisposition,
    CustodyPhase,
    CustodyTraceEntry,
    CustodyTraceRecorder,
    PublicationRecoveryProcedure,
    RecoveryDecision,
)
from .composition import (
    ErrorHandlingComposition,
)

__all__ = [
    # identities (pattern-owned)
    "ErrorHandlingUnitIdentity",
    "ErrorHandlingInvocationIdentity",
    "HandlingOperationAttemptIdentity",
    "HandlingOperationIdentity",
    "OperationEntryPublisherIdentity",
    "PublicationReservationIdentity",
    "AcceptedEntryIdentity",
    # unit / entry / aggregate / recovery
    "ErrorHandlingUnit",
    "ErrorHandlingOperationEntry",
    "HandledErrorOccurrenceReference",
    "ErrorHandlerResult",
    "RecoveryOwner",
    "RecoveryEscrowRecord",
    # publication protocol (working machinery, task 04)
    "OperationEntryPublisher",
    "PublicationReservation",
    "ReservationGrant",
    "PublicationAcknowledgement",
    "PublicationOutcome",
    "PublicationRejection",
    "PublisherContractViolation",
    "ReleaseAcknowledgement",
    "PublicationStatus",
    # publication specialization surface (task 07)
    "AcceptanceKnowledge",
    "StatusQueryOutcome",
    "PublicationStatusQuery",
    "PreallocatedEntryEnvelope",
    "PublicationSequencePolicy",
    "PublicationIdentityPolicy",
    "PublicationStatusRetentionPolicy",
    "derive_accepted_entry_identity",
    "CustodyPhase",
    "CustodyDisposition",
    "CustodyTraceEntry",
    "CustodyTraceRecorder",
    "AmbiguousAcceptanceEscrow",
    "AmbiguousAcceptanceEscrowRecord",
    "RecoveryDecision",
    "PublicationRecoveryProcedure",
    # Step-specific Error Handling Composition
    "ErrorHandlingComposition",
]
