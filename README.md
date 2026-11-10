<div align="center">

# 🧬 GPWCF

### Generic Pipeline and Workflow Components Framework

**A behavior-centric, reusable Python framework for defining, composing, specializing, and coordinating workflow components.**

[![Project ID](https://img.shields.io/badge/ID-SMRB.GenericPipelineWorkflowComponentsFramework-6A5ACD?style=flat-square&logo=identity)](.)
[![Version](https://img.shields.io/badge/Version-1.1.0-blue?style=flat-square)](.)
[![Python](https://img.shields.io/badge/Python-3.15.1-3776AB?style=flat-square&logo=python&logoColor=white)](.)
[![Kind](https://img.shields.io/badge/Kind-Reusable%20Framework%20Package-orange?style=flat-square)](.)
[![License](https://img.shields.io/badge/License-Open%20Source-green?style=flat-square)](.)
[![Usage](https://img.shields.io/badge/Usage-Personal%20%7C%20Single%20Machine-lightgrey?style=flat-square)](.)
[![Commercial](https://img.shields.io/badge/Commercial%20Target-No-red?style=flat-square)](.)
[![Consumer Independence](https://img.shields.io/badge/Consumer%20Independence-Enforced-important?style=flat-square)](.)

</div>

---

## 📖 Overview

**GPWCF** is an independent, reusable, **behavior-centric** Python framework that treats *processing mechanisms and behaviors* as first-class reusable units. Data assets and other artifacts are **possible outputs** of those behaviors — **not** the exclusive organizing concept of the framework.

> [!IMPORTANT]
> GPWCF is **independent of any particular consumer application**.
> `SMRB.PayloadDescriptionGenerator` is the **first intended consumer** — *not* the owner or architectural definition of GPWCF.

The framework provides domain-level contracts and reusable capabilities for:

| Component | Role |
| :--- | :--- |
| 🎭 **Stages** | Top-level composition boundaries coordinating Steps |
| 🪜 **Steps** | Composition boundaries selecting, associating, and invoking Processing Units |
| ⚙️ **Step Processing Units (SPUs)** | Reusable, specialized processing behaviors |
| 🛡️ **Supporting Units** *(optional)* | Validation, error handling, observation responsibilities |
| 📊 **Structured Outcomes** | Typed domain results distinct from external runtime states |

---

## 🏛️ Architectural Philosophy

<div align="center">

### 🎯 Behavior-Centric Workflow Framework

</div>

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#6A5ACD','primaryTextColor':'#fff','primaryBorderColor':'#4B0082','lineColor':'#9370DB','secondaryColor':'#E6E6FA','tertiaryColor':'#F0F8FF'}}}%%
flowchart TD
    A[🧠 Behavior<br/>Processing Mechanism]:::behavior
    B[📦 Artifact<br/>Asset / Output]:::artifact
    C[🔍 Assessment<br/>Validation Findings]:::assess
    D[⚡ Side Effect<br/>Effect / Decision]:::assess

    A -->|produces| B
    A -->|produces| C
    A -->|produces| D

    B -.->|may or may not exist| A
    C -.->|assesses quality| B

    classDef behavior fill:#6A5ACD,color:#fff,stroke:#4B0082,stroke-width:2px
    classDef artifact fill:#32CD32,color:#000,stroke:#228B22,stroke-width:2px
    classDef assess fill:#FF8C00,color:#fff,stroke:#FF4500,stroke-width:2px
```

> [!NOTE]
> **Principle:** The *behavior* is a first-class unit of value and reuse.
> A data asset, file, description, report, decision, or validation finding **may be produced** by that behavior — but **a data asset is not required** for the behavior to be meaningful.

### 🚫 Dagster Position

GPWCF **does not** adopt an **Asset-centric orchestration model** as its foundational abstraction, and **does not require Dagster**.

Asset cataloguing, lineage, materialization, and data-asset lifecycle management are **not** assumed to be universal GPWCF responsibilities.

---

## 🧩 Outcome & Assessment Model

<div align="center">

### ⚠️ Four Distinct Concepts — Never Collapsed

</div>

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#FF6347','primaryTextColor':'#fff','lineColor':'#FF4500'}}}%%
flowchart LR
    subgraph CONCEPTS["🎯 Four Separate Domains"]
        direction TB
        E[✅ Execution Completion<br/><i>did it run?</i>]:::exec
        O[📋 Domain Outcome<br/><i>what did it produce?</i>]:::outcome
        V[🔎 Validation Assessment<br/><i>is it acceptable?</i>]:::valid
        R[🌐 Runtime State<br/><i>is it healthy?</i>]:::runtime
    end

    E -.->|≠| O
    O -.->|≠| V
    V -.->|≠| R
    E -.->|≠| R

    classDef exec fill:#4682B4,color:#fff,stroke:#1E3A5F,stroke-width:2px
    classDef outcome fill:#6A5ACD,color:#fff,stroke:#4B0082,stroke-width:2px
    classDef valid fill:#FF8C00,color:#fff,stroke:#FF4500,stroke-width:2px
    classDef runtime fill:#DC143C,color:#fff,stroke:#8B0000,stroke-width:2px
```

> [!WARNING]
> **A behavior may execute successfully while its output is invalid, non-conforming, unsupported, incomplete, or otherwise unacceptable** under the applicable validation rules.

| Concept | Description | Owner |
| :--- | :--- | :--- |
| **Structured Outcomes** | Typed, structured domain result contracts at Stage / Step / SPU boundaries | GPWCF contracts + consumer specialization |
| **Validation** | Validator Units assess outputs against explicit criteria | Consumer-defined criteria |
| **Error / Failure Semantics** | Domain errors, invocation failures, handling results, validation findings | Distinguished per owning contract |
| **Runtime State** | External orchestration state (e.g., Prefect states) | External runtime |

> [!TIP]
> GPWCF **does not impose** one universal consumer error taxonomy or acceptance policy. It supplies *generic contracts and coordination boundaries*; consumers supply *specialized behavior, criteria, and business interpretation*.

---

## 📐 Architectural Scope

<div align="center">

### ✅ What GPWCF Provides

</div>

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#2E8B57','primaryTextColor':'#fff','lineColor':'#006400'}}}%%
mindmap
  root((🎯 GPWCF<br/>Core))
    Contracts
      Stage & Step contracts
      SPU execution-result models
      Supporting Unit contracts
      Validator Unit contracts
    Composition
      Stage-level coordination
      Step-level selection & invocation
      SPU association
      Lifecycle & result custody
    Semantics
      Structured domain outcomes
      Typed result contributions
      Domain errors & failure semantics
      Diagnostics & observation
    Integration
      Prefect Flow/Deployment binding
      Identity preservation
      Typed result custody
```

**Provided Capabilities:**

- 🏗️ **Programmatic contracts & implementations** for Stage and Step components
- 🎼 **Stage-level composition** — coordinating Steps within a Stage
- 🎬 **Step-level composition** — selecting, associating, invoking, coordinating Processing Units
- ⚙️ **SPU contracts & execution-result models** — reusable specialized behaviors
- 🛡️ **Supporting Units** — validation, error handling, observation (optional)
- 📊 **Structured domain outcomes** — distinct from external runtime states
- 🔍 **Validator Units** — assessing outputs against explicit criteria
- 🩺 **Diagnostics, domain errors, error-handling coordination**
- 🔗 **Common coordination contracts** — association, composition, lifecycle, result custody
- 🚀 **Prefect integration** — binding Stage to Prefect-native Flow/Deployment
- 🧬 **Composition & specialization mechanisms** — preserving component responsibilities

---

### 👤 Consumer Responsibilities

<div align="center">

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#FF8C00','lineColor':'#FF4500'}}}%%
flowchart TD
    C[👤 Consumer]:::consumer
    C --> S1[Select & specialize components]:::task
    C --> S2[Provide concrete PU / SU implementations]:::task
    C --> S3[Define business logic & domain types]:::task
    C --> S4[Compose Stages & Steps]:::task
    C --> S5[Define Pipeline Root & topology]:::task
    C --> S6[Define validation & acceptance rules]:::task
    C --> S7[Choose Prefect profile or Core-only]:::task
    C --> S8[Provide Prefect deployment config]:::task
    C --> S9[Define execution/concurrency/recovery policies]:::task
    C --> S10[Define artifact persistence if needed]:::task

    classDef consumer fill:#FF8C00,color:#fff,stroke:#FF4500,stroke-width:3px
    classDef task fill:#F0F8FF,color:#000,stroke:#4682B4,stroke-width:1px
```

</div>

---

### 🚫 Exclusions

> [!CAUTION]
> **GPWCF explicitly does NOT do the following:**

| ❌ Excluded | Reason |
| :--- | :--- |
| Owning / replacing external orchestration (Prefect, etc.) | Runtime orchestration is external |
| Owning consumer's Pipeline Root / business topology | Consumer-owned |
| Implementing `SMRB.PayloadDescriptionGenerator` business logic | Consumer-owned |
| Treating Data Assets as the only first-class entity | Behavior-centric, not Asset-centric |
| Requiring Dagster or Asset orchestration platform | Optional, not foundational |
| Prescribing fixed topology for Stages/Steps/SPUs | Flexible composition |
| Requiring use of every component | Optional composition |
| Universal PU registry / plugin manager / loader | No universal registry |
| Universal business validation / error / retry policy | Consumer-specific |
| Universal workflow framework adapter abstraction | Only explicit integrations |
| Consumer-specific artifact schemas / persistence / lineage | Consumer-owned |

---

## 🌉 Execution & Integration Boundary

<div align="center">

### 🏛️ Three-Layer Ownership Model

</div>

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#6A5ACD','lineColor':'#9370DB'}}}%%
flowchart TB
    subgraph GPWCF_CORE["🧬 GPWCF Core"]
        direction TB
        A1[Domain contracts<br/>Stage • Step • SPU]:::core
        A2[Composition semantics]:::core
        A3[Structured results]:::core
        A4[Lifecycle • Error • Validation]:::core
    end

    subgraph PREFECT_INT["🚀 integrations.prefect"]
        direction TB
        B1[Flow • Deployment • Subflow]:::prefect
        B2[Task • TaskRunner • Runtime API]:::prefect
        B3[Invocation translation]:::prefect
        B4[Operational state capture]:::prefect
    end

    subgraph CONSUMER["👤 Consumer"]
        direction TB
        C1[Pipeline Root Flow]:::consumer
        C2[Business logic & rules]:::consumer
        C3[Concrete implementations]:::consumer
        C4[Acceptance criteria]:::consumer
    end

    CONSUMER -->|depends on| GPWCF_CORE
    PREFECT_INT -->|binds| GPWCF_CORE
    CONSUMER -->|optionally uses| PREFECT_INT

    GPWCF_CORE -.->|must never depend on| CONSUMER
    PREFECT_INT -.->|preserves| GPWCF_CORE

    classDef core fill:#6A5ACD,color:#fff,stroke:#4B0082,stroke-width:2px
    classDef prefect fill:#3776AB,color:#fff,stroke:#1E3A5F,stroke-width:2px
    classDef consumer fill:#FF8C00,color:#fff,stroke:#FF4500,stroke-width:2px
```

### 🧬 GPWCF Core Ownership

- **Owns** domain-level Stage, Step, SPU, and Supporting Pattern *contracts*, *identities*, *composition semantics*, *structured result contracts*, and *specialized domain lifecycle / error / validation responsibilities*
- Domain outcomes and results remain **authoritative domain values** — *not inferred from or replaced by* external runtime states

### 🚀 Prefect Integration Ownership

- **Owns** Prefect-native `Flow`, `Deployment`, `Subflow`, `Task`, `TaskRunner`, and runtime API interaction
- **Translates** GPWCF invocations to Prefect-native execution while **preserving** domain identities, invocation contracts, and typed results
- **Captures** Prefect operational states and native identifiers as *separate operational evidence* — correlated with, but **not replacing**, GPWCF domain identities
- **Remains optional** — GPWCF Core contracts remain **importable and usable without Prefect**

> [!IMPORTANT]
> **Prefect-native completion, failure, cancellation, or crash does NOT by itself establish:**
> - ✅ Domain result acceptability
> - ✅ Publication acceptance
> - ✅ Lifecycle release
> - ✅ Safe settlement of domain custody

### 👤 Consumer Ownership

- Owns its **Pipeline Root Flow** and overall workflow topology
- Owns concrete Stage / Step / SPU / Supporting Pattern implementations
- Owns business rules and specialized validation/acceptance criteria
- Selects and configures the Prefect execution profile **when using the optional integration**

> [!TIP]
> **Integration Principle:** GPWCF supplies *reusable behavioral/workflow structure and domain semantics*; Prefect supplies *external runtime orchestration*. The integration **binds** these layers **without transferring domain ownership to Prefect** or **reducing an SPU/behavior to a native Prefect Task**.

---

## 📦 Dependency Management

<div align="center">

### 🧪 Environment

</div>

| Aspect | Value |
| :--- | :--- |
| **Development Interpreter** | `SMRB` solution shared virtual environment |
| **Path** | `..\.env\Scripts\python.exe` |
| **Python Version** | `3.15.1` |
| **User Site Packages** | `disabled` |
| **Project Requirements** | `requirements.txt` |
| **Solution Aggregator** | `..\requirements.txt` |

### 🔌 Runtime Dependencies

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#2E8B57','lineColor':'#006400'}}}%%
flowchart LR
    subgraph BASELINE["📚 Core Baseline"]
        STD[Python Standard Library<br/><i>only dependency</i>]:::std
    end

    subgraph OPTIONAL["🚀 Optional Extra"]
        PREF[Prefect<br/><i>integrations.prefect only</i>]:::opt
    end

    CORE[🧬 GPWCF Core]:::core
    CORE --> STD
    OPTIONAL -.->|optional| PREF

    classDef std fill:#32CD32,color:#000,stroke:#228B22,stroke-width:2px
    classDef opt fill:#3776AB,color:#fff,stroke:#1E3A5F,stroke-width:2px
    classDef core fill:#6A5ACD,color:#fff,stroke:#4B0082,stroke-width:2px
```

> [!NOTE]
> - **Core implementation baseline** uses the **Python standard library only**
> - **Prefect** is an *optional dependency* of the `integrations.prefect` extra/profile — **NOT** a Core base dependency
> - The framework **does not own or duplicate** a Python runtime

### 🔒 Consumer Isolation

> The framework package **must not depend on** the private dependency bundle, source tree, or implementation details of `SMRB.PayloadDescriptionGenerator` or **any other consumer**.

A consuming application retains **ownership of its runtime and dependency environment**.

---

## 📚 Documentation

| 📁 Section | 📂 Path |
| :--- | :--- |
| 📖 **Root** | `.docs` |
| 🏛️ **Primary Architecture** | `.docs/00.00_Primary_Architecture` |
| 🚀 **Prefect Adoption & Integration** | `.docs/02.00_Prefect_Adoption_Integration Architecture` |
| ⚠️ **Prefect Integration — Environment & Runtime Lessons** | `.docs/00.07_Prefect_Integration_Environment_Runtime_Dependencies_Lessons` |

---

## 📊 Project Status

<div align="center">

| 🎯 Area | 📈 Status | 🔍 Notes |
| :--- | :---: | :--- |
| **Identity Established** | ✅ | — |
| **Implementation Capabilities** | 🟡 | *Partially implemented and technically verified.* Core, Prefect integration, packaging, and defined test profiles passed their recorded tests. **Not** a claim that every designed capability or production scenario is qualified. |
| **Prefect Integration** | 🟡 | *Implemented and tested* for defined fixture and same-machine profiles. Production binding of all specialized implementations and advanced failure/recovery scenarios **remain subject to explicit qualification gates**. |
| **Consumer Integration** | ⚪ | *Not yet established.* `SMRB.PayloadDescriptionGenerator` is currently an **implementation-pending consumer skeleton** — it is the first intended consumer, **not** a dependency or architectural owner of GPWCF. |
| **Release Readiness** | 🟡 | Technical implementation evidence exists. **Formal dependency-license review**, Prefect lock release-gate reconciliation, and remaining architecture/operational qualification gates are **tracked separately**. |

</div>

> [!WARNING]
> Consult the **owning contracts, acceptance evidence, and open gates** — this status table does not substitute for them.

---

## 🗺️ Consumer Onboarding Map

<div align="center">

### 🚀 How to Become a GPWCF Consumer

</div>

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#6A5ACD','lineColor':'#9370DB','fontSize':'14px'}}}%%
flowchart TD
    START([👋 New Consumer]):::start

    START --> S1[1️⃣ Read Primary Architecture<br/>.docs/00.00_Primary_Architecture]:::step
    S1 --> S2[2️⃣ Understand Behavior-Centric Model<br/>SPU = first-class behavior]:::step
    S2 --> S3[3️⃣ Choose Scope<br/>Core-only OR Core + Prefect]:::decision
    S3 -->|Core-only| C1[Import Core contracts]:::core
    S3 -->|+ Prefect| P1[Install Prefect extra]:::prefect

    C1 --> I1[4️⃣ Implement Stage / Step / SPU contracts]:::impl
    P1 --> I1

    I1 --> I2[5️⃣ Define domain types & results]:::impl
    I2 --> I3[6️⃣ Define validation criteria]:::impl
    I3 --> I4[7️⃣ Compose Pipeline Root]:::impl
    I4 --> I5[8️⃣ Qualify against owning contracts]:::impl
    I5 --> DONE([✅ Integrated Consumer]):::done

    classDef start fill:#32CD32,color:#000,stroke:#228B22,stroke-width:3px
    classDef step fill:#F0F8FF,color:#000,stroke:#4682B4,stroke-width:1.5px
    classDef decision fill:#FFD700,color:#000,stroke:#B8860B,stroke-width:2px
    classDef core fill:#6A5ACD,color:#fff,stroke:#4B0082,stroke-width:2px
    classDef prefect fill:#3776AB,color:#fff,stroke:#1E3A5F,stroke-width:2px
    classDef impl fill:#FF8C00,color:#fff,stroke:#FF4500,stroke-width:1.5px
    classDef done fill:#32CD32,color:#000,stroke:#228B22,stroke-width:3px
```

---

<div align="center">

### 🧬 *Behavior is the unit. Assets are the outcome.*

[![Made with Python](https://img.shields.io/badge/Made%20with-Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](.)
[![Framework](https://img.shields.io/badge/Framework-GPWCF-6A5ACD?style=for-the-badge)](.)
[![Prefect](https://img.shields.io/badge/Prefect-Optional-3776AB?style=for-the-badge&logo=prefect&logoColor=white)](.)

</div>