# Auto-Docs Action

Automatically update Python docstrings using Claude Code CLI. This GitHub Action detects changed Python files and adds comprehensive Google-style docstrings to functions, classes, and methods that lack proper documentation.

## Features

- **🔍 Smart Detection**: Only processes files that have changed since the last auto-docs commit
- **🤖 AI-Powered**: Uses Claude Code CLI to generate high-quality, context-aware docstrings
- **✅ Safe Updates**: AST validation ensures only docstrings are modified, never function logic
- **🔄 Retry Logic**: Automatic retries with file restoration for reliability
- **📊 Real-time Logs**: See processing progress live in GitHub Actions
- **🔀 Multi-file Support**: Processes multiple files concurrently with proper error handling

## Quick Start

Add this workflow to your repository at `.github/workflows/auto-docs.yml`:

```yaml
name: Auto-Docs

on:
  push:
    branches: [ main ]
    paths: [ '**.py' ]
  pull_request:
    types: [ opened, synchronize ]
    branches: [ main ]
    paths: [ '**.py' ]
  workflow_dispatch: # Allow manual triggering

# Cancel older runs if new commits are pushed
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
          ref: ${{ github.head_ref || github.ref }}  # Checkout PR branch or push branch
          fetch-depth: 32  # Need history for git diff (increase if you have more than 32 commits between auto-docs runs)

      - name: Auto-update docstrings
        uses: dominiquegarmier/auto-docs-action@main
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          max_retries: 2
```

## Setup

1. **Get Anthropic API Key**: Sign up at [console.anthropic.com](https://console.anthropic.com) and create an API key
2. **Add Secret**: Go to your repository Settings → Secrets and variables → Actions, and add `ANTHROPIC_API_KEY`
3. **Add Workflow**: Create the workflow file above in your repository
4. **Push Changes**: The action will trigger on Python file changes and automatically push docstring updates

## Configuration

### Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `anthropic_api_key` | Your Anthropic API key for Claude Code | Yes | - |
| `max_retries` | Maximum retry attempts per file | No | `2` |
| `claude_command` | Path to Claude Code CLI executable | No | `claude` |

### Outputs

| Output | Description |
|--------|-------------|
| `files_processed` | Total number of Python files processed |
| `files_successful` | Number of files successfully updated |
| `files_failed` | Number of files that failed processing |

## How It Works

1. **Detection**: Identifies Python files changed since the last `github-actions[bot]` commit
2. **Analysis**: For each file, generates a git diff to understand what changed
3. **Processing**: Sends files to Claude Code CLI with context-aware prompts
4. **Validation**: Uses AST parsing to ensure only docstrings were modified
5. **Commit**: Creates a commit with updated docstrings and pushes back to the repository
6. **Auto-fix PRs**: For pull requests, automatically pushes updates to the PR branch (like pre-commit.ci)

### First Run

On the first run (no previous auto-docs commits), the action processes all Python files in the repository to establish a baseline of documented code.

### Smart Diff Detection

The action uses intelligent diff detection:
- **Push to main**: Compares against the last commit made by `github-actions[bot]`
- **Pull requests**: Compares against PR base commit or last bot commit (whichever has less history)
- Handles multiple commits between auto-docs runs
- Prevents processing unchanged files for efficiency

## Example Output

The action generates comprehensive Google-style docstrings:

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

## Safety & Validation

- **AST Validation**: Mathematically proves only docstrings were changed
- **Syntax Checking**: Ensures all modifications result in valid Python
- **File Restoration**: Automatically restores files if validation fails
- **Retry Logic**: Up to 3 attempts per file with clean state between tries
- **Race Condition Protection**: Checks for concurrent commits before pushing

## Limitations

- Requires Anthropic API key (Claude usage costs apply)
- Only processes Python files (`.py` extension)
- Designed for Google-style docstrings
- Requires `contents: write` permission for commits

## Contributing

Issues and pull requests are welcome! Please ensure all tests pass and follow the existing code style.

## License

MIT License - see [LICENSE](LICENSE) file for details.
