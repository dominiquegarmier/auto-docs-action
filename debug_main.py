#!/usr/bin/env python3
"""Minimal debug version of main.py to isolate the issue."""

from __future__ import annotations

import os
import sys
from pathlib import Path

print("🔍 Debug script starting...", flush=True)
print(f"Python version: {sys.version}", flush=True)
print(f"Working directory: {Path.cwd()}", flush=True)
print(f"Script location: {Path(__file__).resolve()}", flush=True)

# Test basic imports
try:
    print("Testing basic imports...", flush=True)
    import logging

    print("✅ logging imported", flush=True)

    import subprocess

    print("✅ subprocess imported", flush=True)

    from pathlib import Path

    print("✅ pathlib imported", flush=True)

    # Test our module imports
    print("Testing our module imports...", flush=True)

    import git_operations

    print("✅ git_operations imported", flush=True)

    from file_processor import FileProcessor

    print("✅ FileProcessor imported", flush=True)

    print("✅ All imports successful!", flush=True)

except Exception as e:
    print(f"❌ Import failed: {e}", flush=True)
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Test basic functionality
try:
    print("Testing basic functionality...", flush=True)

    # Check if we're in a git repo
    if Path(".git").exists():
        print("✅ Git repository detected", flush=True)
    else:
        print("❌ No git repository found", flush=True)
        sys.exit(1)

    # Test git operations
    print("Testing git operations...", flush=True)
    changed_files = git_operations.get_changed_py_files()
    print(f"✅ Found {len(changed_files)} Python files", flush=True)

    print("🎉 Debug script completed successfully!", flush=True)

except Exception as e:
    print(f"❌ Functionality test failed: {e}", flush=True)
    import traceback

    traceback.print_exc()
    sys.exit(1)

print("✅ Debug script finished successfully", flush=True)
