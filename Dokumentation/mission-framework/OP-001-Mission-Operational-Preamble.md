> **Vendored copy** — mirrored verbatim from `github.com/froekjaer/mission-framework`
> (`docs/operational/OP-001-Mission-Operational-Preamble.md`, commit `2db8c2ba`,
> 2026-07-22) into this repository on 2026-08-17, per the framework's own
> continuity principle (§1.3/§1.4 below): "No human, AI model, connector,
> conversation or runtime session shall be the sole carrier of mission-critical
> knowledge or state." TimeLapse Pro is named as a reference mission for this
> framework's continuity/verification proposition (see mission-framework's
> `README.md` and `MISSION.md`). If this copy and the upstream repo ever
> disagree, treat the disagreement itself as a Framework Finding (see
> `docs/FRAMEWORK_FINDINGS.md` upstream) rather than silently picking one.

# OP-001 — Mission Operational Preamble (MOP)

**Status:** Canonical Operational Procedure  
**Version:** 1.0  
**Effective date:** 2026-07-22  
**Category:** Operational Protocol  
**Applies to:** All AI-assisted engineering activities within Mission Framework

## 1. Purpose

Mission Framework defines principles, architecture and governance for evidence-driven engineering.

Experience has shown that principles alone are insufficient. Long-running AI-assisted engineering projects are vulnerable to gradual operational drift, including:

- forgotten decisions;
- duplicated or independently reinvented concepts;
- inconsistent terminology;
- diverging repository structures;
- recreated artefacts;
- broken dependencies;
- incorrect assumptions becoming operational truth.

These failures can accumulate gradually and remain undetected until significant inconsistency has developed.

This Operational Preamble establishes a mandatory procedure that shall be executed before substantive engineering activity. Its purpose is to preserve continuity, architectural integrity, traceability and evidence-based decision-making.

## 2. Scope

This protocol applies whenever an AI or human participant performs work involving:

- architecture;
- engineering;
- documentation;
- governance;
- repository maintenance;
- implementation;
- research;
- reviews;
- release management;
- canonical project identifiers or dependencies.

Routine conversational exchanges that do not affect operational or canonical state are outside scope.

## 3. Governing Maxim

> **Never operate from memory when an authoritative source is available.**

Memory may generate hypotheses. Memory is not an authoritative operational source.

## 4. Bootstrap of Canonical Artefacts

The first canonical version of an artefact is a special case.

Before an artefact exists in an authoritative repository, the explicitly approved engineering conversation or source material that produced it may temporarily serve as the bootstrap source.

Bootstrap authority shall only be used when:

1. the intended artefact does not yet exist in the authoritative repository;
2. the approved source is available in full;
3. the destination repository, branch and path have been verified;
4. the content is transferred without silent reconstruction or unapproved alteration; and
5. the resulting commit is verified.

Upon successful commit:

- the repository version becomes the sole authoritative operational source;
- the conversation or temporary source ceases to be authoritative;
- all subsequent modifications shall begin from the repository version;
- normal change governance and verification shall apply.

If the approved bootstrap source cannot be recovered exactly, creation shall stop rather than rely on memory.

## 5. Mandatory Operational Procedure

### Step 0 — Classify the Task

Determine the nature of the requested work, for example:

- Research
- Engineering
- Architecture
- Documentation
- Governance
- Review
- Implementation
- Repository Maintenance

The classification determines which evidence and authoritative sources are required.

### Step 1 — Establish Operational State

Determine whether the task depends on existing operational artefacts, including:

- GitHub repositories;
- canonical documents;
- Architecture Decision Records;
- Framework Findings;
- repository structure;
- existing implementations;
- existing governance;
- prior approved decisions.

If such artefacts exist, identify and inspect the authoritative source before continuing.

### Step 2 — Verify Operational Identifiers

Before using an operational identifier, determine its provenance.

This includes:

- repository names;
- branch names;
- tags;
- filenames and paths;
- URLs;
- document titles;
- ADR identifiers;
- Framework Finding identifiers;
- issue and pull-request numbers;
- release versions;
- service, host, namespace and endpoint names.

Each identifier shall be classified as:

#### VERIFIED

Obtained directly from an authoritative operational source.

A verified identifier may be used operationally.

#### DERIVED

Inferred from verified information through explicit reasoning.

A derived identifier or conclusion may be used only when clearly identified as derived and when the derivation is reproducible.

#### ASSUMED

Obtained from memory, probability or unverified inference.

An assumed identifier shall not be used as the basis for an operational action.

### Step 3 — Recover Existing Context

Determine whether relevant decisions, structures or artefacts already exist.

Recover them from authoritative sources. Do not reconstruct project history solely from conversation memory, model memory or recollection.

When context cannot be recovered, state the gap and stop any action that could overwrite, duplicate or contradict canonical state.

### Step 4 — Review Architectural Consistency

Before introducing change, determine whether it would:

- duplicate existing work;
- rename an existing concept;
- create a parallel structure;
- contradict established principles or decisions;
- weaken continuity;
- introduce incompatible terminology;
- separate dependent artefacts.

