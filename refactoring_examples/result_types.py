"""Standardized result types for consistent error handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar('T')
E = TypeVar('E')


@dataclass
class OperationResult(Generic[T]):
    """Standard result type for operations that can succeed or fail.
    
    This provides a consistent interface for error handling across the application,
    replacing the inconsistent mix of boolean returns, None values, and exceptions.
    """
    
    success: bool
    data: T | None = None
    error_message: str | None = None
    error_code: str | None = None
    
    @classmethod
    def success_with_data(cls, data: T) -> OperationResult[T]:
        """Create a successful result with data."""
        return cls(success=True, data=data)
    
    @classmethod
    def failure(cls, error_message: str, error_code: str | None = None) -> OperationResult[T]:
        """Create a failed result with error details."""
        return cls(success=False, error_message=error_message, error_code=error_code)
    
    def unwrap(self) -> T:
        """Get the data, raising an exception if the operation failed."""
        if not self.success:
            raise ValueError(f"Operation failed: {self.error_message}")
        if self.data is None:
            raise ValueError("Operation succeeded but no data was returned")
        return self.data
    
    def unwrap_or(self, default: T) -> T:
        """Get the data, returning a default value if the operation failed."""
        return self.data if self.success and self.data is not None else default


@dataclass
class GitOperationResult(OperationResult[str]):
    """Specialized result type for git operations."""
    
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    
    @classmethod
    def from_subprocess_result(cls, returncode: int, stdout: str, stderr: str) -> GitOperationResult:
        """Create result from subprocess output."""
        success = returncode == 0
        error_message = stderr.strip() if stderr and not success else None
        
        return cls(
            success=success,
            data=stdout,
            error_message=error_message,
            error_code=f"exit_{returncode}" if not success else None,
            stdout=stdout,
            stderr=stderr,
            return_code=returncode
        )


@dataclass  
class FileOperationResult(OperationResult[str]):
    """Specialized result type for file operations."""
    
    file_path: str | None = None
    operation_type: str | None = None  # "read", "write", "validate", etc.
    
    @classmethod
    def read_success(cls, file_path: str, content: str) -> FileOperationResult:
        """Create successful file read result."""
        return cls(
            success=True,
            data=content,
            file_path=file_path,
            operation_type="read"
        )
    
    @classmethod
    def read_failure(cls, file_path: str, error: str) -> FileOperationResult:
        """Create failed file read result."""
        return cls(
            success=False,
            error_message=f"Failed to read {file_path}: {error}",
            error_code="file_read_error",
            file_path=file_path,
            operation_type="read"
        )


# Example of how existing code could be refactored:
"""
# OLD CODE (inconsistent error handling):
def get_file_content(path: Path) -> str | None:
    try:
        return path.read_text()
    except Exception as e:
        logging.error(f"Failed to read {path}: {e}")
        return None

# NEW CODE (consistent error handling):
def get_file_content(path: Path) -> FileOperationResult:
    try:
        content = path.read_text()
        return FileOperationResult.read_success(str(path), content)
    except Exception as e:
        return FileOperationResult.read_failure(str(path), str(e))

# Usage becomes:
result = get_file_content(file_path)
if result.success:
    content = result.data
else:
    logger.error(result.error_message)
"""