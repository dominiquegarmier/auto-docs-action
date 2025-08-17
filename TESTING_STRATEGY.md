# Testing Strategy

## Overview

**Goal**: Test each component with real functionality, minimal mocking. Only mock Claude Code CLI calls since we can't rely on external API during tests.

## Core Testing Approach

### What We Test & How

| Component | Test Method | Mock Level |
|-----------|-------------|------------|
| `git_operations.py` | Real git repos in temp dirs | No mocks - test actual subprocess calls |
| `ast_validator.py` | Real Python AST parsing | No mocks - test actual AST comparison |
| `docstring_updater.py` | Mock subprocess only | Mock subprocess.run, test real parsing |
| `file_processor.py` | Integration test | Mock Claude Code, real git + AST |
| `main.py` | Full workflow test | Mock Claude Code, real everything else |

## Key Test Examples

### 1. AST Validator (Real Python Parsing)
```python
def test_logic_change_detection():
    original = 'def add(a, b): return a + b'
    modified = 'def add(a, b): return a - b'  # Logic changed!

    result = ast_validator.validate_changes(original, write_temp_file(modified))

    assert result.passed == False
    assert "structure_changed" in result.status
```

### 2. Git Operations (Real Git Repos)
```python
def test_git_restore_works(temp_git_repo):
    file_path = temp_git_repo / "test.py"
    file_path.write_text("original")

    # Make git commit, modify file, restore
    subprocess.run(["git", "add", "test.py"], cwd=temp_git_repo)
    subprocess.run(["git", "commit", "-m", "init"], cwd=temp_git_repo)
    file_path.write_text("modified")

    git_ops.restore_file(file_path)

    assert file_path.read_text() == "original"  # Actually restored
```

### 3. Integration Test (Mock Claude Code Only)
```python
def test_complete_workflow(temp_git_repo, monkeypatch):
    # Setup real git repo with Python file missing docstrings
    setup_repo_with_python_files(temp_git_repo)
    monkeypatch.setenv("INPUT_ANTHROPIC_API_KEY", "test-key")

    # Mock Claude Code to make realistic docstring additions
    with patch('subprocess.run') as mock_claude:
        mock_claude.side_effect = make_realistic_docstring_changes

        # Run actual main.py
        main()

        # Verify real results
        assert git_commit_created()
        assert docstrings_added_to_files()
        assert ast_validation_passed()
```

## Test Structure

```
tests/
├── conftest.py                    # Temp git repos, sample files fixtures
├── test_data/python_samples/      # Static Python files for testing
├── unit/
│   ├── test_git_operations.py     # Real subprocess git commands
│   ├── test_ast_validator.py      # Real AST parsing & comparison
│   ├── test_docstring_updater.py  # Mock subprocess, real parsing
│   └── test_file_processor.py     # Integration with mocked components
└── integration/
    └── test_main_workflow.py      # Full main.py execution

```

## Success Criteria

✅ **Functional**: All components work correctly
✅ **Safe**: AST proves only docstrings changed
✅ **Traceable**: Complete operation logs
✅ **Recoverable**: git restore cleans failed states
✅ **Performant**: <5 minutes for typical repos
