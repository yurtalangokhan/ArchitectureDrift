# Multi-Evidence Architecture Conformance

Research prototype developed for the ICSA 2027 Research Track.

## Research Scope

The framework evaluates architecture conformance using three evidence
configurations:

1. Non-Runtime Evidence
2. Runtime Evidence
3. Fused Evidence

## Case Systems

- OpenTelemetry Astronomy Shop
- .NET eShop
- TeaStore

## Experimental Strategy

The experiment uses controlled architectural mutations and a
Baseline -> Mutant Graph Delta strategy.

Longitudinal commit or graph evolution is outside the scope of the study.

## Canonical Architecture Graph

Supported node types:

- SERVICE
- DATASTORE
- BROKER
- GATEWAY
- REGISTRY
- EXTERNAL

Supported relation types:

- CALLS
- READS_FROM
- WRITES_TO
- PUBLISHES_TO
- SUBSCRIBES_TO
- ROUTES_TO
- DISCOVERS_VIA
- EXPOSES_TO

## Architecture Contract Types

- FORBIDDEN_RELATION
- REQUIRED_RELATION
- RESOURCE_OWNERSHIP
- EXPOSURE
- MEDIATION
- COMMUNICATION_MODE

## Ground Truth

Ground truth is represented by:

- architecture contracts
- mutation oracle definitions

## Initial Vertical Slice

Astronomy Shop mutation:

AS-M01

checkout -> recommendation unexpected connector mutation.
