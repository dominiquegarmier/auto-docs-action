"""Tests for git operations functionality."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import git_operations
from git_operations import CalledProcessError
from git_operations import cmd_output


def test_successful_command():
    """Test successful command execution."""
    returncode, stdout, stderr = cmd_output("echo", "hello")

    assert returncode == 0
    assert stdout.strip() == "hello"
    assert stderr == ""


def test_failing_command_with_check_true():
    """Test that failing command with check=True raises exception."""
    with pytest.raises(CalledProcessError) as exc_info:
        cmd_output("false")  # Command that always fails

    assert "failed with code 1" in str(exc_info.value)


def test_failing_command_with_check_false():
    """Test failing command with check=False returns error code."""
    returncode, stdout, stderr = cmd_output("false", check=False)

    assert returncode == 1


def test_timeout_handling():
    """Test command timeout."""
    with pytest.raises(CalledProcessError) as exc_info:
        cmd_output("sleep", "2", timeout=1)

    assert "timed out" in str(exc_info.value)


def test_get_changed_py_files_empty_repo(temp_git_repo: Path, monkeypatch):
    """Test getting changed files from empty repository."""

    with monkeypatch.context() as m:
        m.chdir(temp_git_repo)
        changed_files = git_operations.get_changed_py_files()

    # Should return empty list for empty repo (no HEAD~1)
    assert changed_files == []


def test_get_changed_py_files_with_changes(git_repo_with_files: Path, monkeypatch):
    """Test detection of changed Python files (returns all files when no auto-docs history)."""

    # Modify a Python file
    py_file = git_repo_with_files / "good_docstrings.py"
    content = py_file.read_text()
    py_file.write_text(content + "\n# Added comment")

    # Add and commit the change
    subprocess.run(["git", "add", str(py_file)], cwd=git_repo_with_files, check=True)
    subprocess.run(["git", "commit", "-m", "Modify Python file"], cwd=git_repo_with_files, check=True)

    # Test our function - should return ALL Python files since no auto-docs history
    with monkeypatch.context() as m:
        m.chdir(git_repo_with_files)
        changed_files = git_operations.get_changed_py_files()

    assert len(changed_files) == 4  # All Python files in repo
    file_names = {f.name for f in changed_files}
    assert file_names == {"good_docstrings.py", "missing_docstrings.py", "mixed_quality.py", "syntax_error.py"}


def test_get_changed_files_filters_non_python(git_repo_with_files: Path, monkeypatch):
    """Test that only .py files are returned (all files when no auto-docs history)."""

    # Create and modify non-Python files
    txt_file = git_repo_with_files / "readme.txt"
    txt_file.write_text("Some text content")

    py_file = git_repo_with_files / "missing_docstrings.py"
    content = py_file.read_text()
    py_file.write_text(content + "\n# Modified")

    # Commit both changes
    subprocess.run(["git", "add", "."], cwd=git_repo_with_files, check=True)
    subprocess.run(["git", "commit", "-m", "Add txt file and modify py file"], cwd=git_repo_with_files, check=True)

    with monkeypatch.context() as m:
        m.chdir(git_repo_with_files)
        changed_files = git_operations.get_changed_py_files()

    # Should return ALL Python files (no auto-docs history), excluding .txt files
    assert len(changed_files) == 4  # All Python files in repo
    file_names = {f.name for f in changed_files}
    assert file_names == {"good_docstrings.py", "missing_docstrings.py", "mixed_quality.py", "syntax_error.py"}
    # txt file should be excluded


def test_get_file_diff(git_repo_with_files: Path, monkeypatch):
    """Test getting diff for specific file (returns empty when no auto-docs history)."""

    # Modify a file and commit
    py_file = git_repo_with_files / "good_docstrings.py"
    original_content = py_file.read_text()
    py_file.write_text(original_content + "\n# Added line")

    subprocess.run(["git", "add", str(py_file)], cwd=git_repo_with_files, check=True)
    subprocess.run(["git", "commit", "-m", "Add line to file"], cwd=git_repo_with_files, check=True)

    with monkeypatch.context() as m:
        m.chdir(git_repo_with_files)
        diff = git_operations.get_file_diff(py_file)

    # Should return empty diff when no auto-docs history exists
    assert diff == ""


def test_stage_file(git_repo_with_files: Path, monkeypatch):
    """Test staging individual files."""

    # Modify a file (don't stage it yet)
    py_file = git_repo_with_files / "missing_docstrings.py"
    py_file.write_text("# Modified content")

    with monkeypatch.context() as m:
        m.chdir(git_repo_with_files)
        success = git_operations.stage_file(py_file)

    assert success is True

    # Verify file is staged
    result = subprocess.run(
        ["git", "diff", "--staged", "--name-only"], cwd=git_repo_with_files, capture_output=True, text=True
    )
    assert str(py_file.name) in result.stdout


def test_restore_file(git_repo_with_files: Path, monkeypatch):
    """Test restoring files to HEAD state."""

    py_file = git_repo_with_files / "good_docstrings.py"

    # Get original content
    original_content = py_file.read_text()

    # Modify file
    py_file.write_text("# This is modified content")
    assert py_file.read_text() != original_content

    # Restore file
    with monkeypatch.context() as m:
        m.chdir(git_repo_with_files)
        success = git_operations.restore_file(py_file)

    assert success is True
    assert py_file.read_text() == original_content


def test_has_staged_files(git_repo_with_files: Path, monkeypatch):
    """Test checking for staged files."""

    # Initially no staged files
    with monkeypatch.context() as m:
        m.chdir(git_repo_with_files)
        assert git_operations.has_staged_files() is False

    # Modify and stage a file
    py_file = git_repo_with_files / "missing_docstrings.py"
    py_file.write_text("# New content")

    with monkeypatch.context() as m:
        m.chdir(git_repo_with_files)
        git_operations.stage_file(py_file)
        # Now should have staged files
        assert git_operations.has_staged_files() is True


def test_create_commit(git_repo_with_files: Path, monkeypatch):
    """Test creating commits with staged files."""

    # Modify and stage a file
    py_file = git_repo_with_files / "missing_docstrings.py"
    py_file.write_text("# New content")
    subprocess.run(["git", "add", str(py_file)], cwd=git_repo_with_files, check=True)

    with monkeypatch.context() as m:
        m.chdir(git_repo_with_files)
        success = git_operations.create_commit("Test commit message")

    assert success is True

    # Verify commit was created with correct message and [skip ci]
    result = subprocess.run(
        ["git", "log", "-1", "--pretty=format:%s"], cwd=git_repo_with_files, capture_output=True, text=True
    )
    assert "Test commit message" in result.stdout

    # Check full commit message includes [skip ci]
    result = subprocess.run(
        ["git", "log", "-1", "--pretty=format:%B"], cwd=git_repo_with_files, capture_output=True, text=True
    )
    assert "[skip ci]" in result.stdout
    assert "Auto-generated by auto-docs-action" in result.stdout


def test_create_commit_no_staged_files(git_repo_with_files: Path, monkeypatch):
    """Test commit creation fails when no files are staged."""

    with monkeypatch.context() as m:
        m.chdir(git_repo_with_files)
        success = git_operations.create_commit("Empty commit")

    # Should fail because nothing is staged
    assert success is False
