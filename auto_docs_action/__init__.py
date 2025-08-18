"""Auto-docs GitHub Action package.

A GitHub Action that automatically updates Python docstrings using Claude Code CLI.
"""

from __future__ import annotations

__version__ = "1.0.0"

from .main import main

__all__ = ["main"]
