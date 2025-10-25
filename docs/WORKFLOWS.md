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
- **Automatic:** When you push a version tag (e.g., `v2.0.0`)
- **Manual:** Via GitHub Actions web interface

**What it does:**
1. 🪟 Builds Windows executable (`.exe`)
2. 🐧 Builds Linux executable (`.tar.gz`)
3. 🍎 Builds macOS executable (`.tar.gz`)
4. 📦 Creates GitHub Release with all binaries
5. 📝 Uses release notes from `docs/releases/{VERSION}.md`

**Platforms:**
- Windows: Python 3.11, PyInstaller
- Linux: Python 3.11, Ubuntu latest, system dependencies
- macOS: Python 3.11, macOS latest, Homebrew dependencies

**Artifacts:**
- `usdxfixgap-{VERSION}-windows.exe`
- `usdxfixgap-{VERSION}-linux.tar.gz`
- `usdxfixgap-{VERSION}-macos.tar.gz`

---

## 🚀 How to Create a Release

### Prerequisites

1. **Update VERSION file:**
   ```bash
   echo "v2.0.0" > VERSION
   ```

2. **Create release notes:**
   ```bash
   # Create/update docs/releases/v2.0.0.md with changelog
   ```

3. **Commit changes:**
   ```bash
   git add VERSION docs/releases/v2.0.0.md
   git commit -m "Prepare release v2.0.0"
   git push
   ```

### Method 1: Automatic (Recommended)

**Create and push a tag:**
```bash
# Make sure VERSION file contains "v2.0.0"
git tag -a v2.0.0 -m "Release v2.0.0"
git push origin v2.0.0
```

This will:
- ✅ Automatically trigger the release workflow
- ✅ Build all 3 platforms
- ✅ Create GitHub release with tag `v2.0.0`
- ✅ Use release notes from `docs/releases/v2.0.0.md`
- ✅ Upload all binaries

### Method 2: Manual Trigger

1. Go to: **GitHub → Actions → Release - Multi-Platform Builds**
2. Click **Run workflow**
3. Select branch (usually `main`)
4. Click **Run workflow** button

This will:
- ✅ Read version from `VERSION` file
- ✅ Create/update tag automatically
- ✅ Build and release as Method 1

---

## 📝 Release Notes Format

**Location:** `docs/releases/{VERSION}.md`

**Example:** `docs/releases/v2.0.0.md`

The release notes file should follow this structure:

```markdown
# v2.0.0 - Title Here

### ⚠️ Breaking Changes
- List breaking changes
- Migration steps if needed

### What's New

#### Feature Category 1
- New feature description
- Implementation details

#### Feature Category 2
- More features

### Bug Fixes
- Fixed issue description
- More fixes

### Upgrading from v1.x.x
1. Step-by-step upgrade instructions
2. Configuration changes
3. Data migration if needed
```

**If release notes file doesn't exist:**
- Workflow generates default notes with download instructions
- Still creates release successfully

---

## 🔧 Dependencies Management

### Development Setup

```bash
# Install base + dev dependencies
.\run.bat install-dev

# Or manually:
pip install -r requirements.txt          # Base runtime dependencies
pip install -r requirements-dev.txt      # Dev tools (includes base)
```

### Important Notes

1. **requirements.txt**
   - Runtime dependencies only
   - Included in built executables
   - Used by CI and release builds

2. **requirements-dev.txt**
   - Development tools (pytest, flake8, black, etc.)
   - **Includes** `requirements.txt` via `-r requirements.txt`
   - NOT included in executables
   - Used by CI for testing/quality checks

3. **Build Process**
   - Only `requirements.txt` is installed during builds
   - Keeps executable size small
   - PyInstaller excludes dev packages explicitly

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

**Tests failing:**
```bash
# Run tests locally first
.\run.bat test

# Check specific test
.\run.bat test tests/test_specific.py -v
```

**Code quality issues:**
```bash
# Run analysis locally
.\run.bat analyze

# Auto-fix style issues
.\run.bat cleanup changed
```

### Release Failures

**Build fails on specific platform:**
1. Check build logs in GitHub Actions
2. Test build locally:
   ```bash
   # Windows
   .\build.bat

   # Linux/macOS
   ./build_linux.sh
   ./build_macos.sh
   ```

**Release notes not found:**
- Create `docs/releases/{VERSION}.md`
- Or workflow will generate default notes

**Tag already exists:**
```bash
# Delete local tag
git tag -d v2.0.0

# Delete remote tag
git push origin :refs/tags/v2.0.0

# Create new tag
git tag -a v2.0.0 -m "Release v2.0.0"
git push origin v2.0.0
```

### Version Mismatch

**Ensure VERSION file matches tag:**
```bash
# VERSION file should contain:
v2.0.0

# Not:
2.0.0          # ❌ Missing 'v' prefix
v2.0.0-beta    # ❌ Suffix not supported
```

---

## 📦 Release Checklist

Before creating a release:

- [ ] All tests passing locally (`.\run.bat test`)
- [ ] Code quality checks passing (`.\run.bat analyze`)
- [ ] VERSION file updated (e.g., `v2.0.0`)
- [ ] Release notes created in `docs/releases/v2.0.0.md`
- [ ] CHANGELOG.md updated (if maintained)
- [ ] All changes committed and pushed
- [ ] Tag created and pushed OR manual workflow triggered

After release:

- [ ] Verify all 3 binaries uploaded to GitHub Release
- [ ] Test download and run each binary
- [ ] Update documentation if needed
- [ ] Announce release (if applicable)

---

## 🔄 Workflow Maintenance

### Updating Python Version

Edit workflow files:
```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.11'  # Change here
```

### Adding New Platforms

1. Add new job to `release.yml`:
   ```yaml
   build-freebsd:
     name: Build FreeBSD Executable
     runs-on: ubuntu-latest
     # ... build steps
   ```

2. Add to `needs:` in release job:
   ```yaml
   release:
     needs: [build-windows, build-linux, build-macos, build-freebsd]
   ```

3. Add artifact download and packaging

### Modifying Code Quality Checks

Edit `ci.yml` code quality steps:
```yaml
- name: Code Quality - Style Check
  run: |
    python -m flake8 src/ tests/ scripts/ \
      --max-line-length=120 \
      --extend-ignore=E203,E501  # Add/remove rules
```

---

## 📚 Additional Resources

- **GitHub Actions Documentation:** https://docs.github.com/en/actions
- **PyInstaller Documentation:** https://pyinstaller.org/
- **Project Coding Standards:** `docs/coding-standards.md`
- **Development Guide:** `docs/DEVELOPMENT.md`

---

## 🎯 Summary

### Quick Commands

```bash
# Development
.\run.bat install-dev    # Setup dev environment
.\run.bat test           # Run tests
.\run.bat analyze        # Code quality check
.\run.bat cleanup        # Auto-fix style issues

# Release
git tag -a v2.0.0 -m "Release v2.0.0"
git push origin v2.0.0  # Triggers automatic release

# Manual trigger
# Go to GitHub → Actions → Release → Run workflow
```

### Key Points

1. ✅ **CI runs on every push/PR** - ensures code quality
2. 🚀 **Releases are automatic** - just push a tag
3. 📝 **Release notes are versioned** - stored in `docs/releases/`
4. 🔢 **Version comes from VERSION file** - no date timestamps
5. 🌍 **Multi-platform builds** - Windows, Linux, macOS
6. 📦 **Dependencies are separate** - runtime vs dev
7. 🔄 **Workflows are self-contained** - no manual steps needed
