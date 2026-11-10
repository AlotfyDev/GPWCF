# Pipeline Architecture and Stage Interface Contract

**Purpose:** Normative cross-stage integration contract for Stage 1–13 specifications.  
**Status:** Design baseline; unresolved decisions remain explicitly listed in the owning stage specification.

## 1. System purpose and responsibility boundary

The Generator produces versioned, evidence-bearing descriptions sufficient to establish the storage layout of a supported payload representation and map logical payload entities to locations in that representation.

The Generator produces description information. It does not execute allocation, Buffer creation, Shared Memory mapping, Named Pipe transfer, population, reading/writing, access authorization, synchronization, transport configuration or resource lifecycle.

The pipeline does not define consumer Use Cases, actors, roles, workflows, preconditions or postconditions. A representation profile is a technical description contract, not a consumer Use Case.

## 2. Stage artifact flow

| Stage | Authoritative output | Primary consumers |
|---|---|---|
| 1 — Build Context Discovery | Build Context Inventory | 2, 3, 4, 5–13 for pinned resources |
| 2 — Compilation Context Resolution | Immutable Compilation Context Set + TU association | 4, 5, 6, 7, 10, 12 |
| 3 — Payload Type Input | Type Input Descriptor | 4 |
| 4 — Type Resolution | Resolved Type Binding Set + TU/declaration locators | 5, 6, 7, 8, 9, 10 |
| 5 — AST Extraction | AST Observation Packages | 7, 10 |
| 6 — XML Generation | XML Observation Packages | 7, 10 |
| 7 — Declaration Analysis | Declaration Analysis Model + Layout Control Application candidates | 8, 9, 10 |
| 8 — Dependency Resolution | Resolved Type Dependency Graph | 9, 10 |
| 9 — Logical Description | LD artifact | 10, 11, 12, 13 |
| 10 — Physical Layout Extraction | Context-bound PLD artifact(s) | 11, 12, 13 |
| 11 — Description Composition | Representation-qualified SAM artifact(s) | 12, 13 |
| 12 — Validation | Validation Report + support decision | 13 |
| 13 — Output Generation | Versioned Description Package + manifest | Consumer/runtime |

Stage numbers express logical ownership and dependency, not a requirement that every stage be a separate executable, process, library or deployment unit.

## 3. Execution dependency graph

- Stage 1 is infrastructure-wide for a Generator invocation/environment. It is not repeated per payload type unless the environment or inventory scope changes.
- Stage 2 consumes Stage 1 and may resolve multiple Compilation Contexts/TUs.
- Stage 3 captures the requested type and may run independently of Stage 2 after the Generator invocation is established.
- Stage 4 requires Stage 1 scope, Stage 2 contexts and Stage 3 type input.
- Stages 5 and 6 may run in parallel for each Stage 4 binding, provided both reproduce the same exact Compilation Context.
- Stage 7 consumes Stage 4, 5 and 6; it may tolerate a missing provider only where an approved capability/coverage rule permits it.
- Stage 8 consumes Stage 7's declaration/type graph.
- Stage 9 consumes Stage 7 and 8 and produces logical identities/relationships.
- Stage 10 consumes the exact context, declaration/dependency graph, LD references and evidence observations; it produces one PLD per resolved type/context pair.
- Stage 11 consumes LD, applicable PLD inputs and a selected representation profile/rule set governed by Target_Payload_Representation_Profile_Contract.md; it produces separate SAM artifacts for distinct representations.
- Stage 12 validates the exact LD/PLD/SAM set and its pinned rules.
- Stage 13 packages only the exact artifacts and validation result from Stage 12.

## 4. Artifact identity and immutability

Every artifact payload is published with the sidecar Artifact Envelope defined in Pipeline_Artifact_Envelope_Identity_and_Canonicalization_Contract.md. The envelope must identify:
- Artifact ID, artifact kind, schema/contract ID and version.
- Producing stage, pipeline run and relevant request identity.
- Producer implementation/version where relevant.
- Input artifact IDs and content fingerprints.
- Creation/result status and diagnostics.
- Provenance references and deterministic content digest where supported.

