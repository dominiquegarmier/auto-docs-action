"""Module for updating Python docstrings using Claude Code CLI."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DocstringUpdateResult:
    """Result of docstring update operation."""

    success: bool
    updated_content: str | None = None
    error_message: str | None = None
    claude_response: dict[str, Any] | None = None


class DocstringUpdater:
    """Updates Python docstrings using Claude Code CLI."""

    def __init__(self, claude_command: str = "claude"):
        """Initialize the docstring updater.

        Args:
            claude_command: Command to execute Claude Code CLI (default: "claude")
        """
        self.claude_command = claude_command

    def update_docstrings(self, file_path: Path) -> DocstringUpdateResult:
        """Update docstrings in a Python file using Claude Code CLI.

        Args:
            file_path: Path to the Python file to update

        Returns:
            DocstringUpdateResult with the operation outcome
        """
        try:
            # Prepare the prompt for Claude Code CLI
            prompt = self._create_docstring_prompt(file_path)

            # Execute Claude Code CLI
            result = self._execute_claude_cli(prompt, file_path)

            if result.success and result.claude_response:
                # Parse Claude's response and extract updated content
                updated_content = self._extract_updated_content(result.claude_response)
                if updated_content:
                    return DocstringUpdateResult(
                        success=True, updated_content=updated_content, claude_response=result.claude_response
                    )
                else:
                    return DocstringUpdateResult(
                        success=False,
                        error_message="Could not extract updated content from Claude response",
                        claude_response=result.claude_response,
                    )
            else:
                return result

        except Exception as e:
            logging.error(f"Error updating docstrings for {file_path}: {e}")
            return DocstringUpdateResult(success=False, error_message=f"Unexpected error: {e}")

    def _create_docstring_prompt(self, file_path: Path) -> str:
        """Create a prompt for Claude Code CLI to update docstrings.

        Args:
            file_path: Path to the Python file

        Returns:
            Formatted prompt string for Claude Code CLI
        """
        return f"""Please add or improve Google-style docstrings for all functions and classes in the Python file: {file_path}

Requirements:
1. Follow Google-style docstring conventions
2. Include Args, Returns, and Raises sections as appropriate
3. Add type information in docstrings that complements type hints
4. Ensure docstrings are clear, concise, and helpful
5. Do not modify function signatures, imports, or logic - ONLY add/improve docstrings
6. If a function already has a good docstring, leave it unchanged
7. Return the complete updated file content

The goal is to improve code documentation while maintaining all existing functionality."""

    def _execute_claude_cli(self, prompt: str, file_path: Path) -> DocstringUpdateResult:
        """Execute Claude Code CLI with the given prompt.

        Args:
            prompt: Prompt to send to Claude Code CLI
            file_path: Path to the file being processed

        Returns:
            DocstringUpdateResult with CLI execution outcome
        """
        try:
            # Build Claude Code CLI command
            cmd = [self.claude_command, "-p", prompt, "--output-format", "json", "--max-turns", "3"]

            logging.info(f"Executing Claude Code CLI for {file_path}")
            logging.debug(f"Command: {' '.join(cmd)}")

            # Execute the command
            result = subprocess.run(cmd, cwd=file_path.parent, capture_output=True, text=True, timeout=300)  # 5 minute timeout

            if result.returncode != 0:
                error_msg = f"Claude Code CLI failed with return code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr.strip()}"

                logging.error(error_msg)
                return DocstringUpdateResult(success=False, error_message=error_msg)

            # Parse JSON response
            try:
                claude_response = json.loads(result.stdout)
                return DocstringUpdateResult(success=True, claude_response=claude_response)
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse Claude Code CLI JSON response: {e}")
                logging.debug(f"Raw output: {result.stdout}")
                return DocstringUpdateResult(success=False, error_message=f"Invalid JSON response from Claude Code CLI: {e}")

        except subprocess.TimeoutExpired:
            logging.error(f"Claude Code CLI timed out for {file_path}")
            return DocstringUpdateResult(success=False, error_message="Claude Code CLI operation timed out")
        except Exception as e:
            logging.error(f"Error executing Claude Code CLI: {e}")
            return DocstringUpdateResult(success=False, error_message=f"CLI execution error: {e}")

    def _extract_updated_content(self, claude_response: dict[str, Any]) -> str | None:
        """Extract updated file content from Claude Code CLI response.

        Args:
            claude_response: Parsed JSON response from Claude Code CLI

        Returns:
            Updated file content or None if extraction failed
        """
        try:
            # The exact structure of Claude Code CLI JSON response may vary
            # This implementation assumes a common structure, but may need adjustment

            # Check if response contains file modifications
            if "modifications" in claude_response:
                modifications = claude_response["modifications"]
                if modifications and len(modifications) > 0:
                    # Assume first modification contains the updated content
                    first_mod = modifications[0]
                    if "content" in first_mod:
                        content = first_mod["content"]
                        return content if isinstance(content, str) else None

            # Alternative: check for direct content field
            if "content" in claude_response:
                content = claude_response["content"]
                return content if isinstance(content, str) else None

            # Alternative: check for messages with code blocks
            if "messages" in claude_response:
                for message in claude_response["messages"]:
                    if "content" in message and isinstance(message["content"], str):
                        # Look for code blocks or full file content
                        content = message["content"]
                        if "```python" in content:
                            # Extract Python code block
                            lines = content.split("\n")
                            in_code_block = False
                            code_lines = []
                            for line in lines:
                                if line.strip().startswith("```python"):
                                    in_code_block = True
                                    continue
                                elif line.strip() == "```" and in_code_block:
                                    break
                                elif in_code_block:
                                    code_lines.append(line)

                            if code_lines:
                                return "\n".join(code_lines)

            logging.warning("Could not extract content from Claude response structure")
            logging.debug(f"Response structure: {claude_response.keys()}")
            return None

        except Exception as e:
            logging.error(f"Error extracting content from Claude response: {e}")
            return None
