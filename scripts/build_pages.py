"""Compatibility wrapper: the legacy Pages build moved to tools/build_legacy_pages.py.

Kept during the transition so existing commands (`python scripts/build_pages.py`) still work.
"""
import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.argv[0] = str(Path(__file__).resolve().parents[1] / "tools" / "build_legacy_pages.py")
    runpy.run_path(sys.argv[0], run_name="__main__")
