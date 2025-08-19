"""Unit tests for EVPNManager class."""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

from main import EVPNManager, EVPNStatusChecker


@pytest.fixture
def test_hosts_file():
    """Create a temporary test hosts file."""
    test_config = {
        "defaults": {
            "port": 22,
            "timeout": 30,
            "admin_user": "testuser",
            "user_password": {"testuser": "testpass", "root": "rootpass"},
        },
        "host_groups": {
            "test_devices": [
                {"host": "192.168.1.100", "tags": ["test", "qfx"]},
                {"host": "192.168.1.101", "tags": ["test", "qfx"]},
                {"host": "192.168.1.102", "username": "root", "tags": ["test", "qfx"]},
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
def invalid_hosts_file():
    """Create a temporary invalid hosts file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("invalid: yaml: content: [")
        temp_file = f.name

    yield temp_file

    # Cleanup
    os.unlink(temp_file)


@pytest.fixture
def manager(test_hosts_file):
    """Create an EVPNManager instance for testing."""
    return EVPNManager(test_hosts_file, "data/rules.yaml", fix_mode=False)


@pytest.fixture
def fix_manager(test_hosts_file):
    """Create an EVPNManager instance with fix mode enabled."""
    return EVPNManager(test_hosts_file, "data/rules.yaml", fix_mode=True)


class TestEVPNManager:
    """Test cases for EVPNManager class."""

    @pytest.mark.unit
    def test_init(self, test_hosts_file):
        """Test EVPNManager initialization."""
        manager = EVPNManager(test_hosts_file, "data/rules.yaml", fix_mode=True)

        assert manager.hosts_file == Path(test_hosts_file)
        assert manager.rules_file == Path("data/rules.yaml")
        assert manager.fix_mode is True
        assert manager.devices == []
        assert manager.logger.name == "evpn.manager"

    @pytest.mark.unit
    def test_init_default_fix_mode(self, test_hosts_file):
        """Test EVPNManager initialization with default fix mode."""
        manager = EVPNManager(test_hosts_file, "data/rules.yaml")

        assert manager.fix_mode is False

    @pytest.mark.unit
    def test_load_hosts_success(self, manager):
        """Test successful host configuration loading."""
        devices = manager.load_hosts()

        assert len(devices) == 3

        # Check first device (using defaults)
        device1 = devices[0]
        assert device1["host"] == "192.168.1.100"
        assert device1["username"] == "testuser"
        assert device1["password"] == "testpass"
        assert device1["port"] == 22
        assert device1["timeout"] == 30
        assert device1["tags"] == ["test", "qfx"]

        # Check device with username override
        device3 = devices[2]
        assert device3["host"] == "192.168.1.102"
        assert device3["username"] == "root"
        assert device3["password"] == "rootpass"

    @pytest.mark.unit
    def test_load_hosts_file_not_found(self):
        """Test loading hosts from non-existent file."""
        manager = EVPNManager("/nonexistent/file.yaml", "data/rules.yaml")

        devices = manager.load_hosts()

        assert devices == []

    @pytest.mark.unit
    def test_load_hosts_invalid_yaml(self, invalid_hosts_file):
        """Test loading hosts from invalid YAML file."""
        manager = EVPNManager(invalid_hosts_file, "data/rules.yaml")

        devices = manager.load_hosts()

        assert devices == []

    @pytest.mark.unit
    def test_load_hosts_missing_password(self, test_hosts_file):
        """Test loading hosts when password is missing."""
        # Create config without passwords
        config = {
            "defaults": {"admin_user": "testuser"},
            "host_groups": {"test_devices": [{"host": "192.168.1.100"}]},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            temp_file = f.name

        try:
            manager = EVPNManager(temp_file, "data/rules.yaml")
            devices = manager.load_hosts()

            # Should skip devices without passwords
            assert devices == []
        finally:
            os.unlink(temp_file)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_device_connection_failure(self, manager):
        """Test processing device when connection fails."""
        device_config = {
            "host": "192.168.1.100",
            "name": "test-device",
            "username": "testuser",
            "password": "testpass",
            "port": 22,
            "timeout": 30,
        }

        with patch.object(
            EVPNStatusChecker, "connect", new_callable=AsyncMock
        ) as mock_connect:
            mock_connect.return_value = False

            result = await manager.process_device(device_config)

            expected = {
                "host": "192.168.1.100",
                "name": "test-device",
                "connected": False,
                "status_counts": {},
                "restart_attempted": False,
                "restart_success": False,
            }
            assert result == expected

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_device_success_no_rejected(self, manager):
        """Test processing device successfully with no rejected routes."""
        device_config = {
            "host": "192.168.1.100",
            "name": "test-device",
            "username": "testuser",
            "password": "testpass",
            "port": 22,
            "timeout": 30,
        }

        mock_status = {
            "Accepted": 10,
            "Rejected": 0,
            "Pending": 0,
            "Invalid": 0,
            "Unknown": 0,
        }

        with (
            patch.object(
                EVPNStatusChecker, "connect", new_callable=AsyncMock
            ) as mock_connect,
            patch.object(
                EVPNStatusChecker, "get_evpn_route_status"
            ) as mock_status_method,
            patch.object(EVPNStatusChecker, "disconnect"),
        ):

            mock_connect.return_value = True
            mock_status_method.return_value = mock_status

            result = await manager.process_device(device_config)

            expected = {
                "host": "192.168.1.100",
                "name": "test-device",
                "connected": True,
                "status_counts": mock_status,
                "restart_attempted": False,
                "restart_success": False,
            }
            assert result == expected

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_device_with_rejected_routes_no_fix(self, manager):
        """Test processing device with rejected routes but no fix mode."""
        device_config = {
            "host": "192.168.1.100",
            "username": "testuser",
            "password": "testpass",
            "port": 22,
            "timeout": 30,
        }

        mock_status = {
            "Accepted": 8,
            "Rejected": 2,
            "Pending": 0,
            "Invalid": 0,
            "Unknown": 0,
        }

        with (
            patch.object(
                EVPNStatusChecker, "connect", new_callable=AsyncMock
            ) as mock_connect,
            patch.object(
                EVPNStatusChecker, "get_evpn_route_status"
            ) as mock_status_method,
            patch.object(EVPNStatusChecker, "disconnect"),
        ):

            mock_connect.return_value = True
            mock_status_method.return_value = mock_status

            result = await manager.process_device(device_config)

            # Should not attempt restart since fix_mode is False
            expected = {
                "host": "192.168.1.100",
                "name": "192.168.1.100",
                "connected": True,
                "status_counts": mock_status,
                "restart_attempted": False,
                "restart_success": False,
            }
            assert result == expected

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_device_with_rejected_routes_fix_mode(self, fix_manager):
        """Test processing device with rejected routes in fix mode."""
        device_config = {
            "host": "192.168.1.100",
            "name": "test-device",
            "username": "testuser",
            "password": "testpass",
            "port": 22,
            "timeout": 30,
        }

        mock_status = {
            "Accepted": 8,
            "Rejected": 2,
            "Pending": 0,
            "Invalid": 0,
            "Unknown": 0,
        }

        with (
            patch.object(
                EVPNStatusChecker, "connect", new_callable=AsyncMock
            ) as mock_connect,
            patch.object(
                EVPNStatusChecker, "get_evpn_route_status"
            ) as mock_status_method,
            patch.object(EVPNStatusChecker, "restart_routing") as mock_restart,
            patch.object(EVPNStatusChecker, "disconnect"),
        ):

            mock_connect.return_value = True
            mock_status_method.return_value = mock_status
            mock_restart.return_value = True

            result = await fix_manager.process_device(device_config)

            expected = {
                "host": "192.168.1.100",
                "name": "test-device",
                "connected": True,
                "status_counts": mock_status,
                "restart_attempted": True,
                "restart_success": True,
            }
            assert result == expected
            mock_restart.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_device_restart_failure(self, fix_manager):
        """Test processing device when restart fails."""
        device_config = {
            "host": "192.168.1.100",
            "name": "test-device",
            "username": "testuser",
            "password": "testpass",
            "port": 22,
            "timeout": 30,
        }

        mock_status = {
            "Accepted": 8,
            "Rejected": 2,
            "Pending": 0,
            "Invalid": 0,
            "Unknown": 0,
        }

        with (
            patch.object(
                EVPNStatusChecker, "connect", new_callable=AsyncMock
            ) as mock_connect,
            patch.object(
                EVPNStatusChecker, "get_evpn_route_status"
            ) as mock_status_method,
            patch.object(EVPNStatusChecker, "restart_routing") as mock_restart,
            patch.object(EVPNStatusChecker, "disconnect"),
        ):

            mock_connect.return_value = True
            mock_status_method.return_value = mock_status
            mock_restart.return_value = False  # Restart fails

            result = await fix_manager.process_device(device_config)

            expected = {
                "host": "192.168.1.100",
                "name": "test-device",
                "connected": True,
                "status_counts": mock_status,
                "restart_attempted": True,
                "restart_success": False,
            }
            assert result == expected

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_run_no_devices(self, manager):
        """Test running with no devices loaded."""
        with patch.object(manager, "load_hosts") as mock_load:
            mock_load.return_value = []

            await manager.run()

            # Should exit early when no devices loaded

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_run_with_devices(self, manager, capsys):
        """Test running with multiple devices."""
        # Mock the load_hosts and process_device methods
        mock_devices = [
            {
                "host": "192.168.1.100",
                "username": "testuser",
                "password": "testpass",
                "port": 22,
                "timeout": 30,
                "tags": ["test"],
            },
            {
                "host": "192.168.1.101",
                "username": "testuser",
                "password": "testpass",
                "port": 22,
                "timeout": 30,
                "tags": ["test"],
            },
        ]

        mock_results = [
            {
                "host": "192.168.1.100",
                "name": "192.168.1.100",
                "connected": True,
                "status_counts": {
                    "Accepted": 10,
                    "Rejected": 0,
                    "Pending": 0,
                    "Invalid": 0,
                    "Unknown": 0,
                },
                "restart_attempted": False,
                "restart_success": False,
            },
            {
                "host": "192.168.1.101",
                "name": "192.168.1.101",
                "connected": True,
                "status_counts": {
                    "Accepted": 5,
                    "Rejected": 2,
                    "Pending": 1,
                    "Invalid": 0,
                    "Unknown": 0,
                },
                "restart_attempted": False,
                "restart_success": False,
            },
        ]

        with (
            patch.object(manager, "load_hosts") as mock_load,
            patch.object(
                manager, "process_device", new_callable=AsyncMock
            ) as mock_process,
        ):

            mock_load.return_value = mock_devices
            mock_process.side_effect = mock_results

            await manager.run()

            # Check that process_device was called for each device
            assert mock_process.call_count == 2

            # Check output
            captured = capsys.readouterr()
            assert "EVPN Route Status Summary:" in captured.out
            assert "192.168.1.100" in captured.out
            assert "192.168.1.101" in captured.out
            assert "Accepted: 15, Rejected: 2" in captured.out  # Total summary

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_run_with_connection_failures(self, manager, capsys):
        """Test running with some connection failures."""
        mock_devices = [
            {
                "host": "192.168.1.100",
                "username": "testuser",
                "password": "testpass",
                "port": 22,
                "timeout": 30,
                "tags": ["test"],
            }
        ]

        mock_results = [
            {
                "host": "192.168.1.100",
                "name": "192.168.1.100",
                "connected": False,
                "status_counts": {},
                "restart_attempted": False,
                "restart_success": False,
            }
        ]

        with (
            patch.object(manager, "load_hosts") as mock_load,
            patch.object(
                manager, "process_device", new_callable=AsyncMock
            ) as mock_process,
        ):

            mock_load.return_value = mock_devices
            mock_process.side_effect = mock_results

            await manager.run()

            captured = capsys.readouterr()
            assert "CONNECTION FAILED" in captured.out

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_run_with_exceptions(self, manager, capsys):
        """Test running when process_device raises exceptions."""
        mock_devices = [
            {
                "host": "192.168.1.100",
                "username": "testuser",
                "password": "testpass",
                "port": 22,
                "timeout": 30,
                "tags": ["test"],
            }
        ]

        with (
            patch.object(manager, "load_hosts") as mock_load,
            patch.object(
                manager, "process_device", new_callable=AsyncMock
            ) as mock_process,
        ):

            mock_load.return_value = mock_devices
            mock_process.side_effect = [Exception("Test exception")]

            await manager.run()

            captured = capsys.readouterr()
            assert "Error processing device: Test exception" in captured.out

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_run_fix_mode_recommendations(self, fix_manager, capsys):
        """Test output recommendations in fix mode."""
        mock_devices = [
            {
                "host": "192.168.1.100",
                "username": "testuser",
                "password": "testpass",
                "port": 22,
                "timeout": 30,
                "tags": ["test"],
            }
        ]

        mock_results = [
            {
                "host": "192.168.1.100",
                "name": "192.168.1.100",
                "connected": True,
                "status_counts": {
                    "Accepted": 5,
                    "Rejected": 2,
                    "Pending": 0,
                    "Invalid": 0,
                    "Unknown": 0,
                },
                "restart_attempted": True,
                "restart_success": True,
            }
        ]

        with (
            patch.object(fix_manager, "load_hosts") as mock_load,
            patch.object(
                fix_manager, "process_device", new_callable=AsyncMock
            ) as mock_process,
        ):

            mock_load.return_value = mock_devices
            mock_process.side_effect = mock_results

            await fix_manager.run()

            captured = capsys.readouterr()
            assert "Devices with rejected routes: 1" in captured.out
            assert "2 rejected routes" in captured.out
            assert "✅ Restart: SUCCESS" in captured.out

    @pytest.mark.unit
    def test_load_hosts_empty_config(self, test_hosts_file):
        """Test loading empty host configuration."""
        empty_config = {}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(empty_config, f)
            temp_file = f.name

        try:
            manager = EVPNManager(temp_file, "data/rules.yaml")
            devices = manager.load_hosts()

            assert devices == []
        finally:
            os.unlink(temp_file)
