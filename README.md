[![Tests](https://github.com/dominiquegarmier/auto-docs-action/actions/workflows/test.yml/badge.svg)](https://github.com/dominiquegarmier/auto-docs-action/actions/workflows/test.yml)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/dominiquegarmier/auto-docs-action/main.svg)](https://results.pre-commit.ci/latest/github/dominiquegarmier/auto-docs-action/main)

# Auto-Docs Action

Automatically update Python docstrings using Claude Code CLI. This GitHub Action detects changed Python files and adds comprehensive Google-style docstrings to functions, classes, and methods that lack proper documentation.

## Features

- Smart detection: Only processes files changed since the last auto-docs commit
- AI-powered: Uses Claude Code CLI to generate high-quality, context-aware docstrings
- Safe updates: AST validation ensures only docstrings are modified, never function logic
- Retry logic: Automatic retries with file restoration for reliability
- Real-time logs: See processing progress live in GitHub Actions
- Multi-file support: Processes multiple files concurrently with proper error handling
- Smart git handling: Automatically fetches PR base branches for accurate diff detection

## Quick Start

Add this workflow to your repository at `.github/workflows/auto-docs.yml`:

```yaml
name: Auto-Docs

on:
  push:
    branches: [main]
    paths: ["**.py"]
  pull_request:
    types: [opened, synchronize]
    branches: [main]
    paths: ["**.py"]
  workflow_dispatch: # Allow manual triggering

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: write

jobs:
  auto-docs:
    runs-on: ubuntu-latest
    if: github.actor != 'github-actions[bot]'

    steps:
      - name: Checkout repository
        uses: actions/checkout@v5
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          ref: ${{ github.head_ref || github.ref }}
          fetch-depth: 0

      - name: Auto-update docstrings
        uses: dominiquegarmier/auto-docs-action@main
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          max_retries: 2
```

### With Pre-commit Hooks

To run pre-commit hooks before committing (e.g., formatters, linters):

```yaml
      - name: Auto-update docstrings
        uses: dominiquegarmier/auto-docs-action@main
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          pre_commit_hook: "uv add pre-commit && pre-commit run --all-files"
```

## Setup

1. Get an Anthropic API key at [console.anthropic.com](https://console.anthropic.com)
2. Add `ANTHROPIC_API_KEY` to your repository secrets (Settings → Secrets and variables → Actions)
3. Add the workflow file above to your repository
4. The action will trigger on Python file changes and automatically push docstring updates

## Configuration

### Inputs

| Input               | Description                              | Required | Default  |
| ------------------- | ---------------------------------------- | -------- | -------- |
| `anthropic_api_key` | Your Anthropic API key for Claude Code   | Yes      | -        |
| `max_retries`       | Maximum retry attempts per file          | No       | `2`      |
| `claude_command`    | Path to Claude Code CLI executable       | No       | `claude` |
| `pre_commit_hook`   | Command to run before committing changes | No       | -        |

### Outputs

| Output             | Description                            |
| ------------------ | -------------------------------------- |
| `files_processed`  | Total number of Python files processed |
| `files_successful` | Number of files successfully updated   |
| `files_failed`     | Number of files that failed processing |

## How It Works

1. Detects Python files changed since the last `github-actions[bot]` commit
2. Generates git diff for each file to understand what changed
3. Sends files to Claude Code CLI with context-aware prompts
4. Validates changes using AST parsing to ensure only docstrings were modified
5. Optionally runs pre-commit hooks before committing (if configured)
6. Creates commit with updated docstrings and pushes back to repository
7. For pull requests, automatically pushes updates to PR branch (like pre-commit.ci)
8. Automatically ensures PR base branches are available for accurate diff detection

### First Run

On the first run, the action processes all Python files to establish a baseline of documented code.

### Diff Detection

- Push events: Compares against the last `github-actions[bot]` commit
- Pull requests: Compares against PR base commit or last bot commit (whichever has less history)
- Handles multiple commits between runs
- Automatically fetches PR base branches when needed

### Pre-commit Hook Support

The `pre_commit_hook` input allows you to run any command before the action commits changes. This is useful for:
- Running code formatters (black, isort, etc.)
- Running linters (flake8, pylint, etc.)
- Running pre-commit hooks if your project uses them
- Any custom validation or formatting

The hook command runs after docstrings are updated but before changes are committed. If the hook fails with a non-zero exit code, the changes are still committed (similar to how pre-commit.ci works). Hook output is logged for debugging.

## Example

```python
# Before
def calculate_total(items, tax_rate):
    return sum(items) * (1 + tax_rate)

# After
def calculate_total(items, tax_rate):
    """Calculate the total cost including tax for a list of items.

    Args:
        items: List of item prices as numeric values.
        tax_rate: Tax rate as a decimal (e.g., 0.1 for 10% tax).

    Returns:
        The total cost including tax as a float.
    """
    return sum(items) * (1 + tax_rate)
```
