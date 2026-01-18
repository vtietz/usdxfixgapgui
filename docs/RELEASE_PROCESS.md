# Release Process Guide

Quick reference for creating USDXFixGap releases.

## Pre-Release Checklist

- [ ] All tests passing (`.\run.bat test`)
- [ ] Code quality passing (`.\run.bat analyze`)
- [ ] Release notes created: `docs/releases/vX.Y.Z.md` (see `.github/RELEASE_TEMPLATE.md`)
- [ ] `CHANGELOG.md` updated

**Note:** The `VERSION` file is automatically updated when using `run.bat set-version` (recommended method below).

---

## VERSION File Requirements

⚠️ **CRITICAL**: Must be UTF-8 without BOM, single line: `vX.Y.Z`

**Using `run.bat set-version` (recommended):** Automatically creates correct encoding.

**Manual editing:** Ensure UTF-8 without BOM. Verify encoding (PowerShell):
```powershell
(Get-Content VERSION -Encoding Byte)[0..3]
# Should be: 118 50 46 48 (v2.0)
# NOT: 255 254 or 239 187 191 (BOM detected)
```

**Why**: UTF-16 or UTF-8 with BOM causes garbled release names ("��vX.Y.Z") on Linux.

---

## Release Steps

### Method 1: Automated (Recommended)

Use the `set-version` command to automate VERSION file updates and tagging:

```bash
# Windows
run.bat set-version v2.0.0-rc1

# Linux/macOS
./run.sh set-version v2.0.0-rc1
```

**What it does:**
1. Updates `VERSION` file (UTF-8 without BOM)
2. Commits VERSION file: `Chore: Set version to v2.0.0-rc1`
3. Pushes commit to remote
4. Creates git tag `v2.0.0-rc1`
5. Pushes tag to remote (triggers GitHub Actions build)

**Then manually:**
- Create `docs/releases/v2.0.0.md` (use `.github/RELEASE_TEMPLATE.md`)
- Update `CHANGELOG.md`
- Commit and push these changes

**For final release:**
```bash
run.bat set-version v2.0.0
./run.sh set-version v2.0.0
```

### Method 2: Manual (Legacy)

If you prefer manual control:

```bash
# Edit VERSION: v2.0.0 (UTF-8 without BOM!)
# Create docs/releases/v2.0.0.md (use .github/RELEASE_TEMPLATE.md)
# Update CHANGELOG.md
git add VERSION CHANGELOG.md docs/releases/
git commit -m "Chore: Bump version to v2.0.0"
git push origin main
git tag v2.0.0
git push origin v2.0.0
```

---

## Testing with RC Releases

### 1. Create RC Release

```bash
# Automated (recommended)
run.bat set-version v2.0.0-rc1
./run.sh set-version v2.0.0-rc1

# OR Manual
git tag v2.0.0-rc1
git push origin v2.0.0-rc1
```

### 2. Verify RC Build

**Verify:**
- [ ] 5 builds succeed (~250MB each)
- [ ] Filenames:
  - `usdxfixgap-v2.0.0-windows.exe`
  - `usdxfixgap-v2.0.0-linux.tar.gz`
  - `usdxfixgap-v2.0.0-macos-arm64.tar.gz` (Apple Silicon)
  - `usdxfixgap-v2.0.0-macos-x64.tar.gz` (Intel)
  - Plus portable versions for each platform
- [ ] Release notes from `docs/releases/v2.0.0.md`
- [ ] "Pre-release" badge shown
- [ ] No subscriber emails sent

### 3. Clean Up RC (Optional)

If you need to recreate the RC:
```bash
# Delete remote tag
git push origin :refs/tags/v2.0.0-rc1

# Delete GitHub release
gh release delete v2.0.0-rc1 --yes

# Recreate with set-version (overwrites existing tag)
run.bat set-version v2.0.0-rc1
```

**Note:** `set-version` uses force push, so you can recreate tags without manual deletion.

### 4. Create Final Release

```bash
# Automated (recommended)
run.bat set-version v2.0.0
./run.sh set-version v2.0.0

# OR Manual
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
# Create hotfix branch
git checkout -b hotfix/v2.0.1 v2.0.0

# Fix bug, commit changes
git add .
git commit -m "Fix: <description>"

# Merge back to main
git checkout main
git merge hotfix/v2.0.1
git push origin main

# Update release notes and CHANGELOG
# Create docs/releases/v2.0.1.md
# Update CHANGELOG.md
git add docs/releases/v2.0.1.md CHANGELOG.md
git commit -m "Docs: Add v2.0.1 release notes"
git push

# Test with RC (recommended)
run.bat set-version v2.0.1-rc1

# After verification, create final release
run.bat set-version v2.0.1
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
# === RECOMMENDED METHOD ===
# Test release (no notifications)
run.bat set-version v2.0.0-rc1
./run.sh set-version v2.0.0-rc1

# Final release (notifies subscribers)
run.bat set-version v2.0.0
./run.sh set-version v2.0.0

# === MANUAL METHOD ===
# Test release
git tag v2.0.0-rc1 && git push origin v2.0.0-rc1

# Final release
git tag v2.0.0 && git push origin v2.0.0

# Delete RC (if needed)
git push origin :refs/tags/v2.0.0-rc1

# === UTILITIES ===
# Check VERSION encoding (PowerShell)
(Get-Content VERSION -Encoding Byte)[0..3]  # Should be: 118 50 46 48

# Monitor builds
https://github.com/vtietz/usdxfixgapgui/actions
```

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Release name "��vX.Y.Z" | VERSION has UTF-16/BOM | Use `run.bat set-version` or convert to UTF-8 without BOM |
| Build 6-15MB | Missing dependencies | Check `usdxfixgap.spec` hidden_imports |
| Build >1GB | CUDA included | Check `usdxfixgap.spec` exclude_binaries |
| Empty release notes | Missing file | Create `docs/releases/vX.Y.Z.md` |
| Wrong filenames | VERSION whitespace/dots | Use `run.bat set-version` or clean VERSION file |
| Tag already exists | Need to recreate | Use `run.bat set-version` (force pushes) or delete tag manually |

---

**See also:**
- [Semantic Versioning](https://semver.org/)
- `.github/RELEASE_TEMPLATE.md`
- `docs/DEVELOPMENT.md` (for `set-version` details)
