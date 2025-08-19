"""Pytest configuration and shared fixtures."""

import os
import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (fast, no external dependencies)"
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (slow, may require external resources)",
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names."""
    for item in items:
        # Add 'unit' marker to tests that don't have 'integration' marker
        if "integration" not in [marker.name for marker in item.iter_markers()]:
            if not any(marker.name == "unit" for marker in item.iter_markers()):
                item.add_marker(pytest.mark.unit)


@pytest.fixture(scope="session")
def test_data_dir():
    """Provide path to test data directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sample_hosts_file(test_data_dir):
    """Provide path to sample hosts file."""
    return test_data_dir / "test_hosts.yaml"


@pytest.fixture(scope="session")
def sample_rules_file(test_data_dir):
    """Provide path to sample rules file."""
    return test_data_dir / "rules.yaml"


@pytest.fixture
def mock_junos_device():
    """Create a mock Juniper device for testing."""
    from unittest.mock import Mock

    device = Mock()
    device.connected = True
    device.host = "test-device"

    # Mock RPC methods
    device.rpc = Mock()
    device.rpc.get_evpn_ip_prefix_database_information = Mock()
    device.rpc.restart_routing_process = Mock()

    # Mock connection methods
    device.open = Mock()
    device.close = Mock()

    return device


@pytest.fixture
def sample_evpn_status():
    """Provide sample EVPN status data."""
    return {"Accepted": 10, "Rejected": 2, "Pending": 1, "Invalid": 0, "Unknown": 0}


@pytest.fixture
def sample_device_config():
    """Provide sample device configuration."""
    return {
        "host": "192.168.1.100",
        "username": "testuser",
        "password": "testpass",
        "port": 22,
        "timeout": 30,
        "tags": ["test", "qfx"],
    }


@pytest.fixture(autouse=True)
def setup_test_logging():
    """Setup logging for tests."""
    import logging

    # Configure logging for tests
    logging.basicConfig(
        level=logging.DEBUG, format="%(name)s - %(levelname)s - %(message)s"
    )

    # Suppress some noisy loggers during tests
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    yield

    # Cleanup after tests
    logging.getLogger().handlers.clear()


@pytest.fixture
def temp_hosts_file():
    """Create a temporary hosts file for testing."""
    import tempfile

    import yaml

    test_config = {
        "defaults": {
            "port": 22,
            "timeout": 30,
            "admin_user": "testuser",
            "user_password": {"testuser": "testpass", "root": "rootpass"},
        },
        "host_groups": {
            "test_devices": [
                {"host": "192.168.1.100", "tags": ["test"]},
                {"host": "192.168.1.101", "tags": ["test"]},
            ]
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(test_config, f)
        temp_file = f.name

    yield temp_file

    # Cleanup
    os.unlink(temp_file)


@pytest.fixture
def skip_integration():
    """Skip integration tests unless explicitly enabled."""
    if not os.getenv("INTEGRATION_TESTS"):
        pytest.skip("Integration tests not enabled. Set INTEGRATION_TESTS=1 to run.")


# Custom assertions
def assert_evpn_status_valid(status_dict):
    """Assert that EVPN status dictionary has valid structure."""
    required_keys = ["Accepted", "Rejected", "Pending", "Invalid", "Unknown"]

    assert isinstance(status_dict, dict), "Status must be a dictionary"

    for key in required_keys:
        assert key in status_dict, f"Missing required key: {key}"
        assert isinstance(status_dict[key], int), f"Value for {key} must be integer"
        assert status_dict[key] >= 0, f"Value for {key} must be non-negative"


def assert_device_result_valid(result_dict):
    """Assert that device result dictionary has valid structure."""
    required_keys = [
        "host",
        "connected",
        "status_counts",
        "restart_attempted",
        "restart_success",
    ]

    assert isinstance(result_dict, dict), "Result must be a dictionary"

    for key in required_keys:
        assert key in result_dict, f"Missing required key: {key}"

    assert isinstance(result_dict["host"], str), "Host must be string"
    assert isinstance(result_dict["connected"], bool), "Connected must be boolean"
    assert isinstance(result_dict["status_counts"], dict), "Status counts must be dict"
    assert isinstance(
        result_dict["restart_attempted"], bool
    ), "Restart attempted must be boolean"
    assert isinstance(
        result_dict["restart_success"], bool
    ), "Restart success must be boolean"

    # If connected, status_counts should have valid structure
    if result_dict["connected"]:
        assert_evpn_status_valid(result_dict["status_counts"])


# Add custom assertions to pytest namespace
pytest.assert_evpn_status_valid = assert_evpn_status_valid
pytest.assert_device_result_valid = assert_device_result_valid
