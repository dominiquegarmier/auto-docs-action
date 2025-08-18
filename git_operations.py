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
        logging.error(f"❌ Unexpected error in get_last_bot_commit: {e}", exc_info=True)
        return None


def get_pr_base_commit() -> str | None:
    """Get the actual PR base commit (merge-base with target branch).

    Returns:
        The PR base commit SHA if in PR context, None otherwise
    """
    try:
        # Check if we're in a pull request context
        github_event_name = os.getenv("GITHUB_EVENT_NAME")
        if github_event_name != "pull_request":
            logging.debug(f"Not in PR context (event: {github_event_name})")
            return None

        # Get the target branch from GitHub environment
        github_base_ref = os.getenv("GITHUB_BASE_REF")
        if not github_base_ref:
            logging.debug("No GITHUB_BASE_REF found, not in PR context")
            return None

        logging.info(f"PR target branch: {github_base_ref}")

        # Try to get merge-base with the actual target branch
        try:
            # First try origin/target_branch
            target_ref = f"origin/{github_base_ref}"
            _, stdout, _ = cmd_output("git", "merge-base", "HEAD", target_ref)
            merge_base = stdout.strip()
            logging.info(f"✅ Found PR base commit via merge-base with {target_ref}: {merge_base[:8]}")
            return merge_base
        except CalledProcessError:
            try:
                # Fallback to target_branch without origin prefix
                _, stdout, _ = cmd_output("git", "merge-base", "HEAD", github_base_ref)
                merge_base = stdout.strip()
                logging.info(f"✅ Found PR base commit via merge-base with {github_base_ref}: {merge_base[:8]}")
                return merge_base
            except CalledProcessError:
                logging.debug(f"Could not find merge-base with {github_base_ref}")

        # Fallback: try to find the oldest commit in the current branch
        # that's not in the target branch history
        try:
            # Get the first commit that's unique to this branch
            boundary_ref = f"HEAD...origin/{github_base_ref}^"
            _, stdout, _ = cmd_output("git", "rev-list", "--boundary", boundary_ref, check=False)
            if stdout.strip():
                # Parse boundary commits (marked with -)
                lines = stdout.strip().split("\n")
                for line in lines:
                    if line.startswith("-"):
                        boundary_commit = line[1:]  # Remove the - prefix
                        logging.info(f"✅ Found PR base commit from boundary: {boundary_commit[:8]}")
                        return boundary_commit
        except CalledProcessError:
            pass

        # Last resort: use oldest available commit
        try:
            oldest_commit = get_oldest_available_commit()
            logging.info(f"✅ Using oldest available commit as PR base: {oldest_commit[:8]}")
            return oldest_commit
        except Exception:
            pass

        logging.debug("Could not determine PR base commit, will fall back to bot commit")
        return None

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
    try:
        # Try to get the first commit (root commit)
        _, stdout, _ = cmd_output("git", "rev-list", "--max-parents=0", "HEAD")
        first_commit = stdout.strip()
        if first_commit:
            logging.info(f"✅ Found first commit: {first_commit[:8]}")
            return first_commit
    except CalledProcessError:
        logging.debug("Could not find first commit, trying reverse order")

    try:
        # Fallback for shallow checkout: get oldest available commit
        _, stdout, _ = cmd_output("git", "rev-list", "--max-count=1", "--reverse", "HEAD")
        oldest_commit = stdout.strip()
        if oldest_commit:
            logging.info(f"✅ Found oldest available commit: {oldest_commit[:8]}")
            return oldest_commit
    except CalledProcessError:
        logging.debug("Could not find oldest commit, using HEAD")

    # Ultimate fallback: use HEAD (no diff will be generated)
    _, stdout, _ = cmd_output("git", "rev-parse", "HEAD")
    head_commit = stdout.strip()
    logging.warning(f"⚠️ Using HEAD as oldest commit: {head_commit[:8]}")
    return head_commit


def count_commits_to_head(commit: str) -> int:
    """Count the number of commits from given commit to HEAD.

    Args:
        commit: The commit SHA to count from

    Returns:
        Number of commits from commit to HEAD (0 if commit is HEAD)
        Returns a very large number if count cannot be determined
    """
    try:
        _, stdout, _ = cmd_output("git", "rev-list", "--count", f"{commit}..HEAD")
        count = int(stdout.strip())
        logging.debug(f"Commit {commit[:8]} is {count} commits behind HEAD")
        return count
    except (CalledProcessError, ValueError) as e:
        logging.debug(f"Could not count commits for {commit}: {e}")
        return 999999  # Return large number if we can't count (treat as very old)


