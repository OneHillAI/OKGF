"""Make a fresh source checkout importable as the ``okgf`` package during tests.

The normal path is to install the package first (``pip install -e .``), which makes this a no-op.
This hook additionally lets ``python -m pytest`` work straight from an uninstalled checkout by putting
the repository root on ``sys.path``.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
