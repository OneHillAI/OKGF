#!/usr/bin/env python3
"""Backwards-compatible shim for the OKGF validator.

The validator now lives in the installable ``okgf`` package: install it (``pip install okgf`` or see
``docs/INSTALL.md``) and run the ``okgf`` command, or ``python -m okgf``. This script is kept so that
existing invocations (``python tools/okgf_validate.py ...``) and imports keep working unchanged; it
re-exports the package API and delegates to it.
"""

from __future__ import annotations

import os
import sys

# Allow running straight from a source checkout without installing the package first.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from okgf.validate import *  # noqa: E402,F401,F403  (public API re-export)
from okgf.validate import (  # noqa: E402  explicit re-exports, including names used by callers/tests
    ENUMS,
    INDEX_FILE,
    LOG_FILE,
    RESERVED_FILES,
    SPEC_VERSION,
    Problem,
    Report,
    __version__,
    _canonical_bytes,
    _load_pubkey,
    _validate_signature,
    main,
    split_frontmatter,
    validate_bundle,
    validate_page,
    validate_path,
)

if __name__ == "__main__":
    raise SystemExit(main())
