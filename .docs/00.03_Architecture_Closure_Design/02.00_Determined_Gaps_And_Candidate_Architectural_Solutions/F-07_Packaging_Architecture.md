## F-07 — Packaging Architecture

This gap requires a decision based on distribution independence, rather than the ease of project setup.

Options:

A — Single Distribution with Optional Prefect Extra

```
gpwcf
├── Core
└── Prefect Integration (optional extra)
```

- A single distribution.
- The core does not import Prefect during standard usage.
- Prefect integration is installed via an "extra."
- A unified version for both components.

Most suitable as a starting point.

B — Separate Distributions

```
gpwcf-core
gpwcf-prefect
```

- Complete independence in terms of installation and versioning.
- The integration depends on the core.
- Higher complexity regarding version compatibility and distribution.

C — Monorepo with Multiple Distributions

```
repository/
├── packages/core/
└── packages/prefect/
```

- Actual separation of distributions while maintaining development within a single repository.
- Appropriate if multiple integrations are added or if there is a need for independent versioning.

My recommendation: Option A for the initial phase, with a design that allows for a transition to Option C later.

Reasoning: We currently have only one supported integration, and there is no evidence to suggest that separating the distributions is necessary at this stage.

However, the core must be installable and usable without Prefect, and installing the core must not trigger an indirect installation of Prefect.

The `pyproject.toml` file should be structured based on this decision, with a clear separation between:

- Build dependencies.
- Core runtime dependencies.
- Prefect integration runtime dependencies.
- Development dependencies.
- Test/verification dependencies.

Generator dependencies should not be included within GPWCF.

## PHASE-03 disposition — accepted 2026-11-09

Option A is selected for the initial release: one GPWCF distribution with a dependency-free Core base and an optional prefect extra. Core installs and imports without Prefect; the optional extra supplies the Prefect Integration runtime. Prefect is not added to base Core requirements. prefect==3.9.2 remains the direct Integration requirement; its minimized transitive lock is still a release gate. The Python build backend and build-system pinning remain a separate unresolved gate, so pyproject.toml build metadata is not created as part of the source skeleton.

Python dependency assets remain under the SMRB solution-root .dependencies/ hierarchy. The shared developer virtual environment remains at SMRB solution-root .env/; no GPWCF-local duplicate dependency store or virtual environment is created.


### Detailed Packaging proposal status

The later Primary Architecture Packaging proposal recommends setuptools.build_meta with setuptools==84.2.1 and the initial gpwcf 0.1.0 / Python >=3.15,<3.16 metadata. That document remains draft-for-architecture-review. PHASE-03 accepts only the single-distribution plus optional Prefect-extra shape; it does not yet accept the proposed backend/version/Python metadata, py.typed or lock-file paths. Those remain gated by explicit Wave 6 acceptance.
