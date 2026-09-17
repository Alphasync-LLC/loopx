#!/usr/bin/env python3
"""Compatibility entry; run from the repository root or with it on PYTHONPATH."""
from benchmark.runtime.worker import main

if __name__ == "__main__":
    raise SystemExit(main())
