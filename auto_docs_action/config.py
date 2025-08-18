"""Configuration management for the auto-docs GitHub Action."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from auto_docs_action.constants import DEFAULT_CLAUDE_COMMAND
from auto_docs_action.constants import DEFAULT_MAX_RETRIES
from auto_docs_action.constants import DEFAULT_RETRY_DELAY
from auto_docs_action.constants import ENV_ANTHROPIC_API_KEY
from auto_docs_action.constants import ENV_CLAUDE_COMMAND
from auto_docs_action.constants import ENV_GITHUB_BASE_REF
from auto_docs_action.constants import ENV_GITHUB_EVENT_NAME
from auto_docs_action.constants import ENV_GITHUB_HEAD_REF
from auto_docs_action.constants import ENV_GITHUB_OUTPUT
from auto_docs_action.constants import ENV_GITHUB_REF_NAME
from auto_docs_action.constants import ENV_GITHUB_SHA
from auto_docs_action.constants import ENV_MAX_RETRIES
from auto_docs_action.constants import ENV_RETRY_DELAY
from auto_docs_action.constants import EVENT_PULL_REQUEST
from auto_docs_action.constants import GIT_DIRECTORY


@dataclass
class AppConfig:
    """Main application configuration."""

    claude_command: str
    max_retries: int
    retry_delay: float
    anthropic_api_key: str | None


@dataclass
class GitHubConfig:
    """GitHub Actions environment configuration."""

    event_name: str | None
    base_ref: str | None
    head_ref: str | None
    ref_name: str | None
    sha: str | None
    output_file: str | None

    @property
    def is_pull_request(self) -> bool:
        """Check if current event is a pull request."""
        return self.event_name == EVENT_PULL_REQUEST

    @property
    def has_base_ref(self) -> bool:
        """Check if base ref is available."""
        return self.base_ref is not None and self.base_ref.strip() != ""


def load_app_config() -> AppConfig:
    """Load application configuration from environment variables.

    Returns:
        AppConfig with loaded values and defaults
    """
    return AppConfig(
        claude_command=os.getenv(ENV_CLAUDE_COMMAND, DEFAULT_CLAUDE_COMMAND),
        max_retries=int(os.getenv(ENV_MAX_RETRIES, str(DEFAULT_MAX_RETRIES))),
        retry_delay=float(os.getenv(ENV_RETRY_DELAY, str(DEFAULT_RETRY_DELAY))),
        anthropic_api_key=os.getenv(ENV_ANTHROPIC_API_KEY),
    )


def load_github_config() -> GitHubConfig:
    """Load GitHub Actions configuration from environment variables.

    Returns:
        GitHubConfig with current GitHub Actions context
    """
    return GitHubConfig(
        event_name=os.getenv(ENV_GITHUB_EVENT_NAME),
        base_ref=os.getenv(ENV_GITHUB_BASE_REF),
        head_ref=os.getenv(ENV_GITHUB_HEAD_REF),
        ref_name=os.getenv(ENV_GITHUB_REF_NAME),
        sha=os.getenv(ENV_GITHUB_SHA),
        output_file=os.getenv(ENV_GITHUB_OUTPUT),
    )


def is_git_repository() -> bool:
    """Check if current directory is a git repository.

    Returns:
        True if .git directory exists
    """
    return Path(GIT_DIRECTORY).exists()


def validate_claude_availability(claude_command: str) -> tuple[bool, str | None]:
    """Validate that Claude CLI is available.

    Args:
        claude_command: Command name to check

    Returns:
        Tuple of (is_available, path_or_none)
    """
    import shutil

    claude_path = shutil.which(claude_command)
    return claude_path is not None, claude_path
