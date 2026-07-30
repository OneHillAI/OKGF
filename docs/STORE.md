# OKGF Store

A small, runnable reference for **using** OKGF, not just validating it: ingest knowledge, retrieve it
filtered by trust, and move pages through the review lifecycle. It ships as a Python library, a CLI, and a
zero-dependency HTTP API (see [`store/`](../store)).

## The idea: the bundle is the database

The durable store is the **on-disk OKGF bundle** itself: a directory of markdown pages plus `index.md` and
`log.md`. It stays portable, diffable, and ownable, which is the whole point of the format. Query, search,
and the concept graph read those files directly, so there is no separate database to keep in sync and
nothing to lock you in. Delete any derived index and rebuild it from the files; the files are the source of
truth.

```
your-kb/
  index.md          # lists the pages; declares okf_version
  log.md            # append-only, dated history of every change
  billing-model.md  # one page per concept
  invoices.md
```

## Quickstart

The library needs Python 3.9+ and PyYAML; signing and verification also need `cryptography`.

```sh
pip install pyyaml cryptography

# ingest a page (new pages start as draft), then walk it to authoritative
python -m store.cli --root ./kb add --title "Billing model" --scope org --tier gold \
  --source https://stripe.com/docs --body "# Billing model

We bill monthly per seat."
python -m store.cli --root ./kb propose billing-model
python -m store.cli --root ./kb approve billing-model --org-key org.pem   # signs the promotion
python -m store.cli --root ./kb list --review approved --tier gold
```

Or run the API:

```sh
python -m store.cli --root ./kb serve --port 8080 --org-key org.pem
```

## The compounding loop

Knowledge earns authority instead of being trusted by default:

1. **Ingest** a source. An agent (or a person) writes a page. It starts as `draft`.
2. **Propose** it for review.
3. A human **approves** it. On approval into a shared scope it can be **signed** with the org key.
4. It is now `approved`, and only then does trusted retrieval return it.

Each step is appended to `log.md`, so the history of how a fact became authoritative is auditable. This is
the [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) idea of knowledge that
compounds, with a trust gate in front of it.

## HTTP API

JSON in and out. Default retrieval returns only `approved` (authoritative) pages, and every result carries
its governance so a caller can filter by trust.

| Method and path | Does |
| --- | --- |
| `GET /health` | Liveness and page count. |
| `GET /pages?scope=&review=&tier=&tag=&include=all` | List pages. Returns only `approved` unless `include=all` or `review=` is given. |
| `GET /pages/{slug}` | One page, with frontmatter, body, and `signed` flag. |
| `GET /search?q=&scope=&review=&tier=` | Search titles and bodies. |
| `GET /graph/{slug}` | Outgoing links and backlinks. |
| `GET /export.okgf.tgz` | The whole store as a portable bundle. |
| `POST /pages` | Ingest a page (JSON). New pages default to `draft`. |
| `POST /pages/{slug}/propose` `/approve` `/reject` | Lifecycle transitions. `approve` signs when the server holds an org key. |
| `POST /import` | Ingest content pages from a `.tgz` bundle body. |

### Retrieval for agents

The point of the filter is trust. A retrieval pipeline can ask for exactly the knowledge it is willing to
act on:

```sh
# only org-scope, approved, gold-tier knowledge
curl "http://localhost:8080/pages?scope=org&review=approved&tier=gold"
```

Each returned page carries its `sources` (provenance) and a `signed` flag, so a consumer can prefer curated,
attributed, verifiable knowledge and drop the rest.

## Trust and verification

An approval into a shared scope may be signed (Ed25519 over the canonical page, per
[`SPEC.md`](../SPEC.md)). The verifying public key is published out of band, so anyone can confirm the org
really approved a page, offline:

```python
from store import OkgfStore, okf
store = OkgfStore("./kb")
pub = okf.load_public_key(open("org.pub.pem", "rb").read())
assert store.verify("billing-model", pub)
```

## Notes and limits

- **Reference quality.** The server is single-process and has no auth beyond an optional bearer token
  (`OKGF_STORE_TOKEN`, required on writes when set). Put it behind your own auth or gateway for real use;
  the analysis is deliberately small so you can read it and build your own.
- **Scaling.** Query and search walk the files, which is fine for thousands of pages. For a large store,
  add a derived index (for example SQLite FTS) that you rebuild from the bundle; keep the files canonical.
- **The store governs what it holds.** Pages ingested through it default to `draft`, so nothing is
  authoritative until reviewed.
