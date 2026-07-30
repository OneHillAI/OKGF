# OKGF Conformance

This document defines what it means for a page or bundle to conform to **OKGF v0.1**, and how to check
it with the reference validator in [`tools/okgf_validate.py`](tools/okgf_validate.py). The normative rules
live in [`SPEC.md`](SPEC.md); this file restates them as a checklist and describes the tooling.

## What conformance means

OKGF is a strict superset of [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog). A conformant
OKGF artifact is therefore a conformant OKF artifact that additionally respects the governance rules.

### A conformant page

1. Has a `---`-delimited YAML frontmatter block that parses as a YAML mapping.
2. Declares a non-empty `type` (the only OKF-required field).
3. For every governance field present, the value is within range:
   - `x-okgf-scope` is one of `personal`, `team`, `org`
   - `x-okgf-review` is one of `draft`, `proposed`, `approved`
   - `x-okgf-tier` is one of `bronze`, `silver`, `gold`
   - `x-okgf-sources` is a list of strings (URIs)
   - `x-okgf-signature` is base64 that decodes to a 64-byte Ed25519 signature
4. Preserves any unrecognized frontmatter keys (they are never an error).

Governance fields are **optional**. A page that omits all of them is a conformant (ungoverned) OKGF page.

### A conformant bundle

1. Contains a root `index.md` whose frontmatter declares `okf_version`.
2. `log.md`, `index.md`, `principles.md`, and `schema.md` are reserved and are not validated as content
   pages.
3. Every other `.md` file is a conformant page (above).

### Signature verification (optional)

`x-okgf-signature` is base64 Ed25519 over the UTF-8 bytes of:

```
<type>\n<title>\n<x-okgf-scope>\n<x-okgf-review>\n<body>
```

The verifying public key is distributed out of band. A present-but-invalid signature MUST be treated as
untrusted (the validator reports it as an error when a key is supplied). An unsigned page is valid. When no
key is supplied, the validator format-checks the signature and reports it as **unverified**, not trusted.

## Checking conformance

The reference validator needs Python 3.9+ and PyYAML. Signature verification additionally needs the
`cryptography` package and a public key.

```sh
# Validate pages and/or bundle directories (structure + governance ranges):
python tools/okgf_validate.py examples/minimal examples/governed

# Also cryptographically verify signatures against an org public key:
python tools/okgf_validate.py --pubkey examples/governed/ORG_PUBKEY.pem examples/governed

# Treat warnings (e.g. missing recommended OKF fields, unverified signatures) as failures:
python tools/okgf_validate.py --strict examples/governed
```

Exit status is `0` when there are no errors (and, under `--strict`, no warnings), otherwise `1`. A usage or
environment problem (bad key, missing dependency) exits `2`.

### Errors vs warnings

- **Errors** are conformance violations: missing frontmatter, empty `type`, an out-of-range governance
  value, a malformed or cryptographically invalid signature, or a bundle whose `index.md` is missing or
  does not declare `okf_version`.
- **Warnings** are advisory: a missing recommended OKF field (`title`, `description`, `timestamp`), an
  `okf_version` the validator does not recognize, or a signature that could not be verified because no key
  was supplied.

## Examples

The [`examples/`](examples/) directory ships two bundles that are held conformant by CI:

- `examples/minimal/` - the smallest valid bundle, OKF baseline with no governance.
- `examples/governed/` - full governance: scoped/reviewed/tiered pages, provenance, and a real signed `org`
  promotion with its public key (`ORG_PUBKEY.pem`).
