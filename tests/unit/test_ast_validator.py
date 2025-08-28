"""Tests for AST-based validation of docstring-only changes."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from auto_docs_action import ast_validator
from auto_docs_action.ast_validator import ValidationResult


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


def test_string_literal_in_middle_of_function():
    """Test that string literals added in middle of function body are rejected."""

    original = '''
def process_data(items):
    """Process a list of items."""
    results = []
    for item in items:
        if item > 0:
            results.append(item * 2)
    return results
'''

    modified = '''
def process_data(items):
    """Process a list of items."""
    results = []

    """This is NOT a docstring - it's in the wrong place!"""

    for item in items:
        if item > 0:
            results.append(item * 2)
    return results
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    # This should fail because adding a string literal in the middle
    # of a function body is a structural change, not a docstring change
    assert result.passed is False
    assert result.status == "structure_changed"


def test_string_literal_at_end_of_function():
    """Test that string literals added at end of function body are rejected."""

    original = '''
def calculate_sum(numbers):
    """Calculate sum of numbers."""
    total = 0
    for num in numbers:
        total += num
    return total
'''

    modified = '''
def calculate_sum(numbers):
    """Calculate sum of numbers."""
    total = 0
    for num in numbers:
        total += num

    """This looks like documentation but it's not a docstring!"""

    return total
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    # This should fail because adding a string literal anywhere except
    # the first statement is a structural change, not a docstring change
    assert result.passed is False
    assert result.status == "structure_changed"


def test_string_literal_in_module_body():
    """Test that string literals added in module body (not as first statement) are rejected."""

    original = '''
"""Module docstring."""

import os

def hello():
    return "Hello"
'''

    modified = '''
"""Module docstring."""

import os

"""This is NOT a valid module docstring - it's too late!"""

def hello():
    return "Hello"
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    # This should fail because adding a string literal in the middle
    # of module body is a structural change, not a docstring change
    assert result.passed is False
    assert result.status == "structure_changed"


def test_string_literal_in_class_body():
    """Test that string literals added in class body (not as docstring) are rejected."""

    original = '''
class Calculator:
    """A simple calculator class."""

    def add(self, a, b):
        return a + b
'''

    modified = '''
class Calculator:
    """A simple calculator class."""

    """This is NOT a valid position for documentation!"""

    def add(self, a, b):
        return a + b
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    # This should fail because adding a string literal after the class docstring
    # is a structural change, not a docstring change
    assert result.passed is False
    assert result.status == "structure_changed"


def test_multiple_module_docstrings():
    """Test that multiple module-level docstrings are rejected."""

    original = '''
"""Original module docstring."""

def hello():
    return "world"
'''

    modified = '''
"""Original module docstring."""
"""Second module docstring - invalid!"""

def hello():
    return "world"
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_string_literal_between_imports():
    """Test that string literals between imports are rejected."""

    original = """
import os
import sys

def main():
    pass
"""

    modified = '''
import os
"""This string literal shouldn't be here!"""
import sys

def main():
    pass
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_string_literal_after_class_variable():
    """Test that string literals after class variables are rejected."""

    original = '''
class Config:
    """Configuration class."""
    DEBUG = True

    def __init__(self):
        pass
'''

    modified = '''
class Config:
    """Configuration class."""
    DEBUG = True

    """This documentation is in the wrong place!"""

    def __init__(self):
        pass
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_nested_function_string_literal():
    """Test that string literals in nested functions are rejected when not docstrings."""

    original = '''
def outer():
    """Outer function."""

    def inner():
        """Inner function."""
        return True

    return inner()
'''

    modified = '''
def outer():
    """Outer function."""

    def inner():
        """Inner function."""
        """This is not a docstring - it's after the real docstring!"""
        return True

    return inner()
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_string_literal_in_try_block():
    """Test that string literals added inside try blocks are rejected."""

    original = '''
def risky_operation():
    """Perform a risky operation."""
    try:
        result = 1 / 0
    except ZeroDivisionError:
        return None
    return result
'''

    modified = '''
