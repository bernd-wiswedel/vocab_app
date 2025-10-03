# Dependency Management Automation

This document explains the automated dependency management setup for the vocabulary learning app.

## 🤖 Automated Solutions

### 1. Dependabot (Recommended)

**File:** `.github/dependabot.yml`

Dependabot automatically:
- Scans dependencies weekly (every Monday)
- Creates pull requests for updates
- Groups minor and patch updates together
- Assigns PRs to the repository owner
- Follows semantic versioning rules

**Benefits:**
- Zero maintenance required
- Automatic security updates
- GitHub native integration
- Detailed PR descriptions with changelogs

**Usage:**
- PRs are automatically created
- Review and merge when ready
- Configure ignore rules in the YAML file

### 2. GitHub Actions Workflow

**File:** `.github/workflows/dependency-check.yml`

This workflow runs weekly and:
- Checks for security vulnerabilities using `pip-audit`
- Identifies outdated packages
- Generates detailed reports
- Can be triggered manually

**Benefits:**
- Comprehensive security scanning
- Detailed reporting
- Manual trigger option
- Integrates with GitHub Issues

**Usage:**
```bash
# Manual trigger from GitHub Actions tab
# Or wait for weekly schedule (Monday 9 AM UTC)
```

## 🛠️ Local Tools

### 1. Dependency Checker

**File:** `check_dependencies.py`

A comprehensive local tool that:
- Analyzes requirements.txt
- Checks for outdated packages
- Scans for security vulnerabilities
- Provides update recommendations

**Usage:**
```bash
python check_dependencies.py
```

**Sample Output:**
```
🔍 Vocab App Dependency Checker
========================================
📋 Analyzing requirements.txt...
📦 Found 21 packages in requirements.txt
🔍 Checking for outdated packages...
📦 Found 3 outdated packages:
  - Flask: 3.1.1 → 3.2.0
  - pandas: 2.3.0 → 2.3.1
🔒 Checking for security vulnerabilities...
✅ No security vulnerabilities found!
```

### 2. Update Helper

**File:** `update_dependencies.py`

An interactive tool for safely updating dependencies:
- Creates automatic backups
- Supports security-only updates
- Interactive confirmation
- Runs basic tests after updates

**Usage:**
```bash
# Update all outdated packages (interactive)
python update_dependencies.py

# Update only security vulnerabilities
python update_dependencies.py --security-only

# Non-interactive mode
python update_dependencies.py --non-interactive

# Security-only, non-interactive
python update_dependencies.py --security-only --non-interactive
```

## 📋 Manual Workflow

For manual dependency management:

1. **Check Status:**
   ```bash
   python check_dependencies.py
   ```

2. **Review Updates:**
   ```bash
   pip list --outdated
   ```

3. **Update Specific Package:**
   ```bash
   pip install --upgrade package_name
   pip freeze > requirements.txt
   ```

4. **Security Updates:**
   ```bash
   python update_dependencies.py --security-only
   ```

5. **Test Application:**
   ```bash
   python app.py
   # Manually test core functionality
   ```

## 🔧 Configuration

### Dependabot Configuration

Edit `.github/dependabot.yml` to customize:

```yaml
# Change schedule
schedule:
  interval: "daily"  # daily, weekly, monthly
  
# Ignore specific updates
ignore:
  - dependency-name: "Flask"
    update-types: ["version-update:semver-major"]
    
# Change reviewers
assignees:
  - "your-github-username"
```

### Security Scanning

The setup includes multiple security tools:

- **pip-audit**: Official PyPA tool for vulnerability scanning
- **safety**: Community-driven vulnerability database
- **GitHub Security Advisories**: Integrated with Dependabot

## 📈 Best Practices

### 1. Regular Monitoring
- Review Dependabot PRs weekly
- Run local checks before major releases
- Monitor security advisories

### 2. Update Strategy
- **Security patches**: Apply immediately
- **Minor updates**: Review and test within a week
- **Major updates**: Plan and test thoroughly

### 3. Testing Protocol
- Run automated tests after updates
- Test core functionality manually
- Deploy to staging environment first

### 4. Documentation
- Use GitHub issue templates for tracking
- Document breaking changes
- Keep changelog updated

## 🚨 Security Priority Packages

Pay special attention to these packages:
- `Flask` (web framework)
- `cryptography` (security library)
- `google-auth*` (authentication)
- Any package with known CVEs

## 📊 Monitoring

### GitHub Insights
- Check "Dependency graph" in repository settings
- Review "Security" tab for vulnerabilities
- Monitor "Actions" tab for workflow results

### Local Monitoring
```bash
# Quick daily check
python check_dependencies.py

# Weekly comprehensive update
python update_dependencies.py --interactive
```

## 🔗 Useful Commands

```bash
# List all dependencies with versions
pip freeze

# Check specific package info
pip show package_name

# Update all packages (careful!)
pip freeze | cut -d= -f1 | xargs pip install --upgrade

# Restore from backup
cp requirements.txt.backup requirements.txt
pip install -r requirements.txt
```

## 📞 Troubleshooting

### Common Issues

1. **Update breaks application:**
   ```bash
   cp requirements.txt.backup requirements.txt
   pip install -r requirements.txt
   ```

2. **Conflicting dependencies:**
   ```bash
   pip check
   # Review conflicts and resolve manually
   ```

3. **Security tools not found:**
   ```bash
   pip install pip-audit safety
   ```

4. **GitHub Actions failing:**
   - Check workflow logs in Actions tab
   - Verify Python version compatibility
   - Review permissions settings

This automation setup provides comprehensive dependency management with minimal manual intervention while maintaining security and stability.