# GitHub Workflows Guide

This document explains the automated workflows configured for the USDXFixGap project.

---

## 📋 Available Workflows

### 1. CI - Tests & Code Quality (`ci.yml`)

**Triggers:**
- Every push to `main`, `develop`, or `mdx_only_detection_method` branches
- Every pull request to `main` or `develop`

**What it does:**
1. ✅ Runs all tests with pytest
2. 🔍 Checks code complexity (Lizard)
3. 🎨 Checks code style (Flake8)
4. 🔎 Checks types (MyPy)
5. 🖌️ Checks formatting (Black)

**Purpose:**
Ensures code quality and all tests pass before merging changes.

**Requirements:**
- Tests must pass (failures will block)
- Code quality checks are informational (continue-on-error: true)

---

### 2. Release - Multi-Platform Builds (`release.yml`)

**Triggers:**
- **Automatic:** When you push a version tag (e.g., `v2.0.0`, `v2.0.0-rc1`)

**What it does:**
1. 🪟 Builds Windows executable (`.exe`)
2. 🐧 Builds Linux executable (`.tar.gz`)
3. 🍎 Builds macOS executable (`.tar.gz`)
4. 📦 Creates GitHub Release with all binaries
5. 📝 Uses release notes from `docs/releases/{VERSION}.md`
6. 🔔 Auto-detects pre-release from tag pattern (`-rc`, `-beta`, `-alpha`)

**Build Configuration:**
- Uses `usdxfixgap.spec` (PyInstaller config)
- CPU-only PyTorch (~250MB per executable)
- Excludes CUDA libraries (prevents 3GB bloat)
- Hidden imports: PySide6, torch, demucs, soundfile, librosa

**Artifacts:**
- `usdxfixgap-{VERSION}-windows.exe`
- `usdxfixgap-{VERSION}-linux.tar.gz`
- `usdxfixgap-{VERSION}-macos.tar.gz`

**Pre-Release Detection:**
| Tag | Pre-Release | Subscribers Notified |
|-----|-------------|---------------------|
| `v2.0.0-rc1` | Yes | No |
| `v2.0.0-beta` | Yes | No |
| `v2.0.0-alpha` | Yes | No |
| `v2.0.0` | No | Yes |

---

## 🚀 How to Create a Release

**See:** `docs/RELEASE_PROCESS.md` for detailed instructions.

**Quick version:**

```bash
# 1. Update files
# Edit VERSION: v2.0.0
# Create docs/releases/v2.0.0.md
# Update CHANGELOG.md
git commit -am "chore: Bump version to v2.0.0"
git push

# 2. Test with RC (recommended)
git tag v2.0.0-rc1 && git push origin v2.0.0-rc1

# 3. After verification, create final release
git tag v2.0.0 && git push origin v2.0.0
```

**Important:**
- VERSION file must be UTF-8 without BOM
- RC tags (`-rc`, `-beta`, `-alpha`) don't notify subscribers
- Release notes loaded from `docs/releases/{VERSION}.md`

---

## 📝 Release Notes Format

**Location:** `docs/releases/{VERSION}.md` (VERSION from VERSION file, not tag name)

**Template:** See `.github/RELEASE_TEMPLATE.md`

**Example:** If VERSION file contains `v2.0.0`, release notes should be at `docs/releases/v2.0.0.md`

**Note:** RC tags (`v2.0.0-rc1`) still use `v2.0.0.md` for release notes.

---

## 🔧 Dependencies Management

**Development:**
```bash
.\run.bat install    # Runtime + dev dependencies
```

**Key Files:**
- `requirements.txt` - Runtime dependencies
- `requirements-dev.txt` - Dev tools (includes requirements.txt)
- `requirements-build.txt` - CI/CD build dependencies (CPU-only PyTorch)

**Build Process:**
- GitHub Actions uses `usdxfixgap.spec` + `requirements-build.txt`
- CPU-only PyTorch (~250MB executables)
- CUDA libraries excluded via spec file

