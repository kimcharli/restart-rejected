# Testing Guide

This directory contains comprehensive tests for the restart-rejected EVPN management tool.

## Test Structure

```
tests/
├── __init__.py              # Test package initialization
├── conftest.py              # Pytest configuration and shared fixtures
├── fixtures/                # Test data and mock files
│   ├── evpn_mock_data.py   # Mock EVPN XML responses
│   ├── test_hosts.yaml     # Test device inventory
│   ├── hosts.yaml          # Copy of production hosts file
│   └── rules.yaml          # Copy of production rules file
├── test_evpn_status_checker.py  # Unit tests for EVPNStatusChecker
├── test_evpn_manager.py     # Unit tests for EVPNManager
├── test_integration.py      # Integration tests (live devices)
├── test_cli.py              # CLI argument and interface tests
└── README.md               # This file
```

## Test Categories

### Unit Tests (`@pytest.mark.unit`)
- **Fast execution** (< 1 second per test)
- **No external dependencies** (no network, no live devices)
- **Mock all external calls** (junos-eznc, network connections)
- **Test individual components** in isolation

**Examples:**
- EVPNStatusChecker connection handling
- XML parsing logic
- Configuration file loading
- Error handling scenarios

### Integration Tests (`@pytest.mark.integration`)
- **Slower execution** (may take several seconds)
- **May require external resources** (test devices, network access)
- **Test end-to-end workflows**
- **Validate real device interactions**

**Examples:**
- Live device connection tests (bl03)
- Full workflow testing
- CLI subprocess execution
- File system permissions

## Running Tests

### Quick Test Run (Unit Tests Only)
```bash
# Run unit tests only (fast)
uv run pytest -m unit

# Run with verbose output
uv run pytest -v -m unit

# Run specific test file
uv run pytest tests/test_evpn_status_checker.py -v
```

### Full Test Suite
```bash
# Run all tests (unit + integration)
INTEGRATION_TESTS=1 uv run pytest

# Run with coverage report
WITH_COVERAGE=1 uv run pytest --cov=main --cov-report=html

# Use the test runner script
python run_tests.py
```

### Quality Checks
```bash
# Run linting
uv run ruff check main.py tests/

# Run type checking
uv run mypy main.py

# Run code formatting check
uv run black --check main.py tests/

# Auto-fix issues
uv run ruff check --fix main.py tests/
uv run black main.py tests/
```

## Test Configuration

### Environment Variables
- `INTEGRATION_TESTS=1` - Enable integration tests
- `WITH_COVERAGE=1` - Enable coverage reporting
- `DEBUG=1` - Enable debug logging during tests

### Pytest Markers
- `@pytest.mark.unit` - Unit tests (default)
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.asyncio` - Async test functions

### Test Fixtures

**Device Configuration:**
- `sample_device_config` - Standard device configuration
- `temp_hosts_file` - Temporary YAML hosts file
- `mock_junos_device` - Mock Juniper device object

**EVPN Data:**
- `sample_evpn_status` - Sample status counts
- `test_data_dir` - Path to test fixtures
- `skip_integration` - Skip integration tests conditionally

## Mock Data

### EVPN XML Responses
The `evpn_mock_data.py` provides various mock EVPN responses:

- `healthy` - All routes accepted
- `rejected` - Some routes rejected
- `empty` - No routes found
- `mixed` - All status types present

### Test Scenarios
Each mock response includes expected results for validation:

```python
EXPECTED_RESULTS = {
    'healthy': {'Accepted': 3, 'Rejected': 0, ...},
    'rejected': {'Accepted': 1, 'Rejected': 2, ...},
    ...
}
```

## Writing New Tests

### Unit Test Template
```python
@pytest.mark.unit
def test_my_function(self, fixture):
    """Test description."""
    # Arrange
    input_data = "test_input"
    
    # Act
    result = my_function(input_data)
    
    # Assert
    assert result == expected_value
```

### Integration Test Template
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_integration(self, skip_integration):
    """Test description."""
    # This automatically skips unless INTEGRATION_TESTS=1
    
    # Test with live resources
    result = await some_async_operation()
    assert result is not None
```

### Mock Usage
```python
@pytest.mark.unit
def test_with_mock(self, mock_junos_device):
    """Test with mocked device."""
    # Configure mock behavior
    mock_junos_device.rpc.some_method.return_value = expected_response
    
    # Test your code
    result = code_under_test(mock_junos_device)
    
    # Verify mock was called
    mock_junos_device.rpc.some_method.assert_called_once()
```

## Test Data Management

### Fixture Files
- Keep test data in `tests/fixtures/`
- Use YAML for configuration files
- Use Python modules for complex mock data

### Temporary Files
- Use `tempfile` for temporary test files
- Always clean up in fixture teardown
- Use `@pytest.fixture` with proper scope

### Mock Responses
- Create realistic XML responses
- Include edge cases and error conditions
- Validate mock data structure

## Continuous Integration

The test suite is designed to run in CI environments:

1. **Install dependencies**: `uv sync`
2. **Run linting**: `uv run ruff check`
3. **Run type checking**: `uv run mypy`
4. **Run unit tests**: `uv run pytest -m unit`
5. **Run integration tests**: `INTEGRATION_TESTS=1 uv run pytest -m integration`

## Debugging Tests

### Verbose Output
```bash
# Show detailed test output
uv run pytest -v -s

# Show full tracebacks
uv run pytest --tb=long

# Run single test with debugging
uv run pytest tests/test_file.py::TestClass::test_method -v -s
```

### Logging in Tests
```python
import logging

def test_with_logging(caplog):
    """Test with log capture."""
    logger = logging.getLogger("test")
    logger.info("Test message")
    
    assert "Test message" in caplog.text
```

### Debugging Async Tests
```python
@pytest.mark.asyncio
async def test_async_debug():
    """Debug async test."""
    import asyncio
    
    # Add debug prints
    print("Starting async operation")
    result = await async_function()
    print(f"Result: {result}")
```

## Performance Considerations

- Unit tests should complete in < 1 second each
- Integration tests should complete in < 30 seconds each
- Use `pytest-benchmark` for performance regression testing
- Mock expensive operations (network, file I/O)

## Coverage Goals

- **Unit tests**: 90%+ code coverage
- **Integration tests**: Focus on critical paths
- **Combined coverage**: 85%+ overall

Generate coverage reports:
```bash
uv run pytest --cov=main --cov-report=html --cov-report=term-missing
open htmlcov/index.html  # View HTML report
```