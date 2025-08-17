"""Clean tests for git operations without directory issues."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

import git_operations


def test_get_changed_py_files_with_auto_docs_commit():
    """Test that the logic works with mocked git operations."""
    with (
        patch("git_operations.get_last_auto_docs_commit") as mock_last_commit,
        patch("git_operations.cmd_output") as mock_cmd_output,
    ):

        # Mock finding an auto-docs commit
        mock_last_commit.return_value = "abc123"
        mock_cmd_output.return_value = (0, "file1.py\nfile2.py\n", "")

        result = git_operations.get_changed_py_files()

        assert len(result) == 2
        assert result[0].name == "file1.py"
        assert result[1].name == "file2.py"
        mock_cmd_output.assert_called_with("git", "diff", "--name-only", "abc123", "HEAD")


def test_get_changed_py_files_no_auto_docs_commit():
    """Test fallback to all files when no auto-docs commit exists."""
    with (
        patch("git_operations.get_last_auto_docs_commit") as mock_last_commit,
        patch("git_operations.cmd_output") as mock_cmd_output,
    ):

        # Mock no auto-docs commit found
        mock_last_commit.return_value = None
        mock_cmd_output.return_value = (0, "file1.py\nfile2.py\nfile3.py\n", "")

        result = git_operations.get_changed_py_files()

        assert len(result) == 3
        mock_cmd_output.assert_called_with("git", "ls-files", "*.py")


def test_get_file_diff_with_auto_docs_commit():
    """Test getting file diff when auto-docs commit exists."""
    with (
        patch("git_operations.get_last_auto_docs_commit") as mock_last_commit,
        patch("git_operations.cmd_output") as mock_cmd_output,
    ):

        # Mock finding an auto-docs commit
        mock_last_commit.return_value = "abc123"
        mock_cmd_output.return_value = (0, "diff content here", "")

        result = git_operations.get_file_diff(Path("test.py"))

        assert result == "diff content here"
        mock_cmd_output.assert_called_with("git", "diff", "abc123", "HEAD", "test.py")


def test_get_file_diff_no_auto_docs_commit():
    """Test getting file diff when no auto-docs commit exists."""
    with patch("git_operations.get_last_auto_docs_commit") as mock_last_commit:

        # Mock no auto-docs commit found
        mock_last_commit.return_value = None

        result = git_operations.get_file_diff(Path("test.py"))

        assert result == ""


def test_get_last_auto_docs_commit_patterns():
    """Test that different author patterns are tried."""
    with patch("git_operations.cmd_output") as mock_cmd_output:

        # First pattern fails, second succeeds
        mock_cmd_output.side_effect = [
            Exception("Pattern 1 failed"),
            (0, "abc123\n", ""),  # Second pattern succeeds
        ]

        result = git_operations.get_last_auto_docs_commit()

        assert result == "abc123"
        assert mock_cmd_output.call_count == 2


def test_get_last_auto_docs_commit_no_matches():
    """Test when no auto-docs commits are found."""
    with patch("git_operations.cmd_output") as mock_cmd_output:

        # All patterns fail
        mock_cmd_output.side_effect = [
            (0, "", ""),  # Empty output
            Exception("Pattern failed"),
            Exception("Pattern failed"),
        ]

        result = git_operations.get_last_auto_docs_commit()

        assert result is None
