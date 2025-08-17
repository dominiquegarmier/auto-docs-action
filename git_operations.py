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


def get_last_auto_docs_commit() -> str | None:
    """Get the SHA of the last commit made by github-actions[bot] for auto-docs.

    Returns:
        The commit SHA if found, None if no auto-docs commits exist
    """
    try:
        logging.info("🔍 Searching for last github-actions commit...")
        # Try multiple author patterns to be robust
        patterns = ["github-actions[bot]", "github-actions\\[bot\\]", "*github-actions*"]

        for i, pattern in enumerate(patterns):
            try:
                logging.debug(f"Trying pattern {i + 1}/{len(patterns)}: {pattern}")
                _, stdout, _ = cmd_output("git", "log", f"--author={pattern}", "--format=%H", "-1")
                commit_sha = stdout.strip()
                if commit_sha:
                    logging.info(f"✅ Found last github-actions commit: {commit_sha[:8]} with pattern: {pattern}")
                    return commit_sha
                else:
                    logging.debug(f"Pattern {pattern} returned empty result")
            except CalledProcessError as e:
                logging.debug(f"Pattern {pattern} failed: {e}")
                continue

        logging.info("ℹ️ No github-actions commits found in history")
        return None
    except CalledProcessError as e:
        logging.info(f"ℹ️ No previous github-actions commits found or git error: {e}")
        return None
    except Exception as e:
        logging.error(f"❌ Unexpected error in get_last_auto_docs_commit: {e}", exc_info=True)
        return None


def get_changed_py_files() -> list[Path]:
    """Get list of Python files changed since the last github-actions[bot] commit.

    If no github-actions commits exist, returns ALL Python files in the repository.

    Returns:
        List of Path objects for changed .py files that exist
    """
    try:
        logging.info("🔍 Starting get_changed_py_files...")

        # Find the last github-actions commit
        logging.info("🔍 Looking for last github-actions commit...")
        last_auto_docs = get_last_auto_docs_commit()
        logging.info(f"✅ get_last_auto_docs_commit returned: {last_auto_docs}")

        if last_auto_docs:
            # Diff from last github-actions commit to HEAD
            logging.info(f"🔍 Diffing from {last_auto_docs[:8]} to HEAD...")
            _, stdout, _ = cmd_output("git", "diff", "--name-only", last_auto_docs, "HEAD")
            logging.info(f"Comparing against last github-actions commit: {last_auto_docs[:8]}")
            logging.info(f"Git diff output: {repr(stdout[:200])}...")

            py_files = []
            for line in stdout.strip().split("\n"):
                if line and line.endswith(".py"):
                    if Path(line).exists():
                        py_files.append(Path(line))
                        logging.debug(f"Added Python file: {line}")
                    else:
                        logging.debug(f"Skipped non-existent file: {line}")
        else:
            # Fallback: get ALL Python files in the repository (first run)
            logging.info("🔍 No github-actions history, listing all Python files...")
            _, stdout, _ = cmd_output("git", "ls-files", "*.py")
            logging.info("No previous github-actions commits found, processing all Python files")
            logging.info(f"Git ls-files output: {repr(stdout[:200])}...")

            py_files = []
            for line in stdout.strip().split("\n"):
                if line and Path(line).exists():
                    py_files.append(Path(line))
                    logging.debug(f"Added Python file: {line}")

        logging.info(f"Found {len(py_files)} Python files to process: {[str(f) for f in py_files]}")
        return py_files

    except CalledProcessError as e:
        logging.error(f"Failed to get changed files: {e}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error in get_changed_py_files: {e}", exc_info=True)
        return []


def get_file_diff(file_path: Path) -> str:
    """Get git diff for specific file since the last github-actions[bot] commit.

    If no github-actions commits exist, returns diff from first commit to HEAD.

    Args:
        file_path: Path to the file to get diff for

    Returns:
        Git diff output as string, empty string if error
    """
    try:
        # Find the last github-actions commit
        last_auto_docs = get_last_auto_docs_commit()

        if last_auto_docs:
            # Diff from last github-actions commit to HEAD
            _, stdout, _ = cmd_output("git", "diff", last_auto_docs, "HEAD", str(file_path))
            return stdout
        else:
            # No github-actions history - diff from first commit to HEAD
            try:
                # Get the first commit in the repository
                _, first_commit, _ = cmd_output("git", "rev-list", "--max-parents=0", "HEAD")
                first_commit = first_commit.strip()

                # Diff from first commit to HEAD for this file
                _, stdout, _ = cmd_output("git", "diff", first_commit, "HEAD", str(file_path))
                logging.debug(f"No github-actions history, showing full diff for {file_path} from first commit")
                return stdout
            except CalledProcessError:
                # Fallback: if we can't find first commit, show the entire file as added
                try:
                    _, stdout, _ = cmd_output("git", "show", f"HEAD:{file_path}")
                    # Format as a diff showing the entire file as added
                    lines = stdout.split("\n")
                    diff_lines = ["--- /dev/null", f"+++ b/{file_path}"] + [f"+{line}" for line in lines]
                    return "\n".join(diff_lines)
                except CalledProcessError:
                    logging.warning(f"Could not generate diff for {file_path}")
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
