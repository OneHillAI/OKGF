"""Command line for the OKGF store: run the API, or drive the bundle from the shell.

    python -m store.cli --root ./kb serve --port 8080
    python -m store.cli --root ./kb add --title "Billing model" --scope org --body "# Billing model"
    python -m store.cli --root ./kb propose billing-model
    python -m store.cli --root ./kb approve billing-model --org-key org.pem
    python -m store.cli --root ./kb list --review approved --tier gold
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import okf
from .server import serve
from .store import OkgfStore


def _load_key(path):
    return okf.load_private_key(Path(path).read_bytes()) if path else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="okgf-store", description="Run and drive an OKGF knowledgebase.")
    ap.add_argument("--root", default="okgf-store", help="bundle directory (the durable store)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("serve", help="run the HTTP API")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--org-key", help="Ed25519 private key (PEM) used to sign approvals")

    p = sub.add_parser("add", help="ingest a page (defaults to draft)")
    p.add_argument("--slug")
    p.add_argument("--title", required=True)
    p.add_argument("--type", default="Concept")
    p.add_argument("--scope", choices=okf.SCOPES)
    p.add_argument("--tier", choices=okf.TIERS)
    p.add_argument("--source", action="append", dest="sources")
    p.add_argument("--body", default="", help="body text, or - to read stdin")

    sub.add_parser("get", help="print a page").add_argument("slug")

    p = sub.add_parser("list", help="list pages")
    for f in ("scope", "review", "tier", "tag"):
        p.add_argument("--" + f)

    for name in ("propose", "approve", "reject"):
        p = sub.add_parser(name, help=f"{name} a page")
        p.add_argument("slug")
        if name == "approve":
            p.add_argument("--org-key", help="sign the approval with this Ed25519 private key (PEM)")

    sub.add_parser("search", help="search titles and bodies").add_argument("query")
    sub.add_parser("export", help="write a .tgz bundle to stdout")

    args = ap.parse_args(argv)
    store = OkgfStore(args.root)

    if args.cmd == "serve":
        httpd = serve(args.root, args.host, args.port, private_key=_load_key(args.org_key),
                      token=os.environ.get("OKGF_STORE_TOKEN"))
        sys.stderr.write(f"OKGF store on http://{args.host}:{args.port}  (root={args.root})\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            httpd.shutdown()
    elif args.cmd == "add":
        body = sys.stdin.read() if args.body == "-" else args.body
        pg = store.put(args.slug, title=args.title, type=args.type, scope=args.scope,
                       tier=args.tier, sources=args.sources, body=body)
        print(pg.slug)
    elif args.cmd == "get":
        sys.stdout.write(okf.serialize(store.get(args.slug)))
    elif args.cmd == "list":
        for pg in store.list(scope=args.scope, review=args.review, tier=args.tier, tag=args.tag):
            print(f"{pg.slug}\t{pg.review or '-'}\t{pg.scope or '-'}\t{pg.tier or '-'}\t{pg.title}")
    elif args.cmd in ("propose", "approve", "reject"):
        if args.cmd == "propose":
            pg = store.propose(args.slug)
        elif args.cmd == "reject":
            pg = store.reject(args.slug)
        else:
            pg = store.approve(args.slug, private_key=_load_key(getattr(args, "org_key", None)))
        print(f"{pg.slug} -> {pg.review}")
    elif args.cmd == "search":
        for pg in store.search(args.query):
            print(f"{pg.slug}\t{pg.title}")
    elif args.cmd == "export":
        sys.stdout.buffer.write(store.export_tgz())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