def risky_operation():
    """Perform a risky operation."""
    try:
        """This string literal shouldn't be here!"""
        result = 1 / 0
    except ZeroDivisionError:
        return None
    return result
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_string_literal_in_if_block():
    """Test that string literals added inside if blocks are rejected."""

    original = '''
def check_value(x):
    """Check if value is positive."""
    if x > 0:
        return True
    else:
        return False
'''

    modified = '''
def check_value(x):
    """Check if value is positive."""
    if x > 0:
        """Positive number handling"""
        return True
    else:
        return False
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_string_literal_in_for_loop():
    """Test that string literals added inside for loops are rejected."""

    original = '''
def process_list(items):
    """Process a list of items."""
    results = []
    for item in items:
        results.append(item * 2)
    return results
'''

    modified = '''
def process_list(items):
    """Process a list of items."""
    results = []
    for item in items:
        """Processing each item"""
        results.append(item * 2)
    return results
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_string_literal_with_assignment():
    """Test that adding string literals alongside variable assignments is rejected."""

    original = '''
def setup():
    """Setup function."""
    config = {"debug": True}
    return config
'''

    modified = '''
def setup():
    """Setup function."""
    """Configuration setup"""
    config = {"debug": True}
    return config
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_empty_string_as_docstring_replacement():
    """Test that replacing a docstring with empty string is detected."""

    original = '''
def greet(name):
    """Greet someone by name."""
    return f"Hello, {name}!"
'''

    modified = """
def greet(name):
    ""
    return f"Hello, {name}!"
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is True
    assert result.status == "valid_docstring_only_changes"
    assert len(result.docstring_changes) == 1
    assert result.docstring_changes[0]["name"] == "greet"


def test_multiline_string_vs_docstring():
    """Test that multiline strings not in docstring position are rejected."""

    original = '''
def process_data():
    """Process some data."""
    data = [1, 2, 3]
    return data
'''

    modified = '''
def process_data():
    """Process some data."""
    data = [1, 2, 3]

    """
    This is a multiline string
    that looks like documentation
    but it's in the wrong place!
    """

    return data
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_string_literal_between_decorators():
    """Test that string literals between decorators and functions are rejected."""

    original = '''
@staticmethod
def utility_function():
    """A utility function."""
    return True
'''

    modified = '''
@staticmethod
"""This string shouldn't be here!"""
def utility_function():
    """A utility function."""
    return True
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "syntax_error"  # String between decorator and function is syntax error


def test_class_with_multiple_string_literals():
    """Test that multiple string literals in class body are rejected."""

    original = '''
class DataProcessor:
    """Process data efficiently."""

    def process(self, data):
        return data * 2
'''

    modified = '''
class DataProcessor:
    """Process data efficiently."""

    """Additional class documentation - wrong place!"""

    """Even more documentation - also wrong!"""

    def process(self, data):
        return data * 2
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_string_literal_in_nested_class():
    """Test that string literals in nested classes are handled correctly."""

    original = '''
class Outer:
    """Outer class."""

    class Inner:
        """Inner class."""

        def method(self):
            return "inner"

    def outer_method(self):
        return "outer"
'''

    modified = '''
class Outer:
    """Outer class."""

    class Inner:
        """Inner class."""

        """This documentation is misplaced!"""

        def method(self):
            return "inner"

    def outer_method(self):
        return "outer"
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_valid_docstring_changes_with_complex_structure():
    """Test that valid docstring changes work with complex code structures."""

    original = """
import asyncio
from typing import List, Optional

class AsyncProcessor:

    def __init__(self, config: dict):
        self.config = config

    async def process_batch(self, items: List[str]) -> List[str]:
        results = []
        for item in items:
            if item.startswith("valid"):
                results.append(await self._process_item(item))
        return results

    async def _process_item(self, item: str) -> str:
        await asyncio.sleep(0.1)
        return item.upper()

def factory(config: Optional[dict] = None) -> AsyncProcessor:
    return AsyncProcessor(config or {})
"""

    modified = '''
import asyncio
from typing import List, Optional

