"""Tests for file processor functionality."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from auto_docs_action.ast_validator import ValidationResult
from auto_docs_action.docstring_updater import DocstringUpdateResult
from auto_docs_action.file_processor import FileProcessor
from auto_docs_action.file_processor import ProcessingResult


def test_successful_result_creation():
    """Test creating successful result."""
    file_path = Path("/tmp/test.py")
    validation_result = ValidationResult(passed=True, status="valid")
    update_result = DocstringUpdateResult(success=True, updated_content="code")

    result = ProcessingResult(
        success=True,
        file_path=file_path,
        changes_made=True,
        validation_result=validation_result,
        update_result=update_result,
        retry_count=1,
    )

    assert result.success is True
    assert result.file_path == file_path
    assert result.changes_made is True
    assert result.validation_result == validation_result
    assert result.update_result == update_result
    assert result.error_message is None
    assert result.retry_count == 1


def test_failed_result_creation():
    """Test creating failed result."""
    file_path = Path("/tmp/test.py")

    result = ProcessingResult(success=False, file_path=file_path, error_message="Something failed")

    assert result.success is False
    assert result.file_path == file_path
    assert result.changes_made is False
    assert result.validation_result is None
    assert result.update_result is None
    assert result.error_message == "Something failed"
    assert result.retry_count == 0


def test_initialization_defaults():
    """Test default initialization."""
    processor = FileProcessor()

    assert processor.claude_command == "claude"
    assert processor.max_retries == 3
    assert processor.retry_delay == 1.0


def test_initialization_custom_params():
    """Test initialization with custom parameters."""
    processor = FileProcessor(claude_command="custom-claude", max_retries=5, retry_delay=2.0)

    assert processor.claude_command == "custom-claude"
    assert processor.max_retries == 5
    assert processor.retry_delay == 2.0


def test_restore_file_content_success():
    """Test successful file content restoration."""
    processor = FileProcessor()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("modified content")
        f.flush()
        file_path = Path(f.name)

    try:
        # Restore original content
        processor._restore_file_content(file_path, "original content")

        # Verify restoration
        assert file_path.read_text() == "original content"
    finally:
        file_path.unlink()


def test_restore_file_content_failure():
    """Test file content restoration failure."""
    processor = FileProcessor()
    non_existent_path = Path("/non/existent/file.py")

    # This should not raise an exception, just log an error
    processor._restore_file_content(non_existent_path, "content")


@patch("time.sleep")
@patch("auto_docs_action.ast_validator.validate_changes")
@patch("auto_docs_action.docstring_updater.update_docstrings")
def test_process_file_success_first_attempt(mock_update_docstrings, mock_validate_changes, mock_sleep):
    """Test successful file processing on first attempt."""
    # Mock function returns
    mock_update_docstrings.return_value = DocstringUpdateResult(
        success=True, updated_content='def foo():\n    """A function."""\n    pass'
    )

    mock_validate_changes.return_value = ValidationResult(
        passed=True, status="valid_docstring_only_changes", docstring_changes=[{"type": "function", "name": "foo"}]
    )

    processor = FileProcessor()

    # Create test file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def foo():\n    pass")
        f.flush()
        file_path = Path(f.name)

    try:
        result = processor.process_file(file_path)

        assert result.success is True
        assert result.changes_made is True
        assert result.retry_count == 0
        assert result.error_message is None

        # Verify file was updated
        assert '"""A function."""' in file_path.read_text()

        # Verify no sleep was called (no retries)
        mock_sleep.assert_not_called()

        # Verify function calls
        mock_update_docstrings.assert_called_once_with(file_path, "claude")
        mock_validate_changes.assert_called_once()

    finally:
        file_path.unlink()


@patch("auto_docs_action.ast_validator.validate_changes")
@patch("auto_docs_action.docstring_updater.update_docstrings")
def test_process_file_no_changes_needed(mock_update_docstrings, mock_validate_changes):
    """Test processing when no changes are needed."""
    mock_update_docstrings.return_value = DocstringUpdateResult(success=True, updated_content=None)  # No changes needed

    processor = FileProcessor()

    # Create test file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write('def foo():\n    """Already documented."""\n    pass')
        f.flush()
        file_path = Path(f.name)

    try:
        result = processor.process_file(file_path)

        assert result.success is True
        assert result.changes_made is False
        assert result.retry_count == 0

        # AST validator should not have been called (no changes)
        mock_validate_changes.assert_not_called()

    finally:
        file_path.unlink()


@patch("time.sleep")
@patch("auto_docs_action.ast_validator.validate_changes")
@patch("auto_docs_action.docstring_updater.update_docstrings")
def test_process_file_docstring_update_failure_with_retry(mock_update_docstrings, mock_validate_changes, mock_sleep):
    """Test processing with docstring update failure and retry."""
    # First attempt fails, second succeeds
    mock_update_docstrings.side_effect = [
        DocstringUpdateResult(success=False, error_message="API error"),
        DocstringUpdateResult(success=True, updated_content='def foo():\n    """A function."""\n    pass'),
    ]

    mock_validate_changes.return_value = ValidationResult(passed=True, status="valid_docstring_only_changes")

    processor = FileProcessor(max_retries=2, retry_delay=0.1)

    # Create test file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def foo():\n    pass")
        f.flush()
        file_path = Path(f.name)

    try:
        result = processor.process_file(file_path)

        assert result.success is True
        assert result.changes_made is True
        assert result.retry_count == 1  # Succeeded on second attempt

        # Verify retry delay was called
        mock_sleep.assert_called_once_with(0.1)

        # Verify both calls were made
        assert mock_update_docstrings.call_count == 2

    finally:
        file_path.unlink()


@patch("time.sleep")
@patch("auto_docs_action.ast_validator.validate_changes")
@patch("auto_docs_action.docstring_updater.update_docstrings")
def test_process_file_validation_failure_with_retry(mock_update_docstrings, mock_validate_changes, mock_sleep):
    """Test processing with validation failure and retry."""
    mock_update_docstrings.return_value = DocstringUpdateResult(
        success=True, updated_content='def foo():\n    """A function."""\n    pass'
    )

    # First attempt fails validation, second succeeds
    mock_validate_changes.side_effect = [
        ValidationResult(passed=False, status="structure_changed", reason="Logic changed"),
        ValidationResult(passed=True, status="valid_docstring_only_changes"),
    ]

    processor = FileProcessor(max_retries=1, retry_delay=0.1)

    # Create test file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def foo():\n    pass")
        f.flush()
        file_path = Path(f.name)

    try:
        result = processor.process_file(file_path)

        assert result.success is True
        assert result.changes_made is True
        assert result.retry_count == 1

        # Verify retry was attempted
        mock_sleep.assert_called_once_with(0.1)

    finally:
        file_path.unlink()


@patch("time.sleep")
@patch("auto_docs_action.docstring_updater.update_docstrings")
def test_process_file_max_retries_exceeded(mock_update_docstrings, mock_sleep):
    """Test processing failure after max retries exceeded."""
    mock_update_docstrings.return_value = DocstringUpdateResult(success=False, error_message="Persistent error")

    processor = FileProcessor(max_retries=2, retry_delay=0.1)

    # Create test file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def foo():\n    pass")
        f.flush()
        file_path = Path(f.name)

    try:
        result = processor.process_file(file_path)

        assert result.success is False
        assert result.changes_made is False
        assert result.retry_count == 2  # Max retries reached
        assert "Persistent error" in result.error_message

        # Verify retries were attempted
        assert mock_sleep.call_count == 2
        assert mock_update_docstrings.call_count == 3  # Initial + 2 retries

    finally:
        file_path.unlink()


def test_process_file_file_read_error():
    """Test processing with file read error."""
    processor = FileProcessor()
    non_existent_file = Path("/non/existent/file.py")

    result = processor.process_file(non_existent_file)

    assert result.success is False
    assert "Failed to read file" in result.error_message
    assert result.retry_count == 0


@patch("auto_docs_action.docstring_updater.update_docstrings")
def test_process_file_file_write_error(mock_update_docstrings):
    """Test processing with file write error."""
    mock_update_docstrings.return_value = DocstringUpdateResult(
        success=True, updated_content='def foo():\n    """A function."""\n    pass'
    )

    processor = FileProcessor()

    # Use a read-only directory
    readonly_file = Path("/tmp/readonly_test.py")

    # Create the file first
    readonly_file.write_text("def foo(): pass")

    try:
        # Make file read-only
        readonly_file.chmod(0o444)

        result = processor.process_file(readonly_file)

        # On some systems this might succeed, on others it might fail
        # The important thing is that it handles the exception gracefully
        if not result.success:
            assert (
                "Failed to write updated content" in result.error_message
                or "Permission denied" in result.error_message
                or result.success is True
            )  # Some systems allow the write

    finally:
        # Restore write permissions and clean up
        try:
            readonly_file.chmod(0o644)
            readonly_file.unlink()
        except Exception:
            pass  # Cleanup failure is not critical for test


@patch("time.sleep")
@patch("auto_docs_action.docstring_updater.update_docstrings")
def test_process_file_unexpected_exception(mock_update_docstrings, mock_sleep):
    """Test processing with unexpected exception."""
    mock_update_docstrings.side_effect = RuntimeError("Unexpected error")

    processor = FileProcessor(max_retries=1, retry_delay=0.1)

    # Create test file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def foo(): pass")
        f.flush()
        file_path = Path(f.name)

    try:
        result = processor.process_file(file_path)

        assert result.success is False
        assert "Unexpected error" in result.error_message
        assert result.retry_count == 1  # Retries were attempted

        # Verify retries were attempted
        mock_sleep.assert_called_once_with(0.1)

    finally:
        file_path.unlink()


@patch("auto_docs_action.ast_validator.validate_changes")
@patch("auto_docs_action.docstring_updater.update_docstrings")
def test_process_multiple_files_success(mock_update_docstrings, mock_validate_changes):
    """Test processing multiple files successfully."""
    mock_update_docstrings.return_value = DocstringUpdateResult(
        success=True, updated_content='def foo():\n    """A function."""\n    pass'
    )

    mock_validate_changes.return_value = ValidationResult(passed=True, status="valid_docstring_only_changes")

    processor = FileProcessor()

    # Create test files
    file_paths = []
    for i in range(3):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(f"def func{i}(): pass")
            f.flush()
            file_paths.append(Path(f.name))

    try:
        results = processor.process_multiple_files(file_paths)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(r.changes_made for r in results)

    finally:
        for file_path in file_paths:
            file_path.unlink()


@patch("auto_docs_action.ast_validator.validate_changes")
@patch("auto_docs_action.docstring_updater.update_docstrings")
def test_process_multiple_files_mixed_results(mock_update_docstrings, mock_validate_changes):
    """Test processing multiple files with mixed results."""
    mock_update_docstrings.side_effect = [
        DocstringUpdateResult(success=True, updated_content="updated"),
        DocstringUpdateResult(success=False, error_message="Error"),
        DocstringUpdateResult(success=True, updated_content=None),  # No changes
    ]

    mock_validate_changes.return_value = ValidationResult(passed=True, status="valid_docstring_only_changes")

    processor = FileProcessor(max_retries=0)  # No retries for faster test

    # Create test files
    file_paths = []
    for i in range(3):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(f"def func{i}(): pass")
            f.flush()
            file_paths.append(Path(f.name))

    try:
        results = processor.process_multiple_files(file_paths)

        assert len(results) == 3
        assert results[0].success is True and results[0].changes_made is True
        assert results[1].success is False
        assert results[2].success is True and results[2].changes_made is False

    finally:
        for file_path in file_paths:
            file_path.unlink()


def test_get_processing_statistics_empty_list():
    """Test statistics calculation with empty results list."""
    processor = FileProcessor()

    stats = processor.get_processing_statistics([])

    assert stats["total_files"] == 0
    assert stats["successful"] == 0
    assert stats["failed"] == 0
    assert stats["files_with_changes"] == 0
    assert stats["success_rate"] == 0.0


def test_get_processing_statistics_comprehensive():
    """Test comprehensive statistics calculation."""
    processor = FileProcessor()

    # Create mock results
    results = [
        ProcessingResult(
            success=True,
            file_path=Path("file1.py"),
            changes_made=True,
            validation_result=ValidationResult(
                passed=True,
                status="valid",
                docstring_changes=[{"type": "function", "name": "foo"}, {"type": "class", "name": "Bar"}],
            ),
            retry_count=1,
        ),
        ProcessingResult(success=True, file_path=Path("file2.py"), changes_made=False, retry_count=0),
        ProcessingResult(
            success=False,
            file_path=Path("file3.py"),
            validation_result=ValidationResult(passed=False, status="failed"),
            retry_count=2,
        ),
        ProcessingResult(
            success=False, file_path=Path("file4.py"), update_result=DocstringUpdateResult(success=False), retry_count=1
        ),
    ]

    stats = processor.get_processing_statistics(results)

    assert stats["total_files"] == 4
    assert stats["successful"] == 2
    assert stats["failed"] == 2
    assert stats["files_with_changes"] == 1
    assert stats["total_retries"] == 4
    assert stats["validation_failures"] == 1
    assert stats["update_failures"] == 1
    assert stats["docstring_changes"]["functions"] == 1
    assert stats["docstring_changes"]["classes"] == 1
    assert stats["docstring_changes"]["modules"] == 0
    assert stats["success_rate"] == 0.5


def test_get_processing_statistics_docstring_types():
    """Test statistics calculation for different docstring types."""
    processor = FileProcessor()

    results = [
        ProcessingResult(
            success=True,
            file_path=Path("file1.py"),
            changes_made=True,
            validation_result=ValidationResult(
                passed=True,
                status="valid",
                docstring_changes=[
                    {"type": "module", "name": "__module__"},
                    {"type": "function", "name": "func1"},
                    {"type": "function", "name": "func2"},
                    {"type": "class", "name": "MyClass"},
                ],
            ),
        )
    ]

    stats = processor.get_processing_statistics(results)

    assert stats["docstring_changes"]["modules"] == 1
    assert stats["docstring_changes"]["functions"] == 2
    assert stats["docstring_changes"]["classes"] == 1