Artifacts are immutable after publication. A correction creates a new artifact/version/run; downstream consumers must not observe an in-place mutation. A stage must reject unsupported schema versions and dangling required references rather than guessing their meaning.

## 5. Identity domains — do not conflate

The pipeline distinguishes at minimum:
- Pipeline Run ID.
- Type Input Descriptor / request ID.
- Compilation Context ID and fingerprint.
- Translation Unit identity.
- Resolved Type ID (context-bound resolution result).
- Declaration identity/locator (Stage 7 declaration domain).
- LD logical type/entity IDs (Stage 9).
- PLD physical node IDs (Stage 10).
- Canonical PLD propertyId and Layout Control controlId.
- Evidence ID and provenanceLineageId.
- SAM region, coordinate-space, mapping, expression and parameter IDs.
- Representation profile/rule-set IDs.
- Diagnostic IDs.
- JSON Pointer references.

A provider-native AST/XML node ID is not a canonical declaration or logical identity. A JSON Pointer is a location in one exact serialized document version, not a stable identity. A process-local pointer is not a shared-memory handle. A resolved type ID is not a native type name and not a logical entity ID.

## 6. Compilation Context and representation separation

Compilation Context describes how the consumer's C++ translation unit was compiled: compiler/frontend, language mode, target, standard library, SDK, include paths, macros and ABI-affecting options.

Representation profile describes how logical entities are encoded/mapped into target payload storage. It may be Shared Memory payload representation or message-payload representation, but it is not the operating-system transport configuration.

PLD facts are bound to one exact Compilation Context. SAM is bound to its representation profile and references the PLD inputs it uses. Native offsets are not target offsets unless SAM explicitly establishes and Stage 12 validates equivalence.

## 7. Data ownership across layers

- Stage 7 owns declaration-analysis identities/relationships for the source declaration graph.
- Stage 9 owns stable logical identities and logical relationships (LD).
- Stage 10 owns native physical facts (PLD).
- Stage 11 owns target representation, storage regions, coordinates, mappings and location formulas (SAM).
- Stage 12 owns validation/adjudication results, not producer facts.
- Stage 13 owns packaging, not semantic facts.

One fact has one authoritative owner. Other layers reference it and may add their own separate facts, but may not duplicate or mutate its meaning.

## 8. Cross-cutting evidence and registries

Stage 1 inventories and pins the immutable registry set and schemas. Consuming stages record exact versions/fingerprints.

- Stage 5/6 preserve raw observations and their source/context lineage.
- Stage 7 binds declaration observations and recognized control applications.
- Stage 10 produces native property Facts, Layout Control Applications and special PLD facts.
- Stage 11 produces target-representation facts under SAM-owned property policies.
- Stage 12 independently assesses Evidence Status, Evidence Role, lineage/correlation, comparisons and FactStatus using property-specific policies.
- Stage 13 preserves those exact results.

A new artifact ID or provider name does not create independent evidence. Common source/TU/context lineage and derivation ancestry must be retained.

## 9. Shared numeric contract

Stage 10 defines the shared Numeric Abstraction Layer contract used by Stage 10 and downstream SAM calculation/validation. Canonical integer values use exact mathematical semantics; units and property domains are explicit. All conversions and calculations are exact and checked. No floating-point intermediary, rounding, truncation, wraparound, saturation or unchecked narrowing is allowed.

Native C++ byte quantities use the Compilation Context's CHAR_BIT. Target representation units are separately defined by SAM. JSON numeric serialization/parsing must preserve exact integer values.

## 10. Failure propagation

A stage may emit a partial diagnostic artifact only when its identity, schema and internal structure remain safe to consume. Every output states whether it is complete, partial, blocked, unresolved, conflicting or unsupported.

- A failed prerequisite blocks only dependent claims/branches where possible.
- No stage repairs another stage's authoritative artifact in place.
- A downstream stage must not infer missing upstream facts.
- Unsupported constructs remain explicit and scoped.
- Retrying with identical immutable inputs and versions must be deterministic, apart from declared run/time metadata.

