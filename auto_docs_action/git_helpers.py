"""Helper functions for git operations to improve modularity."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from auto_docs_action.config import GitHubConfig
from auto_docs_action.constants import COMMAND_TIMEOUT_SECONDS
from auto_docs_action.constants import GITHUB_ACTIONS_BOT_PATTERNS
from auto_docs_action.constants import LARGE_COMMIT_COUNT_FALLBACK
from auto_docs_action.git_operations import CalledProcessError
from auto_docs_action.git_operations import cmd_output


@dataclass
class CommitInfo:
    """Information about a git commit."""

    sha: str
    distance_to_head: int


@dataclass
class DiffRange:
    """Git diff range information."""

    from_commit: str
    to_commit: str

    @property
    def has_diff(self) -> bool:
        """Check if there's an actual diff to compute."""
        return self.from_commit != self.to_commit


class GitCommitFinder:
    """Helper class to find specific commits in git history."""

    @staticmethod
    def find_last_bot_commit() -> CommitInfo | None:
        """Find the most recent commit made by github-actions bot.

        Returns:
            CommitInfo if found, None otherwise
        """
        logging.info("🔍 Searching for last github-actions commit...")

        for i, pattern in enumerate(GITHUB_ACTIONS_BOT_PATTERNS):
            try:
                logging.debug(f"Trying pattern {i + 1}/{len(GITHUB_ACTIONS_BOT_PATTERNS)}: {pattern}")
                _, stdout, _ = cmd_output("git", "log", f"--author={pattern}", "--format=%H", "-1")
                commit_sha = stdout.strip()

                if commit_sha:
                    distance = GitCommitFinder._count_commits_to_head(commit_sha)
                    logging.info(f"✅ Found last github-actions commit: {commit_sha[:8]} with pattern: {pattern}")
                    return CommitInfo(sha=commit_sha, distance_to_head=distance)
                else:
                    logging.debug(f"Pattern {pattern} returned empty result")

            except CalledProcessError as e:
                logging.debug(f"Pattern {pattern} failed: {e}")
                continue

        logging.info("ℹ️ No github-actions commits found in history")
        return None

    @staticmethod
    def find_pr_base_commit(github_config: GitHubConfig) -> CommitInfo | None:
        """Find the PR base commit using merge-base.

        Args:
            github_config: GitHub configuration context

        Returns:
            CommitInfo if found, None otherwise
        """
        if not github_config.is_pull_request or not github_config.has_base_ref:
            logging.debug(f"Not in PR context (event: {github_config.event_name})")
            return None

        base_ref = github_config.base_ref
        if not base_ref:
            logging.debug("No base ref available")
            return None

        logging.info(f"PR target branch: {base_ref}")

        # Try different ref formats
        target_refs = [
            f"origin/{base_ref}",
            base_ref,
        ]

        for target_ref in target_refs:
            try:
                _, stdout, _ = cmd_output("git", "merge-base", "HEAD", target_ref)
                merge_base = stdout.strip()
                distance = GitCommitFinder._count_commits_to_head(merge_base)
                logging.info(f"✅ Found PR base commit via merge-base with {target_ref}: {merge_base[:8]}")
                return CommitInfo(sha=merge_base, distance_to_head=distance)
            except CalledProcessError:
                logging.debug(f"Could not find merge-base with {target_ref}")
                continue

        # Try boundary commit approach
        pr_base = GitCommitFinder._try_boundary_commit(base_ref)
        if pr_base:
            return pr_base

        # Last resort: oldest available commit
        oldest = GitCommitFinder.find_oldest_available_commit()
        if oldest:
            logging.info(f"✅ Using oldest available commit as PR base: {oldest.sha[:8]}")
            return oldest

        logging.debug("Could not determine PR base commit")
        return None

    @staticmethod
    def find_oldest_available_commit() -> CommitInfo:
        """Find the oldest commit available in repository.

        Returns:
            CommitInfo for the oldest commit
        """
        # Try to get the first commit (root commit)
        try:
            _, stdout, _ = cmd_output("git", "rev-list", "--max-parents=0", "HEAD")
            first_commit = stdout.strip()
            if first_commit:
                distance = GitCommitFinder._count_commits_to_head(first_commit)
                logging.info(f"✅ Found first commit: {first_commit[:8]}")
                return CommitInfo(sha=first_commit, distance_to_head=distance)
        except CalledProcessError:
            logging.debug("Could not find first commit, trying reverse order")

        # Fallback for shallow checkout
        try:
            _, stdout, _ = cmd_output("git", "rev-list", "--max-count=1", "--reverse", "HEAD")
            oldest_commit = stdout.strip()
            if oldest_commit:
                distance = GitCommitFinder._count_commits_to_head(oldest_commit)
                logging.info(f"✅ Found oldest available commit: {oldest_commit[:8]}")
                return CommitInfo(sha=oldest_commit, distance_to_head=distance)
        except CalledProcessError:
            logging.debug("Could not find oldest commit, using HEAD")

        # Ultimate fallback: use HEAD
        _, stdout, _ = cmd_output("git", "rev-parse", "HEAD")
        head_commit = stdout.strip()
        logging.warning(f"⚠️ Using HEAD as oldest commit: {head_commit[:8]}")
        return CommitInfo(sha=head_commit, distance_to_head=0)

    @staticmethod
    def _count_commits_to_head(commit: str) -> int:
        """Count commits from given commit to HEAD."""
        try:
            _, stdout, _ = cmd_output("git", "rev-list", "--count", f"{commit}..HEAD")
            count = int(stdout.strip())
            logging.debug(f"Commit {commit[:8]} is {count} commits behind HEAD")
            return count
        except (CalledProcessError, ValueError) as e:
            logging.debug(f"Could not count commits for {commit}: {e}")
            return LARGE_COMMIT_COUNT_FALLBACK

    @staticmethod
    def _try_boundary_commit(base_ref: str) -> CommitInfo | None:
        """Try to find PR base using boundary commit approach."""
        try:
            boundary_ref = f"HEAD...origin/{base_ref}^"
            _, stdout, _ = cmd_output("git", "rev-list", "--boundary", boundary_ref, check=False)
            if stdout.strip():
                lines = stdout.strip().split("\n")
                for line in lines:
                    if line.startswith("-"):
                        boundary_commit = line[1:]  # Remove the - prefix
                        distance = GitCommitFinder._count_commits_to_head(boundary_commit)
                        logging.info(f"✅ Found PR base commit from boundary: {boundary_commit[:8]}")
                        return CommitInfo(sha=boundary_commit, distance_to_head=distance)
        except CalledProcessError:
            pass
        return None


