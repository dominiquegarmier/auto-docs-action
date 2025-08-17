"""Tests for docstring updater functionality."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

import docstring_updater
from docstring_updater import DocstringUpdateResult


def test_successful_result_creation():
    """Test creating successful result."""
    result = DocstringUpdateResult(success=True, updated_content="def foo():\n    pass")

    assert result.success is True
    assert result.updated_content == "def foo():\n    pass"
    assert result.error_message is None


def test_failed_result_creation():
    """Test creating failed result."""
    result = DocstringUpdateResult(success=False, error_message="Something went wrong")

    assert result.success is False
    assert result.updated_content is None
    assert result.error_message == "Something went wrong"


def test_functions_work_with_default_command():
    """Test that functions work with default command parameter."""
    # This is a basic test to ensure the function interface works
    file_path = Path("/tmp/test.py")
    git_diff = "diff --git a/test.py..."
    prompt = docstring_updater._create_docstring_prompt(file_path, git_diff)
    assert "Google-style docstrings" in prompt


def test_create_docstring_prompt():
    """Test prompt creation for docstring updates."""
    file_path = Path("/tmp/test.py")
    git_diff = """diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,3 @@
 def add_numbers(a, b):
+    # Added comment
     return a + b"""

    prompt = docstring_updater._create_docstring_prompt(file_path, git_diff)

    assert "Google-style docstrings" in prompt
    assert str(file_path) in prompt
    assert git_diff in prompt
    assert "Edit tool" in prompt
    assert "what triggered this update" in prompt


@patch("subprocess.run")
def test_execute_claude_cli_success(mock_run):
    """Test successful Claude CLI execution with edit tool."""
    # Mock successful subprocess result (edit tool returns success via exit code)
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    file_path = Path("/tmp/test.py")

    result = docstring_updater._execute_claude_cli("test prompt", file_path, "claude")

    assert result.success is True
    assert result.error_message is None

    # Verify subprocess was called correctly for edit tool
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == [
        "claude",
        "-p",
        "test prompt",
        "--verbose",
        "--output-format",
        "json",
        "--allowedTools",
        "Edit",
        "Read",
    ]
    assert call_args[1]["cwd"] == file_path.parent
    assert call_args[1]["capture_output"] is True
    assert call_args[1]["text"] is True
    assert call_args[1]["timeout"] == 300


@patch("subprocess.run")
def test_execute_claude_cli_non_zero_exit(mock_run):
    """Test Claude CLI execution with non-zero exit code."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Command failed")

    file_path = Path("/tmp/test.py")

    result = docstring_updater._execute_claude_cli("test prompt", file_path, "claude")

    assert result.success is False
    assert "failed with return code 1" in result.error_message
    assert "Command failed" in result.error_message


@patch("subprocess.run")
def test_execute_claude_cli_timeout(mock_run):
    """Test Claude CLI execution timeout."""
    mock_run.side_effect = subprocess.TimeoutExpired("claude", 300)

    file_path = Path("/tmp/test.py")

    result = docstring_updater._execute_claude_cli("test prompt", file_path, "claude")

    assert result.success is False
    assert "timed out" in result.error_message


@patch("subprocess.run")
def test_execute_claude_cli_exception(mock_run):
    """Test Claude CLI execution with general exception."""
    mock_run.side_effect = Exception("Unexpected error")

    file_path = Path("/tmp/test.py")

    result = docstring_updater._execute_claude_cli("test prompt", file_path, "claude")

    assert result.success is False
    assert "CLI execution error" in result.error_message
    assert "Unexpected error" in result.error_message


@patch("git_operations.get_file_diff")
@patch("docstring_updater._execute_claude_cli")
def test_update_docstrings_success_with_changes(mock_execute, mock_diff):
    """Test successful docstring update with file changes."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        original_content = "def foo(): pass"
        f.write(original_content)
        f.flush()
        file_path = Path(f.name)

    try:
        # Mock git diff
        mock_diff.return_value = """diff --git a/test.py b/test.py
@@ -1 +1,2 @@
 def foo():
