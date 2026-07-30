"""OkgfStore: a filesystem-backed OKGF knowledgebase with ingest, retrieval, and the review lifecycle.

The bundle on disk (markdown pages plus `index.md` and `log.md`) is the durable store: portable, diffable,
ownable. Query, search, and the concept graph run over the files directly, so there is no separate database
to keep in sync. A page moves draft -> proposed -> approved; only `approved` pages are authoritative, and an
approval into a shared scope can be signed.
"""

from __future__ import annotations

import io
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from . import okf
from .okf import Page

RESERVED = {"index.md", "log.md", "principles.md", "schema.md"}


class ConformanceError(ValueError):
    """A page did not conform to the OKGF spec and was not written."""


class NotFound(KeyError):
    """No page exists for the given slug."""


class TransitionError(ValueError):
    """An illegal lifecycle transition (e.g. approving a page that is not proposed)."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OkgfStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        idx = self.root / "index.md"
        if not idx.exists():
            idx.write_text(f'---\nokf_version: "{okf.OKF_VERSION}"\n---\n# Index\n', encoding="utf-8")

    # --- storage ---

    def _path(self, slug: str) -> Path:
        return self.root / f"{slug}.md"

    def exists(self, slug: str) -> bool:
        return self._path(slug).exists()

    def get(self, slug: str) -> Page:
        p = self._path(slug)
        if not p.exists():
            raise NotFound(slug)
        return okf.parse(p.read_text(encoding="utf-8"), slug=slug)

    def _pages(self):
        for p in sorted(self.root.glob("*.md")):
            if p.name.lower() in RESERVED:
                continue
            yield okf.parse(p.read_text(encoding="utf-8"), slug=p.stem)

    def list(self, *, scope=None, review=None, tier=None, tag=None) -> list:
        """Retrieve pages, filtered by governance. This is the query that makes the store useful to an
        agent: ask for `scope=org, review=approved, tier=gold` and get back only trusted knowledge."""
        out = []
        for pg in self._pages():
            if scope and pg.scope != scope:
                continue
            if review and pg.review != review:
                continue
            if tier and pg.tier != tier:
                continue
            if tag and tag not in (pg.fm.get("tags") or []):
                continue
            out.append(pg)
        return out

    # --- ingest ---

    def put(
        self,
        slug=None,
        *,
        type="Concept",
        title="",
        body="",
        description=None,
        scope=None,
        review=None,
        tier=None,
        sources=None,
        tags=None,
        timestamp=None,
        extra=None,
        log_note=None,
    ) -> Page:
        """Ingest a page. New pages default to `draft`; the store governs everything it holds."""
        slug = slug or okf.slugify(title)
        if not slug:
            raise ValueError("a slug or title is required")
        fm = {"type": type or "Concept"}
        if title:
            fm["title"] = title
        if description:
            fm["description"] = description
        fm["timestamp"] = timestamp or _now_iso()
        if tags:
            fm["tags"] = list(tags)
        if scope:
            fm[okf.SCOPE] = scope
        fm[okf.REVIEW] = review or "draft"
        if tier:
            fm[okf.TIER] = tier
        if sources:
            fm[okf.SOURCES] = list(sources)
        if extra:
            fm.update(extra)
        existed = self.exists(slug)
        return self._write(Page(slug=slug, fm=fm, body=body or ""), log_note or ("update" if existed else "create"))

    def put_page(self, page: Page, log_note="write") -> Page:
        return self._write(page, log_note)

    def _write(self, page: Page, note: str) -> Page:
        errs = okf.conformance_errors(page)
        if errs:
            raise ConformanceError("; ".join(errs))
        self._path(page.slug).write_text(okf.serialize(page), encoding="utf-8")
        self._reindex_listing()
        self._append_log(f"{page.slug}: {note} (review={page.review}, scope={page.scope})")
        return self.get(page.slug)

    def delete(self, slug: str) -> None:
        p = self._path(slug)
        if not p.exists():
            raise NotFound(slug)
        p.unlink()
        self._reindex_listing()
        self._append_log(f"{slug}: delete")

    # --- lifecycle ---

    def propose(self, slug: str) -> Page:
        pg = self.get(slug)
        if pg.review not in (None, "draft"):
            raise TransitionError(f"can only propose a draft, not {pg.review!r}")
        pg.fm[okf.REVIEW] = "proposed"
        return self._write(pg, "propose")

    def approve(self, slug: str, *, private_key=None) -> Page:
        pg = self.get(slug)
        if pg.review != "proposed":
            raise TransitionError(f"can only approve a proposed page, not {pg.review!r}")
        pg.fm[okf.REVIEW] = "approved"
        if private_key is not None:
            pg.fm[okf.SIGNATURE] = okf.sign(pg, private_key)
        return self._write(pg, "approve" + (" (signed)" if private_key else ""))

    def reject(self, slug: str) -> Page:
        pg = self.get(slug)
        if pg.review != "proposed":
            raise TransitionError(f"can only reject a proposed page, not {pg.review!r}")
        pg.fm[okf.REVIEW] = "draft"
        pg.fm.pop(okf.SIGNATURE, None)
        return self._write(pg, "reject")

    def verify(self, slug: str, public_key) -> bool:
        return okf.verify(self.get(slug), public_key)

    # --- graph and search ---

    def links(self, slug: str) -> list:
        return okf.links(self.get(slug))

    def backlinks(self, slug: str) -> list:
        return sorted(pg.slug for pg in self._pages() if slug in okf.links(pg))

    def search(self, q, *, scope=None, review=None, tier=None, limit=50) -> list:
        q = (q or "").lower().strip()
        scored = []
        for pg in self.list(scope=scope, review=review, tier=tier):
            hay = f"{pg.title}\n{pg.body}".lower()
            if not q or q in hay:
                scored.append((hay.count(q) if q else 0, pg))
        scored.sort(key=lambda t: (-t[0], t[1].slug))
        return [pg for _, pg in scored[:limit]]

    # --- bundle io ---

    def export_tgz(self) -> bytes:
        """Pack the whole store into a portable, stable OKGF bundle (sorted, fixed mtime)."""
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            for p in sorted(self.root.glob("**/*")):
                if p.is_file():
                    data = p.read_bytes()
                    info = tarfile.TarInfo(str(p.relative_to(self.root)))
                    info.size = len(data)
                    info.mtime = 0
                    tf.addfile(info, io.BytesIO(data))
        return buf.getvalue()

    def import_tgz(self, data: bytes, *, default_scope=None) -> int:
        """Ingest content pages from a foreign OKGF/OKF bundle. Returns the count imported. Members with
        unsafe names or non-conformant pages are skipped."""
        n = 0
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tf:
            for m in tf.getmembers():
                if not m.isfile():
                    continue
                name = m.name.replace("\\", "/")
                if name.startswith("/") or ".." in name.split("/"):
                    continue
                base = name.rsplit("/", 1)[-1]
                if not base.lower().endswith(".md") or base.lower() in RESERVED:
                    continue
                fh = tf.extractfile(m)
                if fh is None:
                    continue
                page = okf.parse(fh.read().decode("utf-8", "replace"), slug=okf.slugify(base[:-3]))
                if not page.slug:
                    continue
                if default_scope and okf.SCOPE not in page.fm:
                    page.fm[okf.SCOPE] = default_scope
                if okf.conformance_errors(page):
                    continue
                self.put_page(page, log_note="import")
                n += 1
        return n

    # --- reserved bundle files ---

    def _reindex_listing(self) -> None:
        lines = [f'---\nokf_version: "{okf.OKF_VERSION}"\n---\n', "# Index\n"]
        for pg in sorted(self._pages(), key=lambda p: p.slug):
            lines.append(f"- [{pg.title or pg.slug}](/{pg.slug})")
        (self.root / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _append_log(self, msg: str) -> None:
        log = self.root / "log.md"
        head = "" if log.exists() else "# Log\n\n"
        with log.open("a", encoding="utf-8") as f:
            f.write(f"{head}- {_now_iso()} {msg}\n")
