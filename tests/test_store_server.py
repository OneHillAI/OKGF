"""Tests for the OKGF store HTTP API, driven with stdlib urllib against an ephemeral server."""

import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from store.server import serve  # noqa: E402


@pytest.fixture
def base_url(tmp_path):
    httpd = serve(tmp_path, "127.0.0.1", 0, token=None)  # port 0 = ephemeral
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()


def _req(method, url, data=None):
    body = json.dumps(data).encode() if data is not None else None
    headers = {"Content-Type": "application/json"} if body else {}
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def test_health(base_url):
    status, body = _req("GET", base_url + "/health")
    assert status == 200 and body["status"] == "ok"


def test_ingest_retrieve_and_lifecycle(base_url):
    status, pg = _req("POST", base_url + "/pages",
                      {"slug": "billing", "title": "Billing", "scope": "org", "body": "# Billing"})
    assert status == 201 and pg["review"] == "draft"

    assert _req("POST", base_url + "/pages/billing/propose")[0] == 200
    status, pg = _req("POST", base_url + "/pages/billing/approve")
    assert status == 200 and pg["review"] == "approved"

    status, one = _req("GET", base_url + "/pages/billing")
    assert status == 200 and one["title"] == "Billing"


def test_default_retrieval_is_authoritative_only(base_url):
    _req("POST", base_url + "/pages", {"slug": "draftpage", "title": "D", "body": "x"})
    status, body = _req("GET", base_url + "/pages")
    assert status == 200 and body["count"] == 0  # a draft is not returned by default
    status, body = _req("GET", base_url + "/pages?include=all")
    assert body["count"] == 1


def test_search_endpoint(base_url):
    _req("POST", base_url + "/pages", {"slug": "a", "title": "Billing", "body": "we bill per seat"})
    status, body = _req("GET", base_url + "/search?q=bill")
    assert status == 200 and body["count"] == 1 and body["results"][0]["slug"] == "a"


def test_graph_endpoint(base_url):
    _req("POST", base_url + "/pages", {"slug": "a", "title": "A", "body": "see [[b]]"})
    _req("POST", base_url + "/pages", {"slug": "b", "title": "B", "body": "# B"})
    status, body = _req("GET", base_url + "/graph/b")
    assert status == 200 and body["backlinks"] == ["a"]


def test_illegal_transition_is_400(base_url):
    _req("POST", base_url + "/pages", {"slug": "p", "title": "P", "body": "x"})
    status, body = _req("POST", base_url + "/pages/p/approve")  # cannot approve a draft
    assert status == 400 and "error" in body


def test_bad_scope_is_400(base_url):
    status, body = _req("POST", base_url + "/pages", {"slug": "p", "title": "P", "scope": "galaxy", "body": "x"})
    assert status == 400


def test_missing_page_is_404(base_url):
    assert _req("GET", base_url + "/pages/ghost")[0] == 404


def test_bearer_token_guards_writes(tmp_path):
    httpd = serve(tmp_path, "127.0.0.1", 0, token="secret")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        # no token -> 401 on write
        assert _req("POST", base + "/pages", {"slug": "p", "title": "P", "body": "x"})[0] == 401
        # reads still work
        assert _req("GET", base + "/health")[0] == 200
        # with token -> 201
        body = json.dumps({"slug": "p", "title": "P", "body": "x"}).encode()
        req = urllib.request.Request(base + "/pages", data=body, method="POST",
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer secret"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 201
    finally:
        httpd.shutdown()
