# TODO 11 — Core Identities & Diagnostics

**Status:** ✅ implemented | **Priority:** medium | **Effort:** low | **Depends on:** —

**Task JSON:** `.docs\00.05_Implementation_Tasks\11_Core_Identities_Diagnostics.json`
**Dossier:** `.docs\00.06_Implementation_TODOs\dossiers\11_Core_Identities_Diagnostics.md`

## Read first

1. Task JSON + dossier.
2. `.docs\00.00_Primary_Architecture\03.00_Pipeline_Invocation.json`
3. `.docs\00.00_Primary_Architecture\Common\09.00_Generic_Diagnostics.json`

## Source files implemented

| File | Content |
|------|---------|
| `src\gpwcf\core\identities\__init__.py` | 5 nominal identity value types on a shared immutable `_IdentityValue` base (`__slots__`, value validation, in-type equality/hash, nominal cross-type inequality) |
| `src\gpwcf\core\diagnostics\__init__.py` | `DiagnosticCode` (namespaced, producer-owned) + `Diagnostic[TDetails]` (code/message/typed details), frozen dataclasses |

## Test files implemented

- `tests\core\identities\test_identities.py` — 34 tests (contract parametrized over all 5 types, export surface, no-generator/registry rule, cross-type equality prohibition)
- `tests\core\diagnostics\test_diagnostics.py` — 9 tests (code namespacing, validation, typed details, immutability, not-an-exception, no error-model semantics/behavior, exact export surface)
- `tests\architecture\test_core_identities_dependency_free.py` — 6 tests (AST allowlist scans, defined-class checks, clean-interpreter third-party import probe, Core-no-Prefect guard)

Plus: root `conftest.py` puts `src\` on `sys.path` so tests can import the not-yet-installed package.

## Implementation checklist

- [x] `core.identities` is a **dependency-free** module: zero first-party imports; stdlib only.
- [x] Five nominal identity **value types** (immutable, equality/hash by value):
      `PipelineInvocationIdentity`, `StageIdentity`, `StepIdentity`, `SPUIdentity`, `InvocationIdentity`.
- [x] Each identity carries a stable opaque string value assigned once; empty/None/non-str rejected.
- [x] Nominal semantics: equal value ⇒ equal within type; **cross-type equality prohibited** (03.00 contract);
      no implicit conversion to raw string.
- [x] **No identity generator, registry, service, or lifecycle manager** (03.00 contract — no uuid `new()` factory).
- [x] `Diagnostic[TDetails]`: `code: DiagnosticCode`, `message: NonEmptyString`, `details: TDetails`
      (required field; `None` = no details; not an untyped dict — DIAG-003).
- [x] `DiagnosticCode`: producer-owned `namespace` + `value`; equality scoped by both; no global registry (DIAG-002).
- [x] Deliberately omitted: identity, severity, retryability, resolution status, timestamp, origin, cause chain.
- [x] Descriptive only: no behavior (execute/classify/retry/resolve/publish/transition), no error/outcome fields (DIAG-001).
- [x] Docstrings state Diagnostics never substitute for Error Occurrence / Failure / Exception / Domain Outcome (DIAG-005).

## Acceptance criteria (from task JSON)

- [x] core.identities is dependency-free module for nominal identity value types only
- [x] Identity types: PipelineInvocationIdentity, StageIdentity, StepIdentity, SPUIdentity, InvocationIdentity
- [x] core.diagnostics optional Diagnostic value contract implemented
- [x] Diagnostic distinct from Error Occurrence, Failure, Exception, Domain Outcome
- [x] Diagnostics descriptive only; never substitute for error/failure/outcome semantics
- [x] Dependency closure determines which contracts require diagnostics vs specialized error handling
      (module is optional + independently importable; nothing attaches diagnostics to results — DIAG-007)

## Definition of Done

- [x] Identity type unit tests (value semantics, immutability, validation)
- [x] Diagnostic contract tests (descriptive-only, distinctness)
- [x] Architecture test: diagnostics not universal Error Model
- [x] Architecture test: `core.identities` imports nothing first-party/third-party (AST allowlist + clean-interpreter probe)
- [x] `pytest` green — **116 passed** (49 tests for this task; 67 from prior tasks)

## Notes for later tasks

- `Diagnostic[TDetails]` is optional and independently importable; result envelopes
  (`StepExecutionResult`, `SPUExecutionResult`, `StageResult`, `OptionalResultContributions`)
  must NOT acquire a mandatory diagnostics field (DIAG-007).
- Identity types are ready for import by Stage/Step/SPU invocation + result contracts (tasks 01/02/03)
  and for the Prefect domain/native correlation (task 09).
