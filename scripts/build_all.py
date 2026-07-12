#!/usr/bin/env python3
"""Refresh data/ + public backup kit. Usage: python3 scripts/build_all.py"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    runpy.run_path(str(ROOT / "scripts" / "extract_data.py"), run_name="__main__")
    runpy.run_path(str(ROOT / "scripts" / "build_backup_kit.py"), run_name="__main__")
    print("Pipeline OK. Run: python3 server/app.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
