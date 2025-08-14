#!/usr/bin/env python3
"""
EVPN Route Status Manager

A CLI tool for managing Juniper network devices and checking EVPN route status.
Supports bulk operations across multiple devices with automatic remediation.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

try:
    from jnpr.junos import Device
    from jnpr.junos.exception import ConnectAuthError, ConnectError, RpcError
except ImportError as e:
    if __name__ == "__main__":
        print("Error: junos-eznc library not found. Install with: uv add junos-eznc")
        sys.exit(1)
    else:
        # During testing or import, create mock classes
        class Device:
            def __init__(self, *args, **kwargs):
                pass
                
        class ConnectError(Exception):
            pass
            
        class ConnectAuthError(Exception):
            pass
            
        class RpcError(Exception):
            pass


class EVPNStatusChecker:
    """Handles EVPN route status checking and remediation."""

    def __init__(self, host: str, username: str, password: str, port: int = 22, timeout: int = 30, name: str = None):
        self.host = host
        self.name = name or host
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self.device = None
        self.ssh_config_file = None
        self.logger = logging.getLogger(f"evpn.{self.name}")

    async def connect(self) -> bool:
        """Connect to the device."""
        try:
            # Create custom SSH config to avoid DSS key issues
            import tempfile
            ssh_config_content = """
Host *
    HostKeyAlgorithms ssh-ed25519,ecdsa-sha2-nistp256,ecdsa-sha2-nistp384,ecdsa-sha2-nistp521,rsa-sha2-512,rsa-sha2-256,ssh-rsa
    PubkeyAcceptedAlgorithms ssh-ed25519,ecdsa-sha2-nistp256,ecdsa-sha2-nistp384,ecdsa-sha2-nistp521,rsa-sha2-512,rsa-sha2-256,ssh-rsa
    StrictHostKeyChecking no
"""
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ssh_config', delete=False) as f:
                f.write(ssh_config_content)
                self.ssh_config_file = f.name
            
            self.device = Device(
                host=self.host,
                user=self.username,
                passwd=self.password,
                port=self.port,
                timeout=self.timeout,
                ssh_config=self.ssh_config_file
            )
            self.device.open()
            self.logger.info(f"Connected to {self.host}")
            return True
        except Exception as e:
            # Catch any connection-related exception 
            if "ConnectError" in str(type(e)) or "ConnectAuthError" in str(type(e)):
                self.logger.error(f"Connection failed to {self.host}: {e}")
            else:
                self.logger.error(f"Unexpected error connecting to {self.host}: {e}")
            return False

    def disconnect(self):
        """Disconnect from the device."""
        if self.device and self.device.connected:
            self.device.close()
            self.logger.info(f"Disconnected from {self.host}")
        
        # Clean up temporary SSH config file
        if self.ssh_config_file:
            import os
            try:
                os.unlink(self.ssh_config_file)
                self.ssh_config_file = None
            except OSError:
                pass  # File already deleted or doesn't exist

    def get_evpn_route_status(self) -> dict[str, int]:
        """
        Get EVPN route status count using netconf command.
        
        Returns:
            Dict with status counts: {"Accepted": 10, "Rejected": 2, "Pending": 0}
        """
        if not self.device or not self.device.connected:
            self.logger.error("Device not connected")
            return {}

        try:
            # Execute the netconf RPC command
            result = self.device.rpc.get_evpn_ip_prefix_database_information()

            # Parse the response and count statuses
            status_counts = {
                "Accepted": 0,
                "Rejected": 0,
                "Pending": 0,
                "Invalid": 0,
                "Unknown": 0
            }

            # Navigate through the XML structure to find route entries
            if hasattr(result, 'xpath'):
                # Look for adv-ip-route-status elements directly
                status_elements = result.xpath('.//adv-ip-route-status')
                
                self.logger.debug(f"Found {len(status_elements)} adv-ip-route-status elements directly")

                for status_element in status_elements:
                    status = status_element.text.strip() if status_element.text else "Unknown"
                    self.logger.debug(f"Found status: {status}")
                    if status in status_counts:
                        status_counts[status] += 1
                    else:
                        status_counts["Unknown"] += 1
                        self.logger.warning(f"Unknown status found: {status}")
                
                # Also look for entry-prefix entries to understand structure (for debugging)
                prefix_elements = result.xpath('.//entry-prefix')
                self.logger.debug(f"Found {len(prefix_elements)} entry-prefix elements for reference")

            self.logger.info(f"EVPN route status for {self.host}: {status_counts}")
            return status_counts

        except RpcError as e:
            self.logger.error(f"RPC error getting EVPN status from {self.host}: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Unexpected error getting EVPN status from {self.host}: {e}")
            return {}

    def restart_routing(self) -> bool:
        """
        Restart routing process on the device.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.device or not self.device.connected:
            self.logger.error("Device not connected")
            return False

        try:
            self.logger.warning(f"Restarting routing process on {self.host}")
            self.device.rpc.restart_routing_process()
            self.logger.info(f"Routing restart initiated on {self.host}")
            return True

        except RpcError as e:
            self.logger.error(f"Failed to restart routing on {self.host}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error restarting routing on {self.host}: {e}")
            return False


