## F-06 — Stage Flow Result

This represents a fundamental gap; we require a `Stage` result that is consumable by both a parent workflow and the pipeline root, without assuming that every `Stage` produces the exact same detailed structure.

Options:

| Option | Design                                               | Outcome                           |
| ------ | ---------------------------------------------------- | --------------------------------- |
| A      | A unified, generic `FlowResult` for all levels       | Over-generalization               |
| B      | Each `Stage` defines its own result with no shared contract | Poor integration                  |
| C      | A generic `StageResult` contract with a specialized payload | A balance between generality and specialization |
| D      | Using `Prefect State` as the `StageResult`           | Conflation of execution state and functional semantics |

My recommendation: C

Design:

```
core/
└── stage/
├── contracts/
│   └── stage_callable.py
└── results/
├── stage_result_contract.py
└── stage_result_metadata.py
```

I propose that a `StageResult` consist of two parts:

A. Generic Stage Execution Result Envelope

Contains general information required by every `Stage`:

- Stage Identity.
- Stage Invocation Identity.
- Execution Completion.
- Domain Outcome Classification.
- Correlation Information.
- Settlement Information.
- Diagnostics.

B. Specialized Stage Result Payload

Contains the actual result defined by the consumer—for example, a `GeneratorStageResult`.

The envelope does not impose a single schema upon the payload.

In Python, this is represented using Generics or Protocols, depending on the final design:

```
StageResult[TStagePayload]
```

Furthermore, one should not assume that every `Stage` result can be reduced merely to "success" or "failure." Scenarios such as inconclusive outcomes, partial results, or controlled termination may also be significant, depending on the specific contract in place. An important point: The Prefect State remains independent. It is possible for the Prefect State to be 'COMPLETED' while the Stage Domain Result contains an unsuccessful functional outcome; conversely, the relationship cannot be determined without explicit mapping rules.

## PHASE-03 disposition — deferred contract, accepted filesystem constraint (2026-11-09)

Stage owns its Flow Result semantics, independently of StepExecutionResult and Prefect State. The proposed generic envelope/specialized-payload direction remains a candidate requiring a dedicated contract decision; it is not an approved universal StageResult schema in PHASE-03. Consequently, core/stage/results/ and any generic FlowResult/StageResult implementation are deferred and are not materialized in the initial skeleton. Each consumer Stage may retain its own specialized result contract.
