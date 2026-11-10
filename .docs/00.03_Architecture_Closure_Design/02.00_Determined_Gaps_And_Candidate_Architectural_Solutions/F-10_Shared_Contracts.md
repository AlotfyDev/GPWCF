## F-10 — Shared Contracts

The Problem: Do we actually need `core.shared_contracts`?

Options:

- A: Create a `shared_contracts` package immediately.
- B: Prohibit any shared contracts.
- C: Create shared contracts only when a clear need arises for a contract that is independent of any specific entity.

My recommendation: C

However, there must be strict acceptance criteria for any contract moved to the shared space:

1. It must have more than one actual consumer.
2. It must have a meaning independent of the entity that uses it.
3. It must not depend on the implementation of any consumer.
4. It must not create a circular dependency.
5. It must have clear ownership.
6. It must not merely be a reuse of similar names or fields.

If a contract meets these criteria, it may be placed in:

```
core/shared_contracts/
```

If, however, it is stage-specific or step-specific, it should remain with the aggregate that owns it.

This approach enables reuse without resulting in an unwieldy or uncontrolled "shared kernel."