def determine_diff_commits() -> tuple[str, str]:
    """Determine the from and to commits for diff operations.

    Logic:
    - PR context: min_history(pr_base, last_bot) or oldest_available
    - Push context: min_history(oldest_available, last_bot)

    Returns:
        Tuple of (from_commit, to_commit) where to_commit is always HEAD
    """
    try:
        logging.info("🔍 Determining diff commits...")

        # Always diff to HEAD
        to_commit = "HEAD"

        # Check if we're in PR context
        github_event_name = os.getenv("GITHUB_EVENT_NAME")
        is_pr = github_event_name == "pull_request"

        logging.info(f"Context: {'PR' if is_pr else 'Push'} (GITHUB_EVENT_NAME={github_event_name})")

        if is_pr:
            # PR context: min(pr_base, last_bot) or oldest_available
            pr_base = get_pr_base_commit()
            last_bot = get_last_bot_commit()

            if pr_base and last_bot:
                # Choose the one with fewer commits to HEAD (less history)
                pr_base_count = count_commits_to_head(pr_base)
                last_bot_count = count_commits_to_head(last_bot)

                if pr_base_count <= last_bot_count:
                    from_commit = pr_base
                    logging.info(f"Using PR base commit: {from_commit[:8]} ({pr_base_count} commits to HEAD)")
                else:
                    from_commit = last_bot
                    logging.info(f"Using last bot commit: {from_commit[:8]} ({last_bot_count} commits to HEAD)")
            elif pr_base:
                from_commit = pr_base
                logging.info(f"Using PR base commit (no bot history): {from_commit[:8]}")
            elif last_bot:
                from_commit = last_bot
                logging.info(f"Using last bot commit (no PR base): {from_commit[:8]}")
            else:
                from_commit = get_oldest_available_commit()
                logging.info(f"No PR base or bot history, using oldest available: {from_commit[:8]}")
        else:
            # Push context: min(oldest_available, last_bot)
            oldest_available = get_oldest_available_commit()
            last_bot = get_last_bot_commit()

            if last_bot:
                # Choose the one with fewer commits to HEAD (less history)
                oldest_count = count_commits_to_head(oldest_available)
                last_bot_count = count_commits_to_head(last_bot)

                if oldest_count <= last_bot_count:
                    from_commit = oldest_available
                    logging.info(f"Using oldest available commit: {from_commit[:8]} ({oldest_count} commits to HEAD)")
                else:
                    from_commit = last_bot
                    logging.info(f"Using last bot commit: {from_commit[:8]} ({last_bot_count} commits to HEAD)")
            else:
                from_commit = oldest_available
                logging.info(f"No bot history, using oldest available: {from_commit[:8]}")

        logging.info(f"✅ Diff range determined: {from_commit[:8]}..{to_commit}")
        return from_commit, to_commit

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
        logging.info("🔍 Starting get_changed_py_files...")

        # Use central diff logic
        from_commit, to_commit = determine_diff_commits()
        # Get changed files using central diff logic
        if from_commit == to_commit:
            # No diff to compute, return empty list
            logging.info("No diff range available, no files to process")
            py_files: list[Path] = []
        else:
            # Check if we should return ALL files (no bot/PR history)
            github_event_name = os.getenv("GITHUB_EVENT_NAME")
            is_pr = github_event_name == "pull_request"

            should_return_all_files = False
            if is_pr:
                # In PR: return all files if neither PR base nor bot commit found
                pr_base = get_pr_base_commit()
                last_bot = get_last_bot_commit()
                should_return_all_files = pr_base is None and last_bot is None
            else:
                # In push: return all files if no bot commit found
                last_bot = get_last_bot_commit()
                should_return_all_files = last_bot is None

            if should_return_all_files:
                # First run or no relevant history - return ALL Python files
                logging.info("No relevant commit history found, returning all Python files")
                _, stdout, _ = cmd_output("git", "ls-files", "*.py")
                logging.info(f"Git ls-files output: {repr(stdout[:200])}...")

                py_files = []
                for line in stdout.strip().split("\n"):
                    if line and Path(line).exists():
                        py_files.append(Path(line))
                        logging.debug(f"Added Python file: {line}")
            else:
                # Normal case - diff between commits
                _, stdout, _ = cmd_output("git", "diff", "--name-only", from_commit, to_commit)
                logging.info(f"Git diff {from_commit[:8]}..{to_commit}: {repr(stdout[:200])}...")

                py_files = []
                for line in stdout.strip().split("\n"):
                    if line and line.endswith(".py"):
                        if Path(line).exists():
                            py_files.append(Path(line))
                            logging.debug(f"Added Python file: {line}")
                        else:
                            logging.debug(f"Skipped non-existent file: {line}")

        logging.info(f"Found {len(py_files)} Python files to process: {[str(f) for f in py_files]}")
        return py_files

    except CalledProcessError as e:
        logging.error(f"Failed to get changed files: {e}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error in get_changed_py_files: {e}", exc_info=True)
        return []


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