class AsyncProcessor:
    """Asynchronously processes items in batches."""

    def __init__(self, config: dict):
        """Initialize processor with configuration.

        Args:
            config: Configuration dictionary.
        """
        self.config = config

    async def process_batch(self, items: List[str]) -> List[str]:
        """Process a batch of items asynchronously.

        Args:
            items: List of items to process.

        Returns:
            List of processed items.
        """
        results = []
        for item in items:
            if item.startswith("valid"):
                results.append(await self._process_item(item))
        return results

    async def _process_item(self, item: str) -> str:
        """Process a single item.

        Args:
            item: Item to process.

        Returns:
            Processed item.
        """
        await asyncio.sleep(0.1)
        return item.upper()

def factory(config: Optional[dict] = None) -> AsyncProcessor:
    """Create an AsyncProcessor instance.

    Args:
        config: Optional configuration dictionary.

    Returns:
        AsyncProcessor instance.
    """
    return AsyncProcessor(config or {})
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is True
    assert result.status == "valid_docstring_only_changes"
    assert len(result.docstring_changes) == 5  # class + 4 methods/functions


def test_string_literal_after_return_statement():
    """Test that string literals after return statements are rejected."""

    original = '''
def simple_function():
    """A simple function."""
    return "result"
'''

    modified = '''
def simple_function():
    """A simple function."""
    return "result"

    """This comes after return - unreachable but still invalid!"""
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_mixed_single_and_triple_quotes():
    """Test mixed quote styles for docstrings."""

    original = """
def test_function():
    pass
"""

    modified = '''
def test_function():
    """Triple quote docstring."""
    pass
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is True
    assert result.status == "valid_docstring_only_changes"


def test_property_decorator_docstrings():
    """Test that property decorators with docstring changes work correctly."""

    original = """
class Circle:

    def __init__(self, radius):
        self._radius = radius

    @property
    def radius(self):
        return self._radius

    @radius.setter
    def radius(self, value):
        if value <= 0:
            raise ValueError("Radius must be positive")
        self._radius = value
"""

    modified = '''
class Circle:
    """A circle with radius property."""

    def __init__(self, radius):
        """Initialize circle with radius.

        Args:
            radius: Circle radius.
        """
        self._radius = radius

    @property
    def radius(self):
        """Get the circle radius."""
        return self._radius

    @radius.setter
    def radius(self, value):
        """Set the circle radius.

        Args:
            value: New radius value.

        Raises:
            ValueError: If radius is not positive.
        """
        if value <= 0:
            raise ValueError("Radius must be positive")
        self._radius = value
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is True
    assert result.status == "valid_docstring_only_changes"


def test_lambda_with_string_literals():
    """Test that string literals around lambda functions are rejected."""

    original = '''
def create_processors():
    """Create data processors."""

    processors = [
        lambda x: x * 2,
        lambda x: x + 1,
    ]

    return processors
'''

    modified = '''
def create_processors():
    """Create data processors."""

    """Lambda function definitions"""

    processors = [
        lambda x: x * 2,
        lambda x: x + 1,
    ]

    return processors
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_async_function_docstrings():
    """Test that async function docstrings work correctly."""

    original = """
import asyncio

async def fetch_data(url):
    await asyncio.sleep(1)
    return {"data": "example"}

async def process_data(data):
    await asyncio.sleep(0.5)
    return data["data"].upper()
"""

    modified = '''
import asyncio

async def fetch_data(url):
    """Fetch data from URL asynchronously.

    Args:
        url: URL to fetch data from.

    Returns:
        Dictionary containing fetched data.
    """
    await asyncio.sleep(1)
    return {"data": "example"}

async def process_data(data):
    """Process data asynchronously.

    Args:
        data: Data dictionary to process.

    Returns:
        Processed data string.
    """
    await asyncio.sleep(0.5)
    return data["data"].upper()
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is True
    assert result.status == "valid_docstring_only_changes"


def test_context_manager_string_literals():
    """Test that string literals in context managers are rejected."""

    original = '''
def process_file(filename):
    """Process a file."""
    with open(filename) as f:
        content = f.read()
        return content.strip()
'''

    modified = '''
