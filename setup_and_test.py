#!/usr/bin/env python3
"""
Pre-flight check and test runner for the vocabulary app.
This script checks dependencies and runs the test suite.
"""

import sys
import subprocess
import os

def check_and_install_dependencies():
    """Check if test dependencies are installed, offer to install if not."""
    print("Checking test dependencies...")
    
    try:
        import pytest
        print("✓ pytest is installed")
        return True
    except ImportError:
        print("✗ pytest is not installed")
        print("\nTest dependencies are required. Install them with:")
        print("  pip install -r requirements-dev.txt")
        print("\nOr run this command now? (y/n): ", end="")
        
        try:
            response = input().strip().lower()
            if response == 'y':
                print("\nInstalling test dependencies...")
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", "requirements-dev.txt"],
                    check=False
                )
                if result.returncode == 0:
                    print("✓ Dependencies installed successfully")
                    return True
                else:
                    print("✗ Failed to install dependencies")
                    return False
            else:
                print("\nPlease install dependencies manually:")
                print("  pip install -r requirements-dev.txt")
                return False
        except (EOFError, KeyboardInterrupt):
            print("\n\nInstallation cancelled.")
            return False

def run_tests():
    """Run the test suite."""
    print("\n" + "=" * 70)
    print("Running Vocabulary App Test Suite")
    print("=" * 70 + "\n")
    
    # Run pytest
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "-v",
        "-m", "not slow",
        "--tb=short",
        "--color=yes"
    ])
    
    print("\n" + "=" * 70)
    if result.returncode == 0:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed (see above)")
    print("=" * 70 + "\n")
    
    print("Test commands:")
    print("  pytest                    # Run all tests")
    print("  pytest -v                 # Verbose output")
    print("  pytest -m 'not slow'      # Skip slow tests")
    print("  pytest --cov              # With coverage")
    print("  pytest tests/test_level.py  # Run specific module")
    
    return result.returncode

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    if not check_and_install_dependencies():
        sys.exit(1)
    
    sys.exit(run_tests())

if __name__ == "__main__":
    main()
