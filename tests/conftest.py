"""Shared pytest fixtures for auto-docs testing."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Generator

import pytest


@pytest.fixture
def temp_git_repo() -> Generator[Path, None, None]:
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, check=True)

        # Configure git (required for commits)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)

        yield repo_path


@pytest.fixture
def sample_python_files() -> Dict[str, str]:
    """Sample Python files with various docstring scenarios."""
    return {
        "good_docstrings.py": '''
def calculate_area(length: float, width: float) -> float:
    """Calculate the area of a rectangle.

    Args:
        length: The length of the rectangle.
        width: The width of the rectangle.

    Returns:
        The area of the rectangle.
    """
    return length * width

class Rectangle:
    """A simple rectangle class."""

    def __init__(self, length: float, width: float) -> None:
        """Initialize a rectangle.

        Args:
            length: The length of the rectangle.
            width: The width of the rectangle.
        """
        self.length = length
        self.width = width
''',
        "missing_docstrings.py": """
def process_data(data):
    results = []
    for item in data:
        if item > 0:
            results.append(item * 2)
    return results

class DataProcessor:
    def __init__(self, config):
        self.config = config

    def process(self, data):
        return [x for x in data if x % 2 == 0]
""",
        "syntax_error.py": """
def broken_function(:
    return "This has a syntax error"
""",
        "mixed_quality.py": '''
def good_function(x: int) -> int:
    """This function has a good docstring.

    Args:
        x: Input integer.

    Returns:
        The input integer plus one.
    """
    return x + 1

def bad_function(y):
    # This function needs a docstring
    return y * 2
''',
    }


@pytest.fixture
def git_repo_with_files(temp_git_repo: Path, sample_python_files: Dict[str, str]) -> Path:
    """Git repo with sample Python files and initial commit."""
    # Create initial files
    for filename, content in sample_python_files.items():
        file_path = temp_git_repo / filename
        file_path.write_text(content.strip())
        subprocess.run(["git", "add", str(file_path)], cwd=temp_git_repo, check=True)

    # Initial commit
    subprocess.run(["git", "commit", "-m", "Initial commit with Python files"], cwd=temp_git_repo, check=True)

    return temp_git_repo