class DiffRangeDeterminer:
    """Determines appropriate diff ranges for different contexts."""

    def __init__(self, github_config: GitHubConfig):
        """Initialize with GitHub configuration."""
        self.github_config = github_config

    def determine_range(self) -> DiffRange:
        """Determine the appropriate diff range based on context.

        Returns:
            DiffRange with from and to commits
        """
        logging.info("🔍 Determining diff commits...")

        if self.github_config.is_pull_request:
            return self._determine_pr_range()
        else:
            return self._determine_push_range()

    def _determine_pr_range(self) -> DiffRange:
        """Determine diff range for pull request context."""
        logging.info("Context: PR")

        pr_base = GitCommitFinder.find_pr_base_commit(self.github_config)
        last_bot = GitCommitFinder.find_last_bot_commit()

        if pr_base and last_bot:
            # Choose the one with fewer commits to HEAD (less history)
            if pr_base.distance_to_head <= last_bot.distance_to_head:
                from_commit = pr_base.sha
                logging.info(f"Using PR base commit: {from_commit[:8]} ({pr_base.distance_to_head} commits to HEAD)")
            else:
                from_commit = last_bot.sha
                logging.info(f"Using last bot commit: {from_commit[:8]} ({last_bot.distance_to_head} commits to HEAD)")
        elif pr_base:
            from_commit = pr_base.sha
            logging.info(f"Using PR base commit (no bot history): {from_commit[:8]}")
        elif last_bot:
            from_commit = last_bot.sha
            logging.info(f"Using last bot commit (no PR base): {from_commit[:8]}")
        else:
            oldest = GitCommitFinder.find_oldest_available_commit()
            from_commit = oldest.sha
            logging.info(f"No PR base or bot history, using oldest available: {from_commit[:8]}")

        return DiffRange(from_commit=from_commit, to_commit="HEAD")

    def _determine_push_range(self) -> DiffRange:
        """Determine diff range for push context."""
        logging.info("Context: Push")

        oldest_available = GitCommitFinder.find_oldest_available_commit()
        last_bot = GitCommitFinder.find_last_bot_commit()

        if last_bot:
            # Choose the one with fewer commits to HEAD (less history)
            if oldest_available.distance_to_head <= last_bot.distance_to_head:
                from_commit = oldest_available.sha
                logging.info(
                    f"Using oldest available commit: {from_commit[:8]} ({oldest_available.distance_to_head} commits to HEAD)"
                )
            else:
                from_commit = last_bot.sha
                logging.info(f"Using last bot commit: {from_commit[:8]} ({last_bot.distance_to_head} commits to HEAD)")
        else:
            from_commit = oldest_available.sha
            logging.info(f"No bot history, using oldest available: {from_commit[:8]}")

        return DiffRange(from_commit=from_commit, to_commit="HEAD")
