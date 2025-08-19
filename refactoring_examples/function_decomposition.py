"""Example refactoring of the long _main_impl function into smaller, focused functions."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from auto_docs_action.config import AppConfig, GitHubConfig, load_app_config, load_github_config
from auto_docs_action.file_processor import FileProcessor, ProcessingResult


# BEFORE: One long function (135 lines) doing everything
def _main_impl_old(claude_command: str | None, max_retries: int | None, retry_delay: float | None, verbose: bool) -> int:
    """Original long implementation - does too many things."""
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


# AFTER: Broken down into smaller, focused functions

@dataclass
class ApplicationContext:
    """Context object to hold application state and configuration."""
    app_config: AppConfig
    github_config: GitHubConfig
    logger: logging.Logger


def _main_impl_refactored(claude_command: str | None, max_retries: int | None, retry_delay: float | None, verbose: bool) -> int:
    """Refactored main implementation using smaller, focused functions."""
    try:
        context = _setup_application_context(claude_command, max_retries, retry_delay, verbose)
        
        if not _validate_prerequisites(context):
            return 1
            
        processor = _initialize_file_processor(context)
        if processor is None:
            return 1
            
        changed_files = _discover_changed_files(context)
        if changed_files is None:
            return 1
            
        if not changed_files:
            context.logger.info("No Python files changed. Nothing to do.")
            return 0
            
        results = _process_files(context, processor, changed_files)
        if results is None:
            return 1
            
        stats = _calculate_statistics(context, processor, results)
        if stats is None:
            return 1
            
        if not _stage_and_commit_changes(context, results, stats):
            return 1
            
        _finalize_workflow(context, stats)
        return _determine_exit_code(stats)
        
    except KeyboardInterrupt:
        print("❌ Process interrupted by user", file=sys.stderr, flush=True)
        return 1
    except Exception as e:
        _handle_unexpected_error(e)
        return 1


def _setup_application_context(
    claude_command: str | None, 
    max_retries: int | None, 
    retry_delay: float | None, 
    verbose: bool
) -> ApplicationContext:
    """Set up application configuration and logging."""
    from auto_docs_action.main_helpers import setup_logging, log_startup_info
    
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Load and configure application settings
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
        
    log_startup_info(app_config)
    
    return ApplicationContext(
        app_config=app_config,
        github_config=github_config,
        logger=logger
    )


def _validate_prerequisites(context: ApplicationContext) -> bool:
    """Validate that all prerequisites are met."""
    from auto_docs_action.main_helpers import validate_prerequisites
    
    prerequisites_valid, error_msg = validate_prerequisites(context.app_config)
    if not prerequisites_valid:
        context.logger.error(error_msg)
        return False
    return True


def _initialize_file_processor(context: ApplicationContext) -> FileProcessor | None:
    """Initialize the file processor."""
    context.logger.info("📋 Initializing FileProcessor...")
    try:
        processor = FileProcessor(
            claude_command=context.app_config.claude_command,
            max_retries=context.app_config.max_retries,
            retry_delay=context.app_config.retry_delay,
        )
        context.logger.info("✅ FileProcessor initialized successfully")
        return processor
    except Exception as e:
        context.logger.error(f"❌ Failed to initialize FileProcessor: {e}", exc_info=True)
        return None


def _discover_changed_files(context: ApplicationContext) -> list[Path] | None:
    """Discover Python files that have changed."""
    from auto_docs_action import git_operations
    
    context.logger.info("🔍 Detecting changed Python files...")
    try:
        changed_files = git_operations.get_changed_py_files()
        context.logger.info(f"✅ Git operations completed, found {len(changed_files)} files")
        
        if changed_files:
            context.logger.info(f"Found {len(changed_files)} changed Python files:")
            for file_path in changed_files:
                context.logger.info(f"  - {file_path}")
                
        return changed_files
    except Exception as e:
        context.logger.error(f"❌ Failed to get changed Python files: {e}", exc_info=True)
        return None


def _process_files(
    context: ApplicationContext, 
    processor: FileProcessor, 
    changed_files: list[Path]
) -> list[ProcessingResult] | None:
    """Process the changed files."""
    context.logger.info("🔄 Processing files...")
    try:
        results = processor.process_multiple_files(changed_files)
        context.logger.info(f"✅ File processing completed, got {len(results)} results")
        return results
    except Exception as e:
        context.logger.error(f"❌ Failed to process files: {e}", exc_info=True)
        return None


def _calculate_statistics(
    context: ApplicationContext, 
    processor: FileProcessor, 
    results: list[ProcessingResult]
) -> dict[str, Any] | None:
    """Calculate processing statistics."""
    context.logger.info("📊 Calculating statistics...")
    try:
        stats = processor.get_processing_statistics(results)
        context.logger.info(f"Processing complete. Statistics: {stats}")
        return stats
    except Exception as e:
        context.logger.error(f"❌ Failed to calculate statistics: {e}", exc_info=True)
        return None


def _stage_and_commit_changes(
    context: ApplicationContext, 
    results: list[ProcessingResult], 
    stats: dict[str, Any]
) -> bool:
    """Stage successful changes and create commit if needed."""
    from auto_docs_action import git_operations
    from auto_docs_action.main_helpers import create_commit_message
    
    # Stage successful changes
    context.logger.info("📝 Staging successful changes...")
    staged_any = False
    try:
        for processing_result in results:
            if processing_result.success and processing_result.changes_made:
                context.logger.info(f"Staging changes for {processing_result.file_path}")
                if git_operations.stage_file(processing_result.file_path):
                    staged_any = True
                else:
                    context.logger.error(f"Failed to stage {processing_result.file_path}")
        context.logger.info(f"✅ Staging completed, staged_any={staged_any}")
    except Exception as e:
        context.logger.error(f"❌ Failed during staging: {e}", exc_info=True)
        return False

    # Create commit if we have staged changes
    context.logger.info("📦 Creating commit if needed...")
    try:
        if staged_any and git_operations.has_staged_files():
            context.logger.info("Creating commit message...")
            commit_message = create_commit_message(stats, results)
            context.logger.info(f"Commit message prepared: {len(commit_message)} characters")

            if git_operations.create_commit(commit_message):
                context.logger.info("Successfully created commit with docstring updates")
            else:
                context.logger.error("Failed to create commit")
                return False
        elif staged_any:
            context.logger.warning("Files were processed but no changes were staged")
        else:
            context.logger.info("No files required docstring updates")
        return True
    except Exception as e:
        context.logger.error(f"❌ Failed during commit creation: {e}", exc_info=True)
        return False


def _finalize_workflow(context: ApplicationContext, stats: dict[str, Any]) -> None:
    """Finalize the workflow by setting GitHub outputs."""
    from auto_docs_action.main_helpers import set_github_outputs
    
    set_github_outputs(context.github_config, stats)


def _determine_exit_code(stats: dict[str, Any]) -> int:
    """Determine the appropriate exit code based on statistics."""
    from auto_docs_action.main_helpers import determine_exit_code
    
    return determine_exit_code(stats)


def _handle_unexpected_error(error: Exception) -> None:
    """Handle unexpected errors with proper logging."""
    error_msg = f"❌ Unexpected error in main: {error}"
    try:
        logger = logging.getLogger(__name__)
        logger.error(error_msg, exc_info=True)
    except Exception:
        print(error_msg, file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()


"""
Benefits of the refactored approach:

1. **Single Responsibility**: Each function has one clear purpose
2. **Testability**: Each function can be unit tested independently  
3. **Readability**: The main flow is clear and easy to follow
4. **Maintainability**: Changes to one aspect don't affect others
5. **Error Handling**: Each step can handle its own errors appropriately
6. **Reusability**: Individual functions can be reused if needed

The main function now reads like a high-level workflow:
1. Setup context
2. Validate prerequisites  
3. Initialize processor
4. Discover files
5. Process files
6. Calculate statistics
7. Stage and commit
8. Finalize

Each step is a focused function that can be understood and tested in isolation.
"""