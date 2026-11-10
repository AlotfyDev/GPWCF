
## F-05 — Correcting the Dependency Direction between SPU and Step

Critical Gap

The issue is not merely an error in `dependsOn`; we must ensure that the SPU remains independent of the Step, even at the execution level.

Options:

1. The SPU knows about and invokes the Step.
2. The Step knows about and invokes the SPU.
3. Both depend on a "Universal Execution Unit."
4. Both interact via independent contracts, with the Step retaining the responsibility for coordination.

My recommendation: Option 4.

Design:

```
Step Aggregate
| 
| consumes
v
SPU Contract
| 
v
SPU Implementation
```

Functional Workflow:

- Step Composition selects the SPUs.
- Step Composition defines the Invocation Context.
- The SPU receives its inputs via its contract.
- The SPU performs its assigned task.
- The SPU returns an `SPUExecutionResult`.
- Step Composition interprets the result according to its own contract.
- The Step Aggregate aggregates the results and issues a `StepExecutionResult`.

Note that we do not need to define a "Universal Executable Unit" to achieve this.

An independent Invocation Contract can be defined if it is determined that there are, in fact, shared characteristics between the SPU and other "Supporting Units."

Important: A functional relationship does not imply a reverse programmatic dependency. Furthermore, an explicit "association" is not a prerequisite for such a relationship.

## PHASE-03 disposition — accepted 2026-11-09

The dependency direction is accepted as Step Composition to SPU contract only. The SPU package has no package/runtime dependency on Step. Step Composition invoking an SPU is a domain invocation/ownership relationship, not a reverse import edge. No Universal Executable Unit or shared base is introduced.
