#!/usr/bin/env python3
"""OKGF conformance validator.

Checks a single page or a whole bundle against the OKGF v0.1 specification (see ``SPEC.md`` /
``CONFORMANCE.md``). OKGF is a strict superset of OKF, so this validator enforces:

1. OKF baseline: every non-reserved ``.md`` has valid YAML frontmatter with a non-empty ``type``; a
   bundle's root ``index.md`` declares ``okf_version``.
2. OKGF governance: wherever an ``x-okgf-*`` field is present, its value matches the spec table.

Unknown frontmatter keys are tolerated and preserved (never an error), per the OKF rule that consumers
must round-trip unrecognized fields.

Dependencies: Python 3.9+ and PyYAML. Cryptographic signature verification is OPTIONAL and only runs when
a public key is supplied (``--pubkey``) and the ``cryptography`` package is importable; without it, a
present signature is format-checked and reported as unverified rather than trusted. Install the
``verify`` extra (``pip install 'okgf[verify]'``) to pull in ``cryptography``.

Usage:
    okgf PATH [PATH ...]            validate pages and/or bundle directories
    okgf --pubkey key.pem PATH      also cryptographically verify x-okgf-signature
    okgf --strict PATH              treat warnings as failures
    okgf --version                  print the version and exit

Exit status: 0 = conformant (no errors), 1 = at least one error (or a warning under --strict).
"""

from __future__ import annotations

import argparse
import base64
import binascii
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - guidance only
    sys.stderr.write("okgf: PyYAML is required (pip install pyyaml)\n")
    raise SystemExit(2)

__version__ = "0.1.0"

SPEC_VERSION = "0.1"
_DELIM = "---"

# Reserved bundle files: structural, not content pages.
INDEX_FILE = "index.md"
LOG_FILE = "log.md"
RESERVED_FILES = {INDEX_FILE, LOG_FILE, "principles.md", "schema.md"}

# Governance value tables (SPEC.md "Governance extensions").
ENUMS = {
    "x-okgf-scope": {"personal", "team", "org"},
    "x-okgf-review": {"draft", "proposed", "approved"},
    "x-okgf-tier": {"bronze", "silver", "gold"},
}
_ED25519_SIG_BYTES = 64  # a raw Ed25519 signature is 64 bytes
_OKF_RECOMMENDED = ("title", "description", "timestamp")


@dataclass
class Problem:
    path: str
    level: str  # "error" | "warning"
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper():7} {self.path}: {self.message}"


@dataclass
class Report:
    problems: list[Problem] = field(default_factory=list)
    pages_checked: int = 0
    bundles_checked: int = 0

    def error(self, path: str, msg: str) -> None:
        self.problems.append(Problem(path, "error", msg))

    def warning(self, path: str, msg: str) -> None:
        self.problems.append(Problem(path, "warning", msg))

    @property
    def errors(self) -> list[Problem]:
        return [p for p in self.problems if p.level == "error"]

    @property
    def warnings(self) -> list[Problem]:
        return [p for p in self.problems if p.level == "warning"]


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Split ``---``-delimited YAML frontmatter from the body. Returns ``(fm, body)``; ``fm`` is ``None``
    when no well-formed frontmatter block is present (so the caller can distinguish "absent" from "empty").
    Raises ``yaml.YAMLError`` when the block is present but not valid YAML."""
    t = text.lstrip("﻿").lstrip()
    if not t.startswith(_DELIM):
        return None, text.strip()
    rest = t[len(_DELIM):].lstrip("\n")
    end = rest.find(f"\n{_DELIM}")
    if end == -1:
        return None, text.strip()
    fm = yaml.safe_load(rest[:end])
    body = rest[end + len(_DELIM) + 1:].lstrip("\n").rstrip()
    return (fm if fm is not None else {}), body


def _canonical_bytes(fm: dict, body: str) -> bytes:
    """The bytes an x-okgf-signature signs: ``<type>\\n<title>\\n<scope>\\n<review>\\n<body>``."""
    parts = [
        str(fm.get("type") or ""),
        str(fm.get("title") or ""),
        str(fm.get("x-okgf-scope") or ""),
        str(fm.get("x-okgf-review") or ""),
        body,
    ]
    return "\n".join(parts).encode("utf-8")


def _load_pubkey(path: str):
    """Load an Ed25519 public key from a PEM or raw-32-byte file. Returns a verifier or raises."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    raw = Path(path).read_bytes()
    if raw.lstrip().startswith(b"-----BEGIN"):
        return load_pem_public_key(raw)
    if len(raw.strip()) == 32:
        return Ed25519PublicKey.from_public_bytes(raw.strip())
    # try base64-encoded 32 bytes
    decoded = base64.b64decode(raw.strip(), validate=True)
    return Ed25519PublicKey.from_public_bytes(decoded)