## 11. Support decision scope

Stage 10 assesses native physical-fidelity coverage per resolved Type × exact Compilation Context. Stage 11 assesses a selected target representation. Stage 12 makes the composite support decision for the exact LD × applicable PLD/context × SAM representation profile/version.

No global statement that a C++ type is simply "supported" is valid without this qualification. A valid PLD alone does not prove a target representation, Buffer Establishment or Mapping is supported.

## 12. Specification precedence

- Layer contracts define authoritative information ownership and semantic meaning.
- Stage specifications define each stage's executable responsibilities, processing, inputs, outputs, failure behavior and acceptance.
- Machine-readable schemas define structural serialization constraints only; they do not replace semantic validation.
- Matrices define information obligations and feature traceability.
- Tool-selection documents describe candidate/selected implementations and evidence, not semantic authority.

If a stage goal or older document conflicts with this contract or an approved layer contract, the conflict must be resolved explicitly; implementations must not choose whichever wording is easiest.

## 13. Remaining integration gates

1. Implement and verify the shared Artifact Envelope, identity and canonicalization contract across all stages; the normative design is now in Pipeline_Artifact_Envelope_Identity_and_Canonicalization_Contract.md.
2. Complete the Stage 7 declaration-ID and cross-provider AST/XML correlation contract implementation mapping; the normative semantic contract is in Declaration_Identity_and_Cross_Provider_Correlation_Contract.md.
3. Pin the supported compiler/frontend/target and provider capability matrix from demonstrated field-level evidence.
4. Implement and verify the Stage 12 validator for every CIR-001..024 and PL-001..044 obligation using the producer, authoritative layer/property, applicability predicate and explicit Stage 12 verifier now recorded in the matrices.
5. Populate the versioned representation-profile/rule registries and implement the machine-actionable SAM region/coordinate/mapping contracts; the profile and deterministic rule-set semantics/structures are defined by Target_Payload_Representation_Profile_Contract.md, Target_Payload_Representation_Profile.schema.json, Target_Payload_Representation_Rule_Set_Contract.md and Target_Payload_Representation_Rule_Set.schema.json.
6. Stage_Model.json is a reusable documentation schema, not a Stage 1–13 runtime artifact. No per-stage JSON instances are required for this specification baseline; any future instances must reference and conform to the normative StageN_Specification.md contracts.
7. Documentation-level cross-stage consistency review is complete for this baseline. Any future semantic/schema/ownership change MUST rerun the same cross-document review before implementation freeze.

Resolved integration decisions:
- OD-012 is closed; its invocation-anchor and multi-root behavior is normative in Stage 1/4 and the infrastructure matrix.
- Schema 0.2.0 candidate no longer requires consumer Use Cases; feature applicability is native-feature/matrix based.
- Stage 10 NPLM projection uses layoutControlApplications; EffectiveLayoutResult remains represented by authoritative property Facts.
## 14. Normative declaration identity handoff

The authoritative declaration identity, provider-neutral type-key and cross-provider correlation rules are defined by Declaration_Identity_and_Cross_Provider_Correlation_Contract.md and Canonical_Cpp_Type_Key_Contract.md:
- Stage 4 publishes context-specific resolution candidates and declaration locators, not canonical DeclarationIds.
- Stages 5–6 publish provider observations with common source/TU/context lineage preserved.
- Stage 7 assigns DeclarationIds and owns the provider-neutral declaration graph.
- Stage 8 references DeclarationIds; Stage 9 creates separate logical identities; Stage 10 references declaration and logical IDs without replacing them.
- Stage 12 validates identity uniqueness, references, context binding and evidence correlation.

## 15. OD-012 closure

OD-012 is closed. Stage 3 remains type-only. The Generator invocation independently supplies an explicit ordered set of bounded workspace/source roots. Stage 1 records root provenance, scope, canonical paths and metadata freshness; Stage 4 searches all authorized roots, aggregates all candidates, preserves all applicable contexts and reports ambiguity without first-match precedence. No valid anchor means unresolved scope and no machine-wide scan. The Infrastructure Dependency Traceability Matrix contains the closure decision and traceability record.

