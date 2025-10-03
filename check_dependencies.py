#!/usr/bin/env python3
"""
Local dependency checker for the vocabulary app.
Run this script to check for outdated dependencies and security issues.

Usage: python check_dependencies.py
"""

import subprocess
import sys
import json
import re
from typing import List, Dict, Any

def run_command(cmd: List[str]) -> tuple[bool, str]:
    """Run a command and return success status and output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"

def get_python_version() -> str:
    """Get current Python version."""
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

def check_python_compatibility(package_name: str, version: str) -> bool:
    """Check if a package version is compatible with current Python version.
    
    Since we only support Python 3.12+, all modern packages should be compatible.
    """
    # With Python 3.12+ requirement, all modern packages are compatible
    if sys.version_info < (3, 12):
        print(f"⚠️  Python {get_python_version()} detected. This project requires Python 3.12+")
        return False
    return True

def check_outdated_packages() -> None:
    """Check for outdated packages."""
    print("🔍 Checking for outdated packages...")
    success, output = run_command(["pip", "list", "--outdated", "--format=json"])
    
    if success:
        try:
            outdated = json.loads(output)
            if outdated:
                print(f"📦 Found {len(outdated)} outdated packages:")
                python_incompatible = []
                
                for pkg in outdated:
                    print(f"  📦 {pkg['name']}: {pkg['version']} → {pkg['latest_version']}")
                
                print("\nTo update all packages:")
                print("  pip install --upgrade " + " ".join([pkg['name'] for pkg in outdated]))
            else:
                print("✅ All packages are up to date!")
        except json.JSONDecodeError:
            print("❌ Failed to parse outdated packages output")
    else:
        print(f"❌ Failed to check outdated packages: {output}")

def check_security_vulnerabilities() -> None:
    """Check for security vulnerabilities using pip-audit."""
    print("\n🔒 Checking for security vulnerabilities...")
    
    # Try pip-audit first
    success, output = run_command(["pip-audit", "--desc", "--format=json"])
    
    if success:
        try:
            audit_data = json.loads(output)
            vulnerabilities = audit_data.get('vulnerabilities', [])
            if vulnerabilities:
                print(f"⚠️  Found {len(vulnerabilities)} security vulnerabilities:")
                for vuln in vulnerabilities:
                    pkg = vuln.get('package', 'Unknown')
                    version = vuln.get('installed_version', 'Unknown')
                    desc = vuln.get('description', 'No description')
                    print(f"  - {pkg} {version}: {desc}")
            else:
                print("✅ No security vulnerabilities found!")
        except json.JSONDecodeError:
            print("❌ Failed to parse security audit output")
    else:
        print("⚠️  pip-audit not available. Installing...")
        install_success, _ = run_command(["pip", "install", "pip-audit"])
        if install_success:
            print("✅ pip-audit installed. Please run the script again.")
        else:
            print("❌ Failed to install pip-audit. You can install it manually with: pip install pip-audit")

def check_requirements_file() -> None:
    """Check if requirements.txt exists and analyze it."""
    print(f"\n📋 Analyzing requirements.txt (Python {get_python_version()})...")
    try:
        with open("requirements.txt", "r") as f:
            lines = f.readlines()
        
        packages = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
        print(f"📦 Found {len(packages)} packages in requirements.txt")
        
        # Check for version pinning
        pinned = [pkg for pkg in packages if "==" in pkg]
        unpinned = [pkg for pkg in packages if "==" not in pkg]
        
        print(f"  - {len(pinned)} packages with exact versions")
        print(f"  - {len(unpinned)} packages without exact versions")
        
        # Verify Python 3.12+ requirement
        if sys.version_info < (3, 12):
            print(f"\n❌ This project requires Python 3.12+, but you're using {get_python_version()}")
            print("   Please upgrade your Python version")
        else:
            print(f"\n✅ Python {get_python_version()} meets the 3.12+ requirement")
        
        if unpinned:
            print("⚠️  Consider pinning these packages for reproducible builds:")
            for pkg in unpinned:
                print(f"    - {pkg}")
                
    except FileNotFoundError:
        print("❌ requirements.txt not found!")

def main():
    """Main function to run all checks."""
    print("🔍 Vocab App Dependency Checker")
    print("=" * 40)
    
    check_requirements_file()
    check_outdated_packages()
    check_security_vulnerabilities()
    
    print("\n💡 Recommendations:")
    print("  1. Review any security vulnerabilities and update affected packages")
    print("  2. Test your application after updating dependencies")
    print("  3. Consider using virtual environments for isolation")
    print("  4. Keep your requirements.txt file up to date")
    print("  5. Use Dependabot for automated dependency updates")
    print(f"  6. Current Python version: {get_python_version()}")
    if sys.version_info < (3, 12):
        print("  7. ❌ This project requires Python 3.12+. Please upgrade your Python version")
    else:
        print("  7. ✅ Python version meets project requirements (3.12+)")

if __name__ == "__main__":
    main()