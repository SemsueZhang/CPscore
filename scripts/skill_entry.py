#!/usr/bin/env python3
"""Installed skill adapter. This file has a single maintained source."""
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parents[4]
runtime = root / ".cpscore" / "runtime"
if not (runtime / "cpscore" / "__main__.py").is_file():
    raise SystemExit("CPscore shared runtime is missing. Reinstall from the CPscore checkout.")
sys.path.insert(0, str(runtime))
sys.dont_write_bytecode = True
runpy.run_module("cpscore", run_name="__main__")
