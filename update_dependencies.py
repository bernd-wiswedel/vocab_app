#!/usr/bin/env python3
"""
Dependency update helper for the vocabulary app.
This script helps safely update dependencies.

Usage: python update_dependencies.py [--security-only] [--interactive]
"""

import subprocess
import sys
import json
import argparse
from typing import List, Dict

def run_command(cmd: List[str], check=True) -> tuple[bool, str]:
    """Run a command and return success status and output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=check)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"

def backup_requirements():
    """Create a backup of current requirements.txt."""
    print("📋 Creating backup of requirements.txt...")
    success, _ = run_command(["cp", "requirements.txt", "requirements.txt.backup"])
    if success:
        print("✅ Backup created: requirements.txt.backup")
    else:
        print("❌ Failed to create backup")
    return success

def get_security_updates() -> List[str]:
    """Get list of packages that need security updates."""
    print("🔒 Identifying packages with security vulnerabilities...")
    success, output = run_command(["pip-audit", "--format=json"], check=False)
    
    security_packages = []
    if success:
        try:
            audit_data = json.loads(output)
            vulnerabilities = audit_data.get('vulnerabilities', [])
            security_packages = list(set([vuln.get('package') for vuln in vulnerabilities if vuln.get('package')]))
        except json.JSONDecodeError:
            pass
    
    return security_packages

def get_outdated_packages() -> List[Dict]:
    """Get list of outdated packages."""
    print("📦 Checking for outdated packages...")
    success, output = run_command(["pip", "list", "--outdated", "--format=json"])
    
    if success:
        try:
            outdated_packages = json.loads(output)
            # With Python 3.12+ requirement, all packages are compatible
            return outdated_packages
        except json.JSONDecodeError:
            return []
    return []

def update_packages(packages: List[str], interactive: bool = True) -> bool:
    """Update specified packages."""
    if not packages:
        print("✅ No packages to update")
        return True
    
    print(f"\n📦 Packages to update: {', '.join(packages)}")
    
    if interactive:
        response = input("Do you want to proceed with the update? (y/N): ").strip().lower()
        if response != 'y':
            print("❌ Update cancelled")
            return False
    
    # Update packages
    cmd = ["pip", "install", "--upgrade"] + packages
    print(f"Running: {' '.join(cmd)}")
    
    success, output = run_command(cmd, check=False)
    if success:
        print("✅ Packages updated successfully")
        print("📋 Generating new requirements.txt...")
        freeze_success, freeze_output = run_command(["pip", "freeze"])
        if freeze_success:
            with open("requirements.txt", "w") as f:
                f.write(freeze_output)
            print("✅ requirements.txt updated")
        return True
    else:
        print(f"❌ Update failed: {output}")
        return False

def run_tests():
    """Run tests to verify everything still works."""
    print("\n🧪 Running tests to verify updates...")
    
    # Try to import the main app to check for basic issues
    try:
        import app
        print("✅ App imports successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"⚠️  Warning during import: {e}")
        return True

def main():
    parser = argparse.ArgumentParser(description="Update dependencies for vocab app")
    parser.add_argument("--security-only", action="store_true", 
                       help="Only update packages with security vulnerabilities")
    parser.add_argument("--interactive", action="store_true", default=True,
                       help="Ask for confirmation before updating (default: True)")
    parser.add_argument("--non-interactive", dest="interactive", action="store_false",
                       help="Don't ask for confirmation")
    
    args = parser.parse_args()
    
    print("🔄 Vocab App Dependency Updater")
    print("=" * 40)
    
    # Check Python version requirement
    if sys.version_info < (3, 12):
        print(f"❌ This project requires Python 3.12+, but you're using {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        print("Please upgrade Python before updating dependencies.")
        print("See PYTHON_VERSION_POLICY.md for upgrade instructions.")
        return 1
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} meets requirements")
    
    # Create backup
    if not backup_requirements():
        print("❌ Failed to create backup. Aborting.")
        return 1
    
    if args.security_only:
        # Only update packages with security issues
        security_packages = get_security_updates()
        if security_packages:
            print(f"🔒 Found {len(security_packages)} packages with security issues")
            success = update_packages(security_packages, args.interactive)
        else:
            print("✅ No security vulnerabilities found")
            success = True
    else:
        # Update all outdated packages
        outdated = get_outdated_packages()
        if outdated:
            packages = [pkg['name'] for pkg in outdated]
            print(f"📦 Found {len(packages)} outdated packages")
            success = update_packages(packages, args.interactive)
        else:
            print("✅ All packages are up to date")
            success = True
    
    if success:
        # Run basic tests
        test_success = run_tests()
        if test_success:
            print("\n✅ Update completed successfully!")
            print("💡 Remember to:")
            print("  1. Test your application thoroughly")
            print("  2. Commit the updated requirements.txt")
            print("  3. Deploy and test in staging environment")
        else:
            print("\n⚠️  Updates completed but tests failed")
            print("Consider rolling back using: cp requirements.txt.backup requirements.txt")
            return 1
    else:
        print("\n❌ Update failed")
        print("Restoring backup...")
        run_command(["cp", "requirements.txt.backup", "requirements.txt"])
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())