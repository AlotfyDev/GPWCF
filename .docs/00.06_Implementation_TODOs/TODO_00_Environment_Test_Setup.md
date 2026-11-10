# TODO 00 — Environment & Test Runner Setup

**Status:** ✅ implemented | **Priority:** blocker | **Effort:** low | **Depends on:** —

## Why

No test runner is installed in either venv (`pytest` missing), and `tests\architecture\` has
no package init. Every other task's DoD depends on running tests.

## Checklist

- [x] Install pytest into the **project-local** venv (keep the solution venv untouched):
      ```powershell
      .env\Scripts\python.exe -m pip install pytest        # installed pytest 9.2.0
      ```
- [x] Add `requirements-dev.txt` at project root recording the dev-only dependency
      (`pytest>=8`; runtime stays standard-library-only).
- [x] Create `tests\architecture\__init__.py` (empty docstring) — architecture tests land here in later tasks.
- [x] Add a minimal `pytest.ini` at project root (`testpaths = tests`, `addopts = -q`).
      *(Task-11 addendum: root `conftest.py` puts `src\` on `sys.path` so tests import the
      not-yet-installed `gpwcf` package.)*
- [x] Run `pytest` and confirm the placeholder suite collects and passes:
      **76 passed in 0.91s** (placeholder tests).
- [x] Confirm the baseline import works from project root:
      `import gpwcf, gpwcf.core, gpwcf.core.identities, gpwcf.core.diagnostics` → OK.
- [x] Update the status board in `00_MASTER_TODO.md` and `AGENTS.md`.

## Verify

```powershell
.env\Scripts\python.exe -m pytest
```

## Result

- pytest 9.2.0 (+ pluggy, iniconfig, packaging, colorama, pygments) installed into the
  project-local venv only (`.env\`); solution venv untouched.
- All 76 placeholder tests green. Ready for Task 11.
