"""Integration tests for restart-rejected EVPN management tool."""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import EVPNManager, EVPNStatusChecker


class TestIntegration:
    """Integration test cases."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_live_device_connection(self):
        """Test connection to live device (bl03)."""
        # Skip if not in test environment
        if not os.getenv("INTEGRATION_TESTS"):
            pytest.skip("Integration tests not enabled. Set INTEGRATION_TESTS=1")

        checker = EVPNStatusChecker(
            host="10.85.192.16", username="labroot", password="lab123", timeout=30
        )

        try:
            connected = await checker.connect()
            if connected:
                status = checker.get_evpn_route_status()

                # Verify we got some kind of response
                assert isinstance(status, dict)

                # Check expected status keys exist
                expected_keys = [
                    "Accepted",
                    "Rejected",
                    "Pending",
                    "Invalid",
                    "Unknown",
                ]
                for key in expected_keys:
                    assert key in status

                # Verify total routes > 0 (based on README test results)
                total_routes = sum(status.values())
                assert total_routes > 0, f"Expected routes but got: {status}"

            else:
                pytest.skip("Could not connect to test device")

        finally:
            checker.disconnect()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_workflow_with_test_hosts(self):
        """Test full workflow using test hosts file."""
        # Skip if not in test environment
        if not os.getenv("INTEGRATION_TESTS"):
            pytest.skip("Integration tests not enabled. Set INTEGRATION_TESTS=1")

        test_hosts_file = Path(__file__).parent / "fixtures" / "hosts.yaml"

        if not test_hosts_file.exists():
            pytest.skip("Test hosts file not found")

        manager = EVPNManager(str(test_hosts_file), "data/rules.yaml", fix_mode=False)

        # Load and verify hosts
        devices = manager.load_hosts()
        assert len(devices) > 0, "No devices loaded from test hosts file"

        # Run the manager (this will attempt connections)
        await manager.run()

    @pytest.mark.integration
    def test_cli_argument_parsing(self):
        """Test CLI argument parsing with various combinations."""
        import subprocess
        import tempfile

        # Create a minimal test hosts file
        test_config = """
defaults:
  admin_user: testuser
  user_password:
    testuser: testpass
host_groups:
  test:
    - host: 192.168.1.1
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(test_config)
            hosts_file = f.name

        try:
            # Test help
            result = subprocess.run(
                [sys.executable, "main.py", "--help"], capture_output=True, text=True
            )
            assert result.returncode == 0
            assert "EVPN Route Status Manager" in result.stdout

            # Test missing hosts file
            result = subprocess.run(
                [sys.executable, "main.py", "--hosts-file", "/nonexistent/file.yaml"],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 1
            assert "not found" in result.stdout

            # Test invalid log level
            result = subprocess.run(
                [
                    sys.executable,
                    "main.py",
                    "--hosts-file",
                    hosts_file,
                    "--log-level",
                    "INVALID",
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 2  # argparse error

        finally:
            os.unlink(hosts_file)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_device_timeout_handling(self):
        """Test handling of device connection timeouts."""
        # Use a non-routable IP to trigger timeout
        checker = EVPNStatusChecker(
            host="192.0.2.1",  # RFC3330 test address
            username="testuser",
            password="testpass",
            timeout=1,  # Very short timeout
        )

        connected = await checker.connect()
        assert connected is False

    @pytest.mark.integration
    def test_yaml_file_validation(self):
        """Test validation of various YAML file formats."""
        test_files_dir = Path(__file__).parent / "fixtures"

        # Test valid hosts file
        valid_file = test_files_dir / "test_hosts.yaml"
        if valid_file.exists():
            manager = EVPNManager(str(valid_file), "data/rules.yaml")
            devices = manager.load_hosts()
            assert len(devices) > 0

        # Test rules file validation
        rules_file = test_files_dir / "rules.yaml"
        if rules_file.exists():
            import yaml

            with open(rules_file) as f:
                rules = yaml.safe_load(f)

            # Verify expected structure
            assert "evpn_commands" in rules
            assert "evpn_status_check" in rules["evpn_commands"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_device_processing(self):
        """Test processing multiple devices concurrently."""
        # Create mock devices that simulate different response times
        devices = []
        for i in range(5):
            devices.append(
                {
                    "host": f"192.0.2.{i+1}",
                    "username": "testuser",
                    "password": "testpass",
                    "port": 22,
                    "timeout": 1,
                    "tags": ["test"],
                }
            )

        manager = EVPNManager("dummy", "data/rules.yaml", fix_mode=False)
        manager.devices = devices

        # Mock the load_hosts to return our test devices
        with patch.object(manager, "load_hosts") as mock_load:
            mock_load.return_value = devices

            start_time = asyncio.get_event_loop().time()
            await manager.run()
            end_time = asyncio.get_event_loop().time()

            # Should complete in reasonable time despite multiple devices
            # (if sequential, would take 5+ seconds; concurrent should be ~1-2 seconds)
            elapsed = end_time - start_time
            assert elapsed < 5, f"Processing took too long: {elapsed}s"

    @pytest.mark.integration
    def test_logging_output(self, caplog):
        """Test logging output at different levels."""
        import logging

        from main import setup_logging

        # Test different log levels
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            caplog.clear()
            setup_logging(level)

            logger = logging.getLogger("test")
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")

            # Verify appropriate messages are captured
            if level == "DEBUG":
                assert len(caplog.records) == 4
            elif level == "INFO":
                assert len(caplog.records) == 3
            elif level == "WARNING":
                assert len(caplog.records) == 2
            elif level == "ERROR":
                assert len(caplog.records) == 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_resilience(self):
        """Test system resilience to various error conditions."""
        from main import EVPNManager

        # Test with invalid hosts file path
        manager = EVPNManager("/nonexistent/path/hosts.yaml", "data/rules.yaml")
        devices = manager.load_hosts()
        assert devices == []

        # Test running with no devices
        await manager.run()  # Should not raise exception

        # Test with malformed device config
        manager.devices = [{"invalid": "config"}]

        # This should handle the error gracefully
        try:
            await manager.run()
        except Exception as e:
            pytest.fail(f"Should handle errors gracefully, got: {e}")

    @pytest.mark.integration
    def test_environment_variable_handling(self):
        """Test handling of environment variables."""
        # Test behavior with different environment settings
        original_env = os.environ.copy()

        try:
            # Test with debug environment
            os.environ["DEBUG"] = "1"
            # Could test debug-specific behavior here

            # Test with different Python path settings
            os.environ["PYTHONPATH"] = "/tmp"
            # Verify still works

        finally:
            # Restore original environment
            os.environ.clear()
            os.environ.update(original_env)

    @pytest.mark.integration
    def test_file_permissions(self):
        """Test behavior with different file permissions."""
        import stat
        import tempfile

        # Create a hosts file with restricted permissions
        test_config = """
defaults:
  admin_user: test
host_groups:
  test: []
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(test_config)
            hosts_file = f.name

        try:
            # Remove read permissions
            os.chmod(hosts_file, stat.S_IWRITE)

            manager = EVPNManager(hosts_file, "data/rules.yaml")
            devices = manager.load_hosts()

            # Should return empty list due to permission error
            assert devices == []

        finally:
            # Restore permissions and cleanup
            os.chmod(hosts_file, stat.S_IREAD | stat.S_IWRITE)
            os.unlink(hosts_file)
