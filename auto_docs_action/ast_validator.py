"""AST-based validation that only docstrings were modified."""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ValidationResult:
    """Result of AST validation."""

    passed: bool
    status: str
    reason: str | None = None
    docstring_changes: list[dict[str, Any]] | None = None


def validate_changes(original_content: str, current_file_path: Path) -> ValidationResult:
    """Validate that only docstrings were modified using AST comparison.

    Args:
        original_content: Original file content before changes
        current_file_path: Path to current (potentially modified) file

    Returns:
        ValidationResult indicating if changes are valid
    """
    try:
        current_content = current_file_path.read_text()

        # Parse both versions
        original_ast = ast.parse(original_content)
        current_ast = ast.parse(current_content)

        # Extract complete code structures (without docstrings)
        original_structure = _extract_code_structure(original_ast)
        current_structure = _extract_code_structure(current_ast)

        # Compare non-docstring elements
        if not _structures_match(original_structure, current_structure):
            return ValidationResult(
                passed=False,
                status="structure_changed",
                reason="Function/class signatures, imports, or logic were modified",
            )

        # Extract and compare docstrings
        docstring_changes = _compare_docstrings(original_ast, current_ast)

        return ValidationResult(passed=True, status="valid_docstring_only_changes", docstring_changes=docstring_changes)

    except SyntaxError as e:
        return ValidationResult(passed=False, status="syntax_error", reason=f"Modified file has syntax errors: {e}")
    except Exception as e:
        return ValidationResult(passed=False, status="validation_error", reason=f"Validation failed: {e}")


def _extract_code_structure(tree: ast.AST) -> str:
    """Extract complete code structure (excluding docstrings) using recursive AST walking.

    This new approach walks the entire AST recursively and removes docstrings
    from every scope (module, function, class), then serializes the remaining
    structure for comparison.

    Args:
        tree: AST tree to analyze

    Returns:
        String representation of the code structure without docstrings
    """
    # Create a deep copy of the AST to avoid modifying the original
    import copy

    tree_copy = copy.deepcopy(tree)

    # Recursively remove docstrings from all scopes
    _remove_docstrings_recursive(tree_copy)

    # Return serialized structure
    return ast.dump(tree_copy)


def _remove_docstrings_recursive(node: ast.AST) -> None:
    """Recursively remove docstrings from valid docstring scopes in the AST.

    This function walks through the entire AST and removes the first statement
    from scopes that can legally have docstrings (Module, FunctionDef,
    AsyncFunctionDef, ClassDef) if it's a string literal.

    String literals in other contexts (try, if, for, with, match, etc.) are
    preserved as regular statements.

    Args:
        node: AST node to process (modified in-place)
    """
    # Only remove docstrings from scopes that can legally have them
    if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        if hasattr(node, "body") and node.body:
            # Check if first statement is a docstring
            first_stmt = node.body[0]
            if (
                isinstance(first_stmt, ast.Expr)
                and isinstance(first_stmt.value, ast.Constant)
                and isinstance(first_stmt.value.value, str)
            ):
                # Remove the docstring
                node.body = node.body[1:]

    # Recursively process all child nodes
    for child in ast.iter_child_nodes(node):
        _remove_docstrings_recursive(child)


def _structures_match(orig_structure: str, curr_structure: str) -> bool:
    """Compare code structures ignoring docstrings.

    Args:
        orig_structure: Original AST structure (serialized)
        curr_structure: Current AST structure (serialized)

    Returns:
        True if structures match (only docstrings may differ)
    """
    try:
        # Simple string comparison of the docstring-stripped AST structures
        return orig_structure == curr_structure

    except Exception as e:
        logging.error(f"Error comparing structures: {e}")
        return False


def _compare_docstrings(orig_ast: ast.AST, curr_ast: ast.AST) -> list[dict[str, Any]]:
    """Extract docstring differences between two ASTs.

    Args:
        orig_ast: Original AST
        curr_ast: Current AST

    Returns:
        List of docstring changes
    """
    changes = []

    # Compare module docstring
    orig_module_doc = _get_docstring(orig_ast)
    curr_module_doc = _get_docstring(curr_ast)
    if orig_module_doc != curr_module_doc:
        changes.append({"type": "module", "name": "__module__", "original": orig_module_doc, "current": curr_module_doc})

    # Compare function docstrings
    orig_functions = {f.name: f for f in ast.walk(orig_ast) if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))}
    curr_functions = {f.name: f for f in ast.walk(curr_ast) if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))}

    for func_name in set(orig_functions.keys()) | set(curr_functions.keys()):
        orig_doc = _get_docstring(orig_functions.get(func_name)) if func_name in orig_functions else None
        curr_doc = _get_docstring(curr_functions.get(func_name)) if func_name in curr_functions else None

        if orig_doc != curr_doc:
            changes.append({"type": "function", "name": func_name, "original": orig_doc, "current": curr_doc})

    # Compare class docstrings
    orig_classes = {c.name: c for c in ast.walk(orig_ast) if isinstance(c, ast.ClassDef)}
    curr_classes = {c.name: c for c in ast.walk(curr_ast) if isinstance(c, ast.ClassDef)}

    for class_name in set(orig_classes.keys()) | set(curr_classes.keys()):
        orig_doc = _get_docstring(orig_classes.get(class_name)) if class_name in orig_classes else None
        curr_doc = _get_docstring(curr_classes.get(class_name)) if class_name in curr_classes else None

        if orig_doc != curr_doc:
            changes.append({"type": "class", "name": class_name, "original": orig_doc, "current": curr_doc})

    return changes


def _get_docstring(node: ast.AST | None) -> str | None:
    """Extract docstring from an AST node.

    Args:
        node: AST node to extract docstring from

    Returns:
        Docstring text or None if no docstring
    """
    if node is None:
        return None

    # For modules, functions, and classes
    if hasattr(node, "body") and node.body:
        first_stmt = node.body[0]
        if (
            isinstance(first_stmt, ast.Expr)
            and isinstance(first_stmt.value, ast.Constant)
            and isinstance(first_stmt.value.value, str)
        ):
            return first_stmt.value.value

    return None
