# Testing Patterns

**Analysis Date:** 2026-01-31

## Test Framework

**Runner:**
- **Framework:** pytest 8.2+
- **Async support:** pytest-asyncio 0.23.7+
- **Config:** `pytest.ini` in project root

**Configuration (`pytest.ini`):**
```ini
[pytest]
markers =
    unit: mark a test as a unit test.
```

**Run Commands:**
```bash
# Run all tests
uv run pytest

# Run with markers
pytest -m unit

# Run specific test file
pytest tests/utils/test_command.py

# Run via make
make test
```

## Test File Organization

**Location:**
- Tests in `tests/` directory mirroring source structure
- Source: `gpustack/worker/backends/vllm.py` → Test: `tests/worker/backends/test_backend.py`
- One test file per module or feature area

**Naming:**
- Test files: `test_{module}.py` (e.g., `test_scheduler.py`, `test_exceptions.py`)
- Test functions: `test_{description}` (e.g., `test_find_parameter()`, `test_evaluate_pretrained_config()`)

**Structure:**
```
tests/
├── conftest.py                    # Test configuration and fixtures
├── api/
│   └── test_exceptions.py
├── controller/
│   ├── test_controller.py
│   └── test_provisioning.py
├── fixtures/
│   ├── workers/
│   │   ├── fixtures.py            # Worker factory functions
│   │   └── *.json                 # Worker fixture data
│   └── estimates/
│       ├── fixtures.py            # Resource estimate fixtures
│       └── *.json                 # Estimate fixture data
├── policies/
│   ├── candidate_selectors/
│   │   ├── gguf/
│   │   │   └── test_gguf_resource_fit_selector.py
│   │   └── vllm/
│   │       └── test_vllm_resource_fit_selector.py
│   └── worker_filters/
│       └── test_backend_framework_filter.py
├── scheduler/
│   └── test_scheduler.py
├── server/
│   └── test_catalog.py
├── utils/
│   ├── test_command.py
│   └── test_gpu.py
└── worker/
    └── test_logs.py
```

## Test Structure

**Basic Test Function:**
```python
def test_simple_case():
    result = function_under_test()
    assert result == expected_value
```

**Parametrized Tests:**
```python
@pytest.mark.parametrize(
    "name, given, expected",
    [
        ("valid case", {"code": 404, "reason": "NotFound"}, True),
        ("invalid type key", {"code": 404, "type": "NotFound"}, False),
    ],
)
def test_error_response_model_validate(name, given, expected):
    try:
        result = ErrorResponse.model_validate(given)
        assert expected is True, f"Case {name} expected validation to fail"
    except Exception as e:
        assert expected is False, f"Case {name} expected validation to succeed: {e}"
```

**Async Tests:**
```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await async_function()
    assert result.status == "success"
```

**Exception Testing:**
```python
@pytest.mark.asyncio
async def test_evaluate_pretrained_config(config, case_name, model, expect_error):
    if expect_error:
        with pytest.raises(expect_error, match=expect_error_match):
            await evaluate_pretrained_config(model)
    else:
        await evaluate_pretrained_config(model)
        assert model.categories == expected_categories
```

**Unit Marker:**
```python
@pytest.mark.unit
def test_parse_gpu_id():
    # Fast, isolated unit test
    assert parse_gpu_id("worker:cuda:0") == expected
```

## Mocking

**Framework:** `unittest.mock` (standard library)

**Patch Decorator Pattern:**
```python
from unittest.mock import patch, AsyncMock

@patch('gpustack.schemas.models.ModelInstance.all_by_field', return_value=mis)
@patch('gpustack.schemas.workers.Worker.all', return_value=workers)
async def test_with_patches(mock_workers, mock_instances):
    result = await function_under_test()
    assert result == expected
```

**Context Manager Pattern:**
```python
with (
    patch(
        'gpustack.schemas.models.ModelInstance.all_by_field',
        return_value=mis,
    ),
    patch(
        'gpustack.schemas.workers.Worker.all',
        return_value=workers,
    ),
    patch(
        'gpustack.policies.scorers.placement_scorer.async_session',
        return_value=AsyncMock(),
    ),
):
    candidates = await find_scale_down_candidates(mis, m)
    assert len(candidates) == expected_count
```

**Monkeypatch for Simple Cases:**
```python
def test_is_command_available_true(monkeypatch):
    monkeypatch.setattr(shutil, 'which', lambda name: f'/usr/bin/{name}')
    assert is_command_available('foo') is True
```

**AsyncMock for Async Functions:**
```python
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_async_mock():
    mock_service = AsyncMock()
    mock_service.fetch.return_value = mock_data
    result = await evaluate_model_metadata(config, mock_service, model, [])
```

**What to Mock:**
- Database operations (`ModelInstance.all()`, `Worker.all()`)
- External HTTP/API calls
- File system operations
- Async sessions and connections

