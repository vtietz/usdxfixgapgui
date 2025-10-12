# File Storage Analysis & Consolidation Plan

## Current Storage Locations (Inconsistent!)

### 1. App Directory (`get_app_dir()`)
**Location**: Where the executable/script is located
- Development: `c:\Users\live\.coding\usdxfixgapgui\`
- Bundled: Same directory as `usdxfixgap.exe`

**What's stored here**:
- `config.ini` - User configuration
- `usdxfixgap.log` - Application logs
- `.tmp/` - Temporary processing files (vocals, segments)
- `output/` - Default output directory
- `samples/` - Default song directory
- `cache.db` - Song metadata cache

**Issues**:
- ❌ Not portable (tied to exe location)
- ❌ Multiple users can't have separate configs
- ❌ Updates overwrite user data

---

### 2. LOCALAPPDATA (Windows Standard)
**Location**: `%LOCALAPPDATA%\USDXFixGap\`  
Example: `C:\Users\<username>\AppData\Local\USDXFixGap\`

**What's stored here**:
- `gpu_runtime/` - Downloaded GPU Pack (PyTorch CUDA)
  - `torch/` - Extracted PyTorch libraries
  - `torchaudio/` - Extracted torchaudio libraries

**Purpose**:
- ✅ User-specific data
- ✅ Survives app updates
- ✅ Standard Windows location for app data

---

### 3. User Home Cache (Cross-Platform Standard)
**Location**: `~/.cache/`  
Windows: `C:\Users\<username>\.cache\`

**What's stored here** (by libraries, NOT by us):
- `torch/hub/checkpoints/` - Demucs models (auto-downloaded by PyTorch)
  - `htdemucs.pt` (~350 MB)
  - `htdemucs_ft.pt` (~350 MB, fine-tuned)
- `spleeter/` - Spleeter models (auto-downloaded by Spleeter)
  - `2stems/` - 2-stem separation model (~40 MB)
  - `4stems/` - 4-stem separation model (~160 MB)

**Issues**:
- ❌ Not configurable by us (library-controlled)
- ❌ Users can't share models between machines
- ❌ Invisible to users (hidden .cache folder)

---

## Problems with Current Approach

### ❌ Inconsistency
- User data in 3 different locations
- No clear logic for what goes where
- Some data in app dir, some in user home

### ❌ Not Portable
- Can't move app to different location without losing config
- Can't run from USB stick
- Multi-user systems conflict

### ❌ Not Shareable
- Models downloaded per-user (waste of disk space)
- Can't pre-download models and share
- No network share support

### ❌ Not Discoverable
- `.cache` folder is hidden
- Users don't know where models are
- Hard to troubleshoot space issues

---

## Proposed Solution: Unified Storage Structure

### Option A: All in LOCALAPPDATA (Recommended)

```
%LOCALAPPDATA%\USDXFixGap\
├── config.ini              ← User configuration
├── cache.db                ← Song metadata cache
├── usdxfixgap.log          ← Application logs
├── .tmp\                   ← Temporary processing files
│   └── [song-hash]\
│       ├── vocals.mp3
│       ├── waveform.png
│       └── ...
├── output\                 ← Default output directory
├── samples\                ← Default song directory
├── models\                 ← AI models (NEW!)
│   ├── demucs\
│   │   ├── htdemucs.pt          (~350 MB)
│   │   └── htdemucs_ft.pt       (~350 MB)
│   └── spleeter\
│       ├── 2stems\               (~40 MB)
│       └── 4stems\               (~160 MB)
└── gpu_runtime\            ← GPU Pack (existing)
    ├── torch\
    └── torchaudio\
```

**Benefits**:
- ✅ Everything in one place
- ✅ User-specific (multi-user friendly)
- ✅ Survives app updates
- ✅ Standard Windows location
- ✅ Easy to backup/restore
- ✅ Visible to users

**Drawbacks**:
- ⚠️ Models not shared across users (but configurable)

---

### Option B: Configurable Paths (Power Users)

Add config options:
```ini
[Paths]
ModelsDirectory = %LOCALAPPDATA%\USDXFixGap\models
TempDirectory = %LOCALAPPDATA%\USDXFixGap\.tmp
OutputDirectory = %LOCALAPPDATA%\USDXFixGap\output

