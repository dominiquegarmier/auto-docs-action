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
    try:
        setup_logging()
        logger = logging.getLogger(__name__)

        logger.info("🚀 Auto-docs action starting...")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {Path.cwd()}")
        logger.info("Environment variables:")
        logger.info(f"  CLAUDE_COMMAND: {os.getenv('CLAUDE_COMMAND', 'NOT SET')}")
        logger.info(f"  MAX_RETRIES: {os.getenv('MAX_RETRIES', 'NOT SET')}")
        logger.info(f"  ANTHROPIC_API_KEY: {'SET' if os.getenv('ANTHROPIC_API_KEY') else 'NOT SET'}")
        logger.info("Starting auto-docs GitHub Action")

        # Immediately flush logs to ensure they appear
        sys.stdout.flush()
        sys.stderr.flush()

        # Initialize components with environment variables
        logger.info("📋 Initializing FileProcessor...")
        try:
            claude_command = os.getenv("CLAUDE_COMMAND", "claude")
            max_retries = int(os.getenv("MAX_RETRIES", "3"))
            retry_delay = float(os.getenv("RETRY_DELAY", "1.0"))
            logger.info(
                f"Configuration: claude_command={claude_command}, max_retries={max_retries}, retry_delay={retry_delay}"
            )

            processor = FileProcessor(
                claude_command=claude_command,
                max_retries=max_retries,
                retry_delay=retry_delay,
            )
            logger.info("✅ FileProcessor initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize FileProcessor: {e}", exc_info=True)
            return 1

        # Check if we're in a git repository
        logger.info("🔍 Checking git repository...")
        if not Path(".git").exists():
            logger.error("❌ Not in a git repository!")
            return 1
        logger.info("✅ Git repository detected")

        # Check if Claude command is available
        logger.info(f"🔍 Checking Claude command availability: {claude_command}")
        try:
            import shutil

            claude_path = shutil.which(claude_command)
            if not claude_path:
                logger.error(f"❌ Claude command '{claude_command}' not found in PATH")
                # List available commands for debugging
                logger.info("Available commands in PATH:")
                try:
                    import subprocess

                    result = subprocess.run(["which", "claude"], capture_output=True, text=True)
                    logger.info(f"which claude: {result.stdout.strip()} (return code: {result.returncode})")
                    result = subprocess.run(["npm", "list", "-g", "@anthropic-ai/claude-code"], capture_output=True, text=True)
                    logger.info(
                        f"npm list claude-code: {result.stdout.strip() if result.returncode == 0 else result.stderr.strip()}"
                    )
                except Exception as cmd_e:
                    logger.error(f"Error checking commands: {cmd_e}")
                return 1
            logger.info(f"✅ Claude command found at: {claude_path}")
        except Exception as e:
            logger.error(f"❌ Error checking Claude command: {e}", exc_info=True)
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
                commit_message = (
                    f"docs: auto-update docstrings\n\n" f"Updated docstrings for {stats['files_with_changes']} files:\n"
                )

                for processing_result in results:
                    if processing_result.success and processing_result.changes_made and processing_result.validation_result:
                        docstring_count = len(processing_result.validation_result.docstring_changes or [])
                        commit_message += f"- {processing_result.file_path.name}: {docstring_count} docstring changes\n"

                commit_message += (
                    "\nCo-authored-by: github-actions[bot] " "<41898282+github-actions[bot]@users.noreply.github.com>"
                )
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

        # Output GitHub Actions variables
        github_output = os.getenv("GITHUB_OUTPUT")
        if github_output:
            try:
                with open(github_output, "a") as f:
                    f.write(f"files_processed={stats['total_files']}\n")
                    f.write(f"files_successful={stats['successful']}\n")
                    f.write(f"files_failed={stats['failed']}\n")
                logger.info("✅ GitHub Actions outputs set")
            except Exception as e:
                logger.warning(f"Could not set GitHub Actions outputs: {e}")

        # Report final status
        logger.info("🏁 Reporting final status...")
        if stats["failed"] > 0:
            logger.warning(f"{stats['failed']} files failed processing")
            return 1
        else:
            logger.info("All files processed successfully")
            return 0

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


if __name__ == "__main__":
    sys.exit(main())
