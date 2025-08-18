"""Module for updating Python docstrings using Claude Code CLI edit tool."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from auto_docs_action import git_operations

# Prompt template for docstring updates using Claude Code CLI edit tool
DOCSTRING_UPDATE_PROMPT_TEMPLATE = """Please add Google-style docstrings to ALL functions, classes, and methods in \
{file_path} that don't already have them.

Git diff context (what triggered this update):
```
{git_diff}
```

REQUIREMENTS - MUST FOLLOW EXACTLY:
1. ONLY edit the file {file_path} - no other files
2. ADD docstrings to EVERY function, class, and method in {file_path} that lacks a docstring
3. Follow Google-style docstring conventions exactly
4. Include Args, Returns, and Raises sections as appropriate
5. Add comprehensive type information in docstrings that complements type hints
6. CRITICAL: Do not modify function signatures, imports, or any logic - ONLY add docstrings
7. If a function/class/method already has a complete docstring, leave it unchanged
8. If a function/class/method already has an incomplete docstring, improve it to full Google-style format
9. Process the ENTIRE file {file_path} - not just the changed areas from the diff

IMPORTANT: You must add docstrings to ALL functions/classes/methods in the file that don't have them, \
regardless of whether they appear in the git diff or not. The diff is just context for why this file needs updates.

Use the Edit tool to make the changes directly to {file_path}. Add comprehensive documentation to improve code quality."""


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
        logging.info(f"🔄 Starting update_docstrings for {file_path}")

        # Store original content to detect changes
        logging.debug(f"Reading original content from {file_path}")
        original_content = file_path.read_text()
        logging.debug(f"Original content length: {len(original_content)} characters")

        # Get git diff for the file to understand what changed
        logging.info(f"🔍 Getting git diff for {file_path}")
        git_diff = git_operations.get_file_diff(file_path)
        logging.info(f"Git diff length: {len(git_diff)} characters")

        # If no diff available, skip processing (no changes to analyze)
        if not git_diff.strip():
            logging.info(f"ℹ️ No git diff available for {file_path}, skipping docstring updates")
            return DocstringUpdateResult(success=True, updated_content=None)

        # Create prompt for Claude Code CLI with diff context
        logging.info(f"📝 Creating prompt for {file_path}")
        prompt = _create_docstring_prompt(file_path, git_diff)
        logging.debug(f"Prompt length: {len(prompt)} characters")

        # Execute Claude Code CLI with edit tool functionality
        logging.info(f"🤖 Executing Claude CLI for {file_path}")
        result = _execute_claude_cli(prompt, file_path, claude_command)
        logging.info(f"✅ Claude CLI execution completed for {file_path}, success={result.success}")

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
        # Build Claude Code CLI command with print mode, permissions, and JSON output
        cmd = [claude_command, "-p", prompt, "--verbose", "--output-format", "json", "--allowedTools", "Edit", "Read"]

        logging.info(f"🤖 Executing Claude Code CLI edit tool for {file_path}")
        logging.debug(f"Command: {' '.join(cmd)}")
        logging.info(f"Prompt being sent to Claude (first 500 chars): {prompt[:500]}...")
        logging.info(f"Full prompt length: {len(prompt)} characters")

        # Execute the command in the file's directory so Claude can access the file
        logging.info(f"Executing command in directory: {file_path.parent}")
        logging.info(f"Full command: {' '.join(cmd)}")

        # Add shorter timeout to prevent hanging - if Claude hangs, fail fast
        timeout_seconds = 120  # 2 minutes instead of 5
        logging.info(f"Running with timeout: {timeout_seconds} seconds")

        result = subprocess.run(cmd, cwd=file_path.parent, capture_output=True, text=True, timeout=timeout_seconds)

        # Always log Claude's output and errors for debugging
        logging.info(f"✅ Claude CLI return code: {result.returncode}")
        if result.stdout:
            # Truncate very long output for readability
            stdout_preview = result.stdout[:1000] + "..." if len(result.stdout) > 1000 else result.stdout
            logging.info(f"Claude stdout (first 1000 chars): {stdout_preview}")
            logging.info(f"Full stdout length: {len(result.stdout)} characters")
        else:
            logging.info("Claude stdout: (empty)")

        if result.stderr:
            logging.error(f"Claude stderr: {result.stderr}")
        else:
            logging.info("Claude stderr: (empty)")

        if result.returncode != 0:
            error_msg = f"Claude Code CLI failed with return code {result.returncode}"
            if result.stderr:
                error_msg += f": {result.stderr.strip()}"
            elif result.stdout:
                error_msg += f". Output: {result.stdout.strip()}"

            logging.error(error_msg)
            return DocstringUpdateResult(success=False, error_message=error_msg)

        # With edit tool approach, Claude modifies the file directly
        # Success is indicated by return code 0
        logging.info(f"✅ Claude Code CLI completed successfully for {file_path}")
        return DocstringUpdateResult(success=True)

    except subprocess.TimeoutExpired as e:
        error_msg = f"Claude Code CLI timed out for {file_path} after {timeout_seconds} seconds"
        logging.error(error_msg)
        logging.error(f"Timeout details: {e}")
        return DocstringUpdateResult(success=False, error_message=error_msg)
    except Exception as e:
        logging.error(f"Error executing Claude Code CLI: {e}")
        return DocstringUpdateResult(success=False, error_message=f"CLI execution error: {e}")
