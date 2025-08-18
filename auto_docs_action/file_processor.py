"""Module for processing Python files with docstring updates and validation."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auto_docs_action import ast_validator
from auto_docs_action import docstring_updater
from auto_docs_action.ast_validator import ValidationResult
from auto_docs_action.docstring_updater import DocstringUpdateResult


@dataclass
class ProcessingResult:
    """Result of processing a single Python file."""

    success: bool
    file_path: Path
    changes_made: bool = False
    validation_result: ValidationResult | None = None
    update_result: DocstringUpdateResult | None = None
    error_message: str | None = None
    retry_count: int = 0


class FileProcessor:
    """Processes Python files with docstring updates, validation, and retry logic."""

    def __init__(
        self,
        claude_command: str = "claude",
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """Initialize the file processor.

        Args:
            claude_command: Command to execute Claude Code CLI (default: "claude")
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay: Delay between retries in seconds (default: 1.0)
        """
        self.claude_command = claude_command
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def process_file(self, file_path: Path) -> ProcessingResult:
        """Process a single Python file with retry logic.

        Args:
            file_path: Path to the Python file to process

        Returns:
            ProcessingResult with the operation outcome
        """
        logging.info(f"Processing file: {file_path}")

        # Store original content for rollback
        try:
            original_content = file_path.read_text()
        except Exception as e:
            logging.error(f"Failed to read original content from {file_path}: {e}")
            return ProcessingResult(success=False, file_path=file_path, error_message=f"Failed to read file: {e}")

        # Attempt processing with retries
        for attempt in range(self.max_retries + 1):
            try:
                result = self._attempt_processing(file_path, original_content, attempt)

                if result.success:
                    logging.info(f"Successfully processed {file_path} on attempt {attempt + 1}")
                    return result

                # If not successful and we have retries left, restore and retry
                if attempt < self.max_retries:
                    logging.warning(f"Processing failed for {file_path} on attempt {attempt + 1}, retrying...")
                    self._restore_file_content(file_path, original_content)

                    if self.retry_delay > 0:
                        time.sleep(self.retry_delay)
                else:
                    logging.error(f"Processing failed for {file_path} after {self.max_retries + 1} attempts")
                    result.retry_count = attempt
                    return result

            except Exception as e:
                logging.error(f"Unexpected error processing {file_path} on attempt {attempt + 1}: {e}")

                if attempt < self.max_retries:
                    self._restore_file_content(file_path, original_content)
                    if self.retry_delay > 0:
                        time.sleep(self.retry_delay)
                else:
                    return ProcessingResult(
                        success=False,
                        file_path=file_path,
                        error_message=f"Unexpected error after {attempt + 1} attempts: {e}",
                        retry_count=attempt,
                    )

        # Should not reach here, but just in case
        return ProcessingResult(
            success=False,
            file_path=file_path,
            error_message="Processing failed for unknown reasons",
            retry_count=self.max_retries,
        )

    def _attempt_processing(self, file_path: Path, original_content: str, attempt: int) -> ProcessingResult:
        """Attempt to process a file once.

        Args:
            file_path: Path to the Python file
            original_content: Original file content
            attempt: Current attempt number (0-based)

        Returns:
            ProcessingResult for this attempt
        """
        logging.debug(f"Attempting to process {file_path} (attempt {attempt + 1})")

        # Step 1: Update docstrings using Claude Code CLI
        update_result = docstring_updater.update_docstrings(file_path, self.claude_command)

        if not update_result.success:
            logging.warning(f"Docstring update failed for {file_path}: {update_result.error_message}")
            return ProcessingResult(
                success=False,
                file_path=file_path,
                update_result=update_result,
                error_message=f"Docstring update failed: {update_result.error_message}",
                retry_count=attempt,
            )

        if not update_result.updated_content:
            logging.info(f"No content updates for {file_path}")
            return ProcessingResult(
                success=True, file_path=file_path, changes_made=False, update_result=update_result, retry_count=attempt
            )

        # Step 2: Write updated content to file
        try:
            file_path.write_text(update_result.updated_content)
            logging.debug(f"Wrote updated content to {file_path}")
        except Exception as e:
            logging.error(f"Failed to write updated content to {file_path}: {e}")
            return ProcessingResult(
                success=False,
                file_path=file_path,
                update_result=update_result,
                error_message=f"Failed to write updated content: {e}",
                retry_count=attempt,
            )

        # Step 3: Validate that only docstrings were changed
        validation_result = ast_validator.validate_changes(original_content, file_path)

        if not validation_result.passed:
            logging.warning(f"AST validation failed for {file_path}: {validation_result.reason}")
            return ProcessingResult(
                success=False,
                file_path=file_path,
                validation_result=validation_result,
                update_result=update_result,
                error_message=f"Validation failed: {validation_result.reason}",
                retry_count=attempt,
            )

        logging.info(f"Successfully validated changes for {file_path}")
        logging.debug(f"Validation found {len(validation_result.docstring_changes or [])} docstring changes")

        return ProcessingResult(
            success=True,
            file_path=file_path,
            changes_made=True,
            validation_result=validation_result,
            update_result=update_result,
            retry_count=attempt,
        )

    def _restore_file_content(self, file_path: Path, original_content: str) -> None:
        """Restore original file content.

        Args:
            file_path: Path to the file to restore
            original_content: Original file content to restore
        """
        try:
            file_path.write_text(original_content)
            logging.debug(f"Restored original content for {file_path}")
        except Exception as e:
            logging.error(f"Failed to restore original content for {file_path}: {e}")

    def process_multiple_files(self, file_paths: list[Path]) -> list[ProcessingResult]:
        """Process multiple Python files.

        Args:
            file_paths: List of file paths to process

        Returns:
            List of ProcessingResult objects
        """
        logging.info(f"Processing {len(file_paths)} files")

        results = []
        for file_path in file_paths:
            result = self.process_file(file_path)
            results.append(result)

            # Log summary for each file
            if result.success:
                change_msg = "with changes" if result.changes_made else "no changes needed"
                logging.info(f"✓ {file_path.name}: {change_msg}")
            else:
                logging.error(f"✗ {file_path.name}: {result.error_message}")

        # Log overall summary
        successful = sum(1 for r in results if r.success)
        with_changes = sum(1 for r in results if r.success and r.changes_made)
        failed = len(results) - successful

        logging.info(
            f"Processing summary: {successful}/{len(results)} successful, " f"{with_changes} with changes, {failed} failed"
        )

        return results

    def get_processing_statistics(self, results: list[ProcessingResult]) -> dict[str, Any]:
        """Get processing statistics from results.

        Args:
            results: List of processing results

        Returns:
            Dictionary with processing statistics
        """
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        with_changes = sum(1 for r in results if r.success and r.changes_made)
        total_retries = sum(r.retry_count for r in results)

        # Count validation and update failures
        validation_failures = sum(1 for r in results if r.validation_result and not r.validation_result.passed)
        update_failures = sum(1 for r in results if r.update_result and not r.update_result.success)

        # Count docstring changes by type
        docstring_stats = {"functions": 0, "classes": 0, "modules": 0}

        # Map singular to plural forms
        type_mapping = {"function": "functions", "class": "classes", "module": "modules"}

        for result in results:
            if result.validation_result and result.validation_result.docstring_changes:
                for change in result.validation_result.docstring_changes:
                    change_type = change.get("type", "unknown")
                    # Map to plural form
                    plural_type = type_mapping.get(change_type, change_type + "s")
                    if plural_type in docstring_stats:
                        docstring_stats[plural_type] += 1

        return {
            "total_files": total,
            "successful": successful,
            "failed": failed,
            "files_with_changes": with_changes,
            "total_retries": total_retries,
            "validation_failures": validation_failures,
            "update_failures": update_failures,
            "docstring_changes": docstring_stats,
            "success_rate": successful / total if total > 0 else 0.0,
        }
