# EVPN Route Status Manager - Development Guide

This file provides comprehensive guidance to Claude Code when working with the **restart-rejected** EVPN management tool.

## Project Overview

**restart-rejected** is a Python CLI tool for managing Juniper network devices and monitoring EVPN (Ethernet VPN) route status. It provides automated detection of rejected routes and optional remediation through routing process restarts.

## Current Implementation Status ✅

### Completed Features
- **Multi-device EVPN monitoring** - Concurrent processing with async/await
- **Route status parsing** - XML parsing of `get-evpn-ip-prefix-database-information` 
- **Automated remediation** - `restart routing` execution for devices with rejected routes
- **Comprehensive logging** - Timestamped files with rotation and device-specific loggers
- **SSH compatibility** - Custom SSH config excluding DSS key algorithms
- **Error handling** - Graceful connection failures and retry logic
- **CLI interface** - Complete argparse implementation with validation

### Architecture

#### Core Components (Implemented)
- **`EVPNStatusChecker`** (`main.py:41-181`) - Single device operations
  - Device connection with custom SSH configuration  
  - EVPN route status retrieval and parsing
  - Routing process restart functionality
  - Device-specific logging with name resolution

- **`EVPNManager`** (`main.py:183-422`) - Multi-device orchestration
  - YAML configuration loading (hosts.yaml, rules.yaml)
  - Concurrent device processing with asyncio
  - Results aggregation and summary reporting
  - Logging configuration from rules

#### Current Project Structure
```
restart-rejected/
├── main.py              # Complete implementation (509 lines)
├── pyproject.toml       # uv package configuration with CLI entry point
├── data/
│   ├── hosts.yaml       # Device inventory with connection parameters
│   ├── rules.yaml       # EVPN validation rules and logging config
│   └── logs-*.txt      # Timestamped log files (gitignored)
├── tests/               # 62+ comprehensive tests
│   ├── test_evpn_status_checker.py  # 21 unit tests
│   ├── test_evpn_manager.py         # 17 tests  
│   ├── test_cli.py                  # 12 CLI tests
│   ├── test_integration.py          # Integration tests
│   ├── fixtures/                    # Mock data and test configs
│   └── conftest.py                  # Shared pytest fixtures
└── README.md           # Usage documentation
```

#### Device Support (Tested)
- **Connection**: NETCONF over SSH (port 830)
- **Authentication**: Username/password with SSH key compatibility
- **Commands**: `get-evpn-ip-prefix-database-information`, `restart routing`

## Development Commands

### Environment Setup
```bash
# Install dependencies (from implemented pyproject.toml)
uv sync

# Add/remove dependencies  
uv add package-name
uv remove package-name

# CLI tool available after installation
jpt --help  # Entry point: main:main
```

### Testing (62+ Tests Implemented)
```bash
# All tests
uv run pytest

# Unit tests only (50+ tests)
uv run pytest -m unit

# Integration tests 
uv run pytest -m integration

# Specific test categories
uv run pytest tests/test_evpn_status_checker.py  # Device operations
uv run pytest tests/test_evpn_manager.py         # Multi-device coordination
uv run pytest tests/test_cli.py                  # CLI interface

# Test rejected routes functionality (since live env has none)
uv run pytest tests/ -k "reject" -v
```

### CLI Usage (Implemented)
```bash
# Basic EVPN status check (uses defaults)
uv run jpt
# or: uv run main.py

# With specific configuration files
uv run jpt --hosts-file data/hosts.yaml --rules-file data/rules.yaml

# Enable fix mode for rejected routes
uv run jpt --fix

# Debug logging
uv run jpt --log-level DEBUG --fix

# Control concurrency for large device inventories
uv run jpt --fix --max-concurrent 5    # Conservative (5 concurrent)
uv run jpt --fix --max-concurrent 20   # Aggressive (20 concurrent)

# All options
uv run jpt --hosts-file data/hosts.yaml --rules-file data/rules.yaml --fix --log-level DEBUG --max-concurrent 10
```

## Configuration (Implemented)

### Host Configuration (`data/hosts.yaml`)
Device inventory with connection parameters and authentication:
```yaml
defaults:
  admin_user: admin
  port: 830  # NETCONF port
  timeout: 30
  user_password:
    admin: "secure_password"

host_groups:
  leaf_switches:
    - host: 192.168.1.100
      name: spine-01  # Display name (optional, defaults to host)
      username: admin
      tags: [spine, evpn, production]
    - host: 192.168.1.101
      name: leaf-01
      tags: [leaf, evpn, production]
```

### Rules Configuration (`data/rules.yaml`)
EVPN commands, validation rules, and logging configuration:
```yaml
evpn_commands:
  status_check: "get-evpn-ip-prefix-database-information"
  remediation: "restart routing"

validation_rules:
  max_rejected_routes: 0
  alert_thresholds:
    warning: 5
    critical: 10

logging:
  enabled: true
  level: "DEBUG"
  file: "data/logs-{timestamp}.txt"  # Timestamped files
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  max_size_mb: 10
  backup_count: 5
  console: true
```