---

## 🔍 Workflow Details

### CI Workflow

**File:** `.github/workflows/ci.yml`

**Environment:**
- Ubuntu Latest
- Python 3.11
- System dependencies: libsndfile1, ffmpeg, portaudio19-dev
- QT_QPA_PLATFORM=offscreen (for headless Qt testing)

**Code Quality Thresholds:**
- Complexity: CCN ≤ 15, NLOC ≤ 100
- Line length: 120 characters
- Black formatting enforced

**Failure Behavior:**
- ❌ Tests must pass (hard failure)
- ⚠️ Code quality issues are warnings only

### Release Workflow

**File:** `.github/workflows/release.yml`

**Build Matrix:**
| Platform | Runner | Python | System Deps |
|----------|--------|--------|-------------|
| Windows | windows-latest | 3.11 | None |
| Linux | ubuntu-latest | 3.11 | libsndfile1, ffmpeg, portaudio19-dev |
| macOS | macos-latest | 3.11 | portaudio, ffmpeg (via brew) |

**Artifact Retention:**
- Build artifacts: 7 days
- Release binaries: Permanent (on GitHub Releases)

**Permissions:**
- `contents: write` for creating releases
- GITHUB_TOKEN automatically provided

---

## 🐛 Troubleshooting

### CI Failures

```bash
.\run.bat test      # Run tests locally
.\run.bat analyze   # Code quality check
```

### Release Failures

**Common issues:**
- VERSION file encoding (must be UTF-8 without BOM)
- Missing release notes file (`docs/releases/vX.Y.Z.md`)
- Build size issues (check `usdxfixgap.spec`)

**See:** `docs/RELEASE_PROCESS.md` for detailed troubleshooting.

---

## 📦 Release Checklist

**See `docs/RELEASE_PROCESS.md` for complete checklist.**

**Quick version:**
- [ ] Tests pass (`.\run.bat test`)
- [ ] Code quality passes (`.\run.bat analyze`)
- [ ] VERSION file updated (UTF-8 without BOM)
- [ ] Release notes created (`docs/releases/vX.Y.Z.md`)
- [ ] Test with RC tag first (`v2.0.0-rc1`)
- [ ] Create final tag (`v2.0.0`)

---

## 🔄 Workflow Maintenance

### Updating Python Version

Edit `.github/workflows/ci.yml` and `.github/workflows/release.yml`:
```yaml
python-version: '3.11'  # Change version here
```

### Modifying Build Configuration

Edit `usdxfixgap.spec` for PyInstaller settings:
- `hiddenimports` - Add dynamic imports
- `exclude_binaries` - Filter out unwanted libraries (e.g., CUDA)
- `excludes` - Exclude Python modules

---

## 📚 Additional Resources

- **Release Process:** `docs/RELEASE_PROCESS.md`
- **Coding Standards:** `docs/coding-standards.md`
- **Development Guide:** `docs/DEVELOPMENT.md`
- **GitHub Actions:** https://docs.github.com/en/actions
- **PyInstaller:** https://pyinstaller.org/

---

## 🎯 Summary

**Quick Commands:**
```bash
.\run.bat test           # Run tests
.\run.bat analyze        # Code quality

# Release
git tag v2.0.0-rc1 && git push origin v2.0.0-rc1  # Test
git tag v2.0.0 && git push origin v2.0.0          # Final
```

**Key Points:**
1. CI runs on every push/PR
2. Releases triggered by Git tags
3. RC tags (`-rc`, `-beta`, `-alpha`) = pre-release (no notifications)
4. Final tags (`v2.0.0`) = production release (notifies subscribers)
5. VERSION file must be UTF-8 without BOM
6. Release notes from `docs/releases/{VERSION}.md`
7. Builds use `usdxfixgap.spec` for consistent ~250MB executables
