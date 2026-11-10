# TODO 08 — Common Coordination (Association & Lifecycle)

**Status:** ✅ implemented | **Priority:** high | **Effort:** medium | **Depends on:** —

**Task JSON:** `.docs\00.05_Implementation_Tasks\08_Common_Coordination.json`
**Dossier:** `.docs\00.06_Implementation_TODOs\dossiers\08_Common_Coordination.md`

## Read first

1. Task JSON + dossier.
2. `.docs\00.00_Primary_Architecture\Common\Step_Composition_Association_Coordination_Contract.json`
   (documentId: `pipeline.step-composition.association-coordination.contract`)
3. `.docs\00.00_Primary_Architecture\Common\Step_Composition_Internal_Component_Lifecycle_Coordination_Contract.json`
   (documentId: `pipeline.step-composition.internal-component-lifecycle-coordination.contract`)

## Source files implemented

| File | Content |
|------|---------|
| `src\gpwcf\core\coordination\identities.py` *(new)* | 5 distinct identity roles as nominal value types: `ComponentInstanceIdentity`, `AssociationIdentity` (+ `ComponentAssociationIdentity` role alias), `ComponentInvocationIdentity` (reuse the task-11 `_IdentityValue` base) and compound `AssociationTargetIdentity(scope_kind, instance_identity)` |
| `src\gpwcf\core\coordination\association_coordination.py` | `Association` (4-field provenance entity), `AssociationTarget` (Step-owned scope), `InvocationBinding` (5-role provenance), `Dissociation` (effective-end record), `StepCompositionAssociationCoordination` (pure operation surface: `establish`, `change_target`, `dissociate`, `bind_invocation`, `ensure_authorizable`) |
| `src\gpwcf\core\coordination\lifecycle_coordination.py` | 6 distinct lifetime marker types (`RuntimeInstanceLifetime`, `AssociationLifetime`, `InvocationLifetime`, `OperationLifetime`, `ResourceCapabilityLifetime`, `OutputAndEvidenceRetentionLifetime`) + declarative `StepCompositionInternalComponentLifecycleCoordination` (milestones, lifetimes, eligibility/admission/quiescence/release/evidence-independence definitions) |
| `src\gpwcf\core\coordination\__init__.py` *(new)* | public surface of both contracts |

## Test files implemented

- `tests\core\coordination\test_association_coordination.py` — 21 tests (identity-role
  separation, target scope-kind distinction, establishment validity + Step membership,
  no universal cardinality rules, binding provenance/attribution/immutability,
  change-requires-new-identity, dissociation ≠ release, per-association effective end,
  evidence survival, stateless/no-registry, authority surface)
- `tests\core\coordination\test_lifecycle_coordination.py` — 13 tests (6 pairwise-distinct
  lifetimes as value tokens, 8 milestones as descriptive metadata only, no enum/state
  machine, release rule carried in the contract, declarative authority with no
  self-authorization surface, no manager/factory/pool/singleton)
- `tests\architecture\test_no_universal_supporting_unit.py` *(new)* — 5 tests (no
  `SupportingUnit`/universal component/`ExecutionContext`/registry/manager class anywhere
  in `src\gpwcf`; coordination imports nothing above `core.identities`; SPU never imports
  Step/Stage/supporting patterns; supporting patterns never import Step/Stage/SPU —
  relative imports resolved via AST)

## Implementation checklist

- [x] **Association coordination contract** (`StepCompositionAssociationCoordination`):
      explicit component-instance-to-target relationships; establish / change / end
      operations as pure derivations — the owning Step Composition holds all state.
- [x] **Association identity** (`AssociationIdentity`): identity of the relationship itself,
      distinct from participant identities (instance, target, invocation).
- [x] **AssociationTarget**: Step-owned target scope a component becomes applicable to;
      identity distinguishes scope kind AND concrete target instance.
- [x] **InvocationBinding**: per-invocation selection of association context with all five
      conceptual provenance roles; target matches the selected association by construction.
- [x] **Lifecycle coordination contract** (`StepCompositionInternalComponentLifecycleCoordination`):
      eligibility → admission → quiescence → release; evidence independence documented on
      the contract surface.
- [x] **Six distinct conceptual lifetimes** modeled as distinct frozen marker types:
      RuntimeInstance, Association, Invocation, Operation, ResourceCapability,
      OutputAndEvidenceRetention.
- [x] Authority stays with Step Composition: every operation takes the applicable
      association/Step context explicitly; targets/components gain no management
      authority; coordination objects are stateless (no registry/manager/singleton).
- [x] Pair of contracts kept **generic** — no validator/observer/handler specifics
      (per-pattern specialization lives in the supporting-pattern tasks 04/05/06).

## Acceptance criteria (from task JSON)

- [x] Association coordination contract defines explicit component-instance-to-target relationships
- [x] Lifecycle coordination contract defines eligibility/admission/quiescence/release/evidence independence
- [x] Component identity roles distinct (instance, association, invocation, target)
- [x] Conceptual lifetimes distinct (runtime instance, association, invocation, operation, resource capability, output/evidence retention)
- [x] No universal Generic Supporting Unit or universal runtime component type defined
- [x] Step Composition owns association and lifecycle authority

## Definition of Done

- [x] Association contract tests for identity/validity/dissociation
- [x] Lifecycle contract tests for milestones and authority
- [x] Architecture test: no universal supporting unit abstraction imposed (no `SupportingUnit`
      base class / no universal component type anywhere in `src\gpwcf`)
- [x] `pytest` green — **150 passed** (34 tests for this task; 116 from prior tasks)

## Boundary rules honored

- `coordination` imports only stdlib + `gpwcf.core.identities` (nothing above it) —
  enforced by `tests\architecture\test_no_universal_supporting_unit.py`.
- No mandatory enum/state machine for lifecycle milestones; no cardinality/exclusivity
  rules; no association registry; dissociation ≠ instance release; failed release never
  `Released`; reuse keeps instance identity, replacement gets a new identity.