def process_file(filename):
    """Process a file."""
    with open(filename) as f:
        """Reading file content"""
        content = f.read()
        return content.strip()
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_generator_function_docstrings():
    """Test that generator function docstrings work correctly."""

    original = """
def fibonacci_generator(n):
    a, b = 0, 1
    for _ in range(n):
        yield a
        a, b = b, a + b
"""

    modified = '''
def fibonacci_generator(n):
    """Generate Fibonacci numbers.

    Args:
        n: Number of Fibonacci numbers to generate.

    Yields:
        Next Fibonacci number in sequence.
    """
    a, b = 0, 1
    for _ in range(n):
        yield a
        a, b = b, a + b
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is True
    assert result.status == "valid_docstring_only_changes"


def test_exception_handling_string_literals():
    """Test that string literals in exception handling are rejected."""

    original = '''
def divide_safely(a, b):
    """Safely divide two numbers."""
    try:
        return a / b
    except ZeroDivisionError:
        return float('inf')
    except TypeError:
        return None
    finally:
        pass
'''

    modified = '''
def divide_safely(a, b):
    """Safely divide two numbers."""
    try:
        return a / b
    except ZeroDivisionError:
        """Handle division by zero"""
        return float('inf')
    except TypeError:
        return None
    finally:
        pass
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_class_inheritance_with_docstrings():
    """Test that complex inheritance with docstrings works."""

    original = """
from abc import ABC, abstractmethod

class Animal(ABC):

    def __init__(self, name):
        self.name = name

    @abstractmethod
    def make_sound(self):
        pass

class Dog(Animal):

    def make_sound(self):
        return "Woof!"

    def fetch(self, item):
        return f"{self.name} fetched {item}"

class Cat(Animal):

    def make_sound(self):
        return "Meow!"
"""

    modified = '''
from abc import ABC, abstractmethod

class Animal(ABC):
    """Abstract base class for animals."""

    def __init__(self, name):
        """Initialize animal with name.

        Args:
            name: Animal's name.
        """
        self.name = name

    @abstractmethod
    def make_sound(self):
        """Make the animal's characteristic sound.

        Returns:
            String representation of the animal's sound.
        """
        pass

class Dog(Animal):
    """A dog that can bark and fetch."""

    def make_sound(self):
        """Dogs bark.

        Returns:
            Dog's bark sound.
        """
        return "Woof!"

    def fetch(self, item):
        """Fetch an item.

        Args:
            item: Item to fetch.

        Returns:
            Description of fetch action.
        """
        return f"{self.name} fetched {item}"

class Cat(Animal):
    """A cat that can meow."""

    def make_sound(self):
        """Cats meow.

        Returns:
            Cat's meow sound.
        """
        return "Meow!"
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is True
    assert result.status == "valid_docstring_only_changes"


def test_dataclass_with_string_literals():
    """Test that string literals in dataclass are rejected when not docstrings."""

    original = """
from dataclasses import dataclass

@dataclass
class Point:
    x: float
    y: float

    def distance_from_origin(self):
        return (self.x ** 2 + self.y ** 2) ** 0.5
"""

    modified = '''
from dataclasses import dataclass

@dataclass
class Point:
    """A point in 2D space."""
    x: float
    y: float

    """Additional field documentation - wrong place!"""

    def distance_from_origin(self):
        return (self.x ** 2 + self.y ** 2) ** 0.5
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_string_literal_in_list_comprehension():
    """Test that string literals cannot be added inside list comprehensions."""

    original = '''
def process_numbers(numbers):
    """Process a list of numbers."""
    return [x * 2 for x in numbers if x > 0]
'''

    # This should be syntactically invalid, but let's test a related case
    modified = '''
def process_numbers(numbers):
    """Process a list of numbers."""

    """List comprehension processing"""

    return [x * 2 for x in numbers if x > 0]
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_metaclass_with_docstrings():
    """Test that metaclass definitions with docstrings work correctly."""

    original = """
class MetaClass(type):

    def __new__(cls, name, bases, dct):
        return super().__new__(cls, name, bases, dct)

class MyClass(metaclass=MetaClass):

    def method(self):
        return "result"
"""

    modified = '''
