# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GitHub Action that automatically updates Python docstrings using Claude Code CLI. Uses subprocess for git operations, AST validation for safety, and retry logic for reliability.

## Repository Structure & Implementation

```
auto-docs-action/
├── main.py                     # Entry point - orchestrates complete workflow
├── git_operations.py           # Git commands via subprocess (pre-commit pattern)
├── ast_validator.py            # AST-based safety validation
├── docstring_updater.py        # Claude Code CLI interface
├── file_processor.py           # Single file retry logic orchestrator
├── action.yml                  # GitHub Action composite configuration
├── tests/                      # Comprehensive test suite
│   ├── conftest.py            # Shared fixtures (temp git repos, sample files)
│   ├── unit/                  # Component tests (real functionality, minimal mocks)
│   └── integration/           # Full workflow tests
├── TODO.md                    # Detailed implementation tasks
├── IMPLEMENTATION_NOTES.md    # Script architecture & skeleton code
├── TESTING_STRATEGY.md        # Testing approach & examples
└── pyproject.toml            # UV dependencies + dev tools (pytest, pre-commit)
```

## Commands

This is a UV-managed Python project:

- `uv sync --dev` - Install all dependencies including dev tools
- `uv run main.py` - Run the main action script
- `uv run pytest` - Run test suite
- `uv run pytest tests/unit/` - Run unit tests only
- `uv run pytest tests/integration/` - Run integration tests only
- `uv run pytest --cov=.` - Run tests with coverage
- `uv run pre-commit run --all-files` - Run code quality checks

## Development Workflow

The project uses UV for dependency management. Install with `uv sync --dev` before development.

### Key Implementation Details
- **Git Operations**: Use subprocess calls (following pre-commit pattern), not GitPython
- **Claude Code CLI**: `claude -p <prompt> --output-format json --max-turns 3`
- **AST Validation**: Mathematical proof that only docstrings changed
- **Retry Logic**: Max 2 attempts per file, using `git restore` to clean state between attempts
- **Testing**: Real functionality with minimal mocking (only mock Claude Code CLI calls)

### Code Standards
- Use type hints throughout the codebase (`from __future__ import annotations`)
- Follow Google-style docstrings for all functions and classes
- Use dataclasses for structured return types
- Implement comprehensive logging for debugging and monitoring
- Pre-commit hooks: black, flake8, isort, mypy

## Documentation Management

**IMPORTANT**: Always check the contents of all markdown files (TODO.md, IMPLEMENTATION_NOTES.md, TESTING_STRATEGY.md, README.md) when starting work. These contain critical implementation details, progress tracking, and architectural decisions. Update them as you implement features and make discoveries. The markdown files serve as the project's knowledge base and must be kept current.
