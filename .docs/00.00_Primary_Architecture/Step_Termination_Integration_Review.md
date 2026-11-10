# Step Termination and Lifecycle-Boundary Integration Review

**Status:** Design review baseline  
**Scope:** Step public lifecycle boundary, Step Composition internal settlement, Stage Composition coordination, and conformance with selected supporting-component patterns.

**Architectural rule:** Common Architectural Guidance Does Not Imply Common Runtime Structure. Each Specialized Component Realizes Applicable Guidance Through Its Own Responsibilities, Contracts, and Implementation Mechanisms.

## 1. Decision and ownership boundaries

- **Stage Composition** owns the outer decision: whether the Stage's current use of a Step ends with retention for reuse or terminal retirement. It requests the disposition through the public Step boundary and applies the Stage-specific response to the reported outcome.
- **Step** is the public lifecycle boundary and Aggregate Root. It owns the ordering between `execute` admission and terminal-retirement admission closure, and remains accountable for not confirming retirement while accepted invocations or Step-owned obligations remain unsettled.
- **Step Composition** owns internal settlement: internal admission closure, accepted-work reconciliation, component-specific quiescence, output/custody reconciliation, and specialized component retention/release coordination. It reports settlement facts to Step; it does not expose internal topology to Stage.
- **Specialized component implementations** perform their own technical lifecycle mechanics under their own contracts. No common runtime manager, interface, base class, state machine, registry, or coordinator is introduced by this review.

## 2. Distinct dispositions

| Disposition | Meaning | Completion evidence |
|---|---|---|
| End current Stage use | Stage no longer needs the Step for the current flow position; this alone does not imply release | Stage-specific decision only |
| Retain for reuse | Same Step Instance remains eligible for later use subject to reset, readiness, isolation, association, and admission requirements | Step confirms concrete reuse preconditions |
| Terminal retirement | Step stops ordinary admission, settles accepted work and internal obligations, and completes required resource release | Step confirms all required settlement/release, with no unresolved release-sensitive custody |

A request being accepted, queued, initiated, or timed out is not completion evidence. Destructor execution, loss of references, or garbage collection is not a substitute for explicit retirement.

## 3. Public admission/retirement ordering

Every concrete Step defines a linearizable ordering between ordinary `execute` admission and admission closure for either RetainForReuse or TerminalRetirement:

1. An invocation accepted before the effective closure point belongs to the retirement settlement set.
2. An invocation arriving after closure is not admitted as ordinary Step work and receives the concrete Step's defined rejection/response.
3. No accepted invocation may be omitted from active-work, result, or custody accounting.
4. Step Composition must not admit internal work for an invocation the public Step boundary did not accept.
5. Internal admission closure is staged: block unrelated work first, allow accepted invocations to finish their required internal descendants, then close remaining activity admission. The concrete Step defines synchronization, concurrency, correlation, and recovery mechanisms; no universal API or implementation primitive is mandated.

## 4. Internal settlement obligations

For each selected component, Step Composition determines applicable obligations from its specialized contracts. Depending on selected patterns, these may include active invocations, nested operations, callbacks, subscriptions, sampling cycles, queued work, associations, publication reservations, pending handoffs, and resource capabilities.

Before **RetainForReuse**, ordinary admission is temporarily closed, accepted invocations are settled, and concrete reset/readiness/isolation conditions must hold. Admission is reopened only after the Step confirms reuse readiness.

Admission closure is staged: immediately after freezing the accepted Step-invocation set, unrelated/new internal work is blocked, while internal work causally required by already-accepted invocations remains authorized to finish. After that accepted set settles, remaining component/activity admission is closed. Before **TerminalRetirement**, accepted work must be completed, cancelled, drained, or explicitly reconciled; release-sensitive associations/resources must be settled; all produced outputs must have confirmed custody or a named recovery owner; and every required component release must be confirmed. Otherwise Step Composition reports failure or indeterminate settlement to Step.

## 5. Pattern conformance matrix