class EVPNManager:
    """Manages multiple devices and coordinates EVPN operations."""

    def __init__(self, hosts_file: str, rules_file: str = None, fix_mode: bool = False, max_concurrent: int = None):
        self.hosts_file = Path(hosts_file)
        self.rules_file = Path(rules_file) if rules_file else Path("data/rules.yaml")
        self.fix_mode = fix_mode
        self.max_concurrent_override = max_concurrent
        self.devices = []
        self.rules = {}
        self.logger = logging.getLogger("evpn.manager")

    def load_hosts(self) -> list[dict[str, Any]]:
        """Load host configuration from YAML file."""
        try:
            with open(self.hosts_file) as f:
                config = yaml.safe_load(f)

            devices = []
            defaults = config.get('defaults', {})

            # Process all host groups
            for _group_name, hosts in config.get('host_groups', {}).items():
                for host_config in hosts:
                    # Merge defaults with host-specific config
                    device_config = {**defaults, **host_config}

                    # Handle password resolution
                    password = device_config.get('password')
                    if not password and 'user_password' in defaults:
                        username = device_config.get('username', defaults.get('admin_user'))
                        password = defaults['user_password'].get(username)

                    if not password:
                        self.logger.warning(f"No password found for {host_config['host']}")
                        continue

                    devices.append({
                        'host': host_config['host'],
                        'name': host_config.get('name', host_config['host']),
                        'username': device_config.get('username', defaults.get('admin_user')),
                        'password': password,
                        'port': device_config.get('port', 22),
                        'timeout': device_config.get('timeout', 30),
                        'tags': host_config.get('tags', [])
                    })

            self.logger.info(f"Loaded {len(devices)} devices from {self.hosts_file}")
            return devices

        except Exception as e:
            self.logger.error(f"Failed to load hosts from {self.hosts_file}: {e}")
            return []

    def load_rules(self) -> dict[str, Any]:
        """Load rules configuration from YAML file."""
        try:
            with open(self.rules_file) as f:
                rules = yaml.safe_load(f)
            
            self.rules = rules or {}
            self.logger.info(f"Loaded rules from {self.rules_file}")
            return self.rules
            
        except Exception as e:
            self.logger.error(f"Failed to load rules from {self.rules_file}: {e}")
            return {}

    def setup_logging_from_rules(self):
        """Setup logging based on rules configuration."""
        if not self.rules:
            return
            
        log_config = self.rules.get('logging', {})
        
        if not log_config.get('enabled', False):
            return
            
        # Get logging configuration
        log_level = log_config.get('level', 'INFO')
        log_file = log_config.get('file', 'data/logs.txt')
        log_format = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        max_size_mb = log_config.get('max_size_mb', 10)
        backup_count = log_config.get('backup_count', 5)
        console = log_config.get('console', True)
        
        # Replace {timestamp} placeholder in filename
        if '{timestamp}' in log_file:
            import datetime
            timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
            log_file = log_file.replace('{timestamp}', timestamp)
        
        # Create logs directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # File handler with rotation
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(file_handler)
        
        # Console handler (optional)
        if console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)  # Less verbose on console
            console_handler.setFormatter(logging.Formatter(log_format))
            root_logger.addHandler(console_handler)
        
        self.logger.info(f"Logging configured: {log_level} level to {log_file}")
        
        return

    async def process_device(self, device_config: dict[str, Any]) -> dict[str, Any]:
        """Process a single device."""
        # Get performance settings from rules
        performance_config = self.rules.get('performance', {})
        connection_timeout = performance_config.get('connection_timeout', device_config.get('timeout', 30))
        
        checker = EVPNStatusChecker(
            host=device_config['host'],
            username=device_config['username'],
            password=device_config['password'],
            port=device_config['port'],
            timeout=connection_timeout,
            name=device_config.get('name', device_config['host'])
        )

        result = {
            'host': device_config['host'],
            'name': device_config.get('name', device_config['host']),
            'connected': False,
            'status_counts': {},
            'restart_attempted': False,
            'restart_success': False
        }

        # Connect to device
        if not await checker.connect():
            return result

        result['connected'] = True

        try:
            # Get EVPN route status
            status_counts = checker.get_evpn_route_status()
            result['status_counts'] = status_counts

            # Check if fix is needed and requested
            if self.fix_mode and status_counts.get('Rejected', 0) > 0:
                self.logger.info(f"Found {status_counts['Rejected']} rejected routes on {device_config['host']}")
                result['restart_attempted'] = True
                result['restart_success'] = checker.restart_routing()

        finally:
            checker.disconnect()

        return result

    async def run(self):
        """Main execution method."""
        # Load rules configuration and setup logging
        self.load_rules()
        self.setup_logging_from_rules()
        
        devices = self.load_hosts()
        if not devices:
            self.logger.error("No devices loaded")
            return

        # Get concurrency settings from rules or CLI override
        performance_config = self.rules.get('performance', {})
        max_concurrent = self.max_concurrent_override or performance_config.get('max_concurrent_devices', 10)
        
        self.logger.info(f"Processing {len(devices)} devices (fix_mode: {self.fix_mode}, max_concurrent: {max_concurrent})")

        # Process devices with concurrency limiting
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_limit(device):
            async with semaphore:
                return await self.process_device(device)
        
        tasks = [process_with_limit(device) for device in devices]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Display results
        print("\nEVPN Route Status Summary:")
        print("=" * 60)

        total_stats = {"Accepted": 0, "Rejected": 0, "Pending": 0, "Invalid": 0, "Unknown": 0}
        devices_with_rejected = []

        for result in results:
            if isinstance(result, Exception):
                print(f"Error processing device: {result}")
                continue

            # Format device display name
            device_display = f"{result['name']}:{result['host']}"
            
            if not result['connected']:
                print(f"{device_display:<30} - CONNECTION FAILED")
                continue

            status_counts = result['status_counts']

            # Update totals
            for status, count in status_counts.items():
                total_stats[status] += count

            # Format output
            status_str = ", ".join([f"{k}: {v}" for k, v in status_counts.items() if v > 0])
            if not status_str:
                status_str = "No routes found"

            # Add restart status to the same line if in fix mode
            if self.fix_mode:
                if result['restart_attempted']:
                    if result['restart_success']:
                        restart_status = " [✅ Restart: SUCCESS]"
                    else:
                        restart_status = " [❌ Restart: FAILED]"
                else:
                    restart_status = " [ℹ️ Restart: NO]"
                status_str += restart_status

            print(f"{device_display:<30} - {status_str}")

            # Track devices needing fixes
            if status_counts.get('Rejected', 0) > 0:
                devices_with_rejected.append(result)

        # Display summary
        print("\n" + "=" * 60)
        print("Overall Summary:")
        summary_str = ", ".join([f"{k}: {v}" for k, v in total_stats.items() if v > 0])
        print(f"Total routes: {summary_str}")

        if devices_with_rejected:
            print(f"\nDevices with rejected routes: {len(devices_with_rejected)}")
            
            # Show fix results if fix mode was enabled
            if self.fix_mode:
                successful_fixes = []
                failed_fixes = []
                
                for device in devices_with_rejected:
                    rejected_count = device['status_counts'].get('Rejected', 0)
                    device_display = f"{device['name']}:{device['host']}"
                    
                    if device.get('restart_attempted'):
                        if device.get('restart_success'):
                            successful_fixes.append((device_display, rejected_count))
                        else:
                            failed_fixes.append((device_display, rejected_count))
                    else:
                        print(f"  - {device_display}: {rejected_count} rejected routes (no fix attempted)")
                
                if successful_fixes:
                    print(f"\n✅ Successfully restarted routing on {len(successful_fixes)} device(s):")
                    for device_display, rejected_count in successful_fixes:
                        print(f"  - {device_display}: Fixed {rejected_count} rejected routes")
                
                if failed_fixes:
                    print(f"\n❌ Failed to restart routing on {len(failed_fixes)} device(s):")
                    for device_display, rejected_count in failed_fixes:
                        print(f"  - {device_display}: {rejected_count} rejected routes (fix failed)")
            else:
                for device in devices_with_rejected:
                    rejected_count = device['status_counts'].get('Rejected', 0)
                    device_display = f"{device['name']}:{device['host']}"
                    print(f"  - {device_display}: {rejected_count} rejected routes")
                    
                print("\nTo fix rejected routes, run with --fix option")


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="EVPN Route Status Manager for Juniper devices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check EVPN status on all devices
  python main.py --hosts-file data/hosts.yaml --rules-file data/rules.yaml
  
  # Check status and fix rejected routes
  python main.py --hosts-file data/hosts.yaml --rules-file data/rules.yaml --fix
  
  # Enable debug logging (rules file uses default)
  python main.py --hosts-file data/hosts.yaml --log-level DEBUG
        """
    )

    parser.add_argument(
        '--hosts-file',
        default='data/hosts.yaml',
        help='YAML file containing device inventory (default: data/hosts.yaml)'
    )

    parser.add_argument(
        '--rules-file',
        default='data/rules.yaml',
        help='YAML file with EVPN validation rules (default: data/rules.yaml)'
    )

    parser.add_argument(
        '--fix',
        action='store_true',
        help='Restart routing on devices with rejected routes'
    )

    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )

    parser.add_argument(
        '--max-concurrent',
        type=int,
        help='Maximum concurrent device connections (overrides rules.yaml setting)'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Validate hosts file exists
    if not Path(args.hosts_file).exists():
        print(f"Error: Hosts file '{args.hosts_file}' not found")
        sys.exit(1)

    # Validate rules file exists
    if not Path(args.rules_file).exists():
        print(f"Error: Rules file '{args.rules_file}' not found")
        sys.exit(1)

    # Create and run manager
    manager = EVPNManager(args.hosts_file, args.rules_file, fix_mode=args.fix, max_concurrent=args.max_concurrent)

    try:
        asyncio.run(manager.run())
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        logging.getLogger().exception("Unexpected error")
        sys.exit(1)


if __name__ == "__main__":
    main()
