# Python 3.13+ Required

This project requires **Python 3.13 or later**.

## Why Python 3.13+?

- **Latest features**: Access to newest Python language features and optimizations
- **Modern dependencies**: Full compatibility with latest package versions
- **Performance**: Significant performance improvements in Python 3.13+
- **Security**: Latest security patches and improvements
- **Simplicity**: No need to maintain compatibility with older Python versions

## Upgrading Python

### Using pyenv (Recommended)
```bash
# Install pyenv if not already installed
curl https://pyenv.run | bash

# Install Python 3.13 (latest patch release)
pyenv install 3.13
pyenv global 3.13

# Verify installation
python --version  # Should show Python 3.13.x
```

### Using System Package Manager

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install python3.13 python3.13-venv python3.13-pip
```

#### macOS (using Homebrew)
```bash
brew install python@3.13
```

#### Windows
Download from [python.org](https://www.python.org/downloads/) and install Python 3.13+

## Development Setup

After upgrading Python:

```bash
# Create new virtual environment with Python 3.13+
python3.13 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify everything works
python check_dependencies.py
```

## CI/CD Configuration

The project is configured to use Python 3.13+ in:
- **GitHub Actions**: `.github/workflows/` (tests Python 3.13 and 3.14)
- **Deployment**: `.python-version` contains `3.13`
- **Dependabot**: No compatibility constraints needed

The `.python-version` file deliberately names only the major and minor version,
so every build picks up the newest 3.13 patch release. `runtime.txt`, which the
project used before, is deprecated by the Heroku-style Python buildpacks that
Koyeb builds on and has been removed.

Koyeb currently offers Python 3.9 through 3.13 and defaults to 3.13, so 3.13 is
the newest version the deployment can run. Python 3.14 is already out upstream;
move `.python-version` to `3.14` once Koyeb lists it as supported.

## Benefits of This Approach

✅ **Always use latest package versions**  
✅ **Simplified dependency management**  
✅ **Better performance and security**  
✅ **Cleaner codebase without compatibility workarounds**  
✅ **Future-proof development environment**  

## Compatibility Note

If you need to support older Python versions for specific deployment constraints, consider using Docker with a Python 3.13+ image or upgrading your deployment platform.
