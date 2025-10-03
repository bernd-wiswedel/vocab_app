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
    """Check if a package version is compatible with current Python version."""
    try:
        # Get package info
        success, output = run_command(["pip", "show", f"{package_name}=={version}"])
        if not success:
            # Try to get info from PyPI
            success, output = run_command(["pip", "index", "versions", package_name])
        
        # This is a simplified check - in practice, you'd need to query PyPI API
        # For now, we'll just warn about known problematic packages
        problematic_versions = {
            "numpy": {"2.3.0": ">=3.11", "2.3.1": ">=3.11", "2.3.2": ">=3.11"},
            "pandas": {"2.3.0": ">=3.11", "2.3.1": ">=3.11", "2.3.2": ">=3.11"}
        }
        
        if package_name in problematic_versions:
            if version in problematic_versions[package_name]:
                current_python = f"{sys.version_info.major}.{sys.version_info.minor}"
                required_python = problematic_versions[package_name][version].replace(">=", "")
                if current_python < required_python:
                    return False
        
        return True
    except:
        return True  # Assume compatible if we can't check

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
                    latest_version = pkg['latest_version']
                    is_compatible = check_python_compatibility(pkg['name'], latest_version)
                    
                    if is_compatible:
                        print(f"  ✅ {pkg['name']}: {pkg['version']} → {latest_version}")
                    else:
                        python_incompatible.append(pkg)
                        print(f"  ⚠️  {pkg['name']}: {pkg['version']} → {latest_version} (requires Python >=3.11)")
                
                if python_incompatible:
                    print(f"\n⚠️  {len(python_incompatible)} packages require Python >=3.11:")
                    print("   Consider upgrading Python or using compatible versions")
                    
                compatible_packages = [pkg for pkg in outdated if check_python_compatibility(pkg['name'], pkg['latest_version'])]
                if compatible_packages:
                    print("\nTo update compatible packages:")
                    print("  pip install --upgrade " + " ".join([pkg['name'] for pkg in compatible_packages]))
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
        
        # Check for Python compatibility issues
        incompatible_packages = []
        for pkg_line in pinned:
            if "==" in pkg_line:
                name, version = pkg_line.split("==")
                if not check_python_compatibility(name, version):
                    incompatible_packages.append(pkg_line)
        
        if incompatible_packages:
            print(f"\n⚠️  {len(incompatible_packages)} packages may be incompatible with Python {get_python_version()}:")
            for pkg in incompatible_packages:
                print(f"    - {pkg}")
            print("   Consider upgrading Python to 3.11+ or using compatible versions")
        
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
    if sys.version_info < (3, 11):
        print("  7. ⚠️  Consider upgrading to Python 3.11+ for latest package versions")

if __name__ == "__main__":
    main()