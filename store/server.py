"""A zero-dependency reference HTTP API over :class:`OkgfStore` (Python stdlib only).

Reference quality: single process, JSON in and out. It is not hardened for the open internet. Set the
environment variable ``OKGF_STORE_TOKEN`` to require ``Authorization: Bearer <token>`` on writes, and put
it behind your own auth or gateway for real use.

Endpoints
    GET  /health
    GET  /pages[?scope=&review=&tier=&tag=&include=all]   default returns only approved (authoritative)
    GET  /pages/{slug}
    GET  /search?q=[&scope=&review=&tier=]
    GET  /graph/{slug}                                     outgoing links and backlinks
    GET  /export.okgf.tgz
    POST /pages                                            ingest (JSON); new pages default to draft
    POST /pages/{slug}/propose | /approve | /reject        lifecycle transitions
    POST /import                                           ingest a .tgz bundle body
"""

from __future__ import annotations

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .store import ConformanceError, NotFound, OkgfStore, TransitionError

_SLUG = r"([a-z0-9][a-z0-9-]*)"


def _page_json(pg) -> dict:
    return {
        "slug": pg.slug,
        "type": pg.type,
        "title": pg.title,
        "scope": pg.scope,
        "review": pg.review,
        "tier": pg.tier,
        "sources": pg.sources,
        "signed": bool(pg.signature),
        "body": pg.body,
        "frontmatter": pg.fm,
    }


def make_handler(store: OkgfStore, *, private_key=None, token=None):
    class Handler(BaseHTTPRequestHandler):
        server_version = "okgf-store/0.1"

        def log_message(self, *args):  # keep the reference server quiet
            pass

        def _send(self, code, obj=None, raw=None, ctype="application/json"):
            body = raw if raw is not None else (json.dumps(obj).encode() if obj is not None else b"")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _authed(self) -> bool:
            return not token or self.headers.get("Authorization", "") == f"Bearer {token}"

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            path = u.path.rstrip("/") or "/"

            def one(k, default=None):
                v = q.get(k)
                return v[0] if v else default

            try:
                if path in ("/", "/health"):
                    return self._send(200, {"status": "ok", "pages": len(store.list())})
                if path == "/pages":
                    review = one("review")
                    if review is None and one("include") != "all":
                        review = "approved"  # default retrieval is authoritative-only
                    pages = store.list(scope=one("scope"), review=review, tier=one("tier"), tag=one("tag"))
                    return self._send(200, {"count": len(pages), "pages": [_page_json(p) for p in pages]})
                if path == "/search":
                    res = store.search(one("q", ""), scope=one("scope"), review=one("review"), tier=one("tier"))
                    return self._send(200, {"count": len(res), "results": [_page_json(p) for p in res]})
                if path == "/export.okgf.tgz":
                    return self._send(200, raw=store.export_tgz(), ctype="application/gzip")
                m = re.fullmatch(rf"/pages/{_SLUG}", path)
                if m:
                    return self._send(200, _page_json(store.get(m.group(1))))
                m = re.fullmatch(rf"/graph/{_SLUG}", path)
                if m:
                    s = m.group(1)
                    return self._send(200, {"slug": s, "links": store.links(s), "backlinks": store.backlinks(s)})
                return self._send(404, {"error": "not found"})
            except NotFound as e:
                return self._send(404, {"error": f"no such page: {e}"})
            except Exception as e:  # noqa: BLE001 - reference server surfaces the message
                return self._send(500, {"error": str(e)})

        def do_POST(self):
            path = urlparse(self.path).path.rstrip("/") or "/"
            if not self._authed():
                return self._send(401, {"error": "missing or invalid bearer token"})
            try:
                if path == "/pages":
                    d = self._body_json()
                    pg = store.put(
                        d.get("slug"),
                        type=d.get("type", "Concept"),
                        title=d.get("title", ""),
                        body=d.get("body", ""),
                        description=d.get("description"),
                        scope=d.get("scope"),
                        review=d.get("review"),
                        tier=d.get("tier"),
                        sources=d.get("sources"),
                        tags=d.get("tags"),
                    )
                    return self._send(201, _page_json(pg))
                if path == "/import":
                    n = int(self.headers.get("Content-Length") or 0)
                    data = self.rfile.read(n) if n else b""
                    return self._send(200, {"imported": store.import_tgz(data)})
                m = re.fullmatch(rf"/pages/{_SLUG}/(propose|approve|reject)", path)
                if m:
                    slug, action = m.group(1), m.group(2)
                    if action == "propose":
                        pg = store.propose(slug)
                    elif action == "reject":
                        pg = store.reject(slug)
                    else:
                        pg = store.approve(slug, private_key=private_key)
                    return self._send(200, _page_json(pg))
                return self._send(404, {"error": "not found"})
            except NotFound as e:
                return self._send(404, {"error": f"no such page: {e}"})
            except (ConformanceError, TransitionError, ValueError) as e:
                return self._send(400, {"error": str(e)})
            except Exception as e:  # noqa: BLE001
                return self._send(500, {"error": str(e)})

        def _body_json(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

    return Handler


def serve(root, host="127.0.0.1", port=8080, *, private_key=None, token=None) -> ThreadingHTTPServer:
    """Build a running-ready server over the bundle at ``root``. Call ``.serve_forever()`` on the result."""
    if token is None:
        token = os.environ.get("OKGF_STORE_TOKEN")
    handler = make_handler(OkgfStore(root), private_key=private_key, token=token)
    return ThreadingHTTPServer((host, port), handler)
