"""OKGF store: a filesystem-backed reference knowledgebase for OKGF, with a zero-dependency HTTP API.

The on-disk OKGF bundle is the durable store; the API and query layer read the files directly. See
``docs/STORE.md``.
"""

from . import okf
from .server import make_handler, serve
from .store import ConformanceError, NotFound, OkgfStore, TransitionError

__all__ = [
    "OkgfStore",
    "ConformanceError",
    "NotFound",
    "TransitionError",
    "serve",
    "make_handler",
    "okf",
]
