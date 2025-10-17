# Release Process Guide

This guide explains how to create and publish a new release for USDXFixGap.

## Pre-Release Checklist

- [ ] All tests passing (`.\run.bat test`)
- [ ] Version number updated in `VERSION` file
- [ ] CHANGELOG.md updated with new version section
- [ ] Documentation updated
- [ ] Breaking changes documented
- [ ] Migration guide written (if needed)

---

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Breaking changes, incompatible API changes
- **MINOR** (x.Y.0): New features, backward-compatible
- **PATCH** (x.y.Z): Bug fixes, backward-compatible

**Examples:**
- Breaking storage location change: `1.0.0` → `1.1.0` (MINOR, with migration)
- New detection method: `1.1.0` → `1.2.0` (MINOR)
- Bug fix: `1.1.0` → `1.1.1` (PATCH)

---

## Step-by-Step Release Process

### 1. Update Version

Edit `VERSION` file:
```
v1.1.0
```

### 2. Update CHANGELOG.md

Move `[Unreleased]` changes to new version section:

```markdown
## [1.1.0] - 2025-10-12

### ⚠️ BREAKING CHANGES
- Storage location changed (see Migration Guide)

### ✨ Added
- Cross-platform storage support
- Configurable model paths

### 🐛 Fixed
- MDX detection crash on songs without intro
- TorchAudio warnings

[1.1.0]: https://github.com/vtietz/usdxfixgapgui/compare/v1.0.0...v1.1.0
```

### 3. Commit Changes

```bash
git add VERSION CHANGELOG.md
git commit -m "chore: Bump version to v1.1.0"
git push origin vad_detection_method
```

### 4. Create Git Tag

```bash
git tag -a v1.1.0 -m "Release v1.1.0 - Cross-Platform Storage & Bug Fixes"
git push origin v1.1.0
```

### 5. Build Release Artifacts

**Windows:**
```bash
.\build.bat
```
Creates: `build\usdxfixgap\usdxfixgap.exe`

**Linux:**
```bash
./build_linux.sh
```
Creates: `dist/usdxfixgap`

**macOS:**
```bash
./build_macos.sh
```
Creates: `dist/usdxfixgap.app`

### 6. Package Artifacts

**Windows:**
```bash
cd build\usdxfixgap
7z a usdxfixgap-v1.1.0-windows.zip *
```

**Linux:**
```bash
cd dist
tar -czf usdxfixgap-v1.1.0-linux.tar.gz usdxfixgap
```

**macOS:**
```bash
cd dist
tar -czf usdxfixgap-v1.1.0-macos.tar.gz usdxfixgap.app
```

### 7. Generate Checksums

```bash
# Windows (PowerShell)
Get-FileHash usdxfixgap-v1.1.0-windows.zip -Algorithm SHA256

# Linux/macOS
sha256sum usdxfixgap-v1.1.0-linux.tar.gz
sha256sum usdxfixgap-v1.1.0-macos.tar.gz
```

### 8. Create GitHub Release

1. Go to: https://github.com/vtietz/usdxfixgapgui/releases/new
2. **Tag**: Select `v1.1.0`
3. **Title**: `v1.1.0 - Cross-Platform Storage & Bug Fixes`
4. **Description**: Copy from `.github/RELEASE_TEMPLATE.md` and customize
5. **Attach files**: Upload the 3 platform packages
6. **Update checksums** in release notes
7. **Mark as pre-release** if testing needed
8. Click **Publish release**

---

## Release Notes Template

Use this structure (from `.github/RELEASE_TEMPLATE.md`):

### Title
`v1.1.0 - Cross-Platform Storage & Bug Fixes`

### Description

```markdown
### ⚠️ Important: Storage Location Changed

[Explain breaking changes clearly]

### ✨ What's New

[List new features with brief descriptions]

### 🐛 Bug Fixes

[List fixed issues]

### 📥 Installation

[Platform-specific download instructions]

### 🔄 Upgrading from v1.0.0

[Step-by-step upgrade guide]

### 📚 Documentation

[Links to relevant docs]

### Checksums

[SHA256 hashes]
```

---

## Announcing the Release

### On GitHub
- Release notes are automatically visible on Releases page
- Users watching the repo get notified

### In README.md (Optional)
Add a banner at the top:
```markdown
> **📢 Latest Release: v1.1.0** - [Download](https://github.com/vtietz/usdxfixgapgui/releases/latest) | [Changelog](CHANGELOG.md)
```

### Discord/Forum (If Applicable)
Post announcement with:
- What's new
- Download link
- Migration guide link

---

## Post-Release

### 1. Verify Release
- [ ] Download links work
- [ ] Checksums match
- [ ] Installation works on each platform

### 2. Monitor Issues
- Watch for bug reports
- Respond to user questions
- Plan hotfix if needed

### 3. Update Documentation
- Ensure README reflects latest version
- Update screenshots if UI changed

---

## Hotfix Process (Patch Release)

If critical bug found after release:

1. **Create hotfix branch:**
   ```bash
   git checkout -b hotfix/v1.1.1 v1.1.0
   ```

2. **Fix the bug**
   ```bash
   # Make fixes
   git commit -m "fix: Critical bug in MDX detection"
   ```

3. **Update version:**
   - `VERSION`: `v1.1.1`
   - `CHANGELOG.md`: Add `[1.1.1]` section

4. **Merge and release:**
   ```bash
   git checkout main
   git merge hotfix/v1.1.1
   git tag v1.1.1
   git push --tags
   ```

5. **Build and publish** as normal

---

## Communication Templates

### Breaking Change Notice
```
⚠️ IMPORTANT: This release includes breaking changes to storage locations.

Before upgrading:
1. Review the migration guide
2. Backup your config.ini if desired
3. Note the new data location for your platform

The app will create a new config automatically. Your old data remains 
untouched in the app directory.

See full details: [Migration Guide](link)
```

### Bug Fix Notice
```
This release fixes a critical bug affecting songs without intro silence.
If you experienced crashes with certain songs, please update.

See: [Changelog](link)
```

### New Feature Notice
```
🎉 Now available: Cross-platform storage support!

Your data is now stored in the proper OS location:
- Windows: %LOCALAPPDATA%\USDXFixGap\
- Linux: ~/.local/share/USDXFixGap/
- macOS: ~/Library/Application Support/USDXFixGap/

Benefits: Multi-user support, update-safe, follows OS standards

See: [Announcement](link)
```

---

## Checklist Summary

**Before Tag:**
- [ ] Tests pass
- [ ] VERSION updated
- [ ] CHANGELOG.md updated
- [ ] Docs updated
- [ ] Commit and push

**Release:**
- [ ] Create tag
- [ ] Build all platforms
- [ ] Package artifacts
- [ ] Generate checksums
- [ ] Create GitHub release
- [ ] Upload artifacts
- [ ] Publish

**After Release:**
- [ ] Test downloads
- [ ] Verify checksums
- [ ] Monitor issues
- [ ] Announce release

---

## Tools

**Recommended:**
- [GitHub CLI](https://cli.github.com/) - `gh release create v1.1.0 *.zip *.tar.gz`
- [7-Zip](https://www.7-zip.org/) - For creating ZIP archives
- [Git](https://git-scm.com/) - Version control

**Optional:**
- [Conventional Commits](https://www.conventionalcommits.org/) - Commit message standard
- [Release Drafter](https://github.com/release-drafter/release-drafter) - Auto-generate release notes
