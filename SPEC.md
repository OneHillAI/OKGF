# Open Knowledge and Governance Format (OKGF) v0.1

> **Status:** draft v0.1. **License:** Apache-2.0. **Base:** [Open Knowledge Format
> (OKF)](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf) v0.1.
> **Origin:** Andrej Karpathy's [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).
>
> OKGF is a strict **superset** of OKF. An OKGF bundle is a conformant OKF bundle; an OKF-only tool
> reads it correctly and ignores the governance fields. OKGF adds the layer OKF deliberately leaves
> out: **lifecycle, provenance, and trust** for organizational knowledge.

## Why

OKF makes knowledge portable: markdown + YAML frontmatter, human- and agent-readable, diffable in git,
no central registry. It stops at the *format* and explicitly defines no review, approval, lifecycle, or
trust model. Organizations need exactly those: knowledge that is **scoped** (mine vs the team's vs the
org's), **reviewed** before it becomes authoritative, **rated** for downstream use, **attributed** to
its sources, and optionally **signed** so a promotion can be verified. OKGF adds them as reserved
extension fields, so you keep OKF's portability *and* get governance, with no fork.

## Relationship to OKF

- Everything in [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog) applies unchanged:
  markdown files with YAML frontmatter; a non-empty `type` is the only required field; `title`,
  `description`, `resource`, `tags`, `timestamp` are recommended; a Concept ID is the file path minus
  `.md`; links are untyped directed edges; `index.md` and `log.md` are reserved; a bundle declares
  `okf_version` in its root `index.md`.
- OKGF only **adds** frontmatter keys under the reserved `x-okgf-*` namespace. OKF requires
  consumers to **preserve unknown keys**, so an OKGF page round-trips through any OKF tool intact.
- These governance conventions are offered back to the OKF project as proposed extensions, and OKGF is
  submitted to OKF as a known governance superset (see the project README).

## Governance extensions

All optional; all live in page frontmatter. A page that omits them is still valid OKGF (ungoverned).

| Key | Type | Values | Meaning |
| --- | --- | --- | --- |
| `x-okgf-scope` | string | `personal` \| `team` \| `org` | The knowledge plane the page belongs to. `org` is the shared, authoritative set. |
| `x-okgf-review` | string | `draft` \| `proposed` \| `approved` | Lifecycle state (see below). A page is authoritative for its scope only when `approved`. |
| `x-okgf-tier` | string | `bronze` \| `silver` \| `gold` | Quality rating for downstream use (e.g. training-data selection). `gold` is curated/verified. |
| `x-okgf-sources` | list of string (URI) | - | Provenance: where the knowledge came from. |
| `x-okgf-signature` | string (base64) | - | An Ed25519 signature over the page, asserting an approved promotion (see Trust). |

### Lifecycle (`x-okgf-review`)

```
draft ──propose──▶ proposed ──approve──▶ approved
                       │
                       └──reject──▶ draft
```

- **draft** - authored or machine-generated; not yet submitted.
- **proposed** - submitted to a reviewer; awaiting a decision. Promotion across scopes (e.g.
  `team` -> `org`) MUST pass through `proposed`.
- **approved** - a human reviewer accepted it; it is now authoritative for its `x-okgf-scope`.

A consumer SHOULD treat only `approved` pages as authoritative for the org, and MAY surface
`draft`/`proposed` pages as candidates. State transitions belong in the bundle's `log.md`.

### Trust (`x-okgf-signature`)

A promotion to a shared scope MAY be signed. The signature is base64 Ed25519 over the UTF-8 bytes of:

```
<type>\n<title>\n<x-okgf-scope>\n<x-okgf-review>\n<body>
```

(the canonical page minus the signature field itself). The verifying public key is distributed out of
band (e.g. an org's published key). An unsigned page is valid; a present-but-invalid signature MUST be
treated as untrusted. This is the verifiable form of "this page was approved into the org by a holder
of the org key."

## Bundle layout

A flat OKGF bundle is:

```
index.md            # root index; frontmatter declares okf_version; lists pages as /<slug> links
log.md              # append-only, ISO-8601-dated change history
PRINCIPLES.md       # optional: standing principles for the scope
<slug>.md           # one concept per file; Concept ID = <slug>; [[slug]] links resolve to /<slug>
```

Nested directories are permitted (Concept ID = path), per OKF; the flat layout is the common profile.

## Example page

```markdown
---
type: Concept
title: Billing model
description: We bill monthly per seat.
timestamp: '2026-06-28T11:55:31+00:00'
x-okgf-scope: org
x-okgf-review: approved
x-okgf-tier: gold
x-okgf-sources:
- https://stripe.com/docs
---
# Billing model

We bill monthly per seat.

## Related
[invoices](/invoices)
```

## Conformance

An OKGF bundle:

1. is a conformant **OKF** bundle (valid YAML frontmatter in every non-reserved `.md`; non-empty
   `type`; reserved `index.md`/`log.md` structure); and
2. wherever an `x-okgf-*` field is present, its value conforms to the table above.

Consumers MUST tolerate missing governance fields and MUST preserve unrecognized fields.

## Implementation

Reference validator: the [`okgf/`](okgf/) package in this repository, installable as the `okgf`
command (see [`docs/INSTALL.md`](docs/INSTALL.md)), checks single-page and whole-bundle conformance,
including optional Ed25519 signature verification. This **specification** is Apache-2.0, so any tool
may implement OKGF freely.
