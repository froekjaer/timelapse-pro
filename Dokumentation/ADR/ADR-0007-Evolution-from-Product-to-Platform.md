# ADR-0007
# Evolution from Product to Platform

**Status:** Proposed
**Date:** 2026-07-22

## Context

TimeLapse Pro started as a long-term timelapse imaging system. During development it has become clear that the underlying architecture is applicable to many edge-computing scenarios including industrial monitoring, waterworks, maritime systems, SDR/radio applications, environmental sensing and other mission-specific workloads.

The common capabilities belong in a reusable platform. Timelapse should become the first reference implementation rather than define the platform forever.

## Decision

The long-term architectural direction is to evolve from a product into a modular edge platform.

The platform will provide shared capabilities such as identity, security, configuration, scheduling, logging, telemetry, AI runtime, storage, deployment, messaging and hardware abstraction.

Mission-specific functionality will be implemented as independent packages.

## Vision

Mission Framework
→ Knowledge Architecture
→ Platform Core
→ Mission Packages

Initial Mission Packages:
- TimeLapse
- WaterWorks
- Maritime
- Radio
- Inspection
- Environmental Monitoring

## Naming

No platform name is decided yet.

"TimeLapse Pro" is expected to remain the first reference implementation until the platform identity has matured.

## Review Trigger

Revisit this ADR when a second Mission Package enters active development or the majority of functionality is shared platform code.
