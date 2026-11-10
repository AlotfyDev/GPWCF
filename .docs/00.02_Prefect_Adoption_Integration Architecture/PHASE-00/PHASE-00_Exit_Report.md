# PHASE-00 — Adoption Baseline and Contract Freeze

**Status:** Baseline frozen for native capability qualification; production integration gates remain open.  
**Target:** Prefect 3.9.2 / CPython 3.15.1 / Windows x64  
**Decision record:** ADR-GPWCF-PREFECT-001.json

## 1. Outcome

PHASE-00 established a controlled target-specific baseline without changing any specialized GPWCF contracts or rewriting historical Prefect/Dagu evidence.

The accepted decision is to adopt Prefect 3.9.2 as the initial external workflow runtime. Prefect owns native workflow execution and operational state. GPWCF retains the semantic authority for Stage/Step/SPU contracts, composition, identities, typed results, and lifecycle obligations.

The baseline is sufficient to proceed with PHASE-01 native capability qualification. It is **not** a declaration that GPWCF's production runtime implementation or Generator integration is complete.

## 2. Contract inventory

The exact contract IDs, versions, roles, and implementation observations are in PHASE-00_Contract_Inventory.json.

| Contract | Version | PHASE-00 finding |
|---|---:|---|
| Stage-Level Architecture | 0.4.0 | Defines Stage ownership and the Stage facade role; does not prescribe a concrete Python callable/class signature |
| Step Contract | 0.4.0 | Defines the public execute(input) -> StepExecutionResult boundary |
| Step Composition Contract | 0.3.0 | Places internal component selection, invocation, transition and result assembly under the owning Step |
| Step Processing Unit Contract | 0.2.0 | Defines the specialized SPU role invoked by Step Composition |
| SPUExecutionResult Contract | 0.1.0 | Defines an SPU-scoped result, distinct from the Step result |
| StepExecutionResult Contract | 0.2.0 | Preserves independently optional processing, validator, error and error-handler result categories |

### Implementation boundary found

The GPWCF project identity document still reports identityEstablished=false and implementation capabilities as not yet implemented or verified. The inspected Python project entry point is empty, and the current project dependency declaration remains standard-library-only.

Consequently:

- There is no production GPWCF Root/Stage/Step/SPU Python runtime class to bind in PHASE-01.
- The Stage facade is an architectural role, not yet a concrete Python public callable.
- The generic Step execute signature and StepExecutionResult contract are documented, but concrete Generator-specific Step specializations are not yet present.
- The 13 Generator Stage Models are inventoried, but their objectives and execution_steps are not assumed to be GPWCF Steps or SPUs.

PHASE-01 therefore uses explicitly labelled contract-shaped fixtures to qualify Prefect's native constructs. It does not claim to bind production GPWCF classes.

## 3. Runtime and dependency baseline

| Item | Verified value |
|---|---|
| Python executable | C:\poc\GPWCF\prefect-env-managed\Scripts\python.exe |
| Python | 3.15.1, 64-bit |
| Prefect | 3.9.2 |
| Prefect package license metadata | Apache-2.0 |
| Platform | Windows x64 |
| Installed distributions captured | 106 |
| pip check | Passed — no broken requirements |
| Lock snapshot | prefect-3.9.2-managed-lock.txt |
| Metadata manifest | Prefect_Environment_And_Dependency_Manifest.json |

Lock SHA-256:

805c074e3e9182cd5e921c2bfc5198a84300d7f1cd4f686370f044899e2042ee

Manifest SHA-256:

21aca5dea787a9b52dbe592262b98793f99cc71e2fa0ae472d3b6a57f467c790

The lock is a complete snapshot of the existing managed Prefect qualification environment, not a minimized GPWCF runtime dependency set. The manifest contains metadata for 106 installed distributions; 98 expose a license field/expression and 8 do not. This is a metadata observation, not a conclusion that those 8 packages are unlicensed. Package-by-package license-file review remains open.

A clean reconstruction from the lock has not yet been performed. The existing isolated environment was reused without installing or upgrading packages.

## 4. Ownership and result rules frozen for PHASE-01

1. Prefect Root Flow owns pipeline-level orchestration.
2. Each GPWCF Stage specialization is represented by a native Prefect Stage Parent Flow.
3. Each Step is invoked through its public execute(input) callable; that callable enters the native Step Subflow.
4. SPU Tasks execute only inside their owning Step Subflow.
5. Prefect dispatch Tasks may be used as native dispatch mechanics; they do not become additional GPWCF semantic components.
6. Pipeline/Stage/Step/SPU domain identities remain distinct from Prefect Flow Run and Task Run IDs.
7. SPUExecutionResult and StepExecutionResult remain distinct. Prefect State is operational evidence, never a substitute for either domain result.
8. Supporting Units are outside the minimal PHASE-01 slice.
9. No specialized contract was modified.

## 5. Exit-criteria assessment

| PHASE-00 criterion | Result | Evidence / remaining work |
|---|---|---|
| No ownership contradiction among GPWCF, Prefect and Generator | **PASS** | Accepted ADR and contract inventory |
| Exact Windows runtime/package environment reproducibly established | **PARTIAL** | Exact interpreter and Prefect verified; lock captured; clean reconstruction still required |
| No specialized contract changed without approval | **PASS** | No specialized contract file modified |

**PHASE-00 disposition:** The adoption and contract baseline is frozen sufficiently to proceed with PHASE-01. The reproducibility and production-callable implementation gaps remain explicit release gates.

## 6. Open decisions

See PHASE-00_Open_Decisions.json. The key unresolved items are the concrete Stage facade shape, concrete Step specialization and sync/async callable choice, Generator-specific Step/SPU decomposition, sibling Step Subflow concurrency requirements, production result/artifact persistence, clean environment reconstruction, and full dependency license review.

## 7. Files created

- ADR-GPWCF-PREFECT-001.json
- PHASE-00_Contract_Inventory.json
- PHASE-00_Open_Decisions.json
- Prefect_Environment_And_Dependency_Manifest.json
- prefect-3.9.2-managed-lock.txt
- This report

No historical candidate assessment or specialized GPWCF contract was rewritten.