Resolve material conflicts before proceeding.

### Step 5 — Search Before Create

Before creating a new:

- document;
- folder;
- repository structure;
- principle;
- protocol;
- term;
- architecture;
- template;
- identifier;

verify that an equivalent or authoritative predecessor does not already exist.

Creation is the final option, not the default first action.

### Step 6 — Assess Dependencies

Identify all artefacts potentially affected by the requested change.

Dependencies may include:

- documentation;
- READMEs and indexes;
- governance;
- review procedures;
- architecture;
- implementation;
- references and cross-links;
- automation;
- related repositories;
- releases and version metadata.

Assess the complete relevant dependency set rather than only the immediately requested artefact.

### Step 7 — Check Cross-Repository Consistency

When multiple repositories participate in the same mission or framework:

- compare their structures;
- compare terminology;
- compare governance;
- compare documentation and references;
- identify intentional and accidental divergence.

Do not assume repositories remain synchronized.

### Step 8 — Execute

Only after completing Steps 0–7 shall implementation begin.

Execution shall use verified identifiers and the recovered authoritative state.

### Step 9 — Verify the Outcome

After implementation, confirm that:

- the requested objective was achieved;
- continuity was preserved;
- affected dependencies were updated;
- no orphan or duplicate artefacts were created;
- references remain valid;
- repository and architectural integrity are maintained;
- the resulting operational state can be independently verified.

A write operation is not complete merely because it returned success. The resulting state shall be read back or otherwise independently confirmed where tooling permits.

## 6. Operational Knowledge States

### 6.1 Verified Operational State

Information obtained directly from authoritative operational artefacts.

This state is suitable for engineering decisions and execution.

### 6.2 Derived Operational State

Information inferred reproducibly from verified operational state.

This state may support analysis but shall not be misrepresented as directly observed fact.

### 6.3 Assumed State

Information originating from memory, likelihood or inference without verification.

Assumed state shall remain a hypothesis until verified and shall never silently become operational truth.

## 7. Mandatory Engineering Rules

1. **Authoritative operational state has priority over memory.**
2. **Verify identifiers before using them.**
3. **Search before creating.**
4. **Verify before modifying.**
5. **Recover before reconstructing.**
6. **Preserve historical evidence and continuity.**
7. **Protect architectural and cross-repository consistency.**
8. **Treat assumptions as hypotheses until verified.**
9. **Verify outcomes after execution.**
10. **Stop rather than invent missing operational facts.**

## 8. Visible Preamble Record

For substantive Mission Framework work, the participant should provide a concise visible record showing that the preamble has been performed, for example:

```text
Mission Operational Preamble

✓ Task classified
✓ Authoritative source identified
✓ Operational identifiers verified
✓ Existing context recovered
✓ Architectural consistency checked
✓ Search-before-create completed
✓ Dependencies assessed
✓ Ready to execute
```

If a step cannot be completed, it shall be marked as blocked or unverified rather than shown as complete.

The visible record is an execution trace, not a substitute for performing the procedure.

## 9. Failure and Stop Conditions

Execution shall stop when any of the following is true and cannot be resolved safely:

- an essential repository, branch, path or identifier is unverified;
- the authoritative source cannot be accessed;
- conflicting canonical sources exist;
- a requested action risks overwriting or losing historical evidence;
- an existing equivalent artefact may already exist but cannot be checked;
- dependencies cannot be identified sufficiently to avoid uncontrolled divergence;
- the requested result cannot be verified after execution.

The participant shall state what is known, what is missing and what evidence is required to continue.

## 10. Empirical Motivation

This protocol was introduced following repeated observations during long-running AI-assisted engineering work.

Observed failure modes included:

- incorrect repository identifiers generated from memory;
- incorrect identifiers propagated into subsequent work orders;
- duplicated concepts and independently recreated structures;
- forgotten architectural decisions;
- inconsistent terminology;
- gradual divergence between repositories;
- loss of continuity across extended conversations and AI sessions;
- claims that an artefact had been written when it existed only in conversation.

These observations demonstrated that conversational continuity and memory are insufficient foundations for operational engineering state.

## 11. Relationship to Mission Framework

This document defines how Mission Framework principles shall be applied operationally.

Mission Framework principles describe what the framework holds to be important. Operational Protocols prescribe how participants shall work to preserve those principles during execution.

Where this protocol conflicts with an unverified recollection or informal instruction, the verified canonical state takes precedence unless an explicitly authorised change is being made.

## 12. Success Criterion

A participant following this protocol should be able to join a mission at any point and produce work that is:

- consistent with prior verified engineering decisions;
- based on authoritative operational state;
- traceable to evidence;
- reproducible by an independent participant;
- resistant to gradual architectural drift;
- recoverable across AI sessions, people and tools.

## 13. Closing Principle

> **Memory inspires. Evidence governs.**

Every operational engineering decision shall ultimately be traceable to verified evidence rather than recollection.