| Pattern | Existing specialized obligations relevant to Step termination | Required integration behavior |
|---|---|---|
| Validator Unit | Lifecycle specialization covers active validation work, concurrency/isolation, output custody, reuse/reset, release confirmation, and behavior when the owning Step is quiesced/released. Association specialization governs target binding and in-flight work during dissociation. | Step Composition includes accepted validator invocations in settlement, preserves produced validation results, prevents post-closure admissions, and reconciles target/association activity before release. Concrete Step defines result aggregation and concurrency policy. |
| Observation Unit | Lifecycle specialization covers activity/subscription lifetimes, callbacks/queued work, quiescence, cancellation/drain, resource detachment, evidence independence, and Step-level quiescence/release. Association specialization governs capture-time context and in-flight provenance across dissociation. | Step Composition stops new observation activity, reconciles/cancels callbacks, subscriptions, and queued delivery as specialized, preserves capture-time association provenance and captured records, and detaches technical resources. Observation records remain outside StepExecutionResult by default. |
| Error Handling Unit | Lifecycle specialization covers Unit/invocation/operation/Publisher capability lifetimes, reservations, pending result custody, recovery ownership, reuse, release confirmation, and behavior when the owning Step is quiesced/released. Association specialization governs target scope and in-flight operations. | Step Composition does not close Publisher responsibilities or release a Unit while operations, reservations, publication status, or produced-but-unaccepted results remain unresolved. Accepted entries remain in Publisher/Step-specific aggregation custody; unresolved handoffs remain with the designated Recovery Owner. |

### Pattern-specific observations

- **Validator:** No generic validator shutdown abstraction is required. The existing specialized lifecycle contract supplies technical conditions; each Step supplies invocation/result aggregation and reentrancy/concurrency choices.
- **Observation:** Ending observation activity is distinct from deleting captured evidence. Delivery may be pending after capture; the concrete specialization preserves association context at capture and defines drain/cancellation/late-callback behavior.
- **Error Handling:** Unit release, Publisher capability closure, reservation settlement, operation-result custody, and ErrorHandlerResult aggregation are separate obligations. Step retirement cannot collapse them into one generic release action.

## 6. Common Guidance conformance

The two Common contracts remain **documentation-only Framework-level Architectural Guidance**. They are conformance references for:

- separation of Step, component-instance, association, invocation/activity, operation, resource, and evidence lifetimes;
- separation of readiness, admission, association, and invocation authorization;
- preventing new work after effective dissociation/authorization withdrawal while preserving the original context of accepted work;
- quiescence before release, including active and queued work and custody obligations;
- release confirmation and explicit treatment of failed/indeterminate release;
- independent retention and interpretability of outputs/evidence after runtime resources are released.

These principles are realized through the Step boundary and each specialized pattern's own contracts and mechanisms. They do not create shared runtime structures or require identical lifecycle operations across patterns.

## 7. Failure and indeterminate outcomes

- A failed or indeterminate component release prevents Step Composition from reporting complete terminal settlement.
- Step must not report terminal retirement while any required invocation, activity, operation, callback, publication/custody, or resource-release obligation remains unresolved.
- Stage Composition retains access to the Step or explicitly transfers recovery ownership before relinquishing that access.
- Retry, quarantine, replacement, escalation, and Stage flow response remain concrete Step/Stage decisions. Non-idempotent lifecycle actions must not be blindly repeated.
- Lifecycle failures are not automatically converted into SPUError, StageError, ErrorResult, ErrorHandlerResult, or StepExecutionResult.

## 8. Contract allocation

| Concern | Authoritative document |
|---|---|
| Stage decision to retain or retire; handling Step lifecycle outcome | `Stage_Level_Architecture.json` and concrete Stage specialization |
| Public Step lifecycle boundary; execute admission vs retirement; externally visible completion/failure/indeterminate semantics | `Step_Contract.json` |
| Accepted-invocation settlement; internal quiescence; component reconciliation/release; internal settlement report; result/evidence custody | `Step_Composition_Contract.json` |
| Component-specific behavior, association, activity/operation/resource mechanics, and release preconditions | Each selected specialized component contract |
| Cross-cutting conceptual invariants and conformance guidance only | Common Association and Internal Component Lifecycle Coordination Contracts |

## 9. Remaining specialization gates

Each concrete Step must explicitly define:

1. lifecycle request/response shape and correlation/idempotency behavior;
2. execute-admission closure and accepted-invocation accounting;
3. RetainForReuse and TerminalRetirement completion criteria;
4. per-pattern settlement selection, ordering, and failure policy;
5. recovery owner and access path for unresolved custody/release;
6. Stage-specific response to confirmed, failed, and indeterminate lifecycle outcomes.

This review does not claim those concrete Step/Stage specializations or runtime implementations already exist. It establishes their contract obligations.