## Technical Implementation Details

### EVPN Route Status Parsing
The tool executes `get-evpn-ip-prefix-database-information` and parses XML responses:

```python
# XML structure parsed by EVPNStatusChecker.get_evpn_route_status()
status_elements = result.xpath('.//adv-ip-route-status')
for status_element in status_elements:
    status = status_element.text.strip()
    if status in ["Accepted", "Rejected", "Pending", "Invalid"]:
        status_counts[status] += 1
```

Expected XML format:
```xml
<evpn-ip-prefix-database-information>
  <evpn-ip-prefix-database>
    <adv-ip-route-status>Accepted</adv-ip-route-status>
    <ip-prefix>192.168.1.1/32</ip-prefix>
    <rd>65001:1</rd>
  </evpn-ip-prefix-database>
</evpn-ip-prefix-database-information>
```

### SSH Compatibility Fix
Automatic SSH configuration to avoid DSS key issues with modern devices:
```python
ssh_config_content = """
Host *
    HostKeyAlgorithms ssh-ed25519,ecdsa-sha2-nistp256,ecdsa-sha2-nistp384,ecdsa-sha2-nistp521,rsa-sha2-512,rsa-sha2-256,ssh-rsa
    PubkeyAcceptedAlgorithms ssh-ed25519,ecdsa-sha2-nistp256,ecdsa-sha2-nistp384,ecdsa-sha2-nistp521,rsa-sha2-512,rsa-sha2-256,ssh-rsa
    StrictHostKeyChecking no
"""
```

### Logging System
- **Device-specific loggers**: `evpn.{device_name}` for clear identification
- **Timestamped files**: `data/logs-20241214-143022.txt` format
- **Rotation**: 10MB max size with 5 backup files
- **Console + file**: Dual output with different verbosity levels

## Testing Strategy (Comprehensive Implementation)

### Test Coverage
- **21 Unit Tests** - `EVPNStatusChecker` device operations
- **17 Unit Tests** - `EVPNManager` multi-device coordination  
- **12 CLI Tests** - Command-line interface and argument parsing
- **Integration Tests** - End-to-end workflow validation
- **Mock Data** - 4 scenarios (healthy, rejected, mixed, empty)

### Mock Data for Rejected Routes Testing
Since live environments may have no rejected routes, comprehensive mock data enables testing:

```python
# tests/fixtures/evpn_mock_data.py
REJECTED_ROUTES_RESPONSE = """
<evpn-ip-prefix-database-information>
    <evpn-ip-prefix-database>
        <adv-ip-route-status>Rejected</adv-ip-route-status>
        <ip-prefix>192.168.1.2/32</ip-prefix>
    </evpn-ip-prefix-database>
</evpn-ip-prefix-database-information>
"""

EXPECTED_RESULTS = {
    'rejected': {'Accepted': 1, 'Rejected': 2, 'Pending': 1}  # Fix would trigger
}
```

### Key Test Scenarios
- **Connection failures** - Network timeouts, authentication errors
- **XML parsing** - Various route status combinations
- **Fix mode** - Routing restart triggering with rejected routes
- **CLI validation** - Argument parsing and file validation

## Key Dependencies (Implemented)

### Core Dependencies
```toml
dependencies = [
    "junos-eznc>=2.6.0",  # Juniper PyEZ library
    "PyYAML>=6.0",        # YAML configuration parsing  
    "lxml>=4.9.0",        # XML processing
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",  # Async test support
]

[project.scripts]
jpt = "main:main"  # CLI entry point
```

## Current Status & Known Issues

### ✅ Working Features
- Multi-device concurrent processing with configurable limits (tested with 25+ devices)
- EVPN route status parsing (317 Accepted routes found in live test)
- SSH connectivity issues resolved (DSSKey compatibility)
- Device naming with fallback (name or host)
- Comprehensive logging with timestamps
- Fix functionality (restart routing) for rejected routes with clear status indicators
- Concurrency control via rules.yaml and CLI override (--max-concurrent)
- Single-line compact output format optimized for hundreds of devices
- Complete test coverage including rejected route scenarios

### ⚠️ Notes for Development
- **No rejected routes in live environment** - Use test suite for fix functionality validation
- **SSH config** - Automatically handles modern Juniper device compatibility  
- **Logging** - Files are timestamped and gitignored (`data/logs-*`)
- **Device names** - Optional in config, defaults to host IP if not specified
- **Async operations** - All device processing is concurrent for performance

### 🔧 Integration Points
- **CI/CD Ready** - Exit codes indicate success/failure status
- **Monitoring Ready** - Structured JSON-style logging for parsing
- **Scalable** - Async design supports large device inventories