"""Unit tests for EVPNStatusChecker class."""

import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import ConnectAuthError, ConnectError, EVPNStatusChecker, RpcError
from tests.fixtures.evpn_mock_data import EXPECTED_RESULTS, get_mock_xml_response


@pytest.fixture
def checker():
    """Create an EVPNStatusChecker instance for testing."""
    return EVPNStatusChecker(
        host="test-device.local",
        username="testuser",
        password="testpass",
        port=22,
        timeout=30,
    )


@pytest.fixture
def mock_device():
    """Create a mock device object."""
    device = Mock()
    device.connected = True
    return device


class TestEVPNStatusChecker:
    """Test cases for EVPNStatusChecker class."""

    @pytest.mark.unit
    def test_init(self, checker):
        """Test EVPNStatusChecker initialization."""
        assert checker.host == "test-device.local"
        assert checker.username == "testuser"
        assert checker.password == "testpass"
        assert checker.port == 22
        assert checker.timeout == 30
        assert checker.device is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_connect_success(self, checker):
        """Test successful device connection."""
        with patch("main.Device") as mock_device_class:
            mock_device = Mock()
            mock_device_class.return_value = mock_device

            result = await checker.connect()

            assert result is True
            assert checker.device == mock_device
            mock_device.open.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_connect_failure(self, checker):
        """Test failed device connection."""
        with patch("main.Device") as mock_device_class:
            mock_device = Mock()
            # Use a simple Exception that will be caught as a connection error
            mock_device.open.side_effect = Exception("Connection failed")
            mock_device_class.return_value = mock_device

            result = await checker.connect()

            assert result is False
            assert checker.device == mock_device

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_connect_auth_failure(self, checker):
        """Test authentication failure during connection."""
        with patch("main.Device") as mock_device_class:
            mock_device = Mock()
            # Use a simple Exception that will be caught as an auth error
            mock_device.open.side_effect = Exception("Auth failed")
            mock_device_class.return_value = mock_device

            result = await checker.connect()

            assert result is False

    @pytest.mark.unit
    def test_disconnect(self, checker, mock_device):
        """Test device disconnection."""
        checker.device = mock_device

        checker.disconnect()

        mock_device.close.assert_called_once()

    @pytest.mark.unit
    def test_disconnect_no_device(self, checker):
        """Test disconnection when no device is connected."""
        # Should not raise exception
        checker.disconnect()

    @pytest.mark.unit
    def test_get_evpn_route_status_not_connected(self, checker):
        """Test getting EVPN status when not connected."""
        result = checker.get_evpn_route_status()

        assert result == {}

    @pytest.mark.unit
    def test_get_evpn_route_status_healthy(self, checker, mock_device):
        """Test getting EVPN status with all healthy routes."""
        checker.device = mock_device
        mock_response = get_mock_xml_response("healthy")
        mock_device.rpc.get_evpn_ip_prefix_database_information.return_value = (
            mock_response
        )

        result = checker.get_evpn_route_status()

        assert result == EXPECTED_RESULTS["healthy"]

    @pytest.mark.unit
    def test_get_evpn_route_status_rejected(self, checker, mock_device):
        """Test getting EVPN status with some rejected routes."""
        checker.device = mock_device
        mock_response = get_mock_xml_response("rejected")
        mock_device.rpc.get_evpn_ip_prefix_database_information.return_value = (
            mock_response
        )

        result = checker.get_evpn_route_status()

        assert result == EXPECTED_RESULTS["rejected"]

    @pytest.mark.unit
    def test_get_evpn_route_status_empty(self, checker, mock_device):
        """Test getting EVPN status with no routes."""
        checker.device = mock_device
        mock_response = get_mock_xml_response("empty")
        mock_device.rpc.get_evpn_ip_prefix_database_information.return_value = (
            mock_response
        )

        result = checker.get_evpn_route_status()

        assert result == EXPECTED_RESULTS["empty"]

    @pytest.mark.unit
    def test_get_evpn_route_status_mixed(self, checker, mock_device):
        """Test getting EVPN status with mixed route statuses."""
        checker.device = mock_device
        mock_response = get_mock_xml_response("mixed")
        mock_device.rpc.get_evpn_ip_prefix_database_information.return_value = (
            mock_response
        )

        result = checker.get_evpn_route_status()

        assert result == EXPECTED_RESULTS["mixed"]

    @pytest.mark.unit
    def test_get_evpn_route_status_rpc_error(self, checker, mock_device):
        """Test handling RPC error during EVPN status retrieval."""
        checker.device = mock_device
        mock_device.rpc.get_evpn_ip_prefix_database_information.side_effect = RpcError(
            "RPC failed"
        )

        result = checker.get_evpn_route_status()

        assert result == {}

    @pytest.mark.unit
    def test_get_evpn_route_status_exception(self, checker, mock_device):
        """Test handling unexpected exception during EVPN status retrieval."""
        checker.device = mock_device
        mock_device.rpc.get_evpn_ip_prefix_database_information.side_effect = Exception(
            "Unexpected error"
        )

        result = checker.get_evpn_route_status()

        assert result == {}

    @pytest.mark.unit
    def test_restart_routing_not_connected(self, checker):
        """Test restarting routing when not connected."""
        result = checker.restart_routing()

        assert result is False

    @pytest.mark.unit
    def test_restart_routing_success(self, checker, mock_device):
        """Test successful routing restart."""
        checker.device = mock_device

        result = checker.restart_routing()

        assert result is True
        mock_device.rpc.restart_routing_process.assert_called_once()

    @pytest.mark.unit
    def test_restart_routing_rpc_error(self, checker, mock_device):
        """Test handling RPC error during routing restart."""
        checker.device = mock_device
        mock_device.rpc.restart_routing_process.side_effect = RpcError("RPC failed")

        result = checker.restart_routing()

        assert result is False

    @pytest.mark.unit
    def test_restart_routing_exception(self, checker, mock_device):
        """Test handling unexpected exception during routing restart."""
        checker.device = mock_device
        mock_device.rpc.restart_routing_process.side_effect = Exception(
            "Unexpected error"
        )

        result = checker.restart_routing()

        assert result is False

    @pytest.mark.unit
    def test_get_evpn_route_status_no_xpath(self, checker, mock_device):
        """Test handling response without xpath method."""
        checker.device = mock_device
        mock_response = Mock()
        # Remove xpath method to simulate non-lxml response
        if hasattr(mock_response, "xpath"):
            del mock_response.xpath
        mock_device.rpc.get_evpn_ip_prefix_database_information.return_value = (
            mock_response
        )

        result = checker.get_evpn_route_status()

        # Should return empty counts when xpath not available
        expected = {
            "Accepted": 0,
            "Rejected": 0,
            "Pending": 0,
            "Invalid": 0,
            "Unknown": 0,
        }
        assert result == expected

    @pytest.mark.unit
    def test_get_evpn_route_status_malformed_xml(self, checker, mock_device):
        """Test handling malformed XML response."""
        checker.device = mock_device

        # Create mock response with xpath but no matching elements
        mock_response = Mock()
        mock_response.xpath.return_value = []
        mock_device.rpc.get_evpn_ip_prefix_database_information.return_value = (
            mock_response
        )

        result = checker.get_evpn_route_status()

        expected = {
            "Accepted": 0,
            "Rejected": 0,
            "Pending": 0,
            "Invalid": 0,
            "Unknown": 0,
        }
        assert result == expected

    @pytest.mark.unit
    def test_device_not_connected_after_connection_lost(self, checker, mock_device):
        """Test handling when device connection is lost."""
        checker.device = mock_device
        mock_device.connected = False

        result = checker.get_evpn_route_status()

        assert result == {}

    @pytest.mark.unit
    def test_logging_configuration(self, checker):
        """Test that logger is properly configured."""
        assert checker.logger.name == f"evpn.{checker.host}"
