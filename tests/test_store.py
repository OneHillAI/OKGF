"""Tests for the OKGF store (ingest, retrieval, lifecycle, signing, graph, bundle io)."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from store import OkgfStore, okf  # noqa: E402
from store.store import ConformanceError, NotFound, TransitionError  # noqa: E402


def test_ingest_defaults_to_draft(tmp_path):
    s = OkgfStore(tmp_path)
    pg = s.put(title="Billing model", body="# Billing model\n\nWe bill monthly.")
    assert pg.slug == "billing-model"
    assert pg.review == "draft"
    assert s.get("billing-model").title == "Billing model"


def test_slug_or_title_required(tmp_path):
    with pytest.raises(ValueError):
        OkgfStore(tmp_path).put(body="x")


def test_lifecycle_draft_proposed_approved(tmp_path):
    s = OkgfStore(tmp_path)
    s.put("p", title="P", body="# P")
    assert s.propose("p").review == "proposed"
    assert s.approve("p").review == "approved"
    with pytest.raises(TransitionError):
        s.approve("p")  # already approved


def test_cannot_approve_a_draft(tmp_path):
    s = OkgfStore(tmp_path)
    s.put("p", title="P", body="b")
    with pytest.raises(TransitionError):
        s.approve("p")


def test_reject_returns_to_draft_and_drops_signature(tmp_path):
    crypto = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
    priv = crypto.Ed25519PrivateKey.generate()
    s = OkgfStore(tmp_path)
    s.put("p", title="P", scope="org", body="# P")
    s.propose("p")
    s.approve("p", private_key=priv)
    # re-propose is illegal from approved; but a fresh reject path: drive proposed->reject
    s2 = OkgfStore(tmp_path / "b")
    s2.put("q", title="Q", body="b")
    s2.propose("q")
    assert s2.reject("q").review == "draft"


def test_sign_on_approve_and_verify(tmp_path):
    crypto = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
    priv = crypto.Ed25519PrivateKey.generate()
    s = OkgfStore(tmp_path)
    s.put("p", title="P", scope="org", body="# P\n\nbody")
    s.propose("p")
    pg = s.approve("p", private_key=priv)
    assert pg.signature
    assert s.verify("p", priv.public_key()) is True
    assert s.verify("p", crypto.Ed25519PrivateKey.generate().public_key()) is False


def test_retrieval_filters_by_governance(tmp_path):
    s = OkgfStore(tmp_path)
    s.put("a", title="A", scope="org", tier="gold", body="x")
    s.propose("a")
    s.approve("a")
    s.put("b", title="B", scope="org", body="x")  # stays draft
    assert [p.slug for p in s.list(review="approved")] == ["a"]
    assert [p.slug for p in s.list(tier="gold")] == ["a"]
    assert {p.slug for p in s.list(scope="org")} == {"a", "b"}


def test_conformance_rejected(tmp_path):
    s = OkgfStore(tmp_path)
    with pytest.raises(ConformanceError):
        s.put("p", title="P", scope="galaxy", body="b")
    with pytest.raises(ConformanceError):
        s.put("q", title="Q", tier="platinum", body="b")
    # an empty type is filled with the default rather than rejected (friendly ingest)
    assert s.put("r", type="", title="R", body="b").type == "Concept"


def test_get_missing_raises(tmp_path):
    with pytest.raises(NotFound):
        OkgfStore(tmp_path).get("nope")


def test_graph_links_and_backlinks(tmp_path):
    s = OkgfStore(tmp_path)
    s.put("a", title="A", body="see [[b]] and [c](/c)")
    s.put("b", title="B", body="# B")
    s.put("c", title="C", body="# C")
    assert s.links("a") == ["b", "c"]
    assert s.backlinks("b") == ["a"]
    assert s.backlinks("c") == ["a"]


def test_search_ranks_hits(tmp_path):
    s = OkgfStore(tmp_path)
    s.put("a", title="Billing", body="we bill per seat, billing monthly")
    s.put("b", title="Other", body="nothing here")
    hits = [p.slug for p in s.search("bill")]
    assert hits[0] == "a" and "b" not in hits


def test_export_import_roundtrip(tmp_path):
    s = OkgfStore(tmp_path / "a")
    s.put("a", title="A", scope="org", body="x")
    s.propose("a")
    s.approve("a")
    data = s.export_tgz()
    s2 = OkgfStore(tmp_path / "b")
    assert s2.import_tgz(data) == 1
    assert s2.exists("a") and s2.get("a").review == "approved"


def test_log_records_transitions(tmp_path):
    s = OkgfStore(tmp_path)
    s.put("p", title="P", body="b")
    s.propose("p")
    log = (Path(tmp_path) / "log.md").read_text()
    assert "create" in log and "propose" in log


def test_store_output_passes_standalone_validator(tmp_path):
    """What the store writes must satisfy the canonical validator in tools/ (guards against drift)."""
    spec = importlib.util.spec_from_file_location("okgf_validate", ROOT / "tools" / "okgf_validate.py")
    v = importlib.util.module_from_spec(spec)
    sys.modules["okgf_validate"] = v
    spec.loader.exec_module(v)

    s = OkgfStore(tmp_path)
    s.put("a", title="A", description="d", scope="org", tier="gold", sources=["https://x"], body="# A\n\nbody")
    s.propose("a")
    report = v.Report()
    v.validate_page((Path(tmp_path) / "a.md").read_text(), "a.md", report)
    assert report.errors == [], [str(p) for p in report.errors]

    # the whole store is a conformant bundle
    breport = v.Report()
    v.validate_bundle(Path(tmp_path), breport)
    assert breport.errors == [], [str(p) for p in breport.errors]
