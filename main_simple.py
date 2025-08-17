#!/usr/bin/env python3
from __future__ import annotations

print("Script started", flush=True)

try:
    import sys

    print(f"Python: {sys.version}", flush=True)

    import os

    print(f"Working dir: {os.getcwd()}", flush=True)

    from pathlib import Path

    print(f"Git repo exists: {Path('.git').exists()}", flush=True)

    import git_operations

    print("git_operations imported", flush=True)

    files = git_operations.get_changed_py_files()
    print(f"Found {len(files)} files: {files}", flush=True)

    print("SUCCESS", flush=True)

except Exception as e:
    print(f"ERROR: {e}", flush=True)
    import traceback

    traceback.print_exc()
    sys.exit(1)
