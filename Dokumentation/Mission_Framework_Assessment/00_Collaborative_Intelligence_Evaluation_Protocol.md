# Collaborative Intelligence Evaluation Protocol

**Status:** Proposed  
**Date:** 2026-07-22  
**Repository:** `froekjaer/timelapse-pro`

---

## Purpose

This document defines a reproducible evaluation method for applying the Mission Framework and its Collaborative Intelligence approach to both brown-field and green-field projects.

The protocol has two objectives:

1. Improve the project under review.
2. Learn how different AI systems contribute, differ, complement one another, and introduce bias.

The work must therefore preserve both the consolidated conclusions and the original AI outputs.

---

## Research Questions

The evaluation should answer the following questions:

1. Can the Mission Framework be used consistently by multiple AI systems?
2. Which AI systems are strongest in which parts of the task?
3. Which recurring optimisation preferences or biases can be observed?
4. How should conflicting or overlapping feedback be merged?
5. Can the process produce an actionable transformation plan for an existing system?
6. Can the same framework guide a complex green-field project from the beginning?

---

## Guiding Principle

> The objective is not to determine which AI is best. The objective is to understand how their different capabilities can be orchestrated into a stronger collective result.

---

# Evaluation Programme

## Stage 1 — Mission Framework Review

All participating AI systems review the Mission Framework itself.

The review is performed in two phases.

### Phase 1A — Independent Review

Each AI receives the same:

- framework version
- review instruction
- source material
- success criteria
- evidence requirements
- output template

Each AI works independently and must not see the other systems' conclusions.

The review should assess:

- internal coherence
- clarity of concepts
- completeness
- practical applicability
- reproducibility
- governance model
- evidence model
- human and AI usability
- ambiguity
- missing principles
- contradictions

### Phase 1B — Consolidation and Revision

All independent reviews are compared.

The framework is revised using argumentation and evidence rather than majority voting.

Each accepted change should record:

- source observation
- supporting evidence
- dissenting views
- final decision
- rationale

The result becomes an agreed candidate version.

---

## Stage 2 — Framework Freeze

A specific version of the Mission Framework is frozen for the brown-field evaluation.

The frozen version must include:

- version identifier
- commit SHA
- review instruction version
- scoring model version
- output schema version

The framework must not be changed during the TimeLapse Pro review.

Any weaknesses discovered during the review are recorded separately for a later framework revision.

---

## Stage 3 — Brown-Field Review of TimeLapse Pro

All participating AI systems, including ChatGPT, perform an independent review of TimeLapse Pro under the frozen Mission Framework.

All AI systems receive the same:

- repository snapshot
- commit SHA
- framework version
- review prompt
- scope
- constraints
- output template
- evidence rules

The central transformation question is:

> How should TimeLapse Pro evolve from a domain-specific timelapse system into a modular edge platform with a clearly separated Platform Core and TimeLapse mission package?

### Required Review Areas

Each review must assess:

- mission and purpose
- architecture
- code structure
- platform boundaries
- TimeLapse-specific logic
- shared capabilities
- configuration
- scheduling
- storage
- logging
- health monitoring
- security
- deployment
- hardware abstraction
- AI runtime
- testability
- observability
- documentation
- governance
- decision traceability
- collaborative intelligence readiness
- Codex readiness

### Required Output Per Finding

Each finding should contain:

1. Finding identifier
2. Title
3. Observation
4. Evidence
5. Impact
6. Confidence
7. Proposed target state
8. Recommended action
9. Dependencies
10. Risk
11. Acceptance criteria
12. Suggested Codex implementation sprint

---

## Stage 4 — AI Capability and Bias Analysis

The individual reviews are analysed as a dataset.

The purpose is to identify both model capability and recurring model preference.

The term **Natural Optimisation Preference** is preferred over bias where the behaviour is a legitimate strength rather than an error.

### Evaluation Dimensions

Each AI response should be evaluated for:

- evidence quality
- architectural depth
- implementation depth
- governance awareness
- security awareness
- legal and ethical awareness
- documentation quality
- novelty
- actionability
- consistency
- completeness
- precision
- hallucination rate
- uncertainty handling
- cognitive accessibility
- ability to distinguish Platform Core from mission logic

### Comparative Measures

#### Consensus Score

How many AI systems independently identified the same issue?

#### Novelty Score

Was the finding unique, and did it add material value?

#### Evidence Score

Was the finding grounded in verifiable repository evidence?

#### Actionability Score

Can the recommendation be translated into a concrete implementation task?

#### Architectural Value

Would implementation measurably improve the target architecture?

#### Hallucination Rate

How many claims could not be verified against the repository or supplied evidence?

#### Confidence Calibration

Did the model's stated confidence correspond to the quality of its evidence?

---

## Stage 5 — Feedback Merge Method

The final result must not be produced by simple majority voting.

Feedback is merged using:

1. Evidence strength
2. Relevance to the frozen framework
3. Architectural value
4. Implementation feasibility
5. Risk reduction
6. Long-term maintainability
7. Agreement across independent reviewers
8. Unique insight from minority findings

Conflicting recommendations must be recorded explicitly.

For each conflict, the consolidation should document:

- competing recommendations
- evidence for each
- likely optimisation preference behind each
- trade-offs
- selected decision
- reason for selection

