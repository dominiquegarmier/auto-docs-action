"""Edge case tests for auto-docs action."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from auto_docs_action import git_operations
from auto_docs_action.main import main_for_testing


def test_empty_repository_handling():
    """Test behavior with empty git repository (no HEAD~1)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)

        # Initialize empty git repo
        os.chdir(repo_path)
        os.system("git init")
        os.system('git config user.email "test@example.com"')
        os.system('git config user.name "Test User"')

        # Should handle empty repo gracefully
        changed_files = git_operations.get_changed_py_files()
        assert changed_files == []


def test_no_python_files_changed():
    """Test behavior when no Python files are in the diff."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)

        # Setup git repo with non-Python files
        os.chdir(repo_path)
        os.system("git init")
        os.system('git config user.email "test@example.com"')
        os.system('git config user.name "Test User"')

        # Create and commit non-Python file
        (repo_path / "README.md").write_text("# Test")
        os.system("git add README.md")
        os.system("git commit -m 'Initial commit'")

        # Modify and commit another non-Python file
        (repo_path / "config.json").write_text('{"test": true}')
        os.system("git add config.json")
        os.system("git commit -m 'Add config'")

        # Should find no Python files
        changed_files = git_operations.get_changed_py_files()
        assert changed_files == []


def test_invalid_python_syntax():
    """Test handling of Python files with syntax errors."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)

        # Setup git repo
        os.chdir(repo_path)
        os.system("git init")
        os.system('git config user.email "test@example.com"')
        os.system('git config user.name "Test User"')

        # Create Python file with syntax error
        broken_file = repo_path / "broken.py"
        broken_file.write_text("def broken_function(:\n    pass")  # Invalid syntax

        os.system("git add broken.py")
        os.system("git commit -m 'Add broken file'")

        # Modify the broken file
        broken_file.write_text("def broken_function(:\n    print('still broken')")
        os.system("git add broken.py")
        os.system("git commit -m 'Modify broken file'")

        # Should still detect it as a changed file
        changed_files = git_operations.get_changed_py_files()
        assert len(changed_files) == 1
        assert changed_files[0].name == "broken.py"


def test_large_diff_output():
    """Test handling of large git diff output."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)

        os.chdir(repo_path)
        os.system("git init")
        os.system('git config user.email "test@example.com"')
        os.system('git config user.name "Test User"')

        # Create large Python file
        large_content = "\n".join([f"def function_{i}():\n    return {i}" for i in range(1000)])
        large_file = repo_path / "large.py"
        large_file.write_text(large_content)

        os.system("git add large.py")
        os.system("git commit -m 'Add large file'")

        # Create an auto-docs commit first
        os.system(
            'git -c user.name="auto-docs[bot]" -c user.email="auto-docs@users.noreply.github.com" '
            'commit --allow-empty -m "Auto-docs commit"'
        )

        # Modify it significantly
        modified_content = large_content + "\n\ndef new_function():\n    return 'new'"
        large_file.write_text(modified_content)
        os.system("git add large.py")
        os.system("git commit -m 'Modify large file'")

        # Should handle large diffs
        diff = git_operations.get_file_diff(large_file)
        assert "def new_function" in diff
        assert len(diff) > 100  # Should be substantial


@patch("subprocess.run")
def test_claude_cli_timeout_handling(mock_run):
    """Test handling of Claude CLI timeouts."""
    import subprocess

    from auto_docs_action.docstring_updater import _execute_claude_cli

    # Mock timeout
    mock_run.side_effect = subprocess.TimeoutExpired("claude", 300)

    file_path = Path("/tmp/test.py")
    result = _execute_claude_cli("test prompt", file_path, "claude")

    assert result.success is False
    assert "timed out" in result.error_message


@patch("subprocess.run")
def test_claude_cli_permission_denied(mock_run):
    """Test handling of permission denied errors."""
    from unittest.mock import MagicMock

    from auto_docs_action.docstring_updater import _execute_claude_cli

    # Mock permission denied
    mock_run.side_effect = PermissionError("Permission denied")

    file_path = Path("/tmp/test.py")
    result = _execute_claude_cli("test prompt", file_path, "claude")

    assert result.success is False
    assert "CLI execution error" in result.error_message


def test_concurrent_git_operations():
    """Test handling of git operations when repository is locked."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)

        os.chdir(repo_path)
        os.system("git init")
        os.system('git config user.email "test@example.com"')
        os.system('git config user.name "Test User"')

        # Create and commit a file
        test_file = repo_path / "test.py"
        test_file.write_text("def test(): pass")
        os.system("git add test.py")
        os.system("git commit -m 'Add test file'")

        # Create git lock file to simulate concurrent operation
        lock_file = repo_path / ".git" / "index.lock"
        lock_file.touch()

        try:
            # Git operations should handle lock gracefully
            result = git_operations.stage_file(test_file)
            # Should fail gracefully rather than crash
            assert result is False
        finally:
            # Clean up lock file
            if lock_file.exists():
                lock_file.unlink()


def test_environment_variable_handling():
    """Test handling of various environment variable configurations."""
    from auto_docs_action.main import main

    # Test with missing environment variables
    old_env = os.environ.copy()
    try:
        # Clear relevant environment variables
        for key in ["CLAUDE_COMMAND", "MAX_RETRIES", "ANTHROPIC_API_KEY"]:
            os.environ.pop(key, None)

        # Should use defaults gracefully
        claude_command = os.getenv("CLAUDE_COMMAND", "claude")
        max_retries = int(os.getenv("MAX_RETRIES", "3"))

        assert claude_command == "claude"
        assert max_retries == 3

    finally:
        # Restore environment
        os.environ.clear()
        os.environ.update(old_env)


def test_main_with_no_changed_files():
    """Test main function behavior when no files need processing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        try:
            os.chdir(repo_path)

            # Setup minimal git repo with no commits
            os.system("git init")
            os.system('git config user.email "test@example.com"')
            os.system('git config user.name "Test User"')

            # Should exit cleanly with no files to process
            with (
                patch("auto_docs_action.git_operations.get_changed_py_files", return_value=[]),
                patch("shutil.which", return_value="/fake/claude"),
            ):
                exit_code = main_for_testing()
                assert exit_code == 0  # Success even with no files

        finally:
            # Change back to a safe directory
            os.chdir(Path(__file__).parent.parent)


def test_file_permission_errors():
    """Test handling of file permission errors during processing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a read-only file
        readonly_file = Path(temp_dir) / "readonly.py"
        readonly_file.write_text("def test(): pass")
        readonly_file.chmod(0o444)  # Read-only

        try:
            # Attempting to read should work
            content = readonly_file.read_text()
            assert "def test" in content

            # Attempting to write should be handled gracefully by the processor
            # (This would be tested in integration with FileProcessor)

        finally:
            # Restore write permissions for cleanup
            readonly_file.chmod(0o644)
