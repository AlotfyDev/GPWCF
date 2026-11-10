# Prefect Transitive Lock Release Gate

**Status:** Documentation of release gate (implementation pending — release process item)

**Related documents:**
- `PHASE-00\prefect-3.9.2-managed-lock.txt` — 106-package environment snapshot (NOT the minimal lock)
- `PHASE-00\Prefect_Environment_And_Dependency_Manifest.json` — metadata manifest (106 distributions)
- `PHASE-00\PHASE-00_Exit_Report.md` — PHASE-00 exit report with lock SHA-256 and manifest SHA-256
- `PHASE-00\ADR-GPWCF-PREFECT-001.json` — ADR for Prefect 3.9.2 adoption
- `Packaging\15,00_Packaging.json` — packaging contract doc (prefectLock specification)

---

## 1. Purpose

The Prefect transitive lock release gate defines the **minimized exact Prefect 3.9.2 transitive runtime closure** that must be produced, reviewed, and pinned before GPWCF can ship the optional `[prefect]` extra.

This lock is a **release gate**: it must pass (clean reconstruction from `gpwcf[prefect]`, runtime relevance review, license review, hash recording) before any release that includes Prefect integration.

---

## 2. Normative constraints

| Constraint | Source |
|------------|--------|
| Prefect exact version: `prefect==3.9.2` | `pyproject.toml` `[project.optional-dependencies] prefect` |
| Python runtime: CPython 3.15.1 x64, Windows x64 | ADR-GPWCF-PREFECT-001.json, selectedBaseline |
| Prefect license: Apache-2.0 | ADR-GPWCF-PREFECT-001.json, selectedBaseline.license |
| Lock is **minimized** — not a copy of the 106-package snapshot | 15,00_Packaging.json, prefectLock Creation Gate |
| Lock must be **reconstructed** from a clean environment installing only `gpwcf[prefect]` | 15,00_Packaging.json, prefectLock Creation Gate |
| Lock must record exact versions, hashes, and platform markers | 15,00_Packaging.json, prefectLock Purpose |

---

## 3. What the existing artifacts are (and are not)

| Artifact | Content | Status |
|----------|---------|--------|
| `prefect-3.9.2-managed-lock.txt` | 106-package complete environment snapshot from the existing managed Prefect qualification environment | **NOT** the minimal lock; it is a metadata observation of the PHASE-00 environment |
| `Prefect_Environment_And_Dependency_Manifest.json` | Metadata manifest for 106 installed distributions | Metadata observation; 98 distributions expose license fields/expressions, 8 do not |
| Lock SHA-256 | `805c074e3e9182cd5e921c2bfc5198a84300d7f1cd4f686370f044899e2042ee` | Snapshot integrity reference only |
| Manifest SHA-256 | `21aca5dea787a9b52dbe592262b98793f99cc71e2fa0ae472d3b6a57f467c790` | Manifest integrity reference only |

**Prohibited:** Do not copy the 106-package Prefect environment snapshot as the minimal lock. The snapshot includes packages present only in the existing qualification environment (e.g. Docker, Redis, SQLAlchemy, FastAPI, Uvicorn) that are not required for the minimal `gpwcf[prefect]` runtime closure.

---

## 4. Gate creation procedure

The lock must be created through the following steps:

### Step 1 — Clean environment reconstruction

Provision a clean, isolated Python 3.15.1 x64 environment on Windows x64 with **no** pre-installed packages beyond those present in a base `venv`/`virtualenv` creation.

Install **only**:

```
pip install gpwcf[prefect]
```

This resolves `prefect==3.9.2` and its exact transitive closure from PyPI (or the configured index) into the clean environment.

### Step 2 — Freeze the lock

Run:

```
pip freeze --all > requirements-prefect.lock
```

The resulting `requirements-prefect.lock` must contain only packages that are direct or transitive dependencies of `gpwcf[prefect]`. It must **not** contain packages that were only present in the PHASE-00 managed environment.

### Step 3 — Record integrity

Compute and record:

- Lock file SHA-256
- Manifest SHA-256 (if a metadata manifest is generated for the clean environment)
- Environment reconstruction timestamp and host platform (Windows x64, CPython 3.15.1)

### Step 4 — Review (release gate)

Before passing the gate, review the lock for:

1. **Runtime relevance:** Every package must be required by `gpwcf[prefect]`'s transitive closure. No extraneous packages.
2. **License compliance:** Review license metadata for every package. Prefect itself is Apache-2.0. All transitive dependencies must have acceptable, reviewed licenses.
3. **Platform markers:** Verify that platform markers (e.g. `sys_platform == "win32"`, `python_version == "3.15"`) are correctly recorded where applicable.
4. **Hashes:** Record exact version + hash for every pinned package.

---

## 5. What passes the gate

The gate passes when:

- [ ] `requirements-prefect.lock` exists in the project (recommended location: root or `.docs/00.02_Prefect_Adoption_Integration Architecture/`)
- [ ] The lock was reconstructed from a clean `pip install gpwcf[prefect]` environment (not copied from the PHASE-00 snapshot)
- [ ] Every package in the lock is a direct or transitive dependency of `gpwcf[prefect]`
- [ ] License review completed for every package (Prefect = Apache-2.0; all transitive deps reviewed)
- [ ] Platform markers and hashes recorded for every package
- [ ] Lock SHA-256 and Manifest SHA-256 recorded
- [ ] Clean environment reconstruction documented (environment hash, timestamp, host platform)

---

## 6. What fails the gate

Any of the following fails the gate and blocks release of the `[prefect]` extra:

- Copying the 106-package PHASE-00 snapshot as the minimal lock
- Including packages not required by `gpwcf[prefect]`
- Missing license review for any package
- Missing hash or platform marker recording
- Lock created from an environment with extraneous pre-installed packages

---

## 7. Relationship to other artifacts

- `pyproject.toml` declares `prefect==3.9.2` under `[project.optional-dependencies] prefect` — the lock is the **frozen realization** of that declaration.
- The `prefectLock` specification in `15,00_Packaging.json` defines this gate; this document operationalizes it.
- `tests/architecture/test_build_backend_isolation.py` verifies that `pyproject.toml` declares the prefect extra and that core dependencies contain no Prefect — it does **not** verify the lock itself (the lock is a release-process artifact, not a runtime test artifact).

---

## 8. Open items

- [ ] Clean environment reconstruction and lock creation
- [ ] License review for all transitive dependencies
- [ ] Hash and platform marker recording
- [ ] Lock SHA-256 and Manifest SHA-256 recording
- [ ] Gate sign-off
