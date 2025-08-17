"""Tests for auto-docs commit detection functionality."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

import git_operations


def test_get_last_auto_docs_commit_found(git_repo_with_files: Path, monkeypatch):
    """Test finding the last auto-docs commit when one exists."""

    # Create an auto-docs commit
    py_file = git_repo_with_files / "test.py"
    py_file.write_text("def hello(): pass")
    subprocess.run(["git", "add", "test.py"], cwd=git_repo_with_files, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=auto-docs[bot]",
            "-c",
            "user.email=auto-docs[bot]@users.noreply.github.com",
            "commit",
            "-m",
            "docs: auto-update docstrings",
        ],
        cwd=git_repo_with_files,
        check=True,
    )

    # Get the commit SHA for verification
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=git_repo_with_files, capture_output=True, text=True, check=True)
    expected_sha = result.stdout.strip()

    with monkeypatch.context() as m:
        m.chdir(git_repo_with_files)
        commit_sha = git_operations.get_last_auto_docs_commit()

    assert commit_sha == expected_sha
    assert len(commit_sha) == 40  # Full SHA length


def test_get_last_auto_docs_commit_none_found(git_repo_with_files: Path, monkeypatch):
    """Test when no auto-docs commits exist."""

    # Only regular commits exist in the repo
    with monkeypatch.context() as m:
        m.chdir(git_repo_with_files)
        commit_sha = git_operations.get_last_auto_docs_commit()

    assert commit_sha is None


def test_get_last_auto_docs_commit_multiple_commits(git_repo_with_files: Path, monkeypatch):
    """Test getting the most recent auto-docs commit when multiple exist."""

    # Create first auto-docs commit
    py_file = git_repo_with_files / "test1.py"
    py_file.write_text("def hello1(): pass")
    subprocess.run(["git", "add", "test1.py"], cwd=git_repo_with_files, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=auto-docs[bot]",
            "-c",
            "user.email=auto-docs[bot]@users.noreply.github.com",
            "commit",
            "-m",
            "docs: auto-update docstrings (first)",
        ],
        cwd=git_repo_with_files,
        check=True,
    )

    # Create regular commit
    py_file2 = git_repo_with_files / "test2.py"
    py_file2.write_text("def hello2(): pass")
    subprocess.run(["git", "add", "test2.py"], cwd=git_repo_with_files, check=True)
    subprocess.run(["git", "commit", "-m", "Regular commit"], cwd=git_repo_with_files, check=True)

    # Create second auto-docs commit
    py_file3 = git_repo_with_files / "test3.py"
    py_file3.write_text("def hello3(): pass")
    subprocess.run(["git", "add", "test3.py"], cwd=git_repo_with_files, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=auto-docs[bot]",
            "-c",
            "user.email=auto-docs[bot]@users.noreply.github.com",
            "commit",
            "-m",
            "docs: auto-update docstrings (second)",
        ],
        cwd=git_repo_with_files,
        check=True,
    )

    # Get the latest commit SHA (should be the second auto-docs commit)
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=git_repo_with_files, capture_output=True, text=True, check=True)
    expected_sha = result.stdout.strip()

    commit_sha = git_operations.get_last_auto_docs_commit()

    assert commit_sha == expected_sha


def test_get_last_auto_docs_commit_git_error(monkeypatch):
    """Test handling of git command errors."""
    # Change to non-git directory
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.chdir(tmpdir)

        commit_sha = git_operations.get_last_auto_docs_commit()

        assert commit_sha is None


def test_get_changed_py_files_with_auto_docs_commit(git_repo_with_files: Path, monkeypatch):
    """Test getting changed files when auto-docs commit exists."""
    monkeypatch.chdir(git_repo_with_files)

    # Create an auto-docs commit
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=auto-docs[bot]",
            "-c",
            "user.email=auto-docs[bot]@users.noreply.github.com",
            "commit",
            "--allow-empty",
            "-m",
            "docs: auto-update docstrings",
        ],
        cwd=git_repo_with_files,
        check=True,
    )

    # Make some changes after the auto-docs commit
    py_file1 = git_repo_with_files / "new_file1.py"
    py_file1.write_text("def new_func1(): pass")
    py_file2 = git_repo_with_files / "new_file2.py"
    py_file2.write_text("def new_func2(): pass")
    non_py_file = git_repo_with_files / "readme.txt"
    non_py_file.write_text("Some readme")

    subprocess.run(["git", "add", "."], cwd=git_repo_with_files, check=True)
    subprocess.run(["git", "commit", "-m", "Add new files"], cwd=git_repo_with_files, check=True)

    changed_files = git_operations.get_changed_py_files()

    assert len(changed_files) == 2
    file_names = {f.name for f in changed_files}
    assert file_names == {"new_file1.py", "new_file2.py"}


def test_get_changed_py_files_no_auto_docs_commit(git_repo_with_files: Path, monkeypatch):
    """Test getting changed files when no auto-docs commits exist (fallback to all files)."""
    monkeypatch.chdir(git_repo_with_files)

    # Make changes and commit (no auto-docs commits exist yet)
    py_file = git_repo_with_files / "new_file.py"
    py_file.write_text("def new_func(): pass")

    subprocess.run(["git", "add", "new_file.py"], cwd=git_repo_with_files, check=True)
    subprocess.run(["git", "commit", "-m", "Add new file"], cwd=git_repo_with_files, check=True)

    changed_files = git_operations.get_changed_py_files()

    # Should return ALL Python files (existing + new) when no auto-docs history
    assert len(changed_files) >= 5  # Original 4 + new 1
    file_names = {f.name for f in changed_files}
    assert "new_file.py" in file_names
    assert "good_docstrings.py" in file_names  # From original repo


def test_get_file_diff_with_auto_docs_commit(git_repo_with_files: Path, monkeypatch):
    """Test getting file diff when auto-docs commit exists."""
    monkeypatch.chdir(git_repo_with_files)

    # Create an auto-docs commit
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=auto-docs[bot]",
            "-c",
            "user.email=auto-docs[bot]@users.noreply.github.com",
            "commit",
            "--allow-empty",
            "-m",
            "docs: auto-update docstrings",
        ],
        cwd=git_repo_with_files,
        check=True,
    )

    # Modify a file after the auto-docs commit
    py_file = git_repo_with_files / "good_docstrings.py"
    original_content = py_file.read_text()
    py_file.write_text(original_content + "\n# Added after auto-docs commit")

    subprocess.run(["git", "add", str(py_file)], cwd=git_repo_with_files, check=True)
    subprocess.run(["git", "commit", "-m", "Add line after auto-docs"], cwd=git_repo_with_files, check=True)

    diff = git_operations.get_file_diff(py_file)

    assert "# Added after auto-docs commit" in diff
    assert "+++" in diff  # Git diff format
    assert "---" in diff


def test_get_file_diff_no_auto_docs_commit(git_repo_with_files: Path, monkeypatch):
    """Test getting file diff when no auto-docs commits exist (returns empty)."""
    monkeypatch.chdir(git_repo_with_files)

    # Modify a file and commit (no auto-docs commits exist)
    py_file = git_repo_with_files / "good_docstrings.py"
    original_content = py_file.read_text()
    py_file.write_text(original_content + "\n# Added line")

    subprocess.run(["git", "add", str(py_file)], cwd=git_repo_with_files, check=True)
    subprocess.run(["git", "commit", "-m", "Add line to file"], cwd=git_repo_with_files, check=True)

    diff = git_operations.get_file_diff(py_file)

    # Should return empty diff when no auto-docs history (entire file is new)
    assert diff == ""


@patch("git_operations.get_last_auto_docs_commit")
def test_get_changed_py_files_mocked_auto_docs_commit(mock_get_last_auto_docs, git_repo_with_files: Path, monkeypatch):
    """Test get_changed_py_files with mocked auto-docs commit SHA."""
    monkeypatch.chdir(git_repo_with_files)

    # Mock the auto-docs commit to return the initial commit SHA
    result = subprocess.run(
        ["git", "rev-list", "--max-parents=0", "HEAD"], cwd=git_repo_with_files, capture_output=True, text=True, check=True
    )
    initial_commit = result.stdout.strip()
    mock_get_last_auto_docs.return_value = initial_commit

    # Make changes and commit
    py_file = git_repo_with_files / "new_test.py"
    py_file.write_text("def test(): pass")
    subprocess.run(["git", "add", "new_test.py"], cwd=git_repo_with_files, check=True)
    subprocess.run(["git", "commit", "-m", "Add test file"], cwd=git_repo_with_files, check=True)

    changed_files = git_operations.get_changed_py_files()

    # Should include the new file
    assert len(changed_files) == 1
    assert changed_files[0].name == "new_test.py"
    mock_get_last_auto_docs.assert_called_once()
