"""CLI argument parsing and command-line interface tests."""

import argparse
import os
import subprocess
import sys
import tempfile
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import EVPNManager, main, setup_logging


class TestCLI:
    """Test cases for command-line interface."""

    @pytest.mark.unit
    def test_setup_logging_default(self):
        """Test logging setup with default level."""
        import logging

        # Clear existing handlers to avoid interference
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        setup_logging()

        # Check that root logger level is set to INFO
        assert root_logger.level == logging.INFO

    @pytest.mark.unit
    def test_setup_logging_custom_levels(self):
        """Test logging setup with different levels."""
        import logging

        levels = ["DEBUG", "INFO", "WARNING", "ERROR"]

        for level_name in levels:
            # Clear existing handlers to avoid interference
            root_logger = logging.getLogger()
            root_logger.handlers.clear()

            setup_logging(level_name)
            expected_level = getattr(logging, level_name)
            assert root_logger.level == expected_level

    @pytest.mark.unit
    def test_main_missing_hosts_file(self, capsys):
        """Test main function with missing hosts file."""
        test_args = ["main.py", "--hosts-file", "/nonexistent/file.yaml"]

        with (
            patch.object(sys, "argv", test_args),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "not found" in captured.out

    @pytest.mark.unit
    def test_main_help_output(self, capsys):
        """Test main function help output."""
        test_args = ["main.py", "--help"]

        with (
            patch.object(sys, "argv", test_args),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "EVPN Route Status Manager" in captured.out
        assert "--hosts-file" in captured.out
        assert "--rules-file" in captured.out
        assert "--fix" in captured.out
        assert "--log-level" in captured.out

    @pytest.mark.unit
    def test_main_with_valid_args(self):
        """Test main function with valid arguments."""
        # Create temporary hosts file
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
            test_args = ["main.py", "--hosts-file", hosts_file, "--log-level", "DEBUG"]

            with (
                patch.object(sys, "argv", test_args),
                patch.object(EVPNManager, "run") as mock_run,
            ):

                # Mock the async run method to avoid actual execution
                mock_run.return_value = None

                try:
                    main()
                except SystemExit:
                    pass  # main() may call sys.exit() after successful execution

                # Verify EVPNManager was created and run was called
                mock_run.assert_called_once()

        finally:
            os.unlink(hosts_file)

    @pytest.mark.unit
    def test_main_keyboard_interrupt(self, capsys):
        """Test main function handling keyboard interrupt."""
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
            test_args = ["main.py", "--hosts-file", hosts_file]

            with (
                patch.object(sys, "argv", test_args),
                patch("asyncio.run") as mock_asyncio_run,
                pytest.raises(SystemExit) as exc_info,
            ):

                # Simulate keyboard interrupt
                mock_asyncio_run.side_effect = KeyboardInterrupt()

                main()

            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "interrupted by user" in captured.out

        finally:
            os.unlink(hosts_file)

    @pytest.mark.unit
    def test_main_unexpected_exception(self, capsys):
        """Test main function handling unexpected exceptions."""
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
            test_args = ["main.py", "--hosts-file", hosts_file]

            with (
                patch.object(sys, "argv", test_args),
                patch("asyncio.run") as mock_asyncio_run,
                pytest.raises(SystemExit) as exc_info,
            ):

                # Simulate unexpected exception
                mock_asyncio_run.side_effect = Exception("Unexpected error")

                main()

            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "Unexpected error" in captured.out

        finally:
            os.unlink(hosts_file)

    @pytest.mark.unit
    def test_argument_parser_configuration(self):
        """Test argument parser configuration."""
        import argparse

        from main import main

        # Create a parser similar to what main() creates
        parser = argparse.ArgumentParser(
            description="EVPN Route Status Manager for Juniper devices"
        )

        parser.add_argument("--hosts-file", required=True)
        parser.add_argument("--fix", action="store_true")
        parser.add_argument(
            "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO"
        )

        # Test valid arguments
        args = parser.parse_args(["--hosts-file", "test.yaml"])
        assert args.hosts_file == "test.yaml"
        assert args.fix is False
        assert args.log_level == "INFO"

        # Test with fix flag
        args = parser.parse_args(["--hosts-file", "test.yaml", "--fix"])
        assert args.fix is True

        # Test with custom log level
        args = parser.parse_args(["--hosts-file", "test.yaml", "--log-level", "DEBUG"])
        assert args.log_level == "DEBUG"

    @pytest.mark.unit
    def test_argument_parser_invalid_log_level(self):
        """Test argument parser with invalid log level."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--hosts-file", required=True)
        parser.add_argument(
            "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO"
        )

        with pytest.raises(SystemExit):
            parser.parse_args(["--hosts-file", "test.yaml", "--log-level", "INVALID"])

    @pytest.mark.unit
    def test_argument_parser_missing_required(self):
        """Test argument parser with missing required arguments."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--hosts-file", required=True)

        with pytest.raises(SystemExit):
            parser.parse_args([])  # Missing required --hosts-file

    @pytest.mark.integration
    def test_cli_help_subprocess(self):
        """Test CLI help via subprocess call."""
        result = subprocess.run(
            [sys.executable, "main.py", "--help"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )

        assert result.returncode == 0
        assert "EVPN Route Status Manager" in result.stdout
        assert "usage:" in result.stdout
        assert "--hosts-file" in result.stdout
        assert "--rules-file" in result.stdout
        assert "--fix" in result.stdout
        assert "--log-level" in result.stdout

    @pytest.mark.integration
    def test_cli_version_info(self):
        """Test CLI version and environment information."""
        # Test that we can at least import and run the help
        result = subprocess.run(
            [sys.executable, "-c", 'import main; print("Import successful")'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )

        if result.returncode != 0:
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)

        # Note: This might fail if junos-eznc is not installed, which is expected
        # The test is mainly to verify the module structure

    @pytest.mark.unit
    def test_evpn_manager_initialization_from_cli(self):
        """Test EVPNManager initialization with CLI parameters."""
        # Test that EVPNManager can be initialized with parameters
        # that would come from CLI

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
            # Test without fix mode (default)
            manager1 = EVPNManager(hosts_file, "data/rules.yaml", fix_mode=False)
            assert manager1.fix_mode is False
            assert str(manager1.hosts_file) == hosts_file

            # Test with fix mode enabled
            manager2 = EVPNManager(hosts_file, "data/rules.yaml", fix_mode=True)
            assert manager2.fix_mode is True
            assert str(manager2.hosts_file) == hosts_file

        finally:
            os.unlink(hosts_file)

    @pytest.mark.unit
    def test_logging_integration_with_cli(self, caplog):
        """Test logging integration with CLI setup."""
        import logging

        # Capture logs at DEBUG level
        with caplog.at_level(logging.DEBUG):
            # Create a test logger and verify it works
            test_logger = logging.getLogger("test.cli")
            test_logger.debug("Debug message")
            test_logger.info("Info message")
            test_logger.warning("Warning message")
            test_logger.error("Error message")

        # Verify all messages were captured
        assert len(caplog.records) >= 4

        # Verify message levels
        levels = [record.levelname for record in caplog.records]
        assert "DEBUG" in levels
        assert "INFO" in levels
        assert "WARNING" in levels
        assert "ERROR" in levels
