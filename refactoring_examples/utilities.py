"""Utility functions to reduce code duplication and standardize common patterns."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar('T')


class LogUtil:
    """Utility class for standardized logging with emojis."""
    
    @staticmethod
    def log_operation_start(operation: str, details: str = "") -> None:
        """Log the start of an operation."""
        logger = logging.getLogger(__name__)
        logger.info(f"🔄 Starting {operation}{': ' + details if details else '...'}")
    
    @staticmethod
    def log_operation_success(operation: str, details: str = "") -> None:
        """Log successful completion of an operation."""
        logger = logging.getLogger(__name__)
        logger.info(f"✅ {operation} completed{': ' + details if details else ''}")
    
    @staticmethod
    def log_operation_failure(operation: str, error: str) -> None:
        """Log failure of an operation."""
        logger = logging.getLogger(__name__)
        logger.error(f"❌ {operation} failed: {error}")
    
    @staticmethod
    def log_operation_warning(operation: str, warning: str) -> None:
        """Log a warning during an operation."""
        logger = logging.getLogger(__name__)
        logger.warning(f"⚠️ {operation}: {warning}")
    
    @staticmethod
    def log_file_count(operation: str, count: int, file_type: str = "files") -> None:
        """Log file count information."""
        logger = logging.getLogger(__name__)
        logger.info(f"🔍 {operation}: found {count} {file_type}")


class FileUtil:
    """Utility class for common file operations with standardized error handling."""
    
    @staticmethod
    def safe_read_text(file_path: Path) -> tuple[bool, str]:
        """Safely read text from a file.
        
        Returns:
            Tuple of (success, content_or_error_message)
        """
        try:
            content = file_path.read_text()
            return True, content
        except Exception as e:
            return False, f"Failed to read {file_path}: {e}"
    
    @staticmethod
    def safe_write_text(file_path: Path, content: str) -> tuple[bool, str]:
        """Safely write text to a file.
        
        Returns:
            Tuple of (success, success_message_or_error_message)
        """
        try:
            file_path.write_text(content)
            return True, f"Successfully wrote to {file_path}"
        except Exception as e:
            return False, f"Failed to write to {file_path}: {e}"
    
    @staticmethod
    def file_exists_and_readable(file_path: Path) -> bool:
        """Check if file exists and is readable."""
        return file_path.exists() and file_path.is_file()


class SafeExecutor:
    """Utility for safely executing operations with consistent error handling."""
    
    @staticmethod
    def execute_with_logging(
        operation_name: str,
        operation: Callable[[], T],
        on_success: Callable[[T], None] | None = None,
        on_failure: Callable[[Exception], None] | None = None,
        reraise: bool = False
    ) -> T | None:
        """Execute an operation with standardized logging.
        
        Args:
            operation_name: Name of the operation for logging
            operation: The operation to execute
            on_success: Optional callback for successful execution
            on_failure: Optional callback for failed execution  
            reraise: Whether to reraise exceptions after logging
            
        Returns:
            Result of operation or None if failed
        """
        logger = logging.getLogger(__name__)
        
        try:
            LogUtil.log_operation_start(operation_name)
            result = operation()
            LogUtil.log_operation_success(operation_name)
            
            if on_success:
                on_success(result)
                
            return result
            
        except Exception as e:
            LogUtil.log_operation_failure(operation_name, str(e))
            
            if on_failure:
                on_failure(e)
                
            if reraise:
                raise
                
            return None


# Example usage showing how current code could be simplified:
"""
# BEFORE (duplicated patterns):
def process_files():
    logger.info("🔄 Processing files...")
    try:
        results = processor.process_multiple_files(changed_files)
        logger.info(f"✅ File processing completed, got {len(results)} results")
        return results
    except Exception as e:
        logger.error(f"❌ Failed to process files: {e}", exc_info=True)
        return None

def stage_files():
    logger.info("📝 Staging successful changes...")
    try:
        # staging logic...
        logger.info(f"✅ Staging completed, staged_any={staged_any}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed during staging: {e}", exc_info=True)
        return False

# AFTER (using utilities):
def process_files():
    return SafeExecutor.execute_with_logging(
        "File processing",
        lambda: processor.process_multiple_files(changed_files),
        on_success=lambda results: LogUtil.log_file_count("Processing", len(results), "results")
    )

def stage_files():
    def stage_operation():
        # staging logic...
        return staged_any
    
    return SafeExecutor.execute_with_logging(
        "Staging changes",
        stage_operation,
        on_success=lambda staged: LogUtil.log_operation_success("Staging", f"staged_any={staged}")
    ) is not None
"""


class CommandBuilder:
    """Builder for constructing subprocess commands consistently."""
    
    def __init__(self, base_command: str):
        self.command = [base_command]
        self.timeout = 30
        self.cwd = None
    
    def add_arg(self, arg: str) -> CommandBuilder:
        """Add an argument to the command."""
        self.command.append(arg)
        return self
    
    def add_args(self, *args: str) -> CommandBuilder:
        """Add multiple arguments to the command."""
        self.command.extend(args)
        return self
    
    def with_timeout(self, timeout: int) -> CommandBuilder:
        """Set the timeout for the command."""
        self.timeout = timeout
        return self
    
    def in_directory(self, cwd: str | Path) -> CommandBuilder:
        """Set the working directory for the command."""
        self.cwd = str(cwd) if isinstance(cwd, Path) else cwd
        return self
    
    def build(self) -> dict[str, Any]:
        """Build the command configuration."""
        return {
            "cmd": self.command,
            "timeout": self.timeout,
            "cwd": self.cwd
        }


# Example of reducing duplication in git operations:
"""
# BEFORE (duplicated command patterns):
result1 = subprocess.run(["git", "status"], capture_output=True, text=True, timeout=30)
result2 = subprocess.run(["git", "diff", "--name-only"], capture_output=True, text=True, timeout=30)
result3 = subprocess.run(["git", "add", file_path], capture_output=True, text=True, timeout=30)

# AFTER (using builder):
def build_git_command(subcommand: str, *args: str) -> dict[str, Any]:
    return (CommandBuilder("git")
            .add_arg(subcommand)
            .add_args(*args)
            .with_timeout(30)
            .build())

# Usage:
status_cmd = build_git_command("status")
diff_cmd = build_git_command("diff", "--name-only")  
add_cmd = build_git_command("add", str(file_path))
"""