# Python 3.12+ Required

This project requires **Python 3.12 or later**.

## Why Python 3.12+?

- **Latest features**: Access to newest Python language features and optimizations
- **Modern dependencies**: Full compatibility with latest package versions
- **Performance**: Significant performance improvements in Python 3.12+
- **Security**: Latest security patches and improvements
- **Simplicity**: No need to maintain compatibility with older Python versions

## Upgrading Python

### Using pyenv (Recommended)
```bash
# Install pyenv if not already installed
curl https://pyenv.run | bash

# Install Python 3.12
pyenv install 3.12.7
pyenv global 3.12.7

# Verify installation
python --version  # Should show Python 3.12.7
```

### Using System Package Manager

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-pip
```

#### macOS (using Homebrew)
```bash
brew install python@3.12
```

#### Windows
Download from [python.org](https://www.python.org/downloads/) and install Python 3.12+

## Development Setup

After upgrading Python:

```bash
# Create new virtual environment with Python 3.12+
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify everything works
python check_dependencies.py
```

## CI/CD Configuration

The project is configured to use Python 3.12+ in:
- **GitHub Actions**: `.github/workflows/` (tests Python 3.12 and 3.13)
- **Deployment**: `runtime.txt` specifies `python-3.12.7`
- **Dependabot**: No compatibility constraints needed

## Benefits of This Approach

✅ **Always use latest package versions**  
✅ **Simplified dependency management**  
✅ **Better performance and security**  
✅ **Cleaner codebase without compatibility workarounds**  
✅ **Future-proof development environment**  

## Compatibility Note

If you need to support older Python versions for specific deployment constraints, consider using Docker with Python 3.12+ image or upgrading your deployment platform.