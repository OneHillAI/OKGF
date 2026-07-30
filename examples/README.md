# OKGF example bundles

Two bundles that demonstrate the format. CI validates both on every change (see
[`CONFORMANCE.md`](../CONFORMANCE.md)).

## `minimal/`

The smallest conformant bundle: a root `index.md` declaring `okf_version` and one ungoverned `Concept`
page. It carries no `x-okgf-*` fields, showing that an OKGF bundle is a plain OKF bundle when no
governance is applied. Any OKF-only tool reads it unchanged.

## `governed/`

A fully governed bundle:

- `billing-model.md` - `org` / `approved` / `gold`, with provenance and a **real Ed25519 signature**.
- `invoices.md` - `org` / `approved` / `silver`, an authoritative page without a signature.
- `refund-policy.md` - `team` / `proposed` / `bronze`, a candidate that is not yet authoritative.
- `index.md`, `log.md`, `PRINCIPLES.md` - the reserved structural files.
- `ORG_PUBKEY.pem` - the org's public key, published out of band, for verifying the signature.

Verify the signed promotion:

```sh
python ../../tools/okgf_validate.py --pubkey governed/ORG_PUBKEY.pem governed
```

The signature in `billing-model.md` was produced with an example-only key. Do not reuse it; a real
deployment publishes its own org key.
