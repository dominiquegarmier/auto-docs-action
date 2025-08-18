"""Helper functions for main.py to improve modularity and maintainability."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from auto_docs_action.config import AppConfig
from auto_docs_action.config import GitHubConfig
from auto_docs_action.config import is_git_repository
from auto_docs_action.config import validate_claude_availability
from auto_docs_action.constants import LOG_FORMAT


def setup_logging() -> None:
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def log_startup_info(app_config: AppConfig) -> None:
    """Log startup information and configuration."""
    logger = logging.getLogger(__name__)

    logger.info("🚀 Auto-docs action starting...")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {Path.cwd()}")
    logger.info("Environment variables:")
    logger.info(f"  CLAUDE_COMMAND: {app_config.claude_command}")
    logger.info(f"  MAX_RETRIES: {app_config.max_retries}")
    logger.info(f"  ANTHROPIC_API_KEY: {'SET' if app_config.anthropic_api_key else 'NOT SET'}")
    logger.info("Starting auto-docs GitHub Action")

    # Immediately flush logs to ensure they appear
    sys.stdout.flush()
    sys.stderr.flush()


def validate_prerequisites(app_config: AppConfig) -> tuple[bool, str | None]:
    """Validate that all prerequisites are met.

    Args:
        app_config: Application configuration

    Returns:
        Tuple of (success, error_message)
    """
    logger = logging.getLogger(__name__)

    # Check if we're in a git repository
    logger.info("🔍 Checking git repository...")
    if not is_git_repository():
        return False, "❌ Not in a git repository!"
    logger.info("✅ Git repository detected")

    # Check if Claude command is available
    logger.info(f"🔍 Checking Claude command availability: {app_config.claude_command}")
    try:
        is_available, claude_path = validate_claude_availability(app_config.claude_command)

        if not is_available:
            error_msg = f"❌ Claude command '{app_config.claude_command}' not found in PATH"
            logger.error(error_msg)
            _log_debug_commands(logger)
            return False, error_msg

        logger.info(f"✅ Claude command found at: {claude_path}")
        return True, None

    except Exception as e:
        error_msg = f"❌ Error checking Claude command: {e}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg


def _log_debug_commands(logger: logging.Logger) -> None:
    """Log debug information about available commands."""
    logger.info("Available commands in PATH:")
    try:
        import subprocess

        result = subprocess.run(["which", "claude"], capture_output=True, text=True)
        logger.info(f"which claude: {result.stdout.strip()} (return code: {result.returncode})")

        result = subprocess.run(["npm", "list", "-g", "@anthropic-ai/claude-code"], capture_output=True, text=True)
        output = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        logger.info(f"npm list claude-code: {output}")

    except Exception as cmd_e:
        logger.error(f"Error checking commands: {cmd_e}")


def create_commit_message(stats: dict, results: list) -> str:
    """Create a commit message for the docstring updates.

    Args:
        stats: Processing statistics
        results: List of processing results

    Returns:
        Formatted commit message
    """
    from auto_docs_action.constants import GITHUB_ACTIONS_BOT_EMAIL
    from auto_docs_action.constants import GITHUB_ACTIONS_BOT_NAME

    commit_message = f"docs: auto-update docstrings\n\n" f"Updated docstrings for {stats['files_with_changes']} files:\n"

    for processing_result in results:
        if processing_result.success and processing_result.changes_made and processing_result.validation_result:
            docstring_count = len(processing_result.validation_result.docstring_changes or [])
            commit_message += f"- {processing_result.file_path.name}: {docstring_count} docstring changes\n"

    commit_message += f"\nCo-authored-by: {GITHUB_ACTIONS_BOT_NAME} " f"<{GITHUB_ACTIONS_BOT_EMAIL}>"

    return commit_message


def set_github_outputs(github_config: GitHubConfig, stats: dict) -> None:
    """Set GitHub Actions output variables.

    Args:
        github_config: GitHub configuration
        stats: Processing statistics
    """
    logger = logging.getLogger(__name__)

    if not github_config.output_file:
        return

    try:
        with open(github_config.output_file, "a") as f:
            f.write(f"files_processed={stats['total_files']}\n")
            f.write(f"files_successful={stats['successful']}\n")
            f.write(f"files_failed={stats['failed']}\n")
        logger.info("✅ GitHub Actions outputs set")
    except Exception as e:
        logger.warning(f"Could not set GitHub Actions outputs: {e}")


def determine_exit_code(stats: dict) -> int:
    """Determine the appropriate exit code based on processing statistics.

    Args:
        stats: Processing statistics

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = logging.getLogger(__name__)

    logger.info("🏁 Reporting final status...")
    if stats["failed"] > 0:
        logger.warning(f"{stats['failed']} files failed processing")
        return 1
    else:
        logger.info("All files processed successfully")
        return 0
