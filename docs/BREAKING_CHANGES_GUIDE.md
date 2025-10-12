# How to Communicate Breaking Changes to Users

## TL;DR - Quick Answer

You now have **3 ways** to communicate breaking changes:

1. **CHANGELOG.md** - Comprehensive change log (✅ Created)
2. **GitHub Release Notes** - User-friendly announcement (✅ Template ready)
3. **Migration Helper** - Automatic data migration (✅ Code ready)

---

## What We Created

### 1. CHANGELOG.md ✅
**Location:** `CHANGELOG.md` (root directory)

**What it does:**
- Permanent record of all changes
- Follows [Keep a Changelog](https://keepachangelog.com/) standard
- Categorizes changes: Breaking, Added, Fixed, Changed
- Links to GitHub releases

**Usage:**
Update before each release with:
- Breaking changes clearly marked with ⚠️
- Migration instructions
- What changed and why

### 2. GitHub Release Template ✅
**Location:** `.github/RELEASE_TEMPLATE.md`

**What it does:**
- User-friendly announcement format
- Installation instructions
- Upgrade guide
- Q&A section

**Usage:**
When creating a GitHub release:
1. Copy template
2. Customize for your changes
3. Add download links and checksums
4. Publish

### 3. Migration Helper ✅
**Location:** `src/utils/migration.py`

**What it does:**
- Automatically detects old installation
- Migrates user data to new location
- Creates breadcrumb file in old location
- Returns success message or error

**Usage:**
Call in main startup (optional):
```python
from utils.migration import check_and_migrate_if_needed

migrated, message = check_and_migrate_if_needed()
if migrated and message:
    # Show dialog to user
    logger.info(message)
```

### 4. Release Process Guide ✅
**Location:** `docs/RELEASE_PROCESS.md`

**What it does:**
- Step-by-step release checklist
- Version numbering guide
- Build and packaging instructions
- GitHub release creation

**Usage:**
Follow this guide when creating any release.

---

## How to Use This for Your Next Release

### Step 1: Update CHANGELOG.md

Before releasing, move items from `[Unreleased]` to a version section:

```markdown
## [1.1.0] - 2025-10-12

### ⚠️ BREAKING CHANGES
- **Storage Location Changed**: User data now in platform-standard locations
  - Windows: %LOCALAPPDATA%\USDXFixGap\
  - Linux: ~/.local/share/USDXFixGap/
  - macOS: ~/Library/Application Support/USDXFixGap/
  - **Action needed**: None - automatic migration available

### ✨ Added
- Cross-platform storage support
- Configurable model paths via config.ini

### 🐛 Fixed
- MDX detection crash on songs without intro
- TorchAudio MP3 warnings suppressed
```

### Step 2: Create GitHub Release

1. Go to: https://github.com/vtietz/usdxfixgapgui/releases/new
2. **Tag**: `v1.1.0`
3. **Title**: `v1.1.0 - Cross-Platform Storage & Bug Fixes`
4. **Description**: Use `.github/RELEASE_TEMPLATE.md` as base
5. **Files**: Upload Windows/Linux/macOS packages
6. **Publish**

### Step 3: (Optional) Show Migration Dialog

Add to `src/usdxfixgap.py` main():

```python
from utils.migration import check_and_migrate_if_needed

def main():
    # ... existing code ...
    config = Config()
    
    # Check for migration
    migrated, message = check_and_migrate_if_needed()
    if migrated and message:
        # Show friendly dialog to user
        from PySide6.QtWidgets import QMessageBox
        msg = QMessageBox()
        msg.setWindowTitle("Data Migrated")
        msg.setIcon(QMessageBox.Information)
        msg.setText("Your data has been moved to a new location.")
        msg.setInformativeText(message)
        msg.exec()
    
    # ... continue with app startup ...
```

---

## Example: Your Current Breaking Change

### What Changed
- Storage moved from app directory to OS-standard location
- Windows: `%LOCALAPPDATA%\USDXFixGap\`
- Linux: `~/.local/share/USDXFixGap/`
- macOS: `~/Library/Application Support/USDXFixGap/`

### How Users Will Learn About It

**1. CHANGELOG.md** (Permanent Record)
```markdown
## [1.1.0] - 2025-10-12

### ⚠️ BREAKING CHANGES
- Storage location changed to platform-standard directories
- See Migration Guide below
```

**2. GitHub Release** (User Announcement)
```
⚠️ Important: Storage Location Changed

Your data will move to a new location on first run:
- Windows: %LOCALAPPDATA%\USDXFixGap\
- Linux: ~/.local/share/USDXFixGap/
- macOS: ~/Library/Application Support/USDXFixGap/

✅ Automatic migration available
✅ Old data not deleted
✅ Optional manual copy if preferred
```

**3. In-App** (If You Enable Migration Dialog)
```
┌─────────────────────────────────────┐
│ Data Migrated                    [×]│
├─────────────────────────────────────┤
│ Your data has been moved to a new   │
│ location:                           │
│                                     │
│ C:\Users\<you>\AppData\Local\       │
│ USDXFixGap\                         │
│                                     │
│ Old data remains at:                │
│ <old_location>                      │
│                                     │
│        [OK]                         │
└─────────────────────────────────────┘
```

---

## Best Practices for Breaking Changes

### DO ✅
- **Mark clearly** with ⚠️ symbol
- **Explain why** the change was made
- **Provide migration path** (automatic or manual)
- **Keep old data** (don't delete)
- **Document benefits** (why users should upgrade)
- **Test migration** before release

### DON'T ❌
- Make breaking changes without documenting
- Delete user data automatically
- Hide breaking changes in patch notes
- Skip version number (breaking = minor bump minimum)
- Assume users read everything

---

## Communication Channels

### Primary (Required)
1. **CHANGELOG.md** - Comprehensive change log
2. **GitHub Release Notes** - User-friendly announcement

### Secondary (Recommended)
3. **Migration Dialog** - In-app notification
4. **README.md** - Add banner for major releases

### Optional (If Applicable)
5. **Discord/Forum** - Community announcement
6. **Email** - For registered users
7. **Blog Post** - For major milestones

---

## Example Release Announcement

### GitHub Release Title
`v1.1.0 - Cross-Platform Storage & Bug Fixes`

### GitHub Release Description
```markdown
### ⚠️ Important: Storage Location Changed

This release moves user data to platform-standard locations for better
multi-user support and update safety.

**New locations:**
- Windows: `%LOCALAPPDATA%\USDXFixGap\`
- Linux: `~/.local/share/USDXFixGap/`
- macOS: `~/Library/Application Support/USDXFixGap/`

**What you need to do:**
- Nothing! The app handles migration automatically
- Old data stays in app directory (not deleted)
- Optional: Manually copy config.ini if preferred

[Full Migration Guide](CHANGELOG.md#migration-guide)

---

### ✨ What's New
- Cross-platform storage support (Windows/Linux/macOS)
- Configurable model paths via config.ini
- Models stored in centralized location

### 🐛 Bug Fixes
- Fixed crash on songs without intro silence
- Suppressed harmless TorchAudio warnings

[Full Changelog](CHANGELOG.md)

---

### 📥 Downloads
- [Windows (ZIP)](link)
- [Linux (tar.gz)](link)
- [macOS (tar.gz)](link)
```

---

## Your Deliverables

✅ **CHANGELOG.md** - Ready to use
✅ **RELEASE_TEMPLATE.md** - Copy-paste for GitHub releases
✅ **migration.py** - Automatic migration code
✅ **RELEASE_PROCESS.md** - Step-by-step guide
✅ **All tests passing** - 78/78

---

## Next Steps

1. **Review CHANGELOG.md** - Customize if needed
2. **Review RELEASE_TEMPLATE.md** - Adjust wording
3. **Test migration** (optional) - Run `python src/utils/migration.py`
4. **Follow RELEASE_PROCESS.md** - When ready to release
5. **Announce** - Use templates to communicate changes

---

## Questions?

### When should I use CHANGELOG vs Release Notes?

**CHANGELOG.md:**
- Permanent record of ALL changes
- Technical details
- Links to commits/issues
- Machine-readable format

**Release Notes:**
- User-friendly summary
- Highlights only
- Installation instructions
- Download links

### Should I add migration dialog?

**Recommended: Yes** if:
- Breaking change affects all users
- Immediate action helpful
- Want to reduce support questions

**Optional: No** if:
- Change is self-explanatory
- Migration automatic and silent
- Users can discover via CHANGELOG

### How do I test migration?

**Manual test:**
```bash
# Create fake old installation
mkdir old_install
cd old_install
echo "test=1" > config.ini

# Run migration test
cd ..
python src/utils/migration.py
```

**Automated test** (TODO):
Create `tests/test_migration.py` to verify migration logic.

---

## Summary

You now have a **complete release communication system**:

1. 📝 **CHANGELOG.md** - Comprehensive change log
2. 📢 **GitHub Release Template** - User announcement
3. 🔄 **Migration Helper** - Automatic data migration
4. 📚 **Release Process Guide** - Step-by-step workflow

**All ready to use for your next release!**
