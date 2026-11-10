
## F-04 — Consumer Boundary

Problem: We need to clarify the relationship between GPWCF and the applications that consume it, without leaking consumer-specific details into the framework itself.

Options:

| Option | Design                                           |
| ------ | ------------------------------------------------- |
| A      | Include the Generator within GPWCF                |
| B      | Define a generic Consumer Package within GPWCF    |
| C      | Treat the consumer as an independent project that relies on a Public API |
| D      | Create a Consumer SDK within GPWCF                |

My recommendation: C

Each consumer possesses:

- Stage specializations.
- Step specializations.
- SPU implementations.
- Supporting pattern implementations or their specialized policies.
- Business inputs/outputs.
- Consumer-specific error models.
- Workflow topology and execution policy.

For example:

```
SMRB/
├── SMRB.GenericPipelineWorkflowComponentsFramework/
│   └── src/gpwcf/
│
└── SMRB.PayloadDescriptionGenerator/
├── stages/
├── steps/
├── spus/
├── supporting_units/
└── workflow_definitions/
```

Integration is achieved via the Core Public API and the Prefect Integration Public API.

Conclusion: Define a "Consumer Integration Contract" as an architectural boundary, without creating a consumer runtime or a generator package within GPWCF.