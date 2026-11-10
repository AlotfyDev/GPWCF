## F-02 — Conditional Step Error Model

This is one of the most significant gaps, as it affects the independence of GPWCF from the Generator.

The current issue is that `Common/Error_Model.json` contains concepts tied to the Generator, and some contracts—ostensibly general-purpose—depend on it.

I do not recommend moving this model to GPWCF in its current form.

Architectural Options:

| Option | Design                                                 | Primary Drawback                   |
| ------ | ------------------------------------------------------ | ---------------------------------- |
| A      | Move the Generator Error Model to the Core             | Leaks consumer-specific semantics  |
| B      | Build a Generic Error Contract within the Core         | Requires defining the scope of its responsibilities |
| C      | Use Exceptions exclusively                             | Fails to cover structured results and settlements |
| D      | Capability-specific Error Contracts with a limited general contract | Requires careful design to avoid redundancy |

My recommendation: D, combined with a minimal core derived from B.

I propose a breakdown into three independent concepts:

1. Error Identity / Error Description

Represents the description of the problem or abnormal state:

- Code
- Category
- Description
- Origin
- Context
- Diagnostic Details

2. Failure Semantics

Represents the functional meaning of the failure:

- Why did the operation fail?
- What condition was not met?
- Is a retry possible?
- Did the execution fail, or did the settlement fail?
- Is the outcome definitive or indeterminate?

3. Execution Outcome

Represents the result of the operation from the perspective of the contract that executed it.

It is crucial here not to conflate "Error," "Failure," and "Outcome." I propose keeping the general core small:

```
core/
└── shared_contracts/
└── diagnostics/
├── error_descriptor.py
├── failure_descriptor.py
└── diagnostic_context.py
```

However, we should not create `shared_contracts` solely for the sake of this proposal. We must first verify that these contracts are genuinely shared across Stages, Steps, SPUs, and Supporting Patterns—ensuring they represent more than just a duplication of names.

As for the specifics of error handling, they should remain under:

```
core/supporting_patterns/error_handling/
```

Furthermore, the Generator should remain free to define its own error model and map GPWCF errors to its own specific semantics.

Decision required: Adopt a limited "Generic Diagnostics Contract," while maintaining "Error Handling" as an optional Supporting Pattern and keeping the "Generator Error Model" independent.