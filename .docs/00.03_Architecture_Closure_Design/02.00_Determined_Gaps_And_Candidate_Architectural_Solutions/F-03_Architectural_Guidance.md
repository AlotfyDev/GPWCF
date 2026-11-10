## F-03 — Architectural Guidance

This is not a runtime function; therefore, it should not be packaged as an executable component.

However, simply placing it in a documentation folder—without defining its relationship to established contracts—is insufficient.

Options:

- A: Documentation only.
- B: Documentation + Conformance Rules.
- C: Documentation + Runtime Governance Engine.

My recommendation: B

Proposed structure:

```
.docs/
└── Architecture/
├── Entity_Conformance/
├── Composition_Conformance/
├── Association_Conformance/
├── Lifecycle_Conformance/
└── Integration_Conformance/
```

This approach provides programmatically verifiable rules, without the need to build a runtime manager or a universal validator.

For example:

- A `Stage` is not permitted to call an `SPU` directly.
- The `Core` is not permitted to import `Prefect`.
- An `SPU` is not permitted to import `Step Composition`.
- The `Core` is not permitted to depend on a `Generator`.
- Replacing a `Domain Result` with a `Prefect State` is not permitted.

These rules can be enforced through "architecture tests."

In this way, the guidance evolves from mere advice into testable conformance standards, without introducing any new operational responsibilities.