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
        logging.debug(f"🔧 Running command: {' '.join(cmd)} (cwd={cwd}, timeout={timeout})")
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        logging.debug(
            f"✅ Command completed: return_code={result.returncode}, "
            f"stdout_len={len(result.stdout)}, stderr_len={len(result.stderr)}"
        )

        if check and result.returncode != 0:
            error_msg = f"Command {cmd} failed with code {result.returncode}: {result.stderr.strip()}"
            logging.error(f"❌ {error_msg}")
            raise CalledProcessError(error_msg)

        return result.returncode, result.stdout, result.stderr

    except subprocess.TimeoutExpired as e:
        error_msg = f"Command {cmd} timed out after {timeout} seconds"
        logging.error(f"⏰ {error_msg}")
        raise CalledProcessError(error_msg) from e
    except Exception as e:
        error_msg = f"Unexpected error running command {cmd}: {e}"
        logging.error(f"❌ {error_msg}")
        raise CalledProcessError(error_msg) from e


def get_last_bot_commit() -> str | None:
    """Get the SHA of the last commit made by github-actions[bot].

    Returns:
        The commit SHA if found, None if no bot commits exist
    """
    try:
        from auto_docs_action.git_helpers import GitCommitFinder

        commit_info = GitCommitFinder.find_last_bot_commit()
        return commit_info.sha if commit_info else None
    except Exception as e:
        logging.error(f"❌ Unexpected error in get_last_bot_commit: {e}", exc_info=True)
        return None


def get_pr_base_commit() -> str | None:
    """Get the actual PR base commit (merge-base with target branch).

    Returns:
        The PR base commit SHA if in PR context, None otherwise
    """
    try:
        from auto_docs_action.config import load_github_config
        from auto_docs_action.git_helpers import GitCommitFinder

        github_config = load_github_config()
        commit_info = GitCommitFinder.find_pr_base_commit(github_config)
        return commit_info.sha if commit_info else None
    except Exception as e:
        logging.error(f"❌ Unexpected error in get_pr_base_commit: {e}", exc_info=True)
        return None


def get_oldest_available_commit() -> str:
    """Get the oldest commit available in the repository (handles shallow checkout).

    Returns:
        The oldest commit SHA available

    Raises:
        CalledProcessError: If no commits are found
    """
    from auto_docs_action.git_helpers import GitCommitFinder

    commit_info = GitCommitFinder.find_oldest_available_commit()
    return commit_info.sha


def count_commits_to_head(commit: str) -> int:
    """Count the number of commits from given commit to HEAD.

    Args:
        commit: The commit SHA to count from

    Returns:
        Number of commits from commit to HEAD (0 if commit is HEAD)
        Returns a very large number if count cannot be determined
    """
    from auto_docs_action.git_helpers import GitCommitFinder

    return GitCommitFinder._count_commits_to_head(commit)


def determine_diff_commits() -> tuple[str, str]:
    """Determine the from and to commits for diff operations.

    Logic:
    - PR context: min_history(pr_base, last_bot) or oldest_available
    - Push context: min_history(oldest_available, last_bot)

    Returns:
        Tuple of (from_commit, to_commit) where to_commit is always HEAD
    """
    try:
        from auto_docs_action.config import load_github_config
        from auto_docs_action.git_helpers import DiffRangeDeterminer

        github_config = load_github_config()
        determiner = DiffRangeDeterminer(github_config)
        diff_range = determiner.determine_range()

        logging.info(f"✅ Diff range determined: {diff_range.from_commit[:8]}..{diff_range.to_commit}")
        return diff_range.from_commit, diff_range.to_commit
    except Exception as e:
        logging.error(f"❌ Error determining diff commits: {e}", exc_info=True)
        # Safe fallback: use HEAD (will result in no diff)
        head_commit = "HEAD"
        logging.warning(f"⚠️ Falling back to HEAD..HEAD (no diff): {head_commit[:8]}")
        return head_commit, head_commit


