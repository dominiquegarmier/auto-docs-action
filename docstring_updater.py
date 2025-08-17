"""Module for updating Python docstrings using Claude Code CLI edit tool."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

import git_operations

# Prompt template for docstring updates using Claude Code CLI edit tool
DOCSTRING_UPDATE_PROMPT_TEMPLATE = """Based on the git diff below, please add or improve Google-style docstrings \
for the functions/classes that were changed in {file_path}.

Git diff showing what changed:
```
{git_diff}
```

Requirements:
1. Only edit the file {file_path} - focus on the changed functions/classes shown in the diff
2. Follow Google-style docstring conventions exactly
3. Include Args, Returns, and Raises sections as appropriate
4. Add comprehensive type information in docstrings that complements type hints
5. CRITICAL: Do not modify function signatures, imports, or any logic - ONLY add/improve docstrings
6. If a function already has a complete Google-style docstring, leave it unchanged
7. For functions without docstrings that were changed, add complete Google-style docstrings
8. For functions with incomplete docstrings that were changed, improve them to full Google-style format
9. Focus only on the areas that changed according to the git diff

Use the Edit tool to make the changes directly to {file_path}. Focus on improving documentation quality \
for the changed code while preserving all existing functionality."""


@dataclass
class DocstringUpdateResult:
    """Result of docstring update operation."""

    success: bool
    updated_content: str | None = None
    error_message: str | None = None


def update_docstrings(file_path: Path, claude_command: str = "claude") -> DocstringUpdateResult:
    """Update docstrings in a Python file using Claude Code CLI edit tool.

    Args:
        file_path: Path to the Python file to update
        claude_command: Command to execute Claude Code CLI (default: "claude")

    Returns:
        DocstringUpdateResult with the operation outcome
    """
    try:
        # Store original content to detect changes
        original_content = file_path.read_text()

        # Get git diff for the file to understand what changed
        git_diff = git_operations.get_file_diff(file_path)

        # If no diff available, skip processing (no changes to analyze)
        if not git_diff.strip():
            logging.info(f"No git diff available for {file_path}, skipping docstring updates")
            return DocstringUpdateResult(success=True, updated_content=None)

        # Create prompt for Claude Code CLI with diff context
        prompt = _create_docstring_prompt(file_path, git_diff)

        # Execute Claude Code CLI with edit tool functionality
        result = _execute_claude_cli(prompt, file_path, claude_command)

        if result.success:
            # Check if file was modified by comparing content
            try:
                current_content = file_path.read_text()
                if current_content != original_content:
                    # File was modified by Claude
                    return DocstringUpdateResult(success=True, updated_content=current_content)
                else:
                    # No changes were made
                    return DocstringUpdateResult(success=True, updated_content=None)
            except Exception as e:
                logging.error(f"Error reading updated file {file_path}: {e}")
                return DocstringUpdateResult(success=False, error_message=f"Failed to read updated file: {e}")
        else:
            return result

    except Exception as e:
        logging.error(f"Error updating docstrings for {file_path}: {e}")
        return DocstringUpdateResult(success=False, error_message=f"Unexpected error: {e}")


def _create_docstring_prompt(file_path: Path, git_diff: str) -> str:
    """Create a prompt for Claude Code CLI to update docstrings.

    Args:
        file_path: Path to the Python file being processed
        git_diff: Git diff showing what changed in the file

    Returns:
        Formatted prompt string for Claude Code CLI
    """
    return DOCSTRING_UPDATE_PROMPT_TEMPLATE.format(file_path=file_path, git_diff=git_diff)


def _execute_claude_cli(prompt: str, file_path: Path, claude_command: str) -> DocstringUpdateResult:
    """Execute Claude Code CLI with the given prompt using edit tool functionality.

    Args:
        prompt: Prompt to send to Claude Code CLI
        file_path: Path to the file being processed
        claude_command: Command to execute Claude Code CLI

    Returns:
        DocstringUpdateResult with CLI execution outcome
    """
    try:
        # Build Claude Code CLI command for file editing
        cmd = [claude_command, prompt]

        logging.info(f"Executing Claude Code CLI edit tool for {file_path}")
        logging.debug(f"Command: {' '.join(cmd)}")

        # Execute the command in the file's directory so Claude can access the file
        result = subprocess.run(cmd, cwd=file_path.parent, capture_output=True, text=True, timeout=300)  # 5 minute timeout

        if result.returncode != 0:
            error_msg = f"Claude Code CLI failed with return code {result.returncode}"
            if result.stderr:
                error_msg += f": {result.stderr.strip()}"

            logging.error(error_msg)
            return DocstringUpdateResult(success=False, error_message=error_msg)

        # With edit tool approach, Claude modifies the file directly
        # Success is indicated by return code 0
        logging.info(f"Claude Code CLI completed successfully for {file_path}")
        return DocstringUpdateResult(success=True)

    except subprocess.TimeoutExpired:
        logging.error(f"Claude Code CLI timed out for {file_path}")
        return DocstringUpdateResult(success=False, error_message="Claude Code CLI operation timed out")
    except Exception as e:
        logging.error(f"Error executing Claude Code CLI: {e}")
        return DocstringUpdateResult(success=False, error_message=f"CLI execution error: {e}")
