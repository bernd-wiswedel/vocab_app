#!/usr/bin/env python3
"""
Quick test status checker for vocabulary app.
Runs tests and displays summary with color output.
"""

import subprocess
import sys

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def run_command(cmd):
    """Run a command and return success status."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def main():
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Vocabulary App Test Status{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    # Check if pytest is installed
    success, _, _ = run_command("pytest --version")
    if not success:
        print(f"{RED}❌ pytest not installed{RESET}")
        print("Install with: pip install -r requirements-dev.txt")
        sys.exit(1)
    
    print(f"{GREEN}✓{RESET} pytest is installed\n")
    
    # Run fast tests
    print(f"{YELLOW}Running fast tests...{RESET}")
    success, stdout, stderr = run_command("pytest -m 'not slow' -v --tb=short")
    
    if success:
        print(f"\n{GREEN}✓ All fast tests passed!{RESET}\n")
    else:
        print(f"\n{RED}✗ Some tests failed{RESET}\n")
        print(stdout)
        if stderr:
            print(stderr)
    
    # Get test count
    success, stdout, _ = run_command("pytest --collect-only -q")
    if success:
        lines = stdout.strip().split('\n')
        for line in lines:
            if 'test' in line.lower():
                print(f"{BLUE}Test count:{RESET} {line}")
    
    # Get coverage if available
    print(f"\n{YELLOW}Checking coverage...{RESET}")
    success, stdout, _ = run_command("pytest -m 'not slow' --cov=level --cov=google_sheet_io --cov=app --cov-report=term-missing -q")
    
    if success and stdout:
        print(stdout)
    
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"\nFor detailed testing info, see:")
    print(f"  - {YELLOW}QUICKTEST.md{RESET} - Quick start guide")
    print(f"  - {YELLOW}TESTING.md{RESET} - Comprehensive documentation")
    print(f"  - {YELLOW}tests/README.md{RESET} - Test suite details")
    print(f"\n{BLUE}{'='*60}{RESET}\n")

if __name__ == "__main__":
    main()
