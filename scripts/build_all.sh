#!/bin/bash
# Prefer: python3 scripts/build_all.py
cd "$(dirname "$0")/.."
exec python3 scripts/build_all.py