class MetaClass(type):
    """Custom metaclass for special behavior."""

    def __new__(cls, name, bases, dct):
        """Create new class instance.

        Args:
            cls: Metaclass.
            name: Class name.
            bases: Base classes.
            dct: Class dictionary.

        Returns:
            New class instance.
        """
        return super().__new__(cls, name, bases, dct)

class MyClass(metaclass=MetaClass):
    """Class using custom metaclass."""

    def method(self):
        """Example method.

        Returns:
            Result string.
        """
        return "result"
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is True
    assert result.status == "valid_docstring_only_changes"


def test_string_literals_in_match_statement():
    """Test that string literals in match statements are rejected (Python 3.10+)."""

    original = '''
def handle_value(value):
    """Handle different value types."""
    match value:
        case int():
            return "integer"
        case str():
            return "string"
        case _:
            return "other"
'''

    modified = '''
def handle_value(value):
    """Handle different value types."""
    match value:
        case int():
            """Handle integer case"""
            return "integer"
        case str():
            return "string"
        case _:
            return "other"
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_mixed_valid_invalid_changes():
    """Test file with both valid docstring changes and invalid string literals."""

    original = """
class Calculator:

    def add(self, a, b):
        return a + b

    def multiply(self, a, b):
        return a * b

def helper_function():
    return "helper"
"""

    modified = '''
class Calculator:
    """A simple calculator class."""

    def add(self, a, b):
        """Add two numbers."""
        return a + b

    """This string literal is misplaced!"""

    def multiply(self, a, b):
        """Multiply two numbers."""
        return a * b

def helper_function():
    """A helper function."""
    return "helper"
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    # Should fail because of the misplaced string literal,
    # even though the docstrings are valid
    assert result.passed is False
    assert result.status == "structure_changed"


def test_nested_class_docstring_support():
    """Test that nested classes with docstring changes now work correctly!"""
    # This test verifies the improved AST validator handles nested structures properly

    original = """
class Outer:

    class Middle:

        def middle_method(self):
            return "middle"

    def outer_method(self):
        return "outer"
"""

    modified = '''
class Outer:
    """Outer class with nested structures."""

    class Middle:
        """Middle nested class."""

        def middle_method(self):
            """Middle method."""
            return "middle"

    def outer_method(self):
        """Outer method."""
        return "outer"
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    # The improved validator now correctly handles nested structures!
    assert result.passed is True
    assert result.status == "valid_docstring_only_changes"
    assert len(result.docstring_changes) == 4  # All classes and methods detected

    # Verify all expected docstring changes are detected
    change_names = {change["name"] for change in result.docstring_changes}
    assert "Outer" in change_names
    assert "Middle" in change_names
    assert "middle_method" in change_names
    assert "outer_method" in change_names


def test_nested_string_literal_rejection():
    """Test that misplaced string literals in nested structures are still rejected."""

    original = """
class Outer:

    class Inner:

        def method(self):
            return "result"
"""

    modified = '''
class Outer:
    """Valid outer docstring."""

    class Inner:
        """Valid inner docstring."""

        """Invalid string literal - wrong position!"""

        def method(self):
            """Valid method docstring."""
            return "result"
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    # Should fail due to the misplaced string literal in nested class
    assert result.passed is False
    assert result.status == "structure_changed"


def test_string_literal_in_walrus_operator():
    """Test that string literals around walrus operator are rejected."""

    original = '''
def process_data(items):
    """Process items if length is sufficient."""
    if (length := len(items)) > 5:
        return items[:length // 2]
    return items
'''

    modified = '''
def process_data(items):
    """Process items if length is sufficient."""

    """Check item length"""

    if (length := len(items)) > 5:
        return items[:length // 2]
    return items
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    assert result.passed is False
    assert result.status == "structure_changed"


def test_extremely_complex_nested_structure():
    """Test the most complex nested structure with all Python features."""

    original = """
import asyncio
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod

class MetaProcessor(type):
    def __new__(cls, name, bases, dct):
        return super().__new__(cls, name, bases, dct)

class BaseProcessor(ABC, metaclass=MetaProcessor):

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    async def process(self, data: Any) -> Any:
        pass

    class InnerValidator:
        def __init__(self, rules: List[str]):
            self.rules = rules

        def validate(self, item: str) -> bool:
            def check_rule(rule: str) -> bool:
                return rule in item
            return all(check_rule(rule) for rule in self.rules)

class AsyncDataProcessor(BaseProcessor):

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._cache: Dict[str, Any] = {}

    async def process(self, data: List[str]) -> List[str]:
        results = []

        async def process_item(item: str) -> str:
            await asyncio.sleep(0.001)
            return item.upper()

        for item in data:
            processed = await process_item(item)
            results.append(processed)

        return results

    @property
    def cache_size(self) -> int:
        return len(self._cache)

def create_processor(config: Optional[Dict[str, Any]] = None) -> AsyncDataProcessor:
    return AsyncDataProcessor(config or {})
"""

    modified = '''
