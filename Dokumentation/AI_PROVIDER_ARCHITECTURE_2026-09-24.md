# TimeLapse Pro — AI Provider Architecture

**Status:** Proposed architecture / implementation baseline  
**Date:** 2026-09-24  
**Scope:** Headend AI capabilities: Image AI, AI Search, SIEM, summarisation and future AI-assisted functions.

## Decision

TimeLapse Pro shall not couple product functions directly to Ollama, Apple Foundation Models or Gemini.

The product shall expose one authoritative AI provider layer. Product functions request capabilities from that layer; provider adapters implement those capabilities.

```text
TimeLapse product capability
        |
AI capability router / policy
        |
+-------+---------+---------+
|                 |         |
Apple             Ollama    Gemini
Foundation Models local     cloud
        |
canonical normalization / policy
        |
DB / sidecar / search / SIEM / UI
```

Apple Foundation Models is a local provider, not an Apple-specific Image AI implementation. Ollama remains a supported local provider and Gemini remains a cloud provider. No provider is removed by this decision.

## Architectural invariants

1. Image AI, AI Search, SIEM and other product capabilities MUST NOT implement provider-specific calls themselves.
2. Provider selection is configuration/policy, not business logic.
3. Provider output is an observation/model result, not authoritative product truth.
4. Canonical TimeLapse vocabulary, alarm semantics, severity, GDPR policy, validation and persistence remain controlled by TimeLapse.
5. Provider-reported confidence is provenance. It MUST NOT by itself become verified fact.
6. AI Search/SIEM tool access MUST use authorised TimeLapse service operations. Providers get no generic shell or unrestricted SQL tool.
7. RBAC and tenant isolation are enforced by TimeLapse before/during tool execution, never delegated to a prompt.
8. Deterministic SIEM rules and safety/security controls remain authoritative. AI may correlate, summarise and explain but MUST NOT silently suppress deterministic alarms.
9. Provider/model/runtime/prompt/schema provenance must be retained sufficiently to explain changed results after model or OS updates.
10. UI, CLI/API and AI consumers should use the same authoritative service/tool implementation where they perform the same operation.

## Provider capability model

The provider contract should be capability-based rather than strategy-name based. Initial capabilities:

- text generation / summarisation
- vision
- structured generation
- tool calling
- local/on-device execution
- cloud execution

Candidate adapters:

- `AppleFoundationProvider`
- `OllamaProvider`
- `GeminiProvider`

The router selects an eligible provider according to the configured product function, capability requirements and fallback policy.

## AI management

The AI management UI should evolve from one global strategy into provider policy per product function while retaining simple presets.

Example:

| Function | Primary | Fallback |
|---|---|---|
| Image analysis | Apple | Gemini |
| AI Search | Apple | Ollama |
| SIEM analysis | Apple | Ollama |
| Summarisation | Apple | Ollama |
| Document analysis | Apple | Gemini |

Possible presets include Local/Private, Local then Cloud, Apple only and Cloud. Exact names and migration from existing `technical_only/local_only/local_then_cloud/cloud_only/apple_only` require a compatibility design before DB migration.

## Apple production integration

For production Python code, use Apple's supported `apple_fm_sdk` rather than spawning `/usr/bin/fm`.

`fm` remains useful for LAB/diagnostics/manual acceptance.

Target path:

```text
TimeLapse AI worker
 -> AppleFoundationProvider
 -> apple_fm_sdk
 -> ImageAttachment / LanguageModelSession
 -> guided generation (Generable)
 -> provider observation result
 -> canonical TimeLapse normalizer/policy
```

Do not rely on prompt-generated free-form JSON when guided generation is available.

## Canonical observation boundary

A provider may return an observation such as:

```text
provider = apple_foundation
label = crane
provider_confidence = high
verification_state = unverified
```

This MUST NOT be interpreted as proof that a crane exists. Normalisation may map labels to controlled vocabulary, retain unsupported observations for review, or reject them according to policy.

For image analysis the provider-side schema should describe observations and evidence. The existing canonical TimeLapse result (scene/tags/quality/GDPR/alarm fields) is produced after validation and policy.

## Apple runtime evidence — 2026-09-24

Physical Headend POC supplied by Peter:

