"""Tests for AST-based validation of docstring-only changes."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

import ast_validator
from ast_validator import ValidationResult


def test_valid_docstring_only_change():
    """Test that adding docstrings passes validation."""

    original = """
def process_data(data):
    results = []
    for item in data:
        if item > 0:
            results.append(item * 2)
    return results
"""

    modified = '''
def process_data(data):
    """Process a list of data items.

    Args:
        data: List of numeric items to process.

    Returns:
        List of processed items (positive values doubled).
    """
    results = []
    for item in data:
        if item > 0:
            results.append(item * 2)
    return results
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is True
    assert result.status == "valid_docstring_only_changes"
    assert len(result.docstring_changes) == 1
    assert result.docstring_changes[0]["type"] == "function"
    assert result.docstring_changes[0]["name"] == "process_data"
    assert result.docstring_changes[0]["original"] is None
    assert "Process a list of data items" in result.docstring_changes[0]["current"]


def test_invalid_logic_change():
    """Test that logic changes fail validation."""

    original = '''
def calculate_area(length, width):
    """Calculate area of rectangle."""
    return length * width
'''

    modified = '''
def calculate_area(length, width):
    """Calculate area of rectangle."""
    return length + width  # Logic changed!
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"
    assert "logic were modified" in result.reason


def test_function_signature_change():
    """Test that function signature changes fail validation."""

    original = '''
def add_numbers(a, b):
    """Add two numbers."""
    return a + b
'''

    modified = '''
def add_numbers(a, b, c):  # Added parameter!
    """Add three numbers."""
    return a + b + c
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_import_change_fails():
    """Test that import changes fail validation."""

    original = """
import os

def get_path():
    return os.getcwd()
"""

    modified = """
import os
import sys  # Added import!

def get_path():
    return os.getcwd()
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_decorator_change_fails():
    """Test that decorator changes fail validation."""

    original = '''
def my_function():
    """A function."""
    return True
'''

    modified = '''
@staticmethod  # Added decorator!
def my_function():
    """A function."""
    return True
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_class_docstring_change_valid():
    """Test that class docstring changes are valid."""

    original = """
class Rectangle:
    def __init__(self, length, width):
        self.length = length
        self.width = width

    def area(self):
        return self.length * self.width
"""

    modified = '''
class Rectangle:
    """A rectangle class for geometric calculations."""

    def __init__(self, length, width):
        """Initialize a rectangle.

        Args:
            length: Rectangle length.
            width: Rectangle width.
        """
        self.length = length
        self.width = width

    def area(self):
        """Calculate the area of the rectangle.

        Returns:
            The area as length * width.
        """
        return self.length * self.width
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is True
    assert result.status == "valid_docstring_only_changes"
    assert len(result.docstring_changes) == 3  # Class + 2 methods

    # Check specific changes
    change_types = {change["name"]: change["type"] for change in result.docstring_changes}
    assert "Rectangle" in change_types
    assert "__init__" in change_types
    assert "area" in change_types


def test_class_method_added_fails():
    """Test that adding class methods fails validation."""

    original = """
class Calculator:
    def add(self, a, b):
        return a + b
"""

    modified = """
class Calculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):  # Added method!
        return a - b
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_syntax_error_detection():
    """Test that syntax errors are detected."""

    original = '''
def good_function():
    """A good function."""
    return True
'''

    syntax_error_content = '''
def broken_function(:  # Syntax error!
    """A broken function."""
    return "This has a syntax error"
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(syntax_error_content)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "syntax_error"
    assert "syntax errors" in result.reason


def test_module_docstring_change_valid():
    """Test that module docstring changes are valid."""

    original = """
def hello():
    return "Hello"
"""

    modified = '''
"""This module contains greeting functions."""

def hello():
    return "Hello"
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is True
    assert result.status == "valid_docstring_only_changes"
    assert len(result.docstring_changes) == 1
    assert result.docstring_changes[0]["type"] == "module"
    assert result.docstring_changes[0]["name"] == "__module__"
    assert "greeting functions" in result.docstring_changes[0]["current"]


def test_no_changes():
    """Test that identical files pass validation with no changes."""

    content = '''
def example_function(x, y):
    """Example function with docstring.

    Args:
        x: First parameter.
        y: Second parameter.

    Returns:
        Sum of x and y.
    """
    return x + y
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        f.flush()

        result = ast_validator.validate_changes(content, Path(f.name))

    assert result.passed is True
    assert result.status == "valid_docstring_only_changes"
    assert len(result.docstring_changes) == 0


def test_complex_class_with_inheritance():
    """Test validation with complex class inheritance."""

    original = """
class Animal:
    def speak(self):
        pass

class Dog(Animal):
    def speak(self):
        return "Woof"

    def fetch(self, item):
        return f"Fetching {item}"
"""

    modified = '''
class Animal:
    """Base class for all animals."""

    def speak(self):
        """Make a sound. Should be overridden by subclasses."""
        pass

class Dog(Animal):
    """A dog that can speak and fetch."""

    def speak(self):
        """Dogs say woof.

        Returns:
            The string 'Woof'.
        """
        return "Woof"

    def fetch(self, item):
        """Fetch an item.

        Args:
            item: The item to fetch.

        Returns:
            A string describing the fetch action.
        """
        return f"Fetching {item}"
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is True
    assert result.status == "valid_docstring_only_changes"
    assert len(result.docstring_changes) == 4  # 2 classes + 2 methods


def test_function_with_type_hints():
    """Test that type hint changes fail validation."""

    original = '''
def add_numbers(a, b):
    """Add two numbers."""
    return a + b
'''

    modified = '''
def add_numbers(a: int, b: int) -> int:  # Added type hints!
    """Add two numbers."""
    return a + b
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"
