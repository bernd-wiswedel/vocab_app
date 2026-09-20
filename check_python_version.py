#!/usr/bin/env python3
"""
Validate Python version for vocab app.
This script ensures Python 3.13+ is being used.
"""

import sys

def check_python_version():
    """Check if Python version meets requirements."""
    required_major = 3
    required_minor = 13
    
    current_version = (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
    required_version = (required_major, required_minor, 0)
    
    print(f"Current Python version: {'.'.join(map(str, current_version))}")
    print(f"Required Python version: {required_major}.{required_minor}+")
    
    if sys.version_info < required_version:
        print("❌ INCOMPATIBLE: This project requires Python 3.13 or later")
        print("\n📋 How to upgrade:")
        print("  • Using pyenv: pyenv install 3.13 && pyenv global 3.13")
        print("  • Using conda: conda install python=3.13")
        print("  • System install: See PYTHON_VERSION_POLICY.md")
        print("\n💡 After upgrading, recreate your virtual environment:")
        print("  python3.13 -m venv venv")
        print("  source venv/bin/activate")
        print("  pip install -r requirements.txt")
        return False
    else:
        print("✅ COMPATIBLE: Python version meets requirements")
        return True

if __name__ == "__main__":
    is_compatible = check_python_version()
    sys.exit(0 if is_compatible else 1)