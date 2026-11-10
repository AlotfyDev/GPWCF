# Supporting Pattern Integration Review

**Review scope:** the nine Behavioral, Association, and Lifecycle contracts for Validator Unit, Observation Unit, and Error Handling Unit, reviewed against `Step_Composition_Contract.json` v0.1.1.

**Review outcome:** retain all three specialized Behavioral contracts; extract two cross-cutting coordination contracts at Pipeline Architecture / Common level; keep Association and Lifecycle specialization contracts for each pattern.

## 1. Architectural decision

The commonality is not a common runtime unit abstraction. It is a pair of responsibilities already owned by Step Composition:

1. Association coordination: establishing and maintaining an explicit relationship between a selected Step-internal instance and a Step-owned target scope, then binding each authorized invocation to the exact relationship.
2. Lifecycle coordination: making instance eligibility, invocation authorization, quiescence, reuse, release, and evidence retention decisions without imposing a common technical lifecycle implementation.

The Framework therefore defines:
- `Step_Composition_Association_Coordination_Contract.json`
- `Step_Composition_Internal_Component_Lifecycle_Coordination_Contract.json`

These contracts define invariants and Step Composition obligations. They do not define a Generic Supporting Unit, common component interface, runtime manager, or universal result model.

## 2. Cross-pattern comparison

| Concern | Validator Unit | Observation Unit | Error Handling Unit | Common treatment |
|---|---|---|---|---|
| Behavioral purpose | Evaluate and produce a validation outcome/evidence | Observe facts and produce records | Execute handling operations and produce operation results/entries | Keep specialized |
| Invocation cardinality | Normally one validation result per normally completed invocation; partial output needs explicit specialization | One activity may emit zero, one, or multiple records; may be call, callback, sampling, or subscription | One invocation may execute zero, one, or multiple operations; each produced operation result has its own entry | No common cardinality |
| Flow authority | Step Composition | Step Composition | Step Composition | Common authority invariant |
| Association scope | SPU, Step, or Step-internal target | SPU, Step, or Step-internal target | SPU, Step, or Step-internal target | Common target-scope model |
| Instance/association/invocation identity | Separate identities | Separate identities | Separate identities, plus attempt and operation identities | Common conceptual identity roles; specialized names retained |
| Result/evidence custody | Result handoff/acceptance to Step Composition | Records may go to Step Composition, Step-owned consumer, or external destination | Reservation-backed entry publication, atomic acceptance, recovery owner | Common no-loss/custody principle; specialized mechanisms retained |
| Association end | Stops new authorization; active work and evidence reconciled | Stops new activities; subscriptions/callbacks/queued events need specialized shutdown | Stops new invocations; operations/reservations/unaccepted entries reconciled | Common dissociation invariant |
| Lifecycle | Readiness, admission, invocation, quiescence, reuse, release | Adds activation and potentially long-lived activity/subscription | Adds operation and Publisher/Reservation lifetimes | Common lifecycle coordination; specialized sub-lifetimes retained |
| Output meaning | Validation judgment/evidence | Factual observation | Handling-operation result/evidence | Must never be unified |

## 3. Invariants promoted to Framework level

### 3.1 Association coordination
- The association is distinct from the component instance and target.
- The target is a Step-owned scope; the common model allows SPU, Step-wide, or another Step-defined internal scope.
- Target identity distinguishes both scope kind and concrete target instance.
- Step Composition alone establishes, changes, and ends associations.
- Multiplicity, sharing, and exclusivity are specialized; no global cardinality is imposed.
- Each invocation/activity authorized under an association is bound to exactly one association and its corresponding target.
- Association existence does not imply readiness, admission, activation, invocation authorization, or ownership.
- Dissociation prevents new work under that association but does not itself release the instance or invalidate historical evidence.
- In-flight work remains attributable to its original association; completion/cancellation/reconciliation is specialized.

### 3.2 Lifecycle coordination
- Instance, association, invocation/activity, technical resource, and output/evidence retention lifetimes are distinct.
- Step Composition owns lifecycle decisions; component implementations perform technical mechanics.
- Preparation, readiness, admission, association, and invocation authorization are distinct concepts.
- Lifecycle milestones are conceptual, not a mandatory state machine or universal enum.
- Quiescence withdraws new-work authorization and reconciles active/queued work and output custody before release.
- Release is successful only when confirmed; failed or indeterminate release remains unresolved.
- Reuse preserves the identity of the same runtime instance; replacement receives a new identity.
- Accepted outputs and historical provenance can outlive the runtime instance and must not retain technical handles/resources merely for historical interpretation.

## 4. Deliberately specialized obligations

The following must not be promoted into a universal behavior contract:

- Validation outcome/evidence semantics, validation timing, gating decisions, and StepValidatorResult aggregation.
- Observation record semantics, zero/one/many emission, callbacks, periodic sampling, subscriptions, event queues, backpressure, and destination selection.
- Error-handling operation taxonomy, attempt versus execution identity, target occurrence references, PublicationReservation, OperationEntryPublisher, atomic acceptance, Recovery Owner, and ErrorHandlerResult aggregation.

The common Lifecycle Coordination Contract states only that specialized active work and output custody must be reconciled before release. It does not prescribe how an observation subscription is drained or how an error-handling publication reservation is reconciled; those remain in their specialized contracts.

## 5. Relationship to Step Composition

