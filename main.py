"""Main entry point for the auto-docs GitHub Action."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import git_operations
from file_processor import FileProcessor


def setup_logging() -> None:
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main() -> int:
    """Main entry point for the auto-docs GitHub Action.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting auto-docs GitHub Action")

        # Initialize components with environment variables
        claude_command = os.getenv("CLAUDE_COMMAND", "claude")
        max_retries = int(os.getenv("MAX_RETRIES", "3"))
        retry_delay = float(os.getenv("RETRY_DELAY", "1.0"))

        processor = FileProcessor(
            claude_command=claude_command,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

        # Get changed Python files from git
        logger.info("Detecting changed Python files...")
        changed_files = git_operations.get_changed_py_files()

        if not changed_files:
            logger.info("No Python files changed. Nothing to do.")
            return 0

        logger.info(f"Found {len(changed_files)} changed Python files:")
        for file_path in changed_files:
            logger.info(f"  - {file_path}")

        # Process files
        logger.info("Processing files...")
        results = processor.process_multiple_files(changed_files)

        # Get statistics
        stats = processor.get_processing_statistics(results)
        logger.info(f"Processing complete. Statistics: {stats}")

        # Stage successful changes
        staged_any = False
        for result in results:
            if result.success and result.changes_made:
                logger.info(f"Staging changes for {result.file_path}")
                if git_operations.stage_file(result.file_path):
                    staged_any = True
                else:
                    logger.error(f"Failed to stage {result.file_path}")

        # Create commit if we have staged changes
        if staged_any and git_operations.has_staged_files():
            commit_message = (
                f"docs: auto-update docstrings\n\n" f"Updated docstrings for {stats['files_with_changes']} files:\n"
            )

            for result in results:
                if result.success and result.changes_made and result.validation_result:
                    docstring_count = len(result.validation_result.docstring_changes or [])
                    commit_message += f"- {result.file_path.name}: {docstring_count} docstring changes\n"

            commit_message += "\nCo-authored-by: auto-docs[bot] <auto-docs[bot]@users.noreply.github.com>"

            if git_operations.create_commit(commit_message):
                logger.info("Successfully created commit with docstring updates")
            else:
                logger.error("Failed to create commit")
                return 1
        elif staged_any:
            logger.warning("Files were processed but no changes were staged")
        else:
            logger.info("No files required docstring updates")

        # Report final status
        if stats["failed"] > 0:
            logger.warning(f"{stats['failed']} files failed processing")
            return 1
        else:
            logger.info("All files processed successfully")
            return 0

    except Exception as e:
        logger.error(f"Unexpected error in main: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
