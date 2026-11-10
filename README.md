# SMRB.GenericPipelineWorkflowComponentsFramework

GPWCF is a reusable Python framework for composing Stage, Step and standalone Processing Unit (SPU) entities. It defines generic contracts and composition ownership; concrete workflow topology, business policies and specializations remain consumer-owned.

## Architecture boundaries

- Core is independent of Prefect and currently uses the Python standard library only.
- Stage Composition coordinates Step public contracts.
- Step Composition coordinates SPUs and only the optional Supporting Pattern capabilities selected by the consumer.
- SPU is a standalone processing entity and does not depend on Step.
- Prefect 3.9.2 is the accepted initial external workflow runtime. Its integration is opt-in and isolated from Core.
- The initial distribution decision is one distribution with a dependency-free Core base and an optional Prefect extra.

## Current implementation status

The repository currently contains the initial package and test directory skeleton. Package markers intentionally export no symbols. Domain implementations, unresolved callable/result contracts, Prefect production bindings and build metadata are not implied by the presence of directories.

## Dependency locations

The SMRB solution-root .dependencies directory stores external dependency/source assets and project-scoped dependency material. The solution-root .env directory is the shared local Python virtual environment. Neither is a GPWCF runtime dependency or part of the distributable package.

## Governing architecture

See:

- .docs/Identity.json
- .docs/00.00_Primary_Architecture/
- .docs/00.02_Prefect_Adoption_Integration Architecture/
- .docs/00.03_Architecture_Closure_Design/

The PHASE-03 Cross-Artifact Consistency Review and Filesystem_Architecture.json govern the initial package skeleton and explicitly record deferred modules and remaining gates.

## Detailed design proposals and Public API readiness

The current Primary Architecture folder contains 16 detailed design-wave proposals (Waves 1-6) that remain in draft-for-architecture-review status. Their proposed identities, generic Stage/Step result and invocation contracts, diagnostics, publication refinements, Prefect bindings, exact Public API exports and packaging metadata are not treated as accepted implementation contracts by the initial skeleton.

Accordingly, the source public_api package is intentionally not materialized yet. It will be created only after the Wave 6 Public API design and the complete detailed-design set are explicitly accepted and reconciled with PHASE-03. The conceptual public API boundary is retained; no public symbols are exported at this stage.
