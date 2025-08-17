"""Tests for docstring updater functionality."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from docstring_updater import DocstringUpdater
from docstring_updater import DocstringUpdateResult


class TestDocstringUpdateResult:
    """Test DocstringUpdateResult dataclass."""

    def test_successful_result_creation(self):
        """Test creating successful result."""
        result = DocstringUpdateResult(success=True, updated_content="def foo():\n    pass", claude_response={"status": "ok"})

        assert result.success is True
        assert result.updated_content == "def foo():\n    pass"
        assert result.error_message is None
        assert result.claude_response == {"status": "ok"}

    def test_failed_result_creation(self):
        """Test creating failed result."""
        result = DocstringUpdateResult(success=False, error_message="Something went wrong")

        assert result.success is False
        assert result.updated_content is None
        assert result.error_message == "Something went wrong"
        assert result.claude_response is None


class TestDocstringUpdater:
    """Test DocstringUpdater functionality."""

    def test_initialization_default_command(self):
        """Test default initialization."""
        updater = DocstringUpdater()
        assert updater.claude_command == "claude"

    def test_initialization_custom_command(self):
        """Test initialization with custom command."""
        updater = DocstringUpdater(claude_command="/usr/local/bin/claude")
        assert updater.claude_command == "/usr/local/bin/claude"

    def test_create_docstring_prompt(self):
        """Test prompt creation for docstring updates."""
        updater = DocstringUpdater()
        file_path = Path("/tmp/test.py")

        prompt = updater._create_docstring_prompt(file_path)

        assert "Google-style docstrings" in prompt
        assert str(file_path) in prompt
        assert "Args, Returns, and Raises" in prompt
        assert "ONLY add/improve docstrings" in prompt

    @patch("subprocess.run")
    def test_execute_claude_cli_success(self, mock_run):
        """Test successful Claude CLI execution."""
        # Mock successful subprocess result
        mock_response = {"status": "success", "content": 'def foo():\n    """A function."""\n    pass'}
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_response), stderr="")

        updater = DocstringUpdater()
        file_path = Path("/tmp/test.py")

        result = updater._execute_claude_cli("test prompt", file_path)

        assert result.success is True
        assert result.claude_response == mock_response
        assert result.error_message is None

        # Verify subprocess was called correctly
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["claude", "-p", "test prompt", "--output-format", "json", "--max-turns", "3"]
        assert call_args[1]["cwd"] == file_path.parent
        assert call_args[1]["capture_output"] is True
        assert call_args[1]["text"] is True
        assert call_args[1]["timeout"] == 300

    @patch("subprocess.run")
    def test_execute_claude_cli_non_zero_exit(self, mock_run):
        """Test Claude CLI execution with non-zero exit code."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Command failed")

        updater = DocstringUpdater()
        file_path = Path("/tmp/test.py")

        result = updater._execute_claude_cli("test prompt", file_path)

        assert result.success is False
        assert "return code 1" in result.error_message
        assert "Command failed" in result.error_message
        assert result.claude_response is None

    @patch("subprocess.run")
    def test_execute_claude_cli_invalid_json(self, mock_run):
        """Test Claude CLI execution with invalid JSON response."""
        mock_run.return_value = MagicMock(returncode=0, stdout="This is not valid JSON", stderr="")

        updater = DocstringUpdater()
        file_path = Path("/tmp/test.py")

        result = updater._execute_claude_cli("test prompt", file_path)

        assert result.success is False
        assert "Invalid JSON response" in result.error_message
        assert result.claude_response is None

    @patch("subprocess.run")
    def test_execute_claude_cli_timeout(self, mock_run):
        """Test Claude CLI execution timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["claude"], timeout=300)

        updater = DocstringUpdater()
        file_path = Path("/tmp/test.py")

        result = updater._execute_claude_cli("test prompt", file_path)

        assert result.success is False
        assert "timed out" in result.error_message
        assert result.claude_response is None

    @patch("subprocess.run")
    def test_execute_claude_cli_exception(self, mock_run):
        """Test Claude CLI execution with unexpected exception."""
        mock_run.side_effect = OSError("Command not found")

        updater = DocstringUpdater()
        file_path = Path("/tmp/test.py")

        result = updater._execute_claude_cli("test prompt", file_path)

        assert result.success is False
        assert "CLI execution error" in result.error_message
        assert "Command not found" in result.error_message
        assert result.claude_response is None

    def test_extract_updated_content_modifications_structure(self):
        """Test content extraction from modifications structure."""
        updater = DocstringUpdater()
        claude_response = {"modifications": [{"content": 'def foo():\n    """A function."""\n    pass', "file": "test.py"}]}

        content = updater._extract_updated_content(claude_response)

        assert content == 'def foo():\n    """A function."""\n    pass'

    def test_extract_updated_content_direct_content(self):
        """Test content extraction from direct content field."""
        updater = DocstringUpdater()
        claude_response = {"content": 'def bar():\n    """Another function."""\n    return True'}

        content = updater._extract_updated_content(claude_response)

        assert content == 'def bar():\n    """Another function."""\n    return True'

    def test_extract_updated_content_messages_with_code_block(self):
        """Test content extraction from messages with code blocks."""
        updater = DocstringUpdater()
        claude_response = {
            "messages": [
                {
                    "content": 'Here\'s the updated code:\n\n```python\ndef baz():\n    """Yet another function."""\n    return 42\n```\n\nI\'ve added docstrings.'
                }
            ]
        }

        content = updater._extract_updated_content(claude_response)

        assert content == 'def baz():\n    """Yet another function."""\n    return 42'

    def test_extract_updated_content_no_extractable_content(self):
        """Test content extraction when no content can be extracted."""
        updater = DocstringUpdater()
        claude_response = {"status": "completed", "message": "No changes needed"}

        content = updater._extract_updated_content(claude_response)

        assert content is None

    def test_extract_updated_content_exception_handling(self):
        """Test content extraction with exception handling."""
        updater = DocstringUpdater()
        # Invalid structure that might cause KeyError
        claude_response = None

        content = updater._extract_updated_content(claude_response)

        assert content is None

    @patch.object(DocstringUpdater, "_execute_claude_cli")
    @patch.object(DocstringUpdater, "_create_docstring_prompt")
    @patch.object(DocstringUpdater, "_extract_updated_content")
    def test_update_docstrings_success(self, mock_extract, mock_prompt, mock_execute):
        """Test successful docstring update."""
        # Setup mocks
        mock_prompt.return_value = "test prompt"
        mock_execute.return_value = DocstringUpdateResult(success=True, claude_response={"content": "updated code"})
        mock_extract.return_value = 'def foo():\n    """Updated."""\n    pass'

        updater = DocstringUpdater()
        file_path = Path("/tmp/test.py")

        result = updater.update_docstrings(file_path)

        assert result.success is True
        assert result.updated_content == 'def foo():\n    """Updated."""\n    pass'
        assert result.error_message is None
        assert result.claude_response == {"content": "updated code"}

        # Verify method calls
        mock_prompt.assert_called_once_with(file_path)
        mock_execute.assert_called_once_with("test prompt", file_path)
        mock_extract.assert_called_once_with({"content": "updated code"})

    @patch.object(DocstringUpdater, "_execute_claude_cli")
    @patch.object(DocstringUpdater, "_create_docstring_prompt")
    def test_update_docstrings_cli_failure(self, mock_prompt, mock_execute):
        """Test docstring update when CLI execution fails."""
        # Setup mocks
        mock_prompt.return_value = "test prompt"
        mock_execute.return_value = DocstringUpdateResult(success=False, error_message="CLI failed")

        updater = DocstringUpdater()
        file_path = Path("/tmp/test.py")

        result = updater.update_docstrings(file_path)

        assert result.success is False
        assert result.error_message == "CLI failed"
        assert result.updated_content is None

    @patch.object(DocstringUpdater, "_execute_claude_cli")
    @patch.object(DocstringUpdater, "_create_docstring_prompt")
    @patch.object(DocstringUpdater, "_extract_updated_content")
    def test_update_docstrings_extraction_failure(self, mock_extract, mock_prompt, mock_execute):
        """Test docstring update when content extraction fails."""
        # Setup mocks
        mock_prompt.return_value = "test prompt"
        mock_execute.return_value = DocstringUpdateResult(success=True, claude_response={"status": "ok"})
        mock_extract.return_value = None  # Extraction failed

        updater = DocstringUpdater()
        file_path = Path("/tmp/test.py")

        result = updater.update_docstrings(file_path)

        assert result.success is False
        assert "Could not extract updated content" in result.error_message
        assert result.updated_content is None
        assert result.claude_response == {"status": "ok"}

    @patch.object(DocstringUpdater, "_create_docstring_prompt")
    def test_update_docstrings_unexpected_exception(self, mock_prompt):
        """Test docstring update with unexpected exception."""
        # Setup mock to raise exception
        mock_prompt.side_effect = Exception("Unexpected error")

        updater = DocstringUpdater()
        file_path = Path("/tmp/test.py")

        result = updater.update_docstrings(file_path)

        assert result.success is False
        assert "Unexpected error" in result.error_message
        assert result.updated_content is None
        assert result.claude_response is None

    def test_real_file_integration(self):
        """Test with real file (without actually calling Claude CLI)."""
        updater = DocstringUpdater()

        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                """def add_numbers(a, b):
    return a + b

class Calculator:
    def multiply(self, x, y):
        return x * y
"""
            )
            f.flush()
            file_path = Path(f.name)

        try:
            # Test prompt creation
            prompt = updater._create_docstring_prompt(file_path)
            assert str(file_path) in prompt
            assert "Google-style docstrings" in prompt

        finally:
            # Clean up
            file_path.unlink()

    def test_custom_claude_command_usage(self):
        """Test that custom Claude command is used in CLI execution."""
        custom_command = "/custom/path/claude"
        updater = DocstringUpdater(claude_command=custom_command)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='{"status": "ok"}', stderr="")

            file_path = Path("/tmp/test.py")
            updater._execute_claude_cli("test prompt", file_path)

            # Verify custom command was used
            call_args = mock_run.call_args
            assert call_args[0][0][0] == custom_command
