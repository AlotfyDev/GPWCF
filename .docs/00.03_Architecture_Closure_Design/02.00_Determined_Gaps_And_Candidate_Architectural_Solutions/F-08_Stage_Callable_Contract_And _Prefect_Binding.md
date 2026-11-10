## F-08 — Stage Callable Contract and Prefect Binding

This represents a gap that goes beyond simply deferring the `stage.py` file.

We need a unified contract that defines how a Stage receives an invocation, returns a result, and integrates with the parent workflow.

Architectural Options:

| Option | Design                                                   | Evaluation           |
| ------ | --------------------------------------------------------- | -------------------- |
| A      | Stage as a simple Python Callable                         | Insufficient         |
| B      | Stage Protocol defining invocation and result             | Good                 |
| C      | Stage Aggregate implementing a callable contract independent of Prefect | Best                 |
| D      | Prefect Flow as the Stage contract                       | Couples the core to the runtime |

My recommendation: C

Proposed Design:

```
Stage
├── StageIdentity
├── StageDefinition
├── StageCallableContract
├── StageInvocation
├── StageExecutionContext
├── StageResult
└── StageLifecycle
```

The general contract defines:

1. What makes an entity a callable "Stage"?
2. What constitutes the standard input?
3. How is the execution context passed?
4. What is the structure of the result?
5. How are completion, failure, and indeterminate states expressed?
6. How are cancellations and timeouts handled?
7. What are the lifecycle boundaries and cleanup responsibilities?

The Prefect integration then establishes the binding:

```
Stage Callable Contract
| 
v
Prefect Stage Binding
| 
v
Prefect Stage Flow / Deployment
```

Crucially, the `StageCallableContract` has no awareness of `Flow`, `Deployment`, or `FlowRun`.

Once the contract is stable, the Prefect Public API can facilitate this Stage binding.

We do not need to make the Stage itself a Prefect Flow; rather, the Stage must be functionally bindable to a Prefect Flow.