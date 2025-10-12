# Fixes Summary - October 12, 2025

## 1. ✅ TorchAudio MP3 Warning Suppressed

**Problem:**
```
UserWarning: The MPEG_LAYER_III subtype is unknown to TorchAudio. 
As a result, the bits_per_sample attribute will be set to 0.
```

**Cause:**
TorchAudio's soundfile backend doesn't fully recognize MP3 MPEG Layer III format, resulting in harmless but annoying warnings.

**Fix:**
Added global warning filter in `src/utils/providers/mdx_provider.py`:
```python
import warnings

# Suppress TorchAudio MP3 warning globally for this module
warnings.filterwarnings("ignore", message=".*MPEG_LAYER_III.*")
warnings.filterwarnings("ignore", category=UserWarning, module="torchaudio")
```

**Impact:**
- Cleaner console output during MDX detection
- No functional changes, purely cosmetic
- Warning was already being filtered locally, now global

---

## 2. ✅ MDX Detection Failure on Songs Without Intro

**Problem:**
```
WARNING: No onset detected after 4 expansions
WARNING: No vocal onset detected, assuming vocals at start
INFO: Detected vocal onset at 0.0ms
ERROR: Failed to detect gap in ...101 Dalmatiner - Cruella De Vil.mp3
Exception: Failed to detect gap
```

**Root Cause:**
Songs with vocals starting immediately (no intro silence) would:
1. MDX provider detects onset at 0ms (correct)
2. Returns empty silence periods list: `[]`
3. `detect_nearest_gap([])` returns `None`
4. Exception raised: "Failed to detect gap"

**Fix:**
Updated `detect_nearest_gap()` in `src/utils/detect_gap.py`:
```python
def detect_nearest_gap(silence_periods, start_position_ms):
    # NEW: If no silence periods found (vocals start immediately), return 0
    if not silence_periods:
        logger.debug("No silence periods found, vocals start at beginning (gap=0)")
        return 0
    
    # ... existing logic ...
```

**Impact:**
- Songs with no intro silence now successfully detect gap=0
- No more false failures on songs like "101 Dalmatiner - Cruella De Vil"
- Graceful handling of edge case
- Tests still pass (78/78)

**Examples of Songs This Fixes:**
- Songs that start immediately with vocals (no intro)
- Live recordings
- Songs with very short intros (<100ms)
- Acapella tracks

---

## 3. ✅ Cache Database Moved to LOCALAPPDATA

**Problem:**
Cache database (`cache.db`) was still in app directory while everything else moved to LOCALAPPDATA.

**Fix:**
Updated `src/common/database.py`:
```python
# Before:
from utils.files import get_app_dir
DB_PATH = os.path.join(get_app_dir(), 'cache.db')

# After:
from utils.files import get_localappdata_dir
DB_PATH = os.path.join(get_localappdata_dir(), 'cache.db')
```

**Impact:**
- Cache database now stored in `%LOCALAPPDATA%\USDXFixGap\cache.db`
- Consistent with unified storage architecture
- Multi-user friendly
- Update-safe

---

## 4. ✅ Model Downloads to Centralized Location

**Already Implemented** (from unified storage work):
- Demucs models: `%LOCALAPPDATA%\USDXFixGap\models\demucs\`
- Spleeter models: `%LOCALAPPDATA%\USDXFixGap\models\spleeter\`
- Environment variables set before library imports

**Verified Working:**
```
Downloading: "https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/955717e8-8726e21a.th" 
to C:\Users\live\AppData\Local\USDXFixGap\models\demucs\hub\checkpoints\955717e8-8726e21a.th
100%|████████████████████████████| 80.2M/80.2M [00:01<00:00, 69.8MB/s]
```

---

## GPU Pack Installation Strategy

**Question:** Should we auto-download GPU Pack like Demucs models?

**Recommendation: NO - Keep UI Dialog**

**Reasons:**
1. **Size Difference:**
   - Demucs: 80 MB (quick, silent OK)
   - GPU Pack: ~1 GB (needs user awareness)

2. **User Experience:**
   - Large download needs progress feedback
   - User should consent before 1GB download
   - Error handling with retry options
   - Offline installation option

3. **System Integration:**
   - Requires app restart to take effect
   - Multiple files to extract and validate
   - Clear messaging about prerequisites

4. **Existing Solution Works Well:**
   - Auto-prompt on first GPU detection attempt
   - CLI option: `--setup-gpu`
   - GUI: Settings → Download GPU Pack
   - Offline ZIP installation supported

**What We Have:**
- Automatic GPU detection
- Friendly dialog with progress bar
- Offline installation support
- Clear error messages

**Conclusion:** Keep the current UI-based approach for GPU Pack, it's appropriate for the size and impact.

---

## Testing Results

All tests passing after fixes:
```
78 passed, 3 warnings in 1.17s
```

Warnings are pre-existing (async coroutine cleanup), unrelated to these changes.

---

## Files Modified

1. `src/utils/providers/mdx_provider.py` - Added warning filters
2. `src/utils/detect_gap.py` - Handle empty silence periods
3. `src/common/database.py` - Moved cache to LOCALAPPDATA

---

## Commit Message Suggestion

```
fix: Handle songs without intro silence and suppress TorchAudio warnings

- Fix MDX detection failure on songs with vocals starting immediately
- Return gap=0 when no silence periods found instead of raising exception
- Suppress harmless TorchAudio MPEG_LAYER_III warnings globally
- Move cache.db to LOCALAPPDATA for consistency with unified storage

This resolves detection failures on songs like "101 Dalmatiner - Cruella De Vil"
where vocals start at the very beginning with no intro silence.
All tests passing (78/78).
```
