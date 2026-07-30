# OKGF Governance

OKGF is an open specification stewarded by the **OneHill Foundation**. This document describes how the
spec is maintained and versioned. It governs *this repository*; it is separate from the governance model
that OKGF the format describes (scope / review / trust for knowledge bundles).

## Steward

The OneHill Foundation maintains the specification, publishes releases, and holds the trademark and
copyright for the OKGF name and text. The Foundation's role is to keep OKGF open, stable, and faithful to
its goal: portable knowledge with portable trust, built as a clean superset of OKF.

## Principles

- **Superset, not fork.** Every version of OKGF remains a strict superset of a published OKF version. A
  change that would break OKF conformance is out of scope.
- **Additive and reserved.** Governance lives in the reserved namespace. Existing fields are
  not repurposed; new capability is added, not mutated, so older bundles stay valid.
- **Optional by default.** Governance fields are optional. An ungoverned bundle is always conformant.
- **Implementable and testable.** A normative change ships with the conformance definition and validator
  updates that let anyone check it.

## Versioning

OKGF uses a `MAJOR.MINOR` spec version (currently `0.1`), recorded in tagged releases and stamped by a
bundle's `okf_version` in its root `index.md`.

- **Minor** version: backwards-compatible additions (new optional field, new allowed value, clarified
  wording). Existing conformant bundles stay conformant.
- **Major** version: a change that could make a previously conformant bundle non-conformant. Avoided
  wherever possible; requires a migration note.

While OKGF is pre-1.0, minor versions may still refine field semantics; changes are announced on tagged
releases.

## Decision process

- **Small changes** (wording, examples, validator fixes) are reviewed and merged by a maintainer via pull
  request.
- **Normative changes** (fields, values, lifecycle, signature format) start as an issue for discussion,
  then a PR. The Foundation is the final arbiter and is responsible for keeping the spec coherent and the
  superset relationship intact.

## Relationship to implementations

Implementations are licensed and governed
independently. This repo defines the format they target; it does not govern their code.
