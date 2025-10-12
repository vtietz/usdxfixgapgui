# Release Notes Template for GitHub

Copy this template when creating a new release on GitHub.

---

## v1.1.0 - Cross-Platform Storage & Bug Fixes

### ⚠️ Important: Storage Location Changed

**Your data will move to a new location on first run:**

- **Windows**: `%LOCALAPPDATA%\USDXFixGap\` 
- **Linux**: `~/.local/share/USDXFixGap/`

**What you need to know:**
- ✅ The app handles this automatically
- ✅ Old data stays in app directory (not deleted)
- ✅ Optional: Copy `config.ini` manually if you want to keep settings
- ✅ Models will re-download to new location (~390 MB)

**Why?** Better multi-user support, update-safe storage, and follows OS standards.

---

### ✨ What's New

#### Cross-Platform Storage
- **Proper support for Windows and Linux**
  - Follows platform conventions (LOCALAPPDATA, XDG)
  - Respects environment variables
  - Portable mode fallback
  
- **Unified data directory** - everything in one place:
  - Config, cache, logs
  - AI models (Demucs, Spleeter)
  - Temporary files
  - GPU Pack

- **Configurable model paths** - set custom locations:
  ```ini
  [Paths]
  models_directory = E:\AI_Models
  ```
  - Network shares supported: `\\server\shared\models`
  - Environment variable expansion

#### Bug Fixes
- **Fixed crash on songs without intro**: Songs with vocals starting immediately (like "101 Dalmatiner - Cruella De Vil") no longer fail detection
- **Cleaner console output**: Suppressed harmless TorchAudio warnings

---

### 📥 Installation

#### Windows
1. Download `usdxfixgap-v1.1.0-windows.zip`
2. Extract to any folder
3. Run `usdxfixgap.exe`

#### Linux
1. Download `usdxfixgap-v1.1.0-linux.tar.gz`
2. Extract: `tar -xzf usdxfixgap-v1.1.0-linux.tar.gz`
3. Run: `./usdxfixgap`

---

### 🔄 Upgrading from v1.0.0

**Quick Steps:**
1. Download new version
2. Extract and run
3. (Optional) Copy old `config.ini` to new location

**Finding your new data directory:**
- **Windows**: Press `Win+R`, type `%LOCALAPPDATA%\USDXFixGap`, press Enter
- **Linux**: `~/.local/share/USDXFixGap/`

**To keep your old settings:**
- Copy `config.ini` and `cache.db` from old app directory to new location

**Models will re-download** to new location (~390 MB). To avoid:
- Manually move from `~/.cache/torch/` and `~/.cache/spleeter/` to new `models/` folder

---

### 📚 Documentation

- [Migration Guide](CHANGELOG.md#migration-guide-for-existing-users)
- [Cross-Platform Storage Guide](docs/cross-platform-storage.md)
- [Full Changelog](CHANGELOG.md)

---

### 🐛 Known Issues

None currently. Please report issues on [GitHub Issues](https://github.com/vtietz/usdxfixgapgui/issues).

---

### 💬 Questions?

**Where is my data?**
See "Finding your new data directory" above.

**Can I change model location?**
Yes! Edit `config.ini` and set `models_directory` under `[Paths]`.

**Will this work on my platform?**
- ✅ Windows 10/11
- ✅ Linux (Ubuntu 20.04+, Fedora, Arch, etc.)

---

### 🙏 Thanks

Thanks to all users for feedback and bug reports!

---

### 📝 Full Changelog

See [CHANGELOG.md](CHANGELOG.md) for complete details.

---

### Checksums

```
SHA256:
<hash>  usdxfixgap-v1.1.0-windows.zip
<hash>  usdxfixgap-v1.1.0-linux.tar.gz
```

---

**Download links:**
- [Windows (ZIP)](link)
- [Linux (tar.gz)](link)
