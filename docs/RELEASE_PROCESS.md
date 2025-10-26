# Release Process Guide

Quick reference for creating USDXFixGap releases.

## Pre-Release Checklist

- [ ] All tests passing (`.\run.bat test`)
- [ ] Code quality passing (`.\run.bat analyze`)
- [ ] `VERSION` file updated (UTF-8 without BOM, format: `vX.Y.Z`)
- [ ] Release notes created: `docs/releases/vX.Y.Z.md` (see `.github/RELEASE_TEMPLATE.md`)
- [ ] `CHANGELOG.md` updated

---

## VERSION File Requirements

⚠️ **CRITICAL**: Must be UTF-8 without BOM, single line: `vX.Y.Z`

**Verify encoding** (PowerShell):
```powershell
(Get-Content VERSION -Encoding Byte)[0..3]
# Should be: 118 50 46 48 (v2.0)
# NOT: 255 254 or 239 187 191 (BOM detected)
```

**Why**: UTF-16 or UTF-8 with BOM causes garbled release names ("��vX.Y.Z") on Linux.

---

## Release Steps

### 1. Update Files

```bash
# Edit VERSION: v2.0.0
# Create docs/releases/v2.0.0.md (use .github/RELEASE_TEMPLATE.md)
# Update CHANGELOG.md
git add VERSION CHANGELOG.md docs/releases/
git commit -m "chore: Bump version to v2.0.0"
git push origin main
```

### 2. Test with RC (Recommended)

```bash
git tag v2.0.0-rc1
git push origin v2.0.0-rc1
```

**Verify:**
- [ ] 3 builds succeed (~250MB each)
- [ ] Filenames: `usdxfixgap-v2.0.0-{windows.exe,linux.tar.gz,macos.tar.gz}`
- [ ] Release notes from `docs/releases/v2.0.0.md`
- [ ] "Pre-release" badge shown
- [ ] No subscriber emails sent

**Clean up:**
```bash
git push origin :refs/tags/v2.0.0-rc1
gh release delete v2.0.0-rc1 --yes
```

### 3. Create Final Release

```bash
git tag v2.0.0
git push origin v2.0.0
```

**What happens:** GitHub Actions builds executables, creates release, **notifies subscribers**.

---

## Pre-Release Tag Patterns

| Tag Pattern | Pre-Release | Notifies Subscribers |
|-------------|-------------|----------------------|
| `v2.0.0-rc1` | ✅ Yes | ❌ No |
| `v2.0.0-beta` | ✅ Yes | ❌ No |
| `v2.0.0-alpha` | ✅ Yes | ❌ No |
| `v2.0.0` | ❌ No | ✅ Yes |

Workflow auto-detects pattern `-(rc|beta|alpha)` and sets `prerelease: true` accordingly.

---

## Hotfix Process

```bash
git checkout -b hotfix/v2.0.1 v2.0.0
# Fix bug, commit
# Update VERSION to v2.0.1
# Create docs/releases/v2.0.1.md
# Update CHANGELOG.md
git checkout main && git merge hotfix/v2.0.1
git push origin main
git tag v2.0.1-rc1 && git push origin v2.0.1-rc1  # Test first
# After verification:
git tag v2.0.1 && git push origin v2.0.1
```

---

## Key Files

- `VERSION` - Version number (UTF-8 without BOM)
- `docs/releases/vX.Y.Z.md` - Release notes (see `.github/RELEASE_TEMPLATE.md`)
- `usdxfixgap.spec` - PyInstaller config (hidden imports, CUDA exclusion)
- `.github/workflows/release.yml` - Automated build workflow
- `CHANGELOG.md` - Version history

## Quick Reference

```bash
# Test release (no notifications)
git tag v2.0.0-rc1 && git push origin v2.0.0-rc1

# Final release (notifies subscribers)
git tag v2.0.0 && git push origin v2.0.0

# Delete RC
git push origin :refs/tags/v2.0.0-rc1

# Check VERSION encoding
(Get-Content VERSION -Encoding Byte)[0..3]  # Should be: 118 50 46 48

# Monitor builds
https://github.com/vtietz/usdxfixgapgui/actions
```

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Release name "��vX.Y.Z" | VERSION has UTF-16/BOM | Convert to UTF-8 without BOM |
| Build 6-15MB | Missing dependencies | Check `usdxfixgap.spec` hidden_imports |
| Build >1GB | CUDA included | Check `usdxfixgap.spec` exclude_binaries |
| Empty release notes | Missing file | Create `docs/releases/vX.Y.Z.md` |
| Wrong filenames | VERSION whitespace/dots | Clean VERSION file |

---

**See also:** [Semantic Versioning](https://semver.org/), `.github/RELEASE_TEMPLATE.md`
