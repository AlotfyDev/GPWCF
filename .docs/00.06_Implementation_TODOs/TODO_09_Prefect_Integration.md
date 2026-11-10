# TODO 09 — Prefect Integration

**Status:** ☑ implemented | **Priority:** high | **Effort:** high | **Depends on:** 03, 02, 01

**Task JSON:** `.docs\00.05_Implementation_Tasks\09_Prefect_Integration.json`
**Dossier:** `.docs\00.06_Implementation_TODOs\dossiers\09_Prefect_Integration.md`

## Read first

1. Task JSON + dossier (parsed Prefect binding class diagram + integration sequence).
2. `.docs\00.00_Primary_Architecture\Prefect_Integration\12.00_Prefect_Integration_Binding.json`
3. `.docs\00.00_Primary_Architecture\Prefect_Integration\13.00_Operational_Mapping.json`
4. `.docs\00.02_Prefect_Adoption_Integration Architecture\ADR-GPWCF-PREFECT-001.json`
5. `.docs\00.02_Prefect_Adoption_Integration Architecture\PHASE-01_Qualification_Report.md` and `PHASE-02_Qualification_Report.md` (qualification limits the binding must respect)
6. `.docs\00.02_Prefect_Adoption_Integration Architecture\Prefect_Environment_And_Dependency_Manifest.json` (Prefect 3.9.2)

## Topology (from parsed diagrams — normative)

```
Pipeline Root  -> Native Flow
Stage          -> Stage Parent Flow / Deployment   (run_deployment(as_subflow=True) profile)
Step           -> Step Subflow                      (via invoke_step dispatch Task)
SPU            -> Native Task                       (inside owning Step Subflow)
Supporting pattern -> Task binding
```

## Source files implemented

| File | Notes |
|------|-------|
| `src\gpwcf\integrations\prefect\prefect_integration.py` | PrefectIntegrationPackage, StageFlowDeploymentBinding, StepSubflowBinding, SPUTaskBinding, SupportingPatternTaskBinding, DomainNativeIdentityCorrelation, TypedResultPreservation, StageResultPersistenceRetrieval, RunDeploymentAsSubflowProfile, PrefectNotAvailableError, PREFECT_AVAILABLE |
| `src\gpwcf\integrations\prefect\__init__.py` | exports updated |
| `src\gpwcf\integrations\prefect\bindings\__init__.py` | preserved |
| `src\gpwcf\integrations\prefect\configuration\__init__.py` | preserved |
| `src\gpwcf\integrations\prefect\correlation\__init__.py` | preserved |
| `src\gpwcf\integrations\prefect\invocation\__init__.py` | preserved |
| `src\gpwcf\integrations\prefect\results\__init__.py` | preserved |

## Test files implemented

- `tests\integrations\prefect\test_prefect_integration.py` (28 real tests, replacing 8 placeholders)

## Implementation checklist

- [x] Prefect import is **optional**: `integrations\prefect` imports Prefect lazily/guarded (try/except ImportError); Core never imports it.
- [x] Stage execution realized as Stage Flow/Deployment via `run_deployment(as_subflow=True)` profile.
- [x] Step execution realized as Step Subflow via `invoke_step` dispatch Task.
- [x] SPU execution realized as Prefect Task inside the owning Step Subflow.
- [x] Domain identities (Pipeline/Stage/Step/SPU/invocation) kept **separate** from Prefect operational identities (Flow Run IDs, Task Run IDs, Deployment IDs); correlation record links them, neither substitutes.
- [x] Prefect State is operational evidence, never a domain result; no State→domain inference.
- [x] Typed results (`SPUExecutionResult`, `StepExecutionResult`, `StageResult`) preserved through Prefect execution without replacement.
- [x] Stage result persistence/retrieval mapping (uses Core `StageResult`; persistence is integration-owned, unqualified in PHASE-01/02).
- [x] Respect PHASE-01/02 qualification limits: production binding stays unqualified/flagged.
- [x] Parent/child correlation chains handled (synthetic deployment/subflow invocation records create indirect parent linkage).

## Acceptance criteria (from task JSON)

- [x] Stage execution realized as Stage Flow/Deployment via run_deployment(as_subflow=True)
- [x] Step execution realized as Step Subflow via invoke_step dispatch Task
- [x] SPU execution realized as Prefect Task inside Step Subflow
- [x] Domain identities (Pipeline/Stage/Step/SPU/invocation) separate from Prefect operational identities
- [x] Prefect State never substitutes for domain result
- [x] Typed domain results (SPUExecutionResult, StepExecutionResult, StageResult) preserved through Prefect
- [x] Core remains usable with Prefect absent; no Prefect types leak into Core API
- [x] PHASE-01/02 qualification limits respected (production binding unqualified)

## Definition of Done

- [x] Integration binding tests for Flow/Subflow/Task mapping
- [x] Identity correlation tests (domain vs native)
- [x] Result preservation tests through Prefect execution
- [x] Architecture test: Core does not import Prefect (real AST scan replacing placeholder)
- [x] Tests that must run without Prefect installed are skipped gracefully (module-level importorskip removed; Prefect-dependent tests guarded)
- [x] `pytest` green — 391 collected, 391 passed, 0 failed, 0 skipped

## Summary

Task 09 complete. Sources written:
- `src\gpwcf\integrations\prefect\prefect_integration.py` — full implementation with optional Prefect imports, all 9 implementation classes
- `src\gpwcf\integrations\prefect\__init__.py` — exports updated
- Tests: `tests\integrations\prefect\test_prefect_integration.py` (28 tests: package availability, identity correlation, Stage/Step/SPU bindings, Supporting Pattern binding, typed result preservation, stage result persistence, architecture boundary, package registration)

`pytest` green: 391 collected, 391 passed, 0 failed, 0 skipped.

Next task: Task 10 — Dependency / Packaging / Public API.