import asyncio
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod

class MetaProcessor(type):
    """Metaclass for creating processor classes."""

    def __new__(cls, name, bases, dct):
        """Create new processor class with validation.

        Args:
            cls: The metaclass.
            name: Class name.
            bases: Base classes.
            dct: Class dictionary.

        Returns:
            New processor class.
        """
        return super().__new__(cls, name, bases, dct)

class BaseProcessor(ABC, metaclass=MetaProcessor):
    """Abstract base processor with validation capabilities."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize processor with configuration.

        Args:
            config: Configuration dictionary.
        """
        self.config = config

    @abstractmethod
    async def process(self, data: Any) -> Any:
        """Process data asynchronously.

        Args:
            data: Data to process.

        Returns:
            Processed data.
        """
        pass

    class InnerValidator:
        """Nested validator class for rule checking."""

        def __init__(self, rules: List[str]):
            """Initialize validator with rules.

            Args:
                rules: List of validation rules.
            """
            self.rules = rules

        def validate(self, item: str) -> bool:
            """Validate item against all rules.

            Args:
                item: Item to validate.

            Returns:
                True if item passes all rules.
            """
            def check_rule(rule: str) -> bool:
                """Check individual rule.

                Args:
                    rule: Rule to check.

                Returns:
                    True if rule passes.
                """
                return rule in item
            return all(check_rule(rule) for rule in self.rules)

class AsyncDataProcessor(BaseProcessor):
    """Asynchronous data processor with caching and validation."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize async processor with caching.

        Args:
            config: Configuration dictionary.
        """
        super().__init__(config)
        self._cache: Dict[str, Any] = {}

    async def process(self, data: List[str]) -> List[str]:
        """Process list of strings with caching.

        Args:
            data: List of strings to process.

        Returns:
            List of processed strings.
        """
        results = []

        async def process_item(item: str) -> str:
            """Process individual item asynchronously.

            Args:
                item: String item to process.

            Returns:
                Processed string in uppercase.
            """
            await asyncio.sleep(0.001)
            return item.upper()

        for item in data:
            processed = await process_item(item)
            results.append(processed)

        return results

    @property
    def cache_size(self) -> int:
        """Get current cache size.

        Returns:
            Number of items in cache.
        """
        return len(self._cache)

def create_processor(config: Optional[Dict[str, Any]] = None) -> AsyncDataProcessor:
    """Factory function for creating async processors.

    Args:
        config: Optional configuration dictionary.

    Returns:
        New AsyncDataProcessor instance.
    """
    return AsyncDataProcessor(config or {})
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(modified)
        f.flush()

        result = ast_validator.validate_changes(original, Path(f.name))

    # This extremely complex structure should now work perfectly!
    assert result.passed is True
    assert result.status == "valid_docstring_only_changes"

    # Should detect all docstring additions across all nested levels
    # Note: There are multiple __init__ methods in the hierarchy
    assert len(result.docstring_changes) >= 10

    # Verify complex nested structure detection
    change_names = {change["name"] for change in result.docstring_changes}
    expected_names = {
        "MetaProcessor",
        "__new__",
        "BaseProcessor",
        "__init__",
        "process",
        "InnerValidator",
        "validate",
        "check_rule",
        "AsyncDataProcessor",
        "process_item",
        "cache_size",
        "create_processor",
    }
    # All expected names should be present (there may be duplicates due to inheritance)
    assert expected_names.issubset(change_names)