## 16. Artifact identity and canonicalization

Pipeline_Artifact_Envelope_Identity_and_Canonicalization_Contract.md is normative for all Stage 1–13 artifacts. It defines sidecar envelope fields, content digests, exact numeric-safe canonical JSON serialization, identity domains, evidence lineage IDs, JSON Pointer scope and result-status propagation. Stage-specific schemas remain authoritative for payload semantics; the common envelope is not a replacement or duplicate semantic layer.
## 17. Completed documentation integration checks

The following documentation-level gates are complete for the current working baseline:
- Stage 1–13 each has a normative StageN_Specification.md and a concise StageNGoal.md summary.
- Stage 1–13 artifact flow, inputs/outputs, sidecar Artifact Envelope bindings, artifact kinds, producer stages, schema/contract references and canonical identity domains are cross-referenced.
- Stage 3 Type Input Descriptor and the common Artifact Envelope have machine-readable schemas.
- Stage 4 resolution candidates are separated from Stage 7 authoritative DeclarationId, CanonicalCppTypeKey and ResolvedTypeId ownership.
- Stage 5/6 observation lineage and Stage 7 provider-neutral declaration correlation have normative contracts.
- Stage 10's Type × exact Compilation Context identity and Layout Control Application versus Effective Layout Result separation are reflected in the intermediate model and PLD candidate.
- Stage 11 profile and deterministic rule-set structures have machine-readable schemas and normative contracts; Named Pipe remains a transport, not a representation profile.
- CIR-001..024 and PL-001..044 have explicit Stage 12 verification ownership; the CIR-to-PL crosswalk covers all 24 CIR obligations.
- OD-012 is closed in the infrastructure decision matrix and reflected in Stages 1/3/4.
- Schema 0.2.0 candidate ownership/projection contradictions have been corrected; its approval gates remain open as stated in the Schema Review.

These are documentation/structural checks, not implementation acceptance. No project build, runtime Stage 12 implementation test, full PLD fixture corpus or schema migration test is claimed.

## 18. Mandatory Single-Step publication specialization

A concrete Single Step using one or more ErrorHandlingUnits and an OperationEntryPublisher MUST provide its own Step-specific publication specialization conforming to:

Stage_Level/Stage_Step_Level/Step_Error_Handling/Single_Step_Publication_Specialization_Contract.json

This specialization is part of the Single Step contract, not an implementation note or deferred global Pipeline decision. The Step contract MUST define:

1. Concrete ReservationGrant, PublicationAcknowledgement, PublicationStatus, and PublisherContractViolation representations, plus applicable rejection/release result forms.
2. A concrete non-throwing final ownership-transfer strategy for the complete THandlingOperationResult and ErrorHandlingOperationEntry, with all fallible preparation before atomic acceptance.
3. A named Step-owned Recovery Owner and concrete recovery procedure for Publisher Contract Violation before acceptance, lost acknowledgement after acceptance, and indeterminate publication state.
4. Representation, generation authority, uniqueness scope, stability, retirement, and reuse rules for all publication-protocol identities.
5. Concrete publication-status retention, tombstone, and expiry policy.
6. An end-to-end custody trace from attempt creation through result production, publication, recovery/reconciliation, ErrorHandlerResult aggregation, and StepExecutionResult assembly.

A Step using this path is not contract-complete until these specializations are concrete and consistent. TBD, implementation-defined, or an unqualified reference to common Publisher/Reservation contracts does not satisfy this requirement.

A Step without this publication path records explicit non-applicability and its architectural reason; it does not create an artificial Publisher.

The Stage 1?13 processing sequences are not, solely by being numbered processing actions, proof of a one-to-one mapping to Single Steps or SPUs. The owning Stage/Step decomposition must identify actual Single Steps before per-Step specialization instances are authored.

