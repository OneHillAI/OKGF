"""Tests for the OKGF conformance validator."""

from pathlib import Path

import pytest

from okgf import validate as okgf

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


def _check(text: str, **kw):
    report = okgf.Report()
    okgf.validate_page(text, "test.md", report, **kw)
    return report


PAGE_OK = """---
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
"""


def test_valid_page_has_no_errors():
    r = _check(PAGE_OK)
    assert r.errors == []


def test_missing_frontmatter_is_error():
    r = _check("# Just a heading\n\nno frontmatter here")
    assert any("no YAML frontmatter" in p.message for p in r.errors)


def test_empty_type_is_error():
    r = _check("---\ntype: ''\ntitle: X\n---\nbody")
    assert any("`type`" in p.message for p in r.errors)


def test_unknown_keys_are_preserved_not_errors():
    text = "---\ntype: Concept\ntitle: X\ndescription: d\ntimestamp: t\nresource: http://x\nx-custom: hi\n---\nbody"
    r = _check(text)
    assert r.errors == []


@pytest.mark.parametrize(
    "key,bad",
    [
        ("x-okgf-scope", "global"),
        ("x-okgf-review", "published"),
        ("x-okgf-tier", "platinum"),
    ],
)
def test_bad_enum_value_is_error(key, bad):
    text = f"---\ntype: Concept\ntitle: X\ndescription: d\ntimestamp: t\n{key}: {bad}\n---\nbody"
    r = _check(text)
    assert any(key in p.message for p in r.errors)


def test_sources_must_be_list_of_strings():
    text = "---\ntype: Concept\ntitle: X\ndescription: d\ntimestamp: t\nx-okgf-sources: not-a-list\n---\nbody"
    r = _check(text)
    assert any("x-okgf-sources" in p.message for p in r.errors)


def test_bad_base64_signature_is_error():
    text = "---\ntype: Concept\ntitle: X\ndescription: d\ntimestamp: t\nx-okgf-signature: '!!!not base64!!!'\n---\nbody"
    r = _check(text)
    assert any("base64" in p.message for p in r.errors)


def test_wrong_length_signature_is_error():
    text = "---\ntype: Concept\ntitle: X\ndescription: d\ntimestamp: t\nx-okgf-signature: aGVsbG8=\n---\nbody"
    r = _check(text)
    assert any("Ed25519 signature is" in p.message for p in r.errors)


def test_signature_without_key_warns_unverified():
    text = "---\ntype: Concept\ntitle: X\ndescription: d\ntimestamp: t\nx-okgf-signature: " + "A" * 88 + "\n---\nbody"
    # 88 base64 chars -> 66 bytes; use a real 64-byte blob instead:
    import base64

    sig = base64.b64encode(b"\x00" * 64).decode()
    text = f"---\ntype: Concept\ntitle: X\ndescription: d\ntimestamp: t\nx-okgf-signature: {sig}\n---\nbody"
    r = _check(text)
    assert any("unverified" in p.message for p in r.warnings)


def test_recommended_fields_warn():
    r = _check("---\ntype: Concept\n---\nbody")
    msgs = " ".join(p.message for p in r.warnings)
    assert "title" in msgs and "description" in msgs


# --- Bundle-level ---


def test_bundle_missing_index_is_error(tmp_path):
    (tmp_path / "page.md").write_text("---\ntype: Concept\ntitle: X\ndescription: d\ntimestamp: t\n---\nb")
    report = okgf.Report()
    okgf.validate_bundle(tmp_path, report)
    assert any("index.md" in p.message for p in report.errors)


def test_index_without_okf_version_is_error(tmp_path):
    (tmp_path / "index.md").write_text("---\ntitle: Index\n---\n# Index\n")
    report = okgf.Report()
    okgf.validate_bundle(tmp_path, report)
    assert any("okf_version" in p.message for p in report.errors)


# --- Shipped examples must be conformant ---


def test_minimal_example_is_conformant():
    report = okgf.Report()
    okgf.validate_bundle(EXAMPLES / "minimal", report)
    assert report.errors == [] and report.warnings == []


def test_governed_example_is_conformant_and_signature_verifies():
    pytest.importorskip("cryptography")
    pubkey = okgf._load_pubkey(str(EXAMPLES / "governed" / "ORG_PUBKEY.pem"))
    report = okgf.Report()
    okgf.validate_bundle(EXAMPLES / "governed", report, pubkey=pubkey)
    assert report.errors == [], [str(p) for p in report.errors]
    assert report.warnings == [], [str(p) for p in report.warnings]


def test_governed_signature_fails_under_wrong_key(tmp_path):
    crypto = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
    wrong_pub = crypto.Ed25519PrivateKey.generate().public_key()
    report = okgf.Report()
    page = (EXAMPLES / "governed" / "billing-model.md").read_text()
    okgf.validate_page(page, "billing-model.md", report, pubkey=wrong_pub)
    assert any("INVALID" in p.message for p in report.errors)
