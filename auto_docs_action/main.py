"""Main entry point for the auto-docs GitHub Action."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import click

from auto_docs_action import git_operations
from auto_docs_action.config import load_app_config
from auto_docs_action.config import load_github_config
from auto_docs_action.file_processor import FileProcessor
from auto_docs_action.main_helpers import create_commit_message
from auto_docs_action.main_helpers import determine_exit_code
from auto_docs_action.main_helpers import log_startup_info
from auto_docs_action.main_helpers import set_github_outputs
from auto_docs_action.main_helpers import setup_logging
from auto_docs_action.main_helpers import validate_prerequisites


@click.command()
@click.option("--claude-command", default=None, help='Claude CLI command to use (default: from environment or "claude")')
@click.option(
    "--max-retries", default=None, type=int, help="Maximum number of retries per file (default: from environment or 3)"
)
@click.option(
    "--retry-delay", default=None, type=float, help="Delay between retries in seconds (default: from environment or 1.0)"
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def main(claude_command: str | None, max_retries: int | None, retry_delay: float | None, verbose: bool) -> int:
    """Auto-docs GitHub Action CLI.

    Automatically updates Python docstrings using Claude Code CLI.
    Can be run as a GitHub Action or standalone CLI tool.

    Args:
        claude_command: Claude CLI command to use
        max_retries: Maximum number of retries per file
        retry_delay: Delay between retries in seconds
        verbose: Enable verbose logging

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    return _main_impl(claude_command, max_retries, retry_delay, verbose)


def _main_impl(claude_command: str | None, max_retries: int | None, retry_delay: float | None, verbose: bool) -> int:
    """Implementation of main logic without Click decorators."""
    try:
        setup_logging()
        logger = logging.getLogger(__name__)

        # Load configuration and override with CLI parameters if provided
        app_config = load_app_config()
        if claude_command:
            app_config.claude_command = claude_command
        if max_retries is not None:
            app_config.max_retries = max_retries
        if retry_delay is not None:
            app_config.retry_delay = retry_delay

        github_config = load_github_config()

        # Set verbose logging if requested
        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        # Log startup information
        log_startup_info(app_config)

        # Validate prerequisites
        prerequisites_valid, error_msg = validate_prerequisites(app_config)
        if not prerequisites_valid:
            logger.error(error_msg)
            return 1

        # Initialize FileProcessor
        logger.info("📋 Initializing FileProcessor...")
        try:
            processor = FileProcessor(
                claude_command=app_config.claude_command,
                max_retries=app_config.max_retries,
                retry_delay=app_config.retry_delay,
            )
            logger.info("✅ FileProcessor initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize FileProcessor: {e}", exc_info=True)
            return 1

        # Get changed Python files from git
        logger.info("🔍 Detecting changed Python files...")
        try:
            changed_files = git_operations.get_changed_py_files()
            logger.info(f"✅ Git operations completed, found {len(changed_files)} files")
        except Exception as e:
            logger.error(f"❌ Failed to get changed Python files: {e}", exc_info=True)
            return 1

        if not changed_files:
            logger.info("No Python files changed. Nothing to do.")
            return 0

        logger.info(f"Found {len(changed_files)} changed Python files:")
        for file_path in changed_files:
            logger.info(f"  - {file_path}")

        # Process files
        logger.info("🔄 Processing files...")
        try:
            results = processor.process_multiple_files(changed_files)
            logger.info(f"✅ File processing completed, got {len(results)} results")
        except Exception as e:
            logger.error(f"❌ Failed to process files: {e}", exc_info=True)
            return 1

        # Get statistics
        logger.info("📊 Calculating statistics...")
        try:
            stats = processor.get_processing_statistics(results)
            logger.info(f"Processing complete. Statistics: {stats}")
        except Exception as e:
            logger.error(f"❌ Failed to calculate statistics: {e}", exc_info=True)
            return 1

        # Run pre-commit hook if configured
        pre_commit_hook = os.getenv("PRE_COMMIT_HOOK", "").strip()
        if pre_commit_hook:
            logger.info("Running pre-commit hook before staging...")
            if not git_operations.run_pre_commit_hook(pre_commit_hook):
                logger.error("Pre-commit hook failed critically (timeout or exception)")
                return 1

        # Stage successful changes
        logger.info("📝 Staging successful changes...")
        staged_any = False
        try:
            for processing_result in results:
                if processing_result.success and processing_result.changes_made:
                    logger.info(f"Staging changes for {processing_result.file_path}")
                    if git_operations.stage_file(processing_result.file_path):
                        staged_any = True
                    else:
                        logger.error(f"Failed to stage {processing_result.file_path}")
            logger.info(f"✅ Staging completed, staged_any={staged_any}")
        except Exception as e:
            logger.error(f"❌ Failed during staging: {e}", exc_info=True)
            return 1

        # Create commit if we have staged changes
        logger.info("📦 Creating commit if needed...")
        try:
            if staged_any and git_operations.has_staged_files():
                logger.info("Creating commit message...")
                commit_message = create_commit_message(stats, results)
                logger.info(f"Commit message prepared: {len(commit_message)} characters")

                if git_operations.create_commit(commit_message):
                    logger.info("Successfully created commit with docstring updates")
                else:
                    logger.error("Failed to create commit")
                    return 1
            elif staged_any:
                logger.warning("Files were processed but no changes were staged")
            else:
                logger.info("No files required docstring updates")
        except Exception as e:
            logger.error(f"❌ Failed during commit creation: {e}", exc_info=True)
            return 1

        # Set GitHub Actions outputs
        set_github_outputs(github_config, stats)

        # Report final status and return exit code
        return determine_exit_code(stats)

    except KeyboardInterrupt:
        print("❌ Process interrupted by user", file=sys.stderr, flush=True)
        return 1
    except Exception as e:
        # Ensure we can print error even if logger fails
        error_msg = f"❌ Unexpected error in main: {e}"
        try:
            logger = logging.getLogger(__name__)
            logger.error(error_msg, exc_info=True)
        except Exception:
            print(error_msg, file=sys.stderr, flush=True)
            import traceback

            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()
        return 1


def main_for_testing() -> int:
    """Non-CLI version of main for testing purposes."""
    # Call the underlying function directly, bypassing Click decorators
    return _main_impl(None, None, None, False)


if __name__ == "__main__":
    sys.exit(main())
