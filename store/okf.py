"""OKGF page format: parse, serialize, canonicalize, sign, verify, and check conformance.

Self-contained (Python 3.9+, PyYAML; `cryptography` only for signing and verification), so the store is a
clean reference an implementer can lift out and copy. The conformance rules mirror
`tools/okgf_validate.py`; `tests/test_store.py` cross-checks that the two agree.
"""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass, field

import yaml

OKF_VERSION = "0.1"
_DELIM = "---"
DEFAULT_TYPE = "Concept"

SCOPES = ("personal", "team", "org")
REVIEWS = ("draft", "proposed", "approved")
TIERS = ("bronze", "silver", "gold")

SCOPE = "x-okgf-scope"
REVIEW = "x-okgf-review"
TIER = "x-okgf-tier"
SOURCES = "x-okgf-sources"
SIGNATURE = "x-okgf-signature"

_ENUMS = {SCOPE: set(SCOPES), REVIEW: set(REVIEWS), TIER: set(TIERS)}
_ED25519_SIG_BYTES = 64
_KEY_ORDER = ["type", "title", "description", "timestamp", "tags", SCOPE, REVIEW, TIER, SOURCES, SIGNATURE]
_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
_MDLINK = re.compile(r"\]\(/([a-z0-9][a-z0-9-]*)\)")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).strip().lower()).strip("-")


@dataclass
class Page:
    """An OKGF page: its slug, the frontmatter mapping, and the markdown body."""

    slug: str
    fm: dict = field(default_factory=dict)
    body: str = ""

    @property
    def type(self) -> str:
        return str(self.fm.get("type") or "")

    @property
    def title(self) -> str:
        return str(self.fm.get("title") or "")

    @property
    def scope(self):
        return self.fm.get(SCOPE)

    @property
    def review(self):
        return self.fm.get(REVIEW)

    @property
    def tier(self):
        return self.fm.get(TIER)

    @property
    def sources(self) -> list:
        return list(self.fm.get(SOURCES) or [])

    @property
    def signature(self):
        return self.fm.get(SIGNATURE)


def split_frontmatter(text: str):
    """Split ``---`` YAML frontmatter from the body. Returns ``(fm, body)``; ``fm`` is ``None`` when no
    well-formed block is present. Raises ``yaml.YAMLError`` on invalid YAML."""
    t = text.lstrip("﻿").lstrip()
    if not t.startswith(_DELIM):
        return None, text.strip()
    rest = t[len(_DELIM):].lstrip("\n")
    end = rest.find("\n" + _DELIM)
    if end == -1:
        return None, text.strip()
    fm = yaml.safe_load(rest[:end])
    body = rest[end + len(_DELIM) + 1:].lstrip("\n").rstrip()
    return (fm if isinstance(fm, dict) else {}), body


def parse(text: str, slug: str = "") -> Page:
    fm, body = split_frontmatter(text)
    return Page(slug=slug, fm=(fm or {}), body=body)


def serialize(page: Page) -> str:
    """Serialize a page to OKGF markdown: canonical key order, unknown keys preserved after the known set."""
    ordered: dict = {}
    for k in _KEY_ORDER:
        if k in page.fm and page.fm[k] not in (None, "", []):
            ordered[k] = page.fm[k]
    for k, v in page.fm.items():
        if k not in _KEY_ORDER:
            ordered[k] = v
    if not str(ordered.get("type") or "").strip():
        ordered = {"type": DEFAULT_TYPE, **ordered}
    front = yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True).strip()
    return f"{_DELIM}\n{front}\n{_DELIM}\n\n{page.body.strip()}\n"


def canonical_bytes(page: Page) -> bytes:
    """The bytes an ``x-okgf-signature`` signs: ``<type>\\n<title>\\n<scope>\\n<review>\\n<body>``."""
    parts = [
        str(page.fm.get("type") or ""),
        str(page.fm.get("title") or ""),
        str(page.fm.get(SCOPE) or ""),
        str(page.fm.get(REVIEW) or ""),
        page.body,
    ]
    return "\n".join(parts).encode("utf-8")


def conformance_errors(page: Page) -> list:
    """Return a list of spec violations for a single page (empty means conformant)."""
    errs = []
    if not page.type.strip():
        errs.append("missing required non-empty `type`")
    for key, allowed in _ENUMS.items():
        if key in page.fm and page.fm[key] not in allowed:
            errs.append(f"`{key}` = {page.fm[key]!r}; must be one of {sorted(allowed)}")
    if SOURCES in page.fm:
        s = page.fm[SOURCES]
        if not isinstance(s, list) or not all(isinstance(x, str) for x in s):
            errs.append("`x-okgf-sources` must be a list of strings (URIs)")
    if SIGNATURE in page.fm:
        sig = page.fm[SIGNATURE]
        if not isinstance(sig, str) or not sig.strip():
            errs.append("`x-okgf-signature` must be a non-empty base64 string")
        else:
            try:
                raw = base64.b64decode(sig.strip(), validate=True)
                if len(raw) != _ED25519_SIG_BYTES:
                    errs.append(f"`x-okgf-signature` must decode to {_ED25519_SIG_BYTES} bytes")
            except (binascii.Error, ValueError):
                errs.append("`x-okgf-signature` is not valid base64")
    return errs


def links(page: Page) -> list:
    """Outgoing links from a page body: ``[[slug]]`` wikilinks and OKF ``](/slug)`` links."""
    out = set()
    for m in _WIKILINK.finditer(page.body):
        out.add(slugify(m.group(1).strip()))
    for m in _MDLINK.finditer(page.body):
        out.add(m.group(1))
    return sorted(out)


# --- signing (cryptography is imported lazily; only needed to sign or verify) ---


def sign(page: Page, private_key) -> str:
    return base64.b64encode(private_key.sign(canonical_bytes(page))).decode("ascii")


def verify(page: Page, public_key) -> bool:
    from cryptography.exceptions import InvalidSignature

    sig = page.fm.get(SIGNATURE)
    if not sig:
        return False
    try:
        public_key.verify(base64.b64decode(sig, validate=True), canonical_bytes(page))
        return True
    except (InvalidSignature, binascii.Error, ValueError):
        return False


def load_private_key(data: bytes):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    d = data.strip()
    if d.startswith(b"-----BEGIN"):
        return load_pem_private_key(d, password=None)
    raw = d if len(d) == 32 else base64.b64decode(d, validate=True)
    return Ed25519PrivateKey.from_private_bytes(raw)


def load_public_key(data: bytes):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    d = data.strip()
    if d.startswith(b"-----BEGIN"):
        return load_pem_public_key(d)
    raw = d if len(d) == 32 else base64.b64decode(d, validate=True)
    return Ed25519PublicKey.from_public_bytes(raw)
