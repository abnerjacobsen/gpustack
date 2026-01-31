# Coding Conventions

**Analysis Date:** 2026-01-31

## Naming Patterns

**Files:**
- Source files: `snake_case.py` (e.g., `test_scheduler.py`, `worker_manager.py`)
- Test files: `test_{module}.py` (e.g., `test_exceptions.py`, `test_command.py`)
- Test locations mirror source structure: `tests/{module}/test_{name}.py`

**Functions:**
- `snake_case` for all functions and methods (e.g., `find_parameter()`, `evaluate_model_metadata()`)
- Private helpers prefixed with underscore (e.g., `_schedule_cycle()`)
- Factory functions use `new_` prefix (e.g., `new_model()`, `new_model_instance()`)

**Variables:**
- `snake_case` for variables (e.g., `worker_id`, `gpu_indexes`)
- Private instance variables use underscore prefix (e.g., `_config`, `_queue`)
- Constants: Module-level constants use UPPER_SNAKE_CASE sparingly, prefer class-level

**Classes:**
- `PascalCase` for all classes (e.g., `Scheduler`, `ModelInstance`, `GGUFResourceFitSelector`)
- Exception classes end with `Exception` (e.g., `NotFoundException`, `BadRequestException`)
- Mixin classes use `Mixin` suffix or `Base` prefix (e.g., `BaseModelMixin`)

**Types:**
- Enums use `Enum` suffix (e.g., `SourceEnum`, `CategoryEnum`, `BackendEnum`)
- Type variables use descriptive names, often with type hints from `typing` module

## Code Style

**Formatting:**
- **Tool:** Black
- **Line length:** 88 characters (configured in `pyproject.toml`)
- **Target Python version:** 3.10+
- **String normalization:** Disabled (skip-string-normalization = true)
- Migrations excluded from formatting: `*/migrations/*`

**Linting:**
- **Tool:** flake8 with bugbear plugin
- **Max line length:** 88
- **Max complexity:** 10 (15 for pre-commit)
- **Selected rules:** C,E,F,W,B,B950
- **Ignored rules:** E203,E501,W503,E701,E704
- Excluded: `.git`, `__pycache__`, `*.egg-info`, `.venv`, `*/migrations`, `*/generated*`

**Import Organization:**
```python
# 1. Standard library imports
import asyncio
import logging
from typing import List, Optional

# 2. Third-party imports
from fastapi import FastAPI
from pydantic import BaseModel
from sqlmodel import Field

# 3. Internal package imports
from gpustack.api.exceptions import NotFoundException
from gpustack.config.config import Config
from gpustack.schemas.models import Model
```

## Error Handling

**Exception Hierarchy:**
- Base exception: `HTTPException` in `gpustack/api/exceptions.py`
- Specialized exceptions: `NotFoundException`, `BadRequestException`, `ConflictException`
- OpenAI-compatible: `OpenAIAPIException` subclass for API compatibility

**Pattern:**
```python
# Raise specific exceptions with message
raise NotFoundException("Resource not found")
raise BadRequestException("Invalid input parameter")
```

**Exception Factory:**
- Use `http_exception_factory()` to create new exception types
- Pattern: `{Reason}Exception` naming convention
- Status codes align with HTTP semantics

**Try/Except Patterns:**
```python
# Broad exception handling with logging
try:
    result = await operation()
except asyncio.CancelledError:
    # Re-raise cancellation
    raise
except Exception as e:
    logger.error(f"Operation failed: {e}")
    # Handle or re-raise
```

**Async Error Handling:**
- Always catch `asyncio.CancelledError` separately to allow proper task cancellation
- Log exceptions before re-raising when crossing module boundaries

## Logging

**Framework:** Python standard `logging` module

**Pattern:**
```python
import logging

logger = logging.getLogger(__name__)

# Usage
logger.debug("Debug message: %s", value)
logger.info("Info message")
logger.warning("Warning: %s", warning_msg)
logger.error(f"Error occurred: {e}")
```

**Guidelines:**
- One logger per module using `logging.getLogger(__name__)`
- Use f-strings for error messages with exceptions
- Use % formatting for info/debug messages (lazy evaluation)
- Log at module entry points for major operations
- Configuration centralized in `gpustack/logging.py`

## Comments

**When to Comment:**
- Docstrings for all public functions, classes, and modules
- Inline comments for complex business logic
- Comments explaining "why" not "what"

**Docstring Format:**
```python
def function_name(param: str) -> ReturnType:
    """
    Brief description of function.

    :param param: Description of parameter
    :return: Description of return value
    """
```

**Checkpoint Comments:**
- Test files use checkpoint comments to document test intent:
```python
# Checkpoint:
# The model contains custom code but `--trust-remote-code` is not provided.
# This should raise a ValueError with a specific message.
```

## Function Design

**Size:**
- Functions should be focused and under 50 lines when possible
- Complex operations broken into helper methods
- Class methods that implement interfaces may be longer

**Parameters:**
- Use type hints for all parameters
- Default values for optional parameters
- Use `Optional[Type]` for nullable parameters
- `**kwargs` used in factory functions for flexibility

**Return Values:**
- Always use return type annotations
- Return `None` explicitly for optional returns
- Use dataclasses/Pydantic models for complex return structures

**Async Patterns:**
```python
# Mark async functions
async def fetch_data() -> DataType:
    result = await some_async_operation()
    return result

# Async iteration
async for item in async_generator:
    process(item)
```

## Module Design

**Exports:**
- No `__all__` declarations found - modules export all public names
- Internal utilities kept in `utils/` subpackages
- Schemas separated from business logic

**Barrel Files:**
- Limited use of barrel files (no extensive `__init__.py` re-exports)
- Import from specific module paths

**Package Structure:**
```
gpustack/
├── api/           # API exceptions and responses
├── schemas/       # Pydantic/SQLModel schemas
├── routes/        # FastAPI route handlers
├── worker/        # Worker node implementation
├── server/        # Server/controller logic
├── scheduler/     # Scheduling algorithms
├── policies/      # Policy implementations
├── utils/         # Shared utilities
└── config/        # Configuration management
```

## Type Hints

**Required:**
- All function parameters must be typed
- All return values must be typed
- Use `from __future__ import annotations` for forward references when needed

**Common Patterns:**
```python
from typing import List, Optional, Dict, Any

# Optional types
def find_item(id: int) -> Optional[Item]:
    ...

# Collection types
def process_items(items: List[str]) -> Dict[str, Any]:
    ...

# Union types (Python 3.10+ syntax)
def parse_value(value: str | int) -> Result:
    ...
```

## Schema Patterns

**Pydantic/SQLModel Classes:**
```python
class Model(SQLModel, table=True):
    id: int = Field(primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=utcnow)

class GPUSelector(BaseModel):
    gpu_ids: Optional[List[str]] = None
    gpus_per_replica: Optional[int] = None
```

**Enum Definitions:**
```python
class SourceEnum(str, Enum):
    HUGGING_FACE = "huggingface"
    MODEL_SCOPE = "model_scope"
    LOCAL_PATH = "local_path"
```

---

*Convention analysis: 2026-01-31*
