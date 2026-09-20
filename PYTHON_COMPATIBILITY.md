# Python Version Compatibility Guide

## The Problem

Your build pipeline failed because some dependencies require Python 3.11+, but your deployment environment was using an older Python version.

## Error Analysis

```
ERROR: Ignored the following versions that require a different python version: 2.3.0 Requires-Python >=3.11
```

This error occurs when:
- Dependencies like `numpy>=2.3.0` or `pandas>=2.3.0` require Python 3.11+
- Your deployment platform (Heroku, Railway, etc.) uses Python 3.10 or older
- Dependabot creates PRs without checking Python version compatibility

## Solutions Implemented

### 1. ✅ Runtime Configuration (`.python-version`)
```
3.13
```
This tells Koyeb, Heroku and similar buildpack platforms which Python to use.
Only the major and minor version is named, so each build picks up the newest
3.13 patch release. The older `runtime.txt` file is deprecated by these
buildpacks and is no longer part of this project.

### 2. ✅ Fixed Requirements (`requirements.txt`)
Downgraded problematic packages to Python 3.10-compatible versions:
- `numpy==1.26.4` (instead of 2.3.1)
- `pandas==2.2.3` (instead of 2.3.0)

### 3. ✅ Enhanced Dependabot Configuration
Added ignore rules for packages requiring Python 3.11+:
```yaml
ignore:
  - dependency-name: "numpy"
    versions: [">=2.3.0"]
  - dependency-name: "pandas" 
    versions: [">=2.3.0"]
```

### 4. ✅ Python Compatibility Checker
Enhanced `check_dependencies.py` to warn about Python version mismatches.

### 5. ✅ CI/CD Compatibility Tests
Added GitHub Actions workflow to test multiple Python versions.

## Deployment Platform Setup

### Koyeb (this project's deployment)
1. ✅ `.python-version` with `3.13`
2. Koyeb supports Python 3.9 through 3.13 and defaults to 3.13, so 3.13 is the
   newest version available there. Upstream Python is already at 3.14 — bump
   `.python-version` once Koyeb lists 3.14 as supported.

### Heroku
1. ✅ `.python-version` with `3.13`
2. Verify in the build logs: `Installing Python 3.13.x`

### Railway
1. ✅ `.python-version` with `3.13`
2. Or set a `PYTHON_VERSION` environment variable

### Render
1. ✅ `.python-version` with `3.13`
2. Or specify in render.yaml

### Docker
```dockerfile
FROM python:3.13-slim
# ... rest of Dockerfile
```

## Verification Steps

### 1. Test Locally
```bash
# Check current Python version
python --version

# Test dependencies
python check_dependencies.py

# Try installation
pip install -r requirements.txt
```

### 2. Test in CI/CD
The `python-compatibility.yml` workflow tests Python 3.13 and 3.14.

### 3. Monitor Dependabot PRs
Dependabot will now avoid creating PRs for incompatible package versions.

## Troubleshooting

### If Build Still Fails
1. **Check platform Python version:**
   ```bash
   python --version
   ```

2. **Verify `.python-version` is read:**
   - Look for the installed Python version in the build logs
   - Some platforms require a specific Python version format

3. **Manual package downgrade:**
   ```bash
   pip install 'numpy<2.3.0' 'pandas<2.3.0'
   pip freeze > requirements.txt
   ```

### If You Want a Newer Python
1. **Update all environments:**
   - Local development: `pyenv install 3.13`
   - CI/CD: Already updated to Python 3.13
   - Deployment: `.python-version` handles this

2. **Remove Dependabot ignore rules:**
   - Edit `.github/dependabot.yml`
   - Remove numpy/pandas version restrictions

3. **Update requirements:**
   ```bash
   pip install --upgrade numpy pandas
   pip freeze > requirements.txt
   ```

## Current Status
✅ Fixed immediate build failure  
✅ Set deployment to Python 3.13 via `.python-version`  
✅ Protected against future incompatible updates  
✅ Added compatibility checking tools  

The sections above about Python 3.10 and 3.11 describe the original incident and
are kept for context only. The project now requires Python 3.13+ everywhere; see
[PYTHON_VERSION_POLICY.md](PYTHON_VERSION_POLICY.md).