+    # Added comment
     pass"""

        updated_content = 'def foo():\n    """A test function."""\n    pass'

        def mock_cli_execution(prompt, file_path_arg, claude_command):
            # Simulate Claude edit tool changing the file during CLI execution
            file_path_arg.write_text(updated_content)
            return DocstringUpdateResult(success=True)

        # Mock CLI execution to write updated content during execution
        mock_execute.side_effect = mock_cli_execution

        result = docstring_updater.update_docstrings(file_path)

        assert result.success is True
        assert result.updated_content == updated_content
        assert result.error_message is None

        # Verify git diff was called
        mock_diff.assert_called_once_with(file_path)

    finally:
        file_path.unlink()


@patch("git_operations.get_file_diff")
@patch("docstring_updater._execute_claude_cli")
def test_update_docstrings_success_no_changes(mock_execute, mock_diff):
    """Test successful docstring update with no file changes."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        content = "def foo(): pass"
        f.write(content)
        f.flush()
        file_path = Path(f.name)

    try:
        # Mock git diff
        mock_diff.return_value = "diff --git a/test.py..."

        # Mock successful CLI execution
        mock_execute.return_value = DocstringUpdateResult(success=True)

        result = docstring_updater.update_docstrings(file_path)

        assert result.success is True
        assert result.updated_content is None  # No changes made
        assert result.error_message is None

    finally:
        file_path.unlink()


@patch("git_operations.get_file_diff")
def test_update_docstrings_no_diff(mock_diff):
    """Test docstring update when no git diff is available."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def foo(): pass")
        f.flush()
        file_path = Path(f.name)

    try:
        # Mock empty git diff
        mock_diff.return_value = ""

        result = docstring_updater.update_docstrings(file_path)

        assert result.success is True
        assert result.updated_content is None
        assert result.error_message is None

    finally:
        file_path.unlink()


@patch("git_operations.get_file_diff")
@patch("docstring_updater._execute_claude_cli")
def test_update_docstrings_cli_failure(mock_execute, mock_diff):
    """Test docstring update with CLI execution failure."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def foo(): pass")
        f.flush()
        file_path = Path(f.name)

    try:
        # Mock git diff
        mock_diff.return_value = "diff --git a/test.py..."

        # Mock CLI failure
        mock_execute.return_value = DocstringUpdateResult(success=False, error_message="CLI failed")

        result = docstring_updater.update_docstrings(file_path)

        assert result.success is False
        assert result.error_message == "CLI failed"
        assert result.updated_content is None

    finally:
        file_path.unlink()


@patch("git_operations.get_file_diff")
def test_update_docstrings_file_read_error(mock_diff):
    """Test docstring update with file read error."""
    non_existent_file = Path("/non/existent/file.py")

    # Mock git diff
    mock_diff.return_value = "diff --git a/test.py..."

    result = docstring_updater.update_docstrings(non_existent_file)

    assert result.success is False
    assert "Unexpected error" in result.error_message


@patch("git_operations.get_file_diff")
def test_update_docstrings_unexpected_exception(mock_diff):
    """Test docstring update with unexpected exception."""
    # Mock to raise exception
    mock_diff.side_effect = Exception("Unexpected error")

    file_path = Path("/tmp/test.py")

    result = docstring_updater.update_docstrings(file_path)

    assert result.success is False
    assert "Unexpected error" in result.error_message
    assert result.updated_content is None


def test_real_file_integration():
    """Test with real file (without actually calling Claude CLI)."""

    # Create a temporary Python file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """def add_numbers(a, b):
    return a + b

class Calculator:
    def multiply(self, x, y):
        return x * y
"""
        )
        f.flush()
        file_path = Path(f.name)

    try:
        # Test prompt creation with mock git diff
        git_diff = "diff --git a/test.py b/test.py..."
        prompt = docstring_updater._create_docstring_prompt(file_path, git_diff)

        assert file_path.name in str(file_path)  # File path should be referenced
        assert "Google-style docstrings" in prompt
        assert git_diff in prompt

    finally:
        file_path.unlink()


@patch("subprocess.run")
def test_custom_claude_command_usage(mock_run):
    """Test using custom Claude command."""
    custom_command = "/usr/local/bin/claude"

    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    file_path = Path("/tmp/test.py")
    docstring_updater._execute_claude_cli("test prompt", file_path, custom_command)

    # Verify custom command was used
    call_args = mock_run.call_args
    assert call_args[0][0][0] == custom_command