The existing Step Composition contract already assigns the correct high-level authority:
- It selects and coordinates the internal component set.
- It owns Step-specific flow decisions.
- It owns provisioning/admission/invocation/reuse/release decisions.
- It retains returned results and exceptions independently.
- It keeps component result semantics separate.
- It delegates specialized output aggregation to the relevant composition.

The two new contracts deepen two cross-cutting areas without changing that ownership model. The specialized Association and Lifecycle contracts become refinements of the new common coordination invariants.

## 6. Gaps and alignment findings

1. **Identity vocabulary differs by pattern.** Validator uses `validatorUnitAssociationIdentity` and `validatorInvocationIdentity`; Observation uses its own observation-prefixed identities; Error Handling uses error-handling-prefixed identities. This is appropriate. The common contracts define conceptual identity roles and require each specialization to map them; they do not rename existing fields.
2. **Target identity needs kind plus instance.** This is explicit in the Validator Association contract and promoted to a common invariant. All three specialized Association contracts now map their concrete identity names to the common conceptual roles and require target kind plus concrete target instance.
3. **Lifecycle phase vocabulary is not identical.** Observation distinguishes activation/activity/subscription; Error Handling distinguishes operation and Publisher lifetimes; Validator focuses on invocation. The common milestones remain conceptual and allow specialization-specific phases.
4. **Output custody mechanisms differ.** Validator handoff, Observation destination/record custody, and Error Handling reservation-backed atomic publication cannot be reduced to one mechanism. Only custody integrity and explicit acceptance/recovery ownership are common.
5. **Step Composition already contains most top-level common authority.** The new contracts should be referenced as detailed coordination contracts, not used to duplicate or override Step Composition's flow/result responsibilities.
6. **No Behavioral common contract is justified.** The three behaviors differ in purpose, cardinality, output semantics, and interaction model.

## 7. Conformance and specialization rule

A concrete Step remains responsible for selecting which patterns it uses. For every selected pattern, its specialized Behavioral, Association, and Lifecycle contracts remain authoritative for pattern-specific semantics and mechanics. The new common contracts apply only to the cross-cutting coordination invariants and must not be interpreted as requiring any pattern to exist.

A Step specialization is composition-complete only when its Step Composition specialization and all selected component specializations satisfy both the applicable common coordination contracts and their pattern-specific contracts.

## 8. Scope of this review

This review does not revise the nine specialized contracts, their result models, or their operation/event protocols. It proposes a minimal extraction of common coordination obligations into two Framework-level contracts and records the required conformance relationship.

## 9. Verification performed

- All 12 in-scope JSON documents (the nine specialized contracts, Step Composition, and the two new Framework-level contracts) parsed successfully with the project's isolated Python runtime.
- All 86 relative references across those documents resolved to existing files.
- Each of the six specialized Association/Lifecycle contracts explicitly references its corresponding Framework-level coordination contract.
- Step Composition v0.1.3 identifies both Framework-level coordination contracts in its dedicated frameworkCoordinationContracts section. Its references array retains only pattern/result/architecture dependencies, avoiding duplicate declarations of the same two common references.
- No build or runtime tests were performed; this change is architectural documentation and contract alignment only.

## 10. Detailed Step Composition reconciliation (v0.1.3)

The detailed review identified repeated normative material in the Step Composition contract. The following changes establish a single source for each cross-cutting rule:

- ownershipAndBoundaries.authority now states Step Composition ownership and selection authority, while delegating association/lifecycle detail to the common coordination contracts.
- supportingUnitCoordination.generalRule no longer enumerates target scopes; it points to the common Association Coordination Contract and the applicable specialized Association Contract.
- errorHandlingUnits retains only Error Handling-specific selection, operation-entry publication, custody/reconciliation, and aggregation boundaries. Generic association/lifecycle authority is delegated.
- lifecycleAndInstanceManagement is now a concise ownership/delegation boundary. It identifies the normative common Lifecycle Coordination Contract and leaves technical mechanics and pattern-specific lifetimes to specialized Lifecycle Contracts.
- specializationRequirements.required asks for concrete pattern/instance/association selections and an explicit conformance mapping, rather than restating the shared lifecycle checklist.
- The two common contracts are declared once in frameworkCoordinationContracts; duplicate entries were removed from the generic references array.

No behavioral result semantics, Step flow-control rules, StepCompositionFlowResult rules, Error Model rules, or publication/custody protocol rules were changed. The specialized Validator, Observation, and Error Handling contracts remain authoritative for their own behavior and mechanics.

### Single-source-of-truth allocation

| Responsibility | Normative source | Step Composition role |
|---|---|---|
| Step ownership, internal orchestration, flow decisions, retained flow evidence, result assembly boundary | Step_Composition_Contract.json | Defines |
| Cross-cutting association identity, target scope, multiplicity, validity, invocation binding, dissociation | Step_Composition_Association_Coordination_Contract.json | Selects and coordinates concrete associations |
| Cross-cutting lifecycle authority, readiness/admission distinctions, lifetimes, quiescence, reuse, release, evidence independence | Step_Composition_Internal_Component_Lifecycle_Coordination_Contract.json | Makes Step-specific selections and coordinates lifecycle decisions |
| Pattern-specific association and lifecycle mechanics | Each selected pattern's specialized Association/Lifecycle Contract | Applies and specializes |
| Validation, observation, and handling-operation behavior/result semantics | Each pattern's Behavioral Contract | Invokes/coordinates and retains according to its own contract |
| Error handling publication protocol and custody | OperationEntryPublisher and Single-Step Publication Specialization contracts | Supplies specialized context and coordinates accepted/uncertain publication reconciliation |

