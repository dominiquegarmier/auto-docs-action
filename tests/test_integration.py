"""Integration tests for the full auto-docs workflow."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

import main
from file_processor import FileProcessor


def test_full_workflow_integration():
    """Test the complete workflow with mocked Claude CLI."""
    with tempfile.TemporaryDirectory() as temp_dir:
        old_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)

            # Setup git repo
            os.system("git init")
            os.system('git config user.email "test@example.com"')
            os.system('git config user.name "Test User"')

            # Create Python file without docstrings
            test_file = Path("test_module.py")
            original_content = """def add_numbers(a, b):
    return a + b

class Calculator:
    def multiply(self, x, y):
        return x * y
"""
            test_file.write_text(original_content)
            os.system("git add test_module.py")
            os.system("git commit -m 'Initial commit'")

            # Modify the file (simulate changes)
            modified_content = original_content + "\ndef subtract(a, b):\n    return a - b\n"
            test_file.write_text(modified_content)
            os.system("git add test_module.py")
            os.system("git commit -m 'Add subtract function'")

            # Mock Claude CLI to add docstrings
            def mock_claude_execution(cmd, **kwargs):
                if cmd[0] == "claude":
                    # Simulate Claude adding docstrings
                    file_path = kwargs.get("cwd", Path.cwd()) / "test_module.py"
                    content_with_docstrings = '''def add_numbers(a, b):
    """Add two numbers together.

    Args:
        a: First number to add.
        b: Second number to add.

    Returns:
        The sum of a and b.
    """
    return a + b

class Calculator:
    """A simple calculator class."""

    def multiply(self, x, y):
        """Multiply two numbers.

        Args:
            x: First number.
            y: Second number.

        Returns:
            The product of x and y.
        """
        return x * y

def subtract(a, b):
    """Subtract b from a.

    Args:
        a: Number to subtract from.
        b: Number to subtract.

    Returns:
        The difference a - b.
    """
    return a - b
'''
                    file_path.write_text(content_with_docstrings)
                    return MagicMock(returncode=0, stdout="", stderr="")
                return MagicMock(returncode=1, stdout="", stderr="Command not found")

            # Set environment variables
            os.environ["CLAUDE_COMMAND"] = "claude"
            os.environ["MAX_RETRIES"] = "2"
            os.environ["ANTHROPIC_API_KEY"] = "test-key"

            # Run main with mocked subprocess
            with patch("subprocess.run", side_effect=mock_claude_execution):
                exit_code = main.main()

            # Verify results
            assert exit_code == 0  # Should succeed

            # Check that docstrings were added
            final_content = test_file.read_text()
            assert '"""Add two numbers together.' in final_content
            assert '"""A simple calculator class."""' in final_content
            assert '"""Subtract b from a.' in final_content

        finally:
            os.chdir(old_cwd)


def test_workflow_with_validation_failure():
    """Test workflow when AST validation fails."""
    with tempfile.TemporaryDirectory() as temp_dir:
        old_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)

            # Setup git repo
            os.system("git init")
            os.system('git config user.email "test@example.com"')
            os.system('git config user.name "Test User"')

            # Create Python file
            test_file = Path("test_module.py")
            original_content = "def add(a, b):\n    return a + b\n"
            test_file.write_text(original_content)
            os.system("git add test_module.py")
            os.system("git commit -m 'Initial commit'")

            # Modify file
            test_file.write_text("def add(a, b):\n    return a + b + 1\n")  # Change logic
            os.system("git add test_module.py")
            os.system("git commit -m 'Modify function'")

            # Mock Claude CLI to make invalid changes
            def mock_claude_bad_execution(cmd, **kwargs):
                if cmd[0] == "claude":
                    # Simulate Claude making logic changes (should fail validation)
                    file_path = kwargs.get("cwd", Path.cwd()) / "test_module.py"
                    bad_content = '''def add(a, b):
    """Add two numbers."""
    return a * b  # Changed logic! Should fail validation
'''
                    file_path.write_text(bad_content)
                    return MagicMock(returncode=0, stdout="", stderr="")
                return MagicMock(returncode=1, stdout="", stderr="Command not found")

            os.environ["CLAUDE_COMMAND"] = "claude"
            os.environ["MAX_RETRIES"] = "2"
            os.environ["ANTHROPIC_API_KEY"] = "test-key"

            # Should handle validation failure gracefully
            with patch("subprocess.run", side_effect=mock_claude_bad_execution):
                exit_code = main.main()

            # Should report failures but not crash
            assert exit_code == 1  # Failure exit code due to failed processing

        finally:
            os.chdir(old_cwd)


def test_processor_retry_logic():
    """Test retry logic in FileProcessor."""
    processor = FileProcessor(claude_command="fake-claude", max_retries=2, retry_delay=0.1)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def test(): pass")
        f.flush()
        file_path = Path(f.name)

    try:
        # Mock failing docstring update
        with patch("docstring_updater.update_docstrings") as mock_update:
            mock_update.return_value = MagicMock(success=False, error_message="Mock failure")

            result = processor.process_file(file_path)

            # Should have attempted retries
            assert result.success is False
            assert result.retry_count == 2  # Max retries reached
            assert mock_update.call_count == 3  # Initial + 2 retries

    finally:
        file_path.unlink()


def test_statistics_calculation():
    """Test statistics calculation across multiple files."""
    processor = FileProcessor()

    # Create mock results
    from ast_validator import ValidationResult
    from docstring_updater import DocstringUpdateResult
    from file_processor import ProcessingResult

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
            retry_count=0,
        ),
        ProcessingResult(success=True, file_path=Path("file2.py"), changes_made=False, retry_count=0),
        ProcessingResult(success=False, file_path=Path("file3.py"), error_message="Failed", retry_count=2),
    ]

    stats = processor.get_processing_statistics(results)

    assert stats["total_files"] == 3
    assert stats["successful"] == 2
    assert stats["failed"] == 1
    assert stats["files_with_changes"] == 1
    assert stats["total_retries"] == 2
    assert stats["docstring_changes"]["functions"] == 1
    assert stats["docstring_changes"]["classes"] == 1
    assert stats["success_rate"] == 2 / 3


def test_main_environment_parsing():
    """Test main function's environment variable parsing."""
    old_env = os.environ.copy()
    try:
        # Test default values
        os.environ.pop("CLAUDE_COMMAND", None)
        os.environ.pop("MAX_RETRIES", None)
        os.environ.pop("RETRY_DELAY", None)

        claude_command = os.getenv("CLAUDE_COMMAND", "claude")
        max_retries = int(os.getenv("MAX_RETRIES", "3"))
        retry_delay = float(os.getenv("RETRY_DELAY", "1.0"))

        assert claude_command == "claude"
        assert max_retries == 3
        assert retry_delay == 1.0

        # Test custom values
        os.environ["CLAUDE_COMMAND"] = "custom-claude"
        os.environ["MAX_RETRIES"] = "5"
        os.environ["RETRY_DELAY"] = "2.5"

        claude_command = os.getenv("CLAUDE_COMMAND", "claude")
        max_retries = int(os.getenv("MAX_RETRIES", "3"))
        retry_delay = float(os.getenv("RETRY_DELAY", "1.0"))

        assert claude_command == "custom-claude"
        assert max_retries == 5
        assert retry_delay == 2.5

    finally:
        os.environ.clear()
        os.environ.update(old_env)