---

## Stage 6 — TimeLapse Pro Transformation Plan

The consolidated brown-field result becomes an actionable transformation plan.

The plan should separate:

### Platform Core

Candidate shared capabilities include:

- configuration
- identity
- security
- scheduling
- logging
- telemetry
- health monitoring
- storage abstractions
- messaging
- deployment
- update management
- hardware abstraction
- AI runtime
- policy enforcement
- audit trail
- API services

### TimeLapse Mission Package

Candidate domain-specific capabilities include:

- camera capture
- image acquisition policies
- exposure and focus workflows
- image quality analysis
- timelapse sequencing
- image retention rules
- visual inspection logic
- timelapse-specific user experience

### Transformation Sequence

The transformation should proceed incrementally:

1. Map current dependencies.
2. Define target boundaries.
3. Introduce interfaces before moving implementations.
4. Add boundary tests.
5. Extract one shared capability at a time.
6. Preserve behaviour through regression tests.
7. Update documentation and ADRs with each change.
8. Validate that TimeLapse runs as a consumer of Platform Core.

---

## Stage 7 — Codex Implementation Programme

Codex acts as an implementation partner, not as the final architectural authority.

Each Codex sprint must contain:

- objective
- repository scope
- files in scope
- files out of scope
- architectural constraint
- dependencies
- implementation steps
- tests
- acceptance criteria
- rollback approach
- documentation updates

No large-scale refactoring should begin before the review, consolidation, and target architecture are accepted.

---

## Stage 8 — Brown-Field Method Documentation

The TimeLapse Pro exercise becomes a documented brown-field reference case for Mission Framework.

The case study should preserve:

- original project state
- frozen framework version
- review prompts
- raw AI responses
- comparative analysis
- consolidation decisions
- transformation plan
- implementation commits
- rejected recommendations
- lessons learned
- framework changes proposed after completion

This material should allow another team to reproduce the method.

---

## Stage 9 — Green-Field Evaluation

After the brown-field evaluation, the framework is applied to a complex green-field project:

> A governed platform for background checks and due diligence of political candidates.

The green-field project is suitable because it combines:

- OSINT
- privacy
- GDPR
- EU AI regulation
- ethics
- security
- evidence handling
- human review
- bias management
- governance
- auditability
- reporting
- retention and deletion

The same AI systems should participate under a controlled protocol.

The green-field evaluation should determine whether the framework helps the team make better architectural and governance decisions before implementation begins.

---

## Stage 10 — Final Evaluation

The final evaluation compares the brown-field and green-field exercises.

It should answer:

- Which framework elements worked in both contexts?
- Which elements were only useful in brown-field transformation?
- Which elements were only useful in green-field design?
- Which AI systems produced the most valuable insights in each domain?
- Which optimisation preferences were stable across both projects?
- Which merge strategies produced the strongest outcomes?
- Which framework elements require revision?
- Can the process be reproduced by an independent team?

---

# Evidence Preservation

All raw AI outputs must be preserved unchanged.

Recommended structure:

```text
Dokumentation/
└── Mission_Framework_Assessment/
    ├── 00_Collaborative_Intelligence_Evaluation_Protocol.md
    ├── Framework_Review/
    │   ├── Raw/
    │   ├── Comparative_Analysis/
    │   └── Consolidated/
    ├── Brown_Field_TimeLapse_Pro/
    │   ├── Raw/
    │   ├── Comparative_Analysis/
    │   ├── Consolidated/
    │   └── Transformation_Plan/
    └── Green_Field_Candidate_Due_Diligence/
        ├── Raw/
        ├── Comparative_Analysis/
        ├── Consolidated/
        └── Architecture/
```

Each raw response should record:

- AI system and version
- date and time
- prompt version
- framework version
- repository commit SHA
- supplied context
- tool access
- response content
- known limitations

---

# Experimental Controls

To make comparisons meaningful:

- prompts must be version-controlled
- repository state must be frozen
- each AI must receive the same primary material
- tool access differences must be recorded
- independent reviews must remain isolated
- no model should see another model's output before submitting its own
- raw output must not be edited
- consolidation must preserve dissent
- all factual claims must be verifiable

---

# Success Criteria

The evaluation is successful when it produces:

1. An acceptable reviewed version of Mission Framework.
2. A reproducible multi-AI review protocol.
3. A comparative model capability analysis.
4. A documented understanding of model optimisation preferences and bias.
5. A merged and evidence-based review of TimeLapse Pro.
6. A target architecture separating Platform Core and TimeLapse.
7. A sequenced Codex implementation plan.
8. A brown-field Mission Framework case study.
9. A green-field Mission Framework case study.
10. A final evaluation identifying what should change in the framework.

---

# Governance

The human project owner retains final accountability for:

- scope
- ethical decisions
- architectural acceptance
- risk acceptance
- release decisions

AI systems provide analysis, alternatives, evidence, and implementation assistance.

They do not replace accountable human judgement.

---

# Review Trigger

This protocol should be reviewed before:

- inviting the first external AI system to review the framework
- freezing the framework version
- starting the TimeLapse Pro brown-field review
- starting the green-field project

Any protocol changes after an evaluation has begun must create a new protocol version rather than silently modifying the active one.