def get_changed_py_files() -> list[Path]:
    """Get list of Python files changed since the last github-actions[bot] commit.

    If no github-actions commits exist, returns ALL Python files in the repository.

    Returns:
        List of Path objects for changed .py files that exist
    """
    try:
        from auto_docs_action.config import load_github_config
        from auto_docs_action.constants import PYTHON_FILE_EXTENSION
        from auto_docs_action.constants import PYTHON_FILES_PATTERN

        logging.info("🔍 Starting get_changed_py_files...")
        github_config = load_github_config()

        # Use central diff logic
        from_commit, to_commit = determine_diff_commits()

        if from_commit == to_commit:
            logging.info("No diff range available, no files to process")
            return []

        # Check if we should return ALL files (no bot/PR history)
        should_return_all_files = _should_return_all_python_files(github_config)

        if should_return_all_files:
            return _get_all_python_files()
        else:
            return _get_changed_python_files(from_commit, to_commit)

    except CalledProcessError as e:
        logging.error(f"Failed to get changed files: {e}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error in get_changed_py_files: {e}", exc_info=True)
        return []


def _should_return_all_python_files(github_config) -> bool:
    """Determine if we should return all Python files instead of just changed ones."""
    if github_config.is_pull_request:
        # In PR: return all files if neither PR base nor bot commit found
        pr_base = get_pr_base_commit()
        last_bot = get_last_bot_commit()
        return pr_base is None and last_bot is None
    else:
        # In push: return all files if no bot commit found
        last_bot = get_last_bot_commit()
        return last_bot is None


def _get_all_python_files() -> list[Path]:
    """Get all Python files in the repository."""
    from auto_docs_action.constants import PYTHON_FILES_PATTERN

    logging.info("No relevant commit history found, returning all Python files")
    _, stdout, _ = cmd_output("git", "ls-files", PYTHON_FILES_PATTERN)
    logging.info(f"Git ls-files output: {repr(stdout[:200])}...")

    py_files = []
    for line in stdout.strip().split("\n"):
        if line and Path(line).exists():
            py_files.append(Path(line))
            logging.debug(f"Added Python file: {line}")

    logging.info(f"Found {len(py_files)} Python files to process: {[str(f) for f in py_files]}")
    return py_files


def _get_changed_python_files(from_commit: str, to_commit: str) -> list[Path]:
    """Get Python files that changed between two commits."""
    from auto_docs_action.constants import PYTHON_FILE_EXTENSION

    _, stdout, _ = cmd_output("git", "diff", "--name-only", from_commit, to_commit)
    logging.info(f"Git diff {from_commit[:8]}..{to_commit}: {repr(stdout[:200])}...")

    py_files = []
    for line in stdout.strip().split("\n"):
        if line and line.endswith(PYTHON_FILE_EXTENSION):
            if Path(line).exists():
                py_files.append(Path(line))
                logging.debug(f"Added Python file: {line}")
            else:
                logging.debug(f"Skipped non-existent file: {line}")

    logging.info(f"Found {len(py_files)} Python files to process: {[str(f) for f in py_files]}")
    return py_files


def get_file_diff(file_path: Path) -> str:
    """Get git diff for specific file using central diff logic.

    Args:
        file_path: Path to the file to get diff for

    Returns:
        Git diff output as string, empty string if error
    """
    try:
        # Use central diff logic
        from_commit, to_commit = determine_diff_commits()

        if from_commit == to_commit:
            # No diff to compute
            logging.debug(f"No diff range for {file_path}")
            return ""

        # Generate diff for this specific file
        _, stdout, _ = cmd_output("git", "diff", from_commit, to_commit, str(file_path))
        return stdout

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
                "GIT_AUTHOR_NAME": "github-actions[bot]",
                "GIT_AUTHOR_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
                "GIT_COMMITTER_NAME": "github-actions[bot]",
                "GIT_COMMITTER_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
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