# Allow network shares or custom paths
# ModelsDirectory = \\server\shared\USDXFixGap\models
# ModelsDirectory = E:\USDXFixGap\models
```

**Benefits**:
- ✅ Share models across users/machines
- ✅ Use network storage
- ✅ Separate fast SSD for processing
- ✅ Separate slow HDD for models

---

## Implementation Plan

### Phase 1: Consolidate to LOCALAPPDATA

1. **Create new directory structure** on first run
2. **Migrate existing data** from app dir to LOCALAPPDATA
   - Move config.ini, cache.db, logs
   - Keep .tmp in LOCALAPPDATA (not app dir)
3. **Update `get_app_dir()`** to return LOCALAPPDATA path
4. **Add migration code** to handle upgrades

### Phase 2: Model Management

1. **Demucs Model Download**
   - Override PyTorch's default cache location
   - Set `TORCH_HOME` environment variable
   - Download to `%LOCALAPPDATA%\USDXFixGap\models\demucs\`

2. **Spleeter Model Download**
   - Override Spleeter's default cache location
   - Set `MODEL_PATH` environment variable
   - Download to `%LOCALAPPDATA%\USDXFixGap\models\spleeter\`

3. **Add Download Dialog** (reuse GPU download dialog)
   - Show progress for model downloads
   - Allow cancellation
   - Verify checksums

### Phase 3: Configuration

1. **Add config options**
   ```ini
   [Paths]
   ModelsDirectory = %LOCALAPPDATA%\USDXFixGap\models
   TempDirectory = %LOCALAPPDATA%\USDXFixGap\.tmp
   OutputDirectory = %LOCALAPPDATA%\USDXFixGap\output
   
   [Download]
   AutoDownloadModels = true
   ShowModelDownloadDialog = true
   ```

2. **Add UI settings** for path configuration
3. **Add model management** (delete, re-download, verify)

---

## Migration Strategy

### For Existing Users

```python
def migrate_to_localappdata():
    """Migrate data from app dir to LOCALAPPDATA on first run."""
    old_app_dir = os.path.dirname(sys.executable)  # Old location
    new_app_dir = get_new_app_dir()  # %LOCALAPPDATA%\USDXFixGap
    
    # Check if migration needed
    if os.path.exists(os.path.join(old_app_dir, 'config.ini')):
        print("Migrating user data to new location...")
        
        # Move config, cache, logs
        for file in ['config.ini', 'cache.db', 'usdxfixgap.log']:
            old_path = os.path.join(old_app_dir, file)
            new_path = os.path.join(new_app_dir, file)
            if os.path.exists(old_path):
                shutil.move(old_path, new_path)
        
        # Move directories
        for dir in ['.tmp', 'output']:
            old_path = os.path.join(old_app_dir, dir)
            new_path = os.path.join(new_app_dir, dir)
            if os.path.exists(old_path):
                shutil.move(old_path, new_path)
        
        print(f"Migration complete! Data moved to: {new_app_dir}")
```

### For Model Downloads

```python
def setup_model_paths(config):
    """Configure model download paths before loading libraries."""
    models_dir = config.get_models_directory()
    
    # Demucs (PyTorch hub)
    os.environ['TORCH_HOME'] = os.path.join(models_dir, 'demucs')
    
    # Spleeter
    os.environ['MODEL_PATH'] = os.path.join(models_dir, 'spleeter')
    
    # Create directories
    os.makedirs(os.environ['TORCH_HOME'], exist_ok=True)
    os.makedirs(os.environ['MODEL_PATH'], exist_ok=True)
```

---

## Download Dialog Integration

Reuse GPU download dialog for models:

```python
class ModelDownloadDialog(QDialog):
    """
    Unified download dialog for:
    - GPU Pack (PyTorch CUDA)
    - Demucs models
    - Spleeter models
    """
    
    def __init__(self, model_type, config):
        self.model_type = model_type  # 'gpu-pack', 'demucs', 'spleeter'
        
        if model_type == 'demucs':
            self.title = "Download Demucs Model"
            self.message = "Required for MDX-based detection (~350 MB)"
            self.url = "https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/htdemucs.pt"
        
        elif model_type == 'spleeter':
            self.title = "Download Spleeter Model"
            self.message = "Required for Spleeter-based detection (~40 MB)"
            # Spleeter downloads automatically via library
```

---

## Benefits of Unified Approach

### For Users
- ✅ All data in one predictable location
- ✅ Easy to backup/restore
- ✅ Visible storage usage
- ✅ No hidden folders

### For Developers
- ✅ Consistent code patterns
- ✅ Easier to debug
- ✅ Simpler testing
- ✅ Better error messages

### For Distribution
- ✅ Portable executables
- ✅ Clean uninstall
- ✅ Multi-user support
- ✅ Network deployment friendly

---

## Next Steps

1. ✅ Analyze current storage (this document)
2. ⏳ Implement `get_localappdata_dir()` function
3. ⏳ Add migration code for existing users
4. ⏳ Override model download paths
5. ⏳ Add model download dialog
6. ⏳ Add config UI for paths
7. ⏳ Update documentation
8. ⏳ Test migration on clean install
9. ⏳ Test upgrade from old version

---

## Questions to Resolve

1. **Default behavior**: Auto-download models or ask first?
   - Recommendation: Show dialog with progress (like GPU Pack)

2. **Model sharing**: Allow config or enforce user-specific?
   - Recommendation: Configurable paths for power users

3. **Cleanup**: Delete old models when switching detection method?
   - Recommendation: Keep all models, add "Manage Models" dialog

4. **Portable mode**: Support running from USB?
   - Recommendation: Detect and use app dir if LOCALAPPDATA unavailable