def validate_page(text: str, path: str, report: Report, *, pubkey=None) -> None:
    """Validate a single OKGF page (any non-reserved ``.md``)."""
    report.pages_checked += 1
    try:
        fm, body = split_frontmatter(text)
    except yaml.YAMLError as exc:
        report.error(path, f"invalid YAML frontmatter: {exc}")
        return
    if fm is None:
        report.error(path, "no YAML frontmatter block (OKF requires one)")
        return
    if not isinstance(fm, dict):
        report.error(path, "frontmatter is not a YAML mapping")
        return

    # OKF baseline.
    if not str(fm.get("type") or "").strip():
        report.error(path, "missing required non-empty `type`")
    for key in _OKF_RECOMMENDED:
        if not str(fm.get(key) or "").strip():
            report.warning(path, f"missing recommended OKF field `{key}`")

    # OKGF governance enums.
    for key, allowed in ENUMS.items():
        if key in fm:
            val = fm[key]
            if val not in allowed:
                report.error(path, f"`{key}` = {val!r}; must be one of {sorted(allowed)}")

    # Provenance: list of string URIs.
    if "x-okgf-sources" in fm:
        srcs = fm["x-okgf-sources"]
        if not isinstance(srcs, list) or not all(isinstance(s, str) for s in srcs):
            report.error(path, "`x-okgf-sources` must be a list of strings (URIs)")

    # Signature: base64 Ed25519, optionally verified.
    if "x-okgf-signature" in fm:
        _validate_signature(fm, body, path, report, pubkey=pubkey)


def _validate_signature(fm: dict, body: str, path: str, report: Report, *, pubkey) -> None:
    sig = fm.get("x-okgf-signature")
    if not isinstance(sig, str) or not sig.strip():
        report.error(path, "`x-okgf-signature` must be a non-empty base64 string")
        return
    try:
        raw = base64.b64decode(sig.strip(), validate=True)
    except (binascii.Error, ValueError):
        report.error(path, "`x-okgf-signature` is not valid base64")
        return
    if len(raw) != _ED25519_SIG_BYTES:
        report.error(
            path,
            f"`x-okgf-signature` decodes to {len(raw)} bytes; an Ed25519 signature is "
            f"{_ED25519_SIG_BYTES}",
        )
        return
    if pubkey is None:
        report.warning(path, "`x-okgf-signature` present but unverified (no public key supplied)")
        return
    from cryptography.exceptions import InvalidSignature

    try:
        pubkey.verify(raw, _canonical_bytes(fm, body))
    except InvalidSignature:
        report.error(path, "`x-okgf-signature` is present but INVALID (untrusted)")


def validate_bundle(root: Path, report: Report, *, pubkey=None) -> None:
    """Validate a bundle directory: reserved-file structure plus every content page."""
    report.bundles_checked += 1
    index = root / INDEX_FILE
    if not index.is_file():
        report.error(str(root), f"bundle is missing the reserved `{INDEX_FILE}`")
    else:
        _validate_index(index, report)

    for md in sorted(root.rglob("*.md")):
        name = md.name.lower()
        if name == INDEX_FILE:
            continue
        if name == LOG_FILE:
            continue  # reserved; free-form dated history, not a content page
        if name in RESERVED_FILES:
            continue
        validate_page(md.read_text(encoding="utf-8"), str(md.relative_to(root)), report, pubkey=pubkey)


def _validate_index(index: Path, report: Report) -> None:
    rel = index.name
    try:
        fm, _ = split_frontmatter(index.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        report.error(rel, f"invalid YAML frontmatter: {exc}")
        return
    if not isinstance(fm, dict) or "okf_version" not in fm:
        report.error(rel, "root index.md must declare `okf_version` in its frontmatter")
        return
    declared = str(fm["okf_version"])
    if declared != SPEC_VERSION:
        report.warning(rel, f"okf_version {declared!r} != validator's {SPEC_VERSION!r}")


def validate_path(path: Path, report: Report, *, pubkey=None) -> None:
    if path.is_dir():
        validate_bundle(path, report, pubkey=pubkey)
    elif path.is_file() and path.suffix.lower() == ".md":
        if path.name.lower() == INDEX_FILE:
            _validate_index(path, report)
        elif path.name.lower() in RESERVED_FILES:
            report.warning(str(path), f"`{path.name}` is a reserved file; nothing to validate")
        else:
            validate_page(path.read_text(encoding="utf-8"), str(path), report, pubkey=pubkey)
    else:
        report.error(str(path), "not a .md file or a bundle directory")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="okgf", description="Validate OKGF pages and bundles.")
    ap.add_argument("paths", nargs="+", type=Path, help="pages (.md) or bundle directories")
    ap.add_argument("--pubkey", type=str, default=None, help="Ed25519 public key (PEM/raw/base64) to verify signatures")
    ap.add_argument("--strict", action="store_true", help="treat warnings as failures")
    ap.add_argument("--version", action="version", version=f"okgf {__version__}")
    args = ap.parse_args(argv)

    pubkey = None
    if args.pubkey:
        try:
            pubkey = _load_pubkey(args.pubkey)
        except ImportError:
            sys.stderr.write("okgf: --pubkey needs the `cryptography` package (pip install 'okgf[verify]')\n")
            return 2
        except Exception as exc:  # noqa: BLE001 - surface any key-loading failure
            sys.stderr.write(f"okgf: could not load public key: {exc}\n")
            return 2

    report = Report()
    for path in args.paths:
        validate_path(path, report, pubkey=pubkey)

    for problem in report.problems:
        stream = sys.stderr if problem.level == "error" else sys.stdout
        stream.write(str(problem) + "\n")

    n_err, n_warn = len(report.errors), len(report.warnings)
    summary = (
        f"okgf: {report.pages_checked} page(s), {report.bundles_checked} bundle(s), "
        f"{n_err} error(s), {n_warn} warning(s)"
    )
    print(summary)
    if n_err or (args.strict and n_warn):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
