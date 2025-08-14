# EVPN Route Status Manager

A Python CLI tool for managing Juniper network devices and monitoring EVPN (Ethernet VPN) route status. Provides automated detection of rejected routes and optional remediation through routing process restarts.

## Features

- **EVPN Route Monitoring**: Automated EVPN route status checking with detailed counting
- **Rejected Route Remediation**: Optional `restart routing` command for devices with rejected routes  
- **Concurrent Processing**: Configurable concurrency limits for large device inventories (hundreds of devices)
- **Comprehensive Logging**: Timestamped files with rotation and device-specific loggers
- **SSH Compatibility**: Automatic SSH configuration for modern Juniper devices
- **Compact Output**: Single-line format optimized for large-scale operations
- **Modern Python**: Built with `uv` package manager and comprehensive testing

## Installation

```bash
# Install with uv (recommended) - creates 'jpt' CLI command
uv pip install -e .

# Alternative installation methods
pip install -e .
```

## Quick Start

### Basic Usage

```bash
# Check EVPN status across all configured devices (default configuration)
uv run jpt

# Check status and fix rejected routes automatically
uv run jpt --fix

# Control concurrency for hundreds of devices
uv run jpt --fix --max-concurrent 5   # Conservative
uv run jpt --fix --max-concurrent 20  # Aggressive

# Debug mode with detailed logging
uv run jpt --fix --log-level DEBUG
```

### Configuration Files

The tool uses two YAML configuration files:

#### Device Inventory (`data/hosts.yaml`)
```yaml
defaults:
  admin_user: admin
  port: 830  # NETCONF port
  timeout: 30
  user_password:
    admin: "your_password"

host_groups:
  production_switches:
    - host: 192.168.1.100
      name: spine-01  # Optional display name
      tags: [spine, evpn]
    - host: 192.168.1.101  
      name: leaf-01
      tags: [leaf, evpn]
```

#### Rules & Performance (`data/rules.yaml`)
```yaml
# Performance settings for large deployments
performance:
  max_concurrent_devices: 10    # Concurrent SSH connections
  connection_timeout: 30        # SSH timeout (seconds)
  command_timeout: 60          # NETCONF timeout (seconds)

# Logging configuration  
logging:
  enabled: true
  level: "DEBUG"
  file: "data/logs-{timestamp}.txt"
  max_size_mb: 10
  backup_count: 5
```

## Output Examples

### Status-Only Mode
```
EVPN Route Status Summary:
============================================================
leaf1:10.85.192.14             - Accepted: 82
10.85.192.15:10.85.192.15      - Accepted: 82
leaf3:10.85.192.16             - Accepted: 74
10.85.192.17:10.85.192.17      - Accepted: 79

============================================================
Overall Summary:
Total routes: Accepted: 317
```

### Fix Mode Output
```
EVPN Route Status Summary:
============================================================
leaf1:10.85.192.14             - Accepted: 82 [ℹ️ Restart: NO]
spine-01:192.168.1.100         - Accepted: 78, Rejected: 4 [✅ Restart: SUCCESS]
leaf3:10.85.192.16             - Accepted: 70, Rejected: 4 [❌ Restart: FAILED]

============================================================
Overall Summary:
Total routes: Accepted: 230, Rejected: 8

✅ Successfully restarted routing on 1 device(s):
  - spine-01:192.168.1.100: Fixed 4 rejected routes

❌ Failed to restart routing on 1 device(s):
  - leaf3:10.85.192.16: 4 rejected routes (fix failed)
```

## CLI Options

- `--hosts-file`: Device inventory YAML file (default: data/hosts.yaml)
- `--rules-file`: Rules and performance YAML file (default: data/rules.yaml)  
- `--fix`: Enable routing restart for devices with rejected routes
- `--max-concurrent`: Maximum concurrent connections (overrides rules.yaml)
- `--log-level`: Logging verbosity (DEBUG, INFO, WARNING, ERROR)


## Live Device Testing

The project includes integration tests against real devices:

- **Test Device**: bl03 (10.85.192.16)
- **Credentials**: labroot/lab123 and root/root123
- **Validated**: QFX5100 devices with EVPN configurations
- **Test Results**: 74+ EVPN routes, multiple L3 contexts

```bash
# Run integration tests (requires live device access)
uv run pytest -m integration

# Run unit tests only
uv run pytest -m unit
```

## Development

### Development Commands

#### Environment Setup
```bash
# Install project with development dependencies
uv pip install -e .[dev]

# Sync dependencies from lock file
uv sync

# Add new dependency
uv add package-name

# Remove dependency  
uv remove package-name
```


#### Code Quality
```bash
# Lint code with ruff
uv run ruff check src/ tests/

# Auto-fix linting issues
uv run ruff check --fix src/ tests/

# Type checking
uv run mypy src/

# Format code with black
uv run black src/ tests/

# Run all quality checks
uv run ruff check src/ tests/ && uv run mypy src/ && uv run black --check src/ tests/
```


### Dual OS Support Architecture

The tool is designed to handle both **Junos** (traditional FreeBSD-based) and **Junos-EVO** (Linux-based) operating systems:

- **Auto-Detection**: Automatic OS mode detection during device connection
- **Unified API**: Single interface abstracts OS-specific differences  
- **Feature Mapping**: Mode-specific command availability and behavior
- **Device Compatibility**: QFX5100/5200/10000, MX80/240/480/960/2010, EX2200/3300/4200/4600/9200, SRX300/1500/5400

## License

This project is licensed under the MIT License.