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


class ASTValidator:
    """Validates that only docstrings were changed using AST comparison."""

    def validate_changes(self, original_content: str, current_file_path: Path) -> ValidationResult:
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

            # Extract function/class structures (without docstrings)
            original_structure = self._extract_code_structure(original_ast)
            current_structure = self._extract_code_structure(current_ast)

            # Compare non-docstring elements
            if not self._structures_match(original_structure, current_structure):
                return ValidationResult(
                    passed=False,
                    status="structure_changed",
                    reason="Function/class signatures, imports, or logic were modified",
                )

            # Extract and compare docstrings
            docstring_changes = self._compare_docstrings(original_ast, current_ast)

            return ValidationResult(passed=True, status="valid_docstring_only_changes", docstring_changes=docstring_changes)

        except SyntaxError as e:
            return ValidationResult(passed=False, status="syntax_error", reason=f"Modified file has syntax errors: {e}")
        except Exception as e:
            return ValidationResult(passed=False, status="validation_error", reason=f"Validation failed: {e}")

    def _extract_code_structure(self, tree: ast.AST) -> dict[str, Any]:
        """Extract function/class signatures and logic (excluding docstrings).

        Args:
            tree: AST tree to analyze

        Returns:
            Dictionary representing the code structure without docstrings
        """
        structure: dict[str, Any] = {"imports": [], "functions": [], "classes": [], "module_level": []}

        # Only process top-level nodes, not nested ones
        # AST.body is only available on Module nodes
        if not hasattr(tree, "body"):
            return structure

        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                structure["imports"].append(ast.dump(node))
            elif isinstance(node, ast.FunctionDef):
                func_info = {
                    "name": node.name,
                    "args": self._serialize_args(node.args),
                    "returns": ast.dump(node.returns) if node.returns else None,
                    "decorators": [ast.dump(d) for d in node.decorator_list],
                    "body_without_docstring": self._get_body_without_docstring(node.body),
                }
                structure["functions"].append(func_info)
            elif isinstance(node, ast.ClassDef):
                class_info = {
                    "name": node.name,
                    "bases": [ast.dump(base) for base in node.bases],
                    "decorators": [ast.dump(d) for d in node.decorator_list],
                    "methods": self._extract_class_methods(node),
                    "body_without_docstring": self._get_body_without_docstring(node.body),
                }
                structure["classes"].append(class_info)
            else:
                # Other module-level statements (assignments, etc.)
                # Skip docstrings (handled by _get_body_without_docstring logic)
                if not (
                    isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
                ):
                    structure["module_level"].append(ast.dump(node))

        return structure

    def _serialize_args(self, args: ast.arguments) -> dict[str, Any]:
        """Serialize function arguments for comparison."""
        return {
            "args": [arg.arg for arg in args.args],
            "vararg": args.vararg.arg if args.vararg else None,
            "kwonlyargs": [arg.arg for arg in args.kwonlyargs],
            "kwarg": args.kwarg.arg if args.kwarg else None,
            "defaults": [ast.dump(default) for default in args.defaults],
            "kw_defaults": [ast.dump(default) if default else None for default in args.kw_defaults],
        }

    def _get_body_without_docstring(self, body: list[ast.stmt]) -> list[str]:
        """Get AST body excluding docstring statements."""
        if not body:
            return []

        # Skip docstring (first statement if it's a string literal)
        start_idx = 0
        if (
            len(body) > 0
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            start_idx = 1

        return [ast.dump(stmt) for stmt in body[start_idx:]]

    def _extract_class_methods(self, class_node: ast.ClassDef) -> list[dict[str, Any]]:
        """Extract method information from a class node."""
        methods = []
        for node in class_node.body:
            if isinstance(node, ast.FunctionDef):
                method_info = {
                    "name": node.name,
                    "args": self._serialize_args(node.args),
                    "returns": ast.dump(node.returns) if node.returns else None,
                    "decorators": [ast.dump(d) for d in node.decorator_list],
                    "body_without_docstring": self._get_body_without_docstring(node.body),
                }
                methods.append(method_info)
        return methods

    def _structures_match(self, orig: dict[str, Any], curr: dict[str, Any]) -> bool:
        """Compare code structures ignoring docstrings.

        Args:
            orig: Original structure
            curr: Current structure

        Returns:
            True if structures match (only docstrings may differ)
        """
        try:
            # Compare imports
            if orig["imports"] != curr["imports"]:
                logging.debug("Import statements differ")
                return False

            # Compare functions
            if len(orig["functions"]) != len(curr["functions"]):
                logging.debug("Number of functions differs")
                return False

            for orig_func, curr_func in zip(orig["functions"], curr["functions"]):
                if not self._functions_match(orig_func, curr_func):
                    logging.debug(f"Function {orig_func['name']} differs")
                    return False

            # Compare classes
            if len(orig["classes"]) != len(curr["classes"]):
                logging.debug("Number of classes differs")
                return False

            for orig_class, curr_class in zip(orig["classes"], curr["classes"]):
                if not self._classes_match(orig_class, curr_class):
                    logging.debug(f"Class {orig_class['name']} differs")
                    return False

            # Compare module-level code
            if orig["module_level"] != curr["module_level"]:
                logging.debug("Module-level code differs")
                return False

            return True

        except Exception as e:
            logging.error(f"Error comparing structures: {e}")
            return False

    def _functions_match(self, orig: dict[str, Any], curr: dict[str, Any]) -> bool:
        """Compare two function definitions."""
        return bool(
            orig.get("name") == curr.get("name")
            and orig.get("args") == curr.get("args")
            and orig.get("returns") == curr.get("returns")
            and orig.get("decorators") == curr.get("decorators")
            and orig.get("body_without_docstring") == curr.get("body_without_docstring")
        )

    def _classes_match(self, orig: dict[str, Any], curr: dict[str, Any]) -> bool:
        """Compare two class definitions."""
        # Check basic class properties
        if orig["name"] != curr["name"] or orig["bases"] != curr["bases"] or orig["decorators"] != curr["decorators"]:
            return False

        # Compare methods individually (allows docstring changes)
        if len(orig["methods"]) != len(curr["methods"]):
            return False

        for orig_method, curr_method in zip(orig["methods"], curr["methods"]):
            if not self._functions_match(orig_method, curr_method):
                return False

        # Compare non-method class body statements (excluding docstrings and methods)
        orig_non_method_body = self._get_class_non_method_body(orig)
        curr_non_method_body = self._get_class_non_method_body(curr)

        return orig_non_method_body == curr_non_method_body

    def _get_class_non_method_body(self, class_info: dict[str, Any]) -> list[str]:
        """Get class body statements excluding methods and docstrings."""
        # For now, just return empty list since we store the body as strings
        # but methods are extracted separately. This could be enhanced later
        # if needed for class-level statements like class variables.
        return []

    def _compare_docstrings(self, orig_ast: ast.AST, curr_ast: ast.AST) -> list[dict[str, Any]]:
        """Extract docstring differences between two ASTs.

        Args:
            orig_ast: Original AST
            curr_ast: Current AST

        Returns:
            List of docstring changes
        """
        changes = []

        # Compare module docstring
        orig_module_doc = self._get_docstring(orig_ast)
        curr_module_doc = self._get_docstring(curr_ast)
        if orig_module_doc != curr_module_doc:
            changes.append({"type": "module", "name": "__module__", "original": orig_module_doc, "current": curr_module_doc})

        # Compare function docstrings
        orig_functions = {f.name: f for f in ast.walk(orig_ast) if isinstance(f, ast.FunctionDef)}
        curr_functions = {f.name: f for f in ast.walk(curr_ast) if isinstance(f, ast.FunctionDef)}

        for func_name in set(orig_functions.keys()) | set(curr_functions.keys()):
            orig_doc = self._get_docstring(orig_functions.get(func_name)) if func_name in orig_functions else None
            curr_doc = self._get_docstring(curr_functions.get(func_name)) if func_name in curr_functions else None

            if orig_doc != curr_doc:
                changes.append({"type": "function", "name": func_name, "original": orig_doc, "current": curr_doc})

        # Compare class docstrings
        orig_classes = {c.name: c for c in ast.walk(orig_ast) if isinstance(c, ast.ClassDef)}
        curr_classes = {c.name: c for c in ast.walk(curr_ast) if isinstance(c, ast.ClassDef)}

        for class_name in set(orig_classes.keys()) | set(curr_classes.keys()):
            orig_doc = self._get_docstring(orig_classes.get(class_name)) if class_name in orig_classes else None
            curr_doc = self._get_docstring(curr_classes.get(class_name)) if class_name in curr_classes else None

            if orig_doc != curr_doc:
                changes.append({"type": "class", "name": class_name, "original": orig_doc, "current": curr_doc})

        return changes

    def _get_docstring(self, node: ast.AST | None) -> str | None:
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