**What NOT to Mock:**
- Pure functions with no side effects
- Simple data transformations
- Internal utility functions being tested

## Fixtures and Factories

**Test Data Factories (`tests/utils/model.py`):**
```python
def new_model(
    id,
    name,
    replicas=1,
    huggingface_repo_id=None,
    **kwargs,
) -> Model:
    return Model(
        id=id,
        name=name,
        replicas=replicas,
        huggingface_repo_id=huggingface_repo_id,
        **kwargs,
    )

def new_model_instance(
    id,
    name,
    model_id,
    worker_id=None,
    state=ModelInstanceStateEnum.PENDING,
    **kwargs,
) -> ModelInstance:
    return ModelInstance(...)
```

**Worker Fixtures (`tests/fixtures/workers/fixtures.py`):**
```python
def linux_nvidia_19_4090_24gx2(reserved=False, return_device=None, callback=None):
    """Return a worker with dual RTX 4090 GPUs."""
    worker = load_from_file("linux_nvidia_19_4090_24gx2.json", reserved=reserved)
    if callback:
        callback(worker)
    return worker

def linux_cpu_1(reserved=False):
    return load_from_file("linux_cpu_1.json", reserved=reserved)
```

**Resource Estimate Fixtures (`tests/fixtures/estimates/fixtures.py`):**
```python
def llama3_8b_disable_offload():
    return load_estimate_from_file("llama3_8b_disable_offload.json")

def deepseek_r1_q4_k_m_partial_offload():
    return load_estimate_from_file("deepseek_r1_q4_k_m_partial_offload.json")
```

**Fixture Data Files:**
- JSON files store complex object states
- Loaded by factory functions
- Located in `tests/fixtures/{category}/`

## Coverage

**Tool:** coverage (configured in pyproject.toml dependency group)

**Dependencies:**
```toml
[dependency-groups]
dev = [
    "coverage[toml]>=7.5.1",
    ...
]
```

**View Coverage:**
```bash
# Run with coverage
uv run pytest --cov=gpustack

# Generate report
uv run pytest --cov=gpustack --cov-report=html
```

**Coverage Requirements:**
- No enforced minimum coverage threshold detected
- Relies on manual review and CI checks

## Test Types

**Unit Tests:**
- Marked with `@pytest.mark.unit`
- Fast, isolated, no I/O
- Test single functions or methods
- Located in `tests/utils/`, `tests/api/`

**Integration Tests:**
- Use `@pytest.mark.asyncio`
- Test component interactions
- May use real fixtures or mocked services
- Example: `tests/scheduler/test_scheduler.py`

**Policy Tests:**
- Test scheduling and filtering logic
- Use worker fixtures for various hardware configs
- Test various GPU types: NVIDIA, AMD ROCm, Apple Metal, Huawei Ascend

**Skip Conditions:**
```python
@pytest.mark.skipif(
    not os.getenv("GPUSTACK_MODEL_CATALOG_TOKEN"),
    reason="GPUSTACK_MODEL_CATALOG_TOKEN is not set",
)
def test_model_catalog():
    ...
```

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_async_with_error_handling():
    try:
        result = await async_function()
        assert result.success
    except AssertionError as e:
        raise AssertionError(f"Test failed: {e}") from e
```

**Error Testing:**
```python
@pytest.mark.parametrize(
    "case_name, model, expect_error, expect_error_match",
    [
        ("unsupported_architecture", model, ValueError, "Unsupported architecture:"),
    ],
)
@pytest.mark.asyncio
async def test_error_cases(config, case_name, model, expect_error, expect_error_match):
    with pytest.raises(expect_error, match=expect_error_match):
        await evaluate_pretrained_config(model)
```

**Complex Assertions:**
```python
def compare_candidates(candidates: List[ModelInstanceScore], expected_candidates):
    for i, expected in enumerate(expected_candidates):
        candidate = candidates[i]
        instance = candidate.model_instance

        if "worker_id" in expected:
            assert instance.worker_id == expected["worker_id"]

        if "score" in expected:
            assert str(candidate.score)[:5] == str(expected["score"])[:5]
```

**Test Configuration Setup (`tests/conftest.py`):**
```python
"""
Ensure the local gpustack package is imported before any installed ones.
"""
import os
import sys

# Prepend the repository root to sys.path so that the local gpustack module is used
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
```

## Testing Utilities

**Shared Helpers (`tests/utils/`):**
- `model.py`: Factory functions for Model/ModelInstance creation
- `scheduler.py`: Comparison helpers for scheduler tests

**Assert Patterns:**
- Use f-strings in assertion messages for debugging
- Slice floats for approximate comparison: `str(score)[:5]`
- Test for exception messages with `match` parameter

---

*Testing analysis: 2026-01-31*
