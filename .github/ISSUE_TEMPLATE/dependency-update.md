---
name: Dependency Update
about: Track dependency updates and security patches
title: 'deps: Update [PACKAGE_NAME] to [VERSION]'
labels: ['dependencies', 'enhancement']
assignees: ['bernd-wiswedel']
---

## Dependency Update Request

### Package Information
- **Package Name:** 
- **Current Version:** 
- **Target Version:** 
- **Update Type:** [ ] Security patch [ ] Bug fix [ ] Feature update [ ] Major version

### Reason for Update
<!-- Explain why this update is needed -->
- [ ] Security vulnerability (CVE: )
- [ ] Bug fix
- [ ] New features needed
- [ ] Compatibility with other dependencies
- [ ] Performance improvements

### Impact Assessment
- [ ] Breaking changes expected
- [ ] Requires code changes
- [ ] Affects core functionality
- [ ] Test coverage sufficient

### Checklist
- [ ] Reviewed changelog/release notes
- [ ] Updated requirements.txt
- [ ] Ran dependency checker (`python check_dependencies.py`)
- [ ] Tested locally
- [ ] All tests pass
- [ ] Documentation updated (if needed)

### Testing Notes
<!-- Describe what testing was performed -->

### Related Issues
<!-- Link any related issues -->
Closes #