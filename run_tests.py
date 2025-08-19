#!/usr/bin/env python3
"""Test runner script for restart-rejected project."""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, description):
    """Run a command and report results."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.stdout:
        print("STDOUT:")
        print(result.stdout)
    
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
    
    if result.returncode == 0:
        print(f"✅ {description} PASSED")
    else:
        print(f"❌ {description} FAILED (exit code: {result.returncode})")
    
    return result.returncode == 0


def main():
    """Run all tests and quality checks."""
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    print("🚀 Starting test suite for restart-rejected")
    print(f"Working directory: {project_root}")
    
    all_passed = True
    
    # 1. Install dependencies
    success = run_command(
        ["uv", "sync", "--all-extras"],
        "Installing dependencies"
    )
    if not success:
        print("⚠️ Failed to install dependencies, attempting to continue...")
    
    # 2. Run linting
    success = run_command(
        ["uv", "run", "ruff", "check", "main.py", "tests/"],
        "Code linting (ruff)"
    )
    all_passed = all_passed and success
    
    # 3. Run type checking  
    success = run_command(
        ["uv", "run", "mypy", "main.py"],
        "Type checking (mypy)"
    )
    all_passed = all_passed and success
    
    # 4. Run code formatting check
    success = run_command(
        ["uv", "run", "black", "--check", "main.py", "tests/"],
        "Code formatting check (black)"
    )
    all_passed = all_passed and success
    
    # 5. Run unit tests only
    success = run_command(
        ["uv", "run", "pytest", "-v", "-m", "unit", "--tb=short"],
        "Unit tests"
    )
    all_passed = all_passed and success
    
    # 6. Run integration tests if enabled
    if os.getenv('INTEGRATION_TESTS'):
        success = run_command(
            ["uv", "run", "pytest", "-v", "-m", "integration", "--tb=short"],
            "Integration tests"
        )
        all_passed = all_passed and success
    else:
        print("\n⏭️ Skipping integration tests (set INTEGRATION_TESTS=1 to enable)")
    
    # 7. Run all tests with coverage if requested
    if os.getenv('WITH_COVERAGE'):
        success = run_command(
            ["uv", "run", "pytest", "--cov=main", "--cov-report=term-missing", "-v"],
            "Tests with coverage"
        )
        all_passed = all_passed and success
    
    # 8. Test CLI functionality
    success = run_command(
        ["uv", "run", "python", "main.py", "--help"],
        "CLI help functionality"
    )
    all_passed = all_passed and success
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    
    if all_passed:
        print("🎉 All tests and checks PASSED!")
        print("\nTo run integration tests: INTEGRATION_TESTS=1 python run_tests.py")
        print("To run with coverage: WITH_COVERAGE=1 python run_tests.py")
        return 0
    else:
        print("💥 Some tests or checks FAILED!")
        print("\nCheck the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())