"""Git operations for file management using subprocess (following pre-commit pattern)."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path


class CalledProcessError(Exception):
    """Exception raised when a subprocess command fails."""

    pass


def cmd_output(*cmd: str, cwd: str | None = None, check: bool = True, timeout: int = 30) -> tuple[int, str, str]:
    """Run command and return (returncode, stdout, stderr) - following pre-commit pattern.

    Args:
        cmd: Command arguments to run
        cwd: Working directory for the command
        check: If True, raise CalledProcessError on non-zero exit
        timeout: Command timeout in seconds

    Returns:
        Tuple of (returncode, stdout, stderr)

    Raises:
        CalledProcessError: If check=True and command fails or times out
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if check and result.returncode != 0:
            raise CalledProcessError(f"Command {cmd} failed with code {result.returncode}: {result.stderr.strip()}")

        return result.returncode, result.stdout, result.stderr

    except subprocess.TimeoutExpired as e:
        raise CalledProcessError(f"Command {cmd} timed out after {timeout} seconds") from e


def get_last_auto_docs_commit() -> str | None:
    """Get the SHA of the last commit made by auto-docs[bot].

    Returns:
        The commit SHA if found, None if no auto-docs commits exist
    """
    try:
        # Try multiple author patterns to be robust
        patterns = ["auto-docs[bot]", "auto-docs\\[bot\\]", "*auto-docs*"]

        for pattern in patterns:
            try:
                _, stdout, _ = cmd_output("git", "log", f"--author={pattern}", "--format=%H", "-1")
                commit_sha = stdout.strip()
                if commit_sha:
                    logging.debug(f"Found last auto-docs commit: {commit_sha[:8]} with pattern: {pattern}")
                    return commit_sha
            except CalledProcessError:
                continue

        logging.debug("No auto-docs commits found in history")
        return None
    except CalledProcessError:
        logging.debug("No previous auto-docs commits found or git error")
        return None


def get_changed_py_files() -> list[Path]:
    """Get list of Python files changed since the last auto-docs[bot] commit.

    If no auto-docs commits exist, returns ALL Python files in the repository.

    Returns:
        List of Path objects for changed .py files that exist
    """
    try:
        # Find the last auto-docs commit
        last_auto_docs = get_last_auto_docs_commit()

        if last_auto_docs:
            # Diff from last auto-docs commit to HEAD
            _, stdout, _ = cmd_output("git", "diff", "--name-only", last_auto_docs, "HEAD")
            logging.info(f"Comparing against last auto-docs commit: {last_auto_docs[:8]}")

            py_files = []
            for line in stdout.strip().split("\n"):
                if line and line.endswith(".py") and Path(line).exists():
                    py_files.append(Path(line))
        else:
            # Fallback: get ALL Python files in the repository (first run)
            _, stdout, _ = cmd_output("git", "ls-files", "*.py")
            logging.info("No previous auto-docs commits found, processing all Python files")

            py_files = []
            for line in stdout.strip().split("\n"):
                if line and Path(line).exists():
                    py_files.append(Path(line))

        logging.info(f"Found {len(py_files)} Python files to process")
        return py_files

    except CalledProcessError as e:
        logging.error(f"Failed to get changed files: {e}")
        return []


def get_file_diff(file_path: Path) -> str:
    """Get git diff for specific file since the last auto-docs[bot] commit.

    If no auto-docs commits exist, returns empty string (entire file is new context).

    Args:
        file_path: Path to the file to get diff for

    Returns:
        Git diff output as string, empty string if no auto-docs history or error
    """
    try:
        # Find the last auto-docs commit
        last_auto_docs = get_last_auto_docs_commit()

        if last_auto_docs:
            # Diff from last auto-docs commit to HEAD
            _, stdout, _ = cmd_output("git", "diff", last_auto_docs, "HEAD", str(file_path))
            return stdout
        else:
            # No auto-docs history - return empty diff (entire file is new)
            logging.debug(f"No auto-docs history, treating {file_path} as entirely new")
            return ""

    except CalledProcessError as e:
        logging.error(f"Failed to get diff for {file_path}: {e}")
        return ""


def stage_file(file_path: Path) -> bool:
    """Stage a single file.

    Args:
        file_path: Path to the file to stage

    Returns:
        True if staging succeeded, False otherwise
    """
    try:
        cmd_output("git", "add", str(file_path))
        logging.info(f"Staged {file_path}")
        return True
    except CalledProcessError as e:
        logging.error(f"Failed to stage {file_path}: {e}")
        return False


def restore_file(file_path: Path) -> bool:
    """Restore file to HEAD state using git restore.

    Args:
        file_path: Path to the file to restore

    Returns:
        True if restore succeeded, False otherwise
    """
    try:
        cmd_output("git", "restore", str(file_path))
        logging.info(f"Restored {file_path}")
        return True
    except CalledProcessError as e:
        logging.error(f"Failed to restore {file_path}: {e}")
        return False


def create_commit(message: str) -> bool:
    """Create commit with staged files.

    Args:
        message: Commit message

    Returns:
        True if commit succeeded, False otherwise
    """
    try:
        # Add [skip ci] to prevent infinite loops
        full_message = f"{message}\n\n[skip ci] Auto-generated by auto-docs-action"

        # Configure git for GitHub Actions bot
        env = os.environ.copy()
        env.update(
            {
                "GIT_AUTHOR_NAME": "auto-docs[bot]",
                "GIT_AUTHOR_EMAIL": "41898282+auto-docs[bot]@users.noreply.github.com",
                "GIT_COMMITTER_NAME": "auto-docs[bot]",
                "GIT_COMMITTER_EMAIL": "41898282+auto-docs[bot]@users.noreply.github.com",
            }
        )

        # Create commit
        result = subprocess.run(
            ["git", "commit", "-m", full_message],
            capture_output=True,
            text=True,
            env=env,
        )

        if result.returncode == 0:
            logging.info("Commit created successfully")
            return True
        else:
            logging.error(f"Commit failed: {result.stderr.strip()}")
            return False

    except Exception as e:
        logging.error(f"Failed to create commit: {e}")
        return False


def has_staged_files() -> bool:
    """Check if there are any staged files.

    Returns:
        True if there are staged files, False otherwise
    """
    try:
        returncode, stdout, _ = cmd_output("git", "diff", "--staged", "--name-only", check=False)
        return returncode == 0 and bool(stdout.strip())
    except CalledProcessError:
        return False
