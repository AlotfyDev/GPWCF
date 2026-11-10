## F-01 — Decoupling `StepExecutionResult` from Step Aggregation

The Problem: We have a logically independent module for `StepExecutionResult`, yet it currently resides within the code path dedicated to "Steps." The goal is not necessarily to move it into a separate package, but rather to ensure that the result contract remains independent of the implementation details of "Step Composition."

Architectural Options:

| Option | Design                                         | Evaluation                                     |
| ------ | ---------------------------------------------- | ---------------------------------------------- |
| A      | Placing `Result` directly within the Step implementation | Strong, undesirable coupling                   |
| B      | A logically independent `Result` module within the Step package | Contractual independence with clear ownership  |
| C      | A generic `core.results` package               | Over-separation; risks aggregating heterogeneous results |

My Recommendation: B

Design:

```
core/
└── step/
├── entity.py
├── contracts/
│   └── step_callable.py
├── composition/
├── lifecycle/
└── results/
├── step_execution_result.py
├── result_contract.py
└── result_validation.py
```

However, there is an important nuance: `StepExecutionResult` is not merely a container for results; it is the contract that represents the outcome of a Step's execution.

It should define:

- The identity of the executed Step.
- The identity of the invocation.
- The completion status of the Step execution.
- The results of the executed SPUs (Step Processing Units).
- The results of the selected "Supporting Units."
- Final reconciliation information.
- Details regarding failures or uncertainty, when applicable.

It should *not* include Prefect-specific states or Prefect Run IDs as part of its core semantics.

Furthermore, the result of an SPU must be entirely independent of the result of a Step. Required closure: Define the `StepExecutionResult` contract and its relationship to the Step Callable contract, then subsequently adopt an optional-results policy in F-05.