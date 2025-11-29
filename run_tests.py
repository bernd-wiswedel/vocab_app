#!/usr/bin/env python3
"""
Simple test runner - executes pytest and displays results.
Run this file to test the vocabulary app.
"""

import subprocess
import sys
import os

def main():
    # Change to the directory containing this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    print("=" * 70)
    print("Vocabulary App Test Suite")
    print("=" * 70)
    print()
    
    # Check if pytest is available
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print("ERROR: pytest is not installed!")
            print("Install with: pip install -r requirements-dev.txt")
            sys.exit(1)
        print(f"✓ {result.stdout.strip()}")
    except Exception as e:
        print(f"ERROR: Cannot run pytest: {e}")
        print("Install with: pip install -r requirements-dev.txt")
        sys.exit(1)
    
    print()
    print("Running tests (excluding slow Google Sheets API tests)...")
    print("-" * 70)
    print()
    
    # Run pytest with fast tests only
    result = subprocess.run(
        ["python", "-m", "pytest", "-v", "-m", "not slow", "--tb=short"],
        cwd=script_dir
    )
    
    print()
    print("=" * 70)
    
    if result.returncode == 0:
        print("✓ All tests passed!")
        print()
        print("To run ALL tests (including slow ones): pytest")
        print("To run with coverage: pytest --cov --cov-report=html")
    else:
        print("✗ Some tests failed")
        print()
        print("Run 'pytest -v' for detailed output")
    
    print("=" * 70)
    
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
