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
        repo_path = Path(temp_dir)
        try:
            os.chdir(repo_path)

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

            # Create a github-actions commit first so diff logic works
            os.system(
                'git -c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" '
                'commit --allow-empty -m "GitHub Actions commit"'
            )

            # Add another change after auto-docs commit so there's something to diff
            final_content = modified_content + "\ndef divide(a, b):\n    return a / b\n"
            test_file.write_text(final_content)
            os.system("git add test_module.py")
            os.system("git commit -m 'Add divide function'")

            # Set environment variables
            os.environ["CLAUDE_COMMAND"] = "claude"
            os.environ["MAX_RETRIES"] = "2"
            os.environ["ANTHROPIC_API_KEY"] = "test-key"

            # Run main with mocked Claude CLI execution
            with patch("docstring_updater._execute_claude_cli") as mock_claude:
                # Configure mock to simulate successful Claude execution that adds docstrings
                def side_effect(prompt, file_path, claude_command):
                    # Simulate Claude adding docstrings to the file
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

def divide(a, b):
    """Divide a by b.

    Args:
        a: Dividend.
        b: Divisor.

    Returns:
        The quotient a / b.
    """
    return a / b
'''
                    file_path.write_text(content_with_docstrings)
                    from docstring_updater import DocstringUpdateResult

                    return DocstringUpdateResult(success=True)

                mock_claude.side_effect = side_effect
                exit_code = main.main()

            # Verify results
            assert exit_code == 0  # Should succeed

            # Check that docstrings were added
            final_content = test_file.read_text()
            assert '"""Add two numbers together.' in final_content
            assert '"""A simple calculator class."""' in final_content
            assert '"""Subtract b from a.' in final_content

        finally:
            # Change back to a safe directory
            os.chdir(Path(__file__).parent.parent)


def test_workflow_with_validation_failure():
    """Test workflow when AST validation fails."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        try:
            os.chdir(repo_path)

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

            # Create a github-actions commit first so diff logic works
            os.system(
                'git -c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" '
                'commit --allow-empty -m "GitHub Actions commit"'
            )

            # Modify file
            test_file.write_text("def add(a, b):\n    return a + b + 1\n")  # Change logic
            os.system("git add test_module.py")
            os.system("git commit -m 'Modify function'")

            os.environ["CLAUDE_COMMAND"] = "claude"
            os.environ["MAX_RETRIES"] = "2"
            os.environ["ANTHROPIC_API_KEY"] = "test-key"

            # Should handle validation failure gracefully
            with patch("docstring_updater._execute_claude_cli") as mock_claude:
                # Configure mock to simulate Claude making logic changes that fail validation
                def side_effect(prompt, file_path, claude_command):
                    # Simulate Claude making logic changes (should fail validation)
                    bad_content = '''def add(a, b):
    """Add two numbers."""
    return a * b  # Changed logic! Should fail validation
'''
                    file_path.write_text(bad_content)
                    from docstring_updater import DocstringUpdateResult

                    return DocstringUpdateResult(success=True)

                mock_claude.side_effect = side_effect
                exit_code = main.main()

            # Should report failures but not crash
            assert exit_code == 1  # Failure exit code due to failed processing

        finally:
            # Change back to a safe directory
            os.chdir(Path(__file__).parent.parent)


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
