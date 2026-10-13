# Generic Finding candidate — control-plane state vs. actual object/runtime outcome

**Status:** DRAFT CANDIDATE — for ChatGPT/Peter review. Not submitted upstream. Not a Mission Framework edit. Not itself a claim that this is accepted as a Finding — it is TimeLapse-side evidence prepared per Phase G of the Wave 2 closure mandate (2026-09-16), assessing whether a recurring pattern justifies a Mission Framework Finding candidate.

## The pattern

A status/control object (a database row, a metadata file, a deploy record) can assert a successful/verified/current state without that assertion being bound to — or periodically re-validated against — the actual current state of the object or runtime outcome it purports to describe. Once the control-plane record and the reality it describes diverge, the record can continue asserting success indefinitely, because nothing re-checks the *actual* object — only the record *about* the object is consulted.

## Two independent TimeLapse observations

1. **OP-001 cache metadata (this wave, F1, z.ai adversarial finding):** `OP-001.provenance.json` could report `last_check_result: VERIFIED` — and this wave's original implementation would happily repeat that claim — while the cached file's actual on-disk bytes had been manipulated. The freshness check compared canonical's HEAD against a *recorded revision string*, never the cached file's own bytes. Root cause: "VERIFIED" was defined entirely in terms of a remote comparison, never bound to the local object it was supposed to describe. Fixed by adding a content digest checked against actual bytes before any freshness claim is made.

2. **Edge1 deployment state (earlier, §16.9's origin — Edge1 canary incident):** a device's CMDB/deploy record could report `deployed` while the relevant runtime service (`timelapse-totp.service`) was crash-looping (~13,000 restarts over ~19 hours) due to a `pydantic`/`pydantic_core` version mismatch introduced by the same deployment. The deploy record's "success" was based on the deployment *action* completing, never on the deployed *capability* being observed healthy afterward.

## Distinguishing four things (do not collapse them)

- **Control-plane state:** what a record/database/metadata field *asserts* (`VERIFIED`, `deployed`).
- **Evidence:** what was actually checked, when, and against what — the basis (or absence of one) for the assertion.
- **Consumed object:** the actual bytes/artifact/service that will actually be used or executed.
- **Runtime outcome:** what actually happens when the consumed object is used — does the service respond, does the content match, does the capability work.

Both TimeLapse cases share the same failure shape: the control-plane state and the evidence were real and honestly recorded *at the time they were established*, but nothing re-bound the assertion to the consumed object/runtime outcome at the moment the assertion was later relied upon.

## Relationship to existing Mission Framework / TimeLapse principles

This is **not** a new, unrelated discovery — it is the same generic failure class TimeLapse's own §16.9 ("Deployment-accept: observed runtime health is part of the success criterion") was written to address, now independently reproduced in a second, unrelated domain (local content integrity rather than deployment health). §16.9 itself already generalizes past its Edge1 origin ("a general rule, not incident-specific" — its own text says so), but was worded specifically around *deployment/runtime health*. The OP-001 case shows the same underlying principle — a status claim must be bound to the actual object it describes, not just to the action that was supposed to produce it — applies to **content/artifact integrity claims**, not only to deployment/runtime-health claims. This also connects to OP-001's own "Governing Maxim" ("Never operate from memory when an authoritative source is available") and its Operational Knowledge States (Verified/Derived/Assumed) — a VERIFIED claim that isn't actually bound to the object it describes is, on inspection, closer to an Assumed one.

**Two independent instances of the same generic pattern, in two unrelated domains, is meaningful supporting evidence — not proof the pattern is universal, and not license to over-generalize from two data points.**

## Explicit proportionality — what this is NOT proposing

- **Not** a requirement that every status field perform continuous end-to-end re-verification. Cost/risk-proportionate checking (as OP-001's own STALE/UNKNOWN/CORRUPTED model and §16.9's runtime-health gate already do) remains the right shape — check when it matters (before consequential reliance), not always.
- **Not** a claim that recording control-plane state is itself wrong — it is necessary and useful. The gap is specifically when a *consequential* decision relies on that state *as if it were still bound to the actual object*, without that binding being re-established or the gap being made visible.
- **Not** a claim that every existing status/control record in Mission Framework or its downstream implementations is untrustworthy — only that the binding between assertion and object should be an explicit, checkable property for *consequential* claims, not assumed.

## Classification: supporting evidence for an existing principle, with a modest broadening

This is best classified as **supporting evidence strengthening §16.9's underlying principle** (proving it generalizes beyond its Edge1 origin, across independent domains), **plus a modest broadening of its stated scope**: §16.9 as currently worded addresses deployment/runtime health specifically; the generic formulation above (control-plane state vs. consumed object/runtime outcome) also covers content/artifact integrity claims, which §16.9's literal text does not currently name. This is not "new normative insight" invented from nothing — it is the same principle, observed to apply more broadly than its original single-incident formulation suggested.

## Recommendation

Candidate for eventual inclusion in a future Framework Finding submission (see `FF-TLP-0001`'s own still-open recommendation that §16 itself be submitted as TimeLapse's first real Framework Finding — this generic pattern would strengthen that submission's evidence, not replace it). **Not submitted upstream by this document.** No Mission Framework file is touched. This is TimeLapse-side evidence only, for ChatGPT/Peter to review and decide whether/when to act on.
