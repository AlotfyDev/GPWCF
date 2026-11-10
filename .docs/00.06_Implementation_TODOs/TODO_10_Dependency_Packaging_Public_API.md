# TODO 10 — Dependency / Packaging / Public API

**Status:** ☑ implemented | **Priority:** high | **Effort:** high | **Depends on:** 09

**Task JSON:** `.docs\00.05_Implementation_Tasks\10_Dependency_Packaging_Public_API.json`
**Dossier:** `.docs\00.06_Implementation_TODOs\dossiers\10_Dependency_Packaging_Public_API.md`

## Read first

1. Task JSON + dossier.
2. `.docs\00.00_Primary_Architecture\Dependency\14,00_Dependency.json`
3. `.docs\00.00_Primary_Architecture\Packaging\15.00_Packaging.json`
4. `.docs\00.00_Primary_Architecture\Public_API\16.00_Public_API_Architecture.json`
5. `.docs\00.03_Architecture_Closure_Design\Dependency_and_Public_API_Architecture.json`
6. `.docs\00.03_Architecture_Closure_Design\Filesystem_Architecture.json` + `Framework_Module_Boundary_Model.json`
7. `.docs\00.03_Architecture_Closure_Design\02.00_Determined_Gaps_And_Candidate_Architectural_Solutions\F-07_Packaging_Architecture.md`, `F-09_Public_API_Tests.md`

## Source files to implement

| File | Notes |
|------|-------|
| `src\gpwcf\public_api\__init__.py` | replace `CorePublicAPI`, `IntegrationPublicAPI` placeholders with curated re-export surface |
| New: `pyproject.toml` | PEP 621 metadata; PEP 517/518 build-system with `setuptools==84.2.1` (exact pin) in `[build-system] requires` — build backend isolated from runtime deps |
| New: `src\gpwcf\public_api\core.py` (or package) | Core Public API groups: Stage/Step/SPU callable + result contracts, canonical identities, optional diagnostics sub-surface |
| New: `src\gpwcf\public_api\integrations\prefect.py` | Integration Public API (importable only when Prefect extra installed) |

Packaging shape (from docs): **single distribution** `gpwcf`, Core base dependency-free,
optional extra `prefect` (Prefect 3.9.2 pin). Minimal Prefect transitive lock release gate defined
in release process (see PHASE-00 lock file reference in 00.02 docs).

## Test files to implement

- `tests\public_api\core\test_core_public_api.py` — Public API Conformance Suite (Core):
  exported symbol list is exactly the curated set; importing Core never imports Prefect
  (assert `sys.modules` cleanliness after fresh import).
- `tests\public_api\integrations\prefect\test_integration_public_api.py` — Integration API surface.
- New: `tests\architecture\test_dependency_graph.py`:
  - acyclicity of `gpwcf` internal import graph (AST scan),
  - forbidden directions rejected (`core → integrations`, `processing_units → step`, `supporting_patterns → core.step/core.stage`, public_api→internals beyond curated surface),
  - `core.identities` dependency-free (from task 11) re-verified.
- New: `tests\architecture\test_build_backend_isolation.py` + core-only installation test
  (build sdist/wheel in isolation; `pip install .` with no extras → `import prefect` absent and `import gpwcf` works).

## Implementation checklist

- [x] Dependency ownership/direction graph implemented as test-enforced rules
      (owner/module lists documented in docs, asserted in tests).
- [x] Single `gpwcf` distribution with optional `prefect` extra (`[project.optional-dependencies] prefect = ["prefect==3.9.2"]`).
- [x] Core installs and imports with Prefect absent; no indirect Prefect installation
      (no transitive third-party in Core base — verified by test_build_backend_isolation.py).
- [x] `setuptools==84.2.1` build backend isolated: build requirements only in
      `[build-system].requires`; runtime metadata does not pin build tooling.
- [x] Minimal Prefect transitive lock release gate documented (`PREFECT-LOCK-RELEASE-GATE.md` in PHASE-00 docs; references lock SHA-256, manifest SHA-256, creation procedure, review criteria).
- [x] Core Public API vs Prefect Integration Public API separated; no Prefect types in Core API.
- [x] Public API Conformance Suite: `tests\core\`, `tests\public_api\...`, `tests\architecture\` all green.
- [x] Dependency owner/module lists documented in 00.00_Primary_Architecture/Dependency/14,00_Dependency.json
      and 15,00_Packaging.json.

## Acceptance criteria (from task JSON)

- [ ] Dependency graph acyclic; forbidden dependency directions prohibited
- [ ] Single distribution with optional Prefect extra for initial release
- [ ] Core installs/imports without Prefect; no indirect Prefect installation
- [ ] setuptools build backend isolated from runtime dependencies
- [ ] Minimal Prefect transitive lock release gate defined
- [ ] Core Public API and Prefect Integration Public API separable
- [ ] No Prefect types leak into Core API
- [ ] Public API Conformance Suite (tests/core/, tests/public_api/..., tests/architecture/)
- [ ] Dependency owner/module lists documented

## Definition of Done

- [ ] Dependency graph tests (acyclicity, forbidden directions)
- [ ] Core-only installation test
- [ ] Build backend isolation test
- [ ] Public API conformance suite passes
- [ ] Prefect opt-in extra installation test
- [ ] `pytest` green; package builds (`python -m build` or `pip wheel .`)

## Boundary rules

- Consumers import only via Public API surfaces; internal `gpwcf.core.*` imports by consumers
  are forbidden (enforced by conformance test).