- macOS 27 Headend exposes `/usr/bin/fm`.
- `fm respond "Reply with exactly: OK"` returned `OK` after model availability recovered following reboot.
- Python: 3.14.7.
- `apple_fm_sdk==0.2.1` installed successfully in an isolated venv.
- `LanguageModelSession().respond(...)` returned `OK`.
- SDK exposes `ImageAttachment`, `Generable`, `GenerationSchema`, `GenerationGuide`, `GenerationOptions` and `Tool`.
- Native SDK image analysis succeeded against:
  `Kirkbi_A_S_Travbyen_Kamera_1_20260508_130015.jpg`
  (6,650,179 bytes).
- Free-text native SDK image analysis was observed at approximately 6 seconds in one run.
- Guided generation returned a typed Python `TimeLapseAnalysis` object with 25 observations in 19.25 seconds in one run.
- The typed result classified image quality as `clear_image` and `people_visible=False`.
- These latency values are individual observations, not throughput/SLA claims.

### Accuracy lesson from benchmark case #1

The Apple result was useful but not ground truth. The typed run asserted a large crane with high confidence and inferred that the high viewpoint might be from an aircraft. Those claims demonstrate that provider confidence cannot be treated as verification.

Gemini output for the same capture also differs on several concrete objects. Gemini is therefore a comparison provider, not ground truth. A benchmark must use manually reviewed annotations.

## Benchmark case #1

Use the Travbyen capture above as the first fixed benchmark case.

Compare Apple, Ollama and Gemini using:
- identical task intent and controlled vocabulary where feasible
- manually reviewed ground truth
- object/tag precision and recall
- unsupported/hallucinated observations
- scene usefulness
- quality/GDPR behaviour
- structured-output reliability
- latency
- throughput/concurrency
- CPU/GPU/RAM/thermal impact
- offline behaviour
- provenance completeness

Do not rank providers from one image. Provider defaults should be based on a representative benchmark set.

## SIEM boundary

AI may:
- correlate events
- summarise evidence
- explain likely relationships
- propose investigation steps

AI must not:
- suppress deterministic alarms solely because the model considers them benign
- set authoritative severity without TimeLapse policy
- execute generic shell commands
- bypass RBAC, tenant scope, approval, audit or safety controls

## AI Search / tools

Future provider tool calling should expose narrowly scoped TimeLapse operations, for example:

- `search_captures(...)`
- `get_device_health(...)`
- `get_capture_status(...)`
- `get_security_events(...)`
- `get_update_status(...)`
- `get_network_status(...)`

These must call the same authoritative services used by UI/CLI/API rather than reimplementing operations for AI.

## Provenance

At minimum retain where available:

- provider/engine
- model/model profile/version
- OS/runtime version where material (especially Apple system model)
- prompt version
- schema version
- provider options (for example temperature/sampling policy)
- analysis timestamp
- latency
- source capability/function
- provider confidence separately from TimeLapse verification state

## PR #258 direction

PR #258 began as an Apple image provider using the `fm` CLI and free-form JSON parsing. That prototype established a useful integration seam but is no longer the desired production architecture.

Before merge, replace/rework the CLI implementation around:
- generic provider contract/capability routing
- `apple_fm_sdk` for Apple production integration
- guided typed generation for structured Apple results
- shared canonical normalisation/policy
- provider provenance
- compatibility/migration for current AI strategy configuration
- tests proving product functions do not create provider-specific execution paths

Do not remove Ollama. Do not change the global production default merely because the POC succeeded.

## Acceptance gates

The provider architecture is not complete until:

1. Apple SDK dependency/install is reproducible in the Headend deployment/restore path.
2. Apple availability failure is handled without blocking unrelated Headend functions.
3. Image AI can select Apple through the normal AI management path and persist canonical + provider provenance.
4. Existing Ollama and Gemini behaviour remains supported.
5. At least AI Search and SIEM can consume the generic provider text/structured capability without Apple-specific business logic.
6. Tenant/RBAC tests cover AI Search/tool paths.
7. Deterministic SIEM alarms remain independent of AI judgement.
8. Benchmark evidence is retained and provider defaults are not selected from a single capture.
9. Headend resource/concurrency behaviour is measured before production-scale enablement.
10. GRC records requirements, implementation evidence, limitations and open findings separately.
