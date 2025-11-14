# Media Backend Architecture

## Overview

USDXFixGap uses a unified media backend abstraction layer that supports multiple audio playback engines across different platforms. The architecture prioritizes stability and eliminates platform-specific issues (particularly Windows Media Foundation deadlocks).

## Backend Strategy

### Platform-Specific Backends

| Platform | Primary Backend | Fallback | Rationale |
|----------|----------------|----------|-----------|
| **Windows** | VLC | Qt (WMF) | VLC eliminates Windows Media Foundation deadlocks when unloading media during vocals mode |
| **Linux** | Qt (GStreamer) | VLC | Native GStreamer integration provides best performance and compatibility |
| **macOS** | Qt (AVFoundation) | VLC | Native AVFoundation backend leverages macOS optimizations |

### Backend Selection Logic

The `BackendFactory` automatically selects the best backend:

1. **Windows**:
   - Check if VLC runtime available (bundled or system-installed)
   - Validate VLC functionality (libvlc can be loaded)
   - Fall back to Qt/WMF if VLC unavailable or broken
   - ⚠️ Qt/WMF backend may freeze on gap button clicks in vocals mode

2. **macOS/Linux**:
   - Use Qt backend (AVFoundation/GStreamer)
   - VLC available as fallback if Qt backend fails

## Backend Implementations

### VLC Backend (`VlcBackendAdapter`)

**Platforms**: Windows (primary), Linux/macOS (fallback)

**Key Features**:
- Polling-based position/status updates (timer-driven)
- Position interpolation for smooth 30 FPS playback line
- Millisecond-precise seeking via `set_time()`
- Audio-only mode (no video subsystem)
- Quiet logging (suppresses ES_OUT_SET_PCR warnings)

**Position Interpolation**:
VLC's `get_time()` only updates 3-4 times per second (~300ms intervals). To provide smooth 30 FPS position updates:
- Timer polls every 33ms (30 FPS)
- **Dynamic detection**: Measures actual VLC update frequency during playback
- **Adaptive interpolation**: Automatically disables if VLC provides ≥20 FPS updates (unlikely but possible with different VLC versions)
- When interpolation enabled and VLC position unchanged, add elapsed time to last known position
- **Smart snapping**: Cursor snaps to **nearest** VLC position (forward or backward), not always backward
- Reset interpolation timer when VLC updates
- Cap extrapolation at 1.5× average update interval to prevent drift
- Use exact VLC position when paused

```python
# Example adaptive interpolation logic (see vlc_backend.py)
if vlc_position != self._last_vlc_position:
    # VLC updated - measure interval and adapt
    interval = current_time - self._last_position_update_time
    self._position_update_intervals.append(interval)
    self._avg_update_interval_ms = average(intervals)
    # Disable interpolation if updates are fast enough (>20 FPS)
    self._use_interpolation = self._avg_update_interval_ms > 50
    position = vlc_position
elif playing and self._use_interpolation:
    # Interpolate between VLC updates
    elapsed_ms = self._interpolation_timer.elapsed()
    position = self._last_vlc_position + elapsed_ms
    # Cap at 1.5× average interval
    if elapsed_ms > self._avg_update_interval_ms * 1.5:
        position = self._last_vlc_position + int(self._avg_update_interval_ms * 1.5)
```

**Timers**:
- Position polling: 33ms (30 FPS with interpolation)
- Status polling: 200ms (playback state, media status)
- Timers only active when media loaded (CPU efficiency)

**Limitations**:
- ⚠️ **Seek position display**: VLC's internal position updates are coarse (3-4x/second). After seeking, the displayed position snaps to the nearest VLC-reported value (forward or backward within ~150ms). The actual playback position is accurate; only the display adjusts to VLC's reporting granularity.
- Requires ~100MB VLC runtime (~10MB for system-installed VLC DLLs)
- Polling-based (timer overhead vs. native Qt signals)

### Qt Backend (`QtBackendAdapter`)

**Platforms**: Windows (fallback), Linux/macOS (primary)

**Key Features**:
- Native Qt signal integration (no polling)
- **Dynamic update frequency detection**: Measures actual position update rate from platform backend
- Platform-optimized media engines:
  - **Windows**: Windows Media Foundation (WMF) - typically ~10 updates/sec
  - **macOS**: AVFoundation - typically ~30 updates/sec
  - **Linux**: GStreamer - typically ~20 updates/sec
- Lower memory footprint (no VLC runtime)
- Position updates depend on platform capabilities (no artificial interpolation)

**Limitations**:
- ⚠️ **Windows deadlock risk**: WMF may deadlock when unloading media while playing (particularly in vocals mode with gap button clicks)
- Position updates depend on platform backend (may be less frequent than VLC)
- Seek precision depends on platform codec support

## MediaBackend Protocol

All backends implement the `MediaBackend` protocol:

```python
class MediaBackend(Protocol):
    # Signals
    position_changed: Signal  # int (milliseconds)
    playback_state_changed: Signal  # PlaybackState
    media_status_changed: Signal  # MediaStatus
    error_occurred: Signal  # str

    # Lifecycle
    def load(file_path: str) -> None
    def unload() -> None

    # Playback control
    def play() -> None
    def pause() -> None
    def stop() -> None

    # Position/seeking
    def seek(position_ms: int) -> None
    def get_position() -> int
    def get_duration() -> int

    # State queries
    def is_playing() -> bool
    def get_playback_state() -> PlaybackState
    def get_media_status() -> MediaStatus

    # Volume control
    def set_volume(volume: int) -> None  # 0-100
    def get_volume() -> int
```

## Unified Enums

### PlaybackState
```python
class PlaybackState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
```

### MediaStatus
```python
class MediaStatus(Enum):
    NO_MEDIA = "no_media"
    LOADING = "loading"
    LOADED = "loaded"
    BUFFERING = "buffering"
    BUFFERED = "buffered"
    STALLED = "stalled"
    INVALID = "invalid"
```

## VLC Detection

### Development Setup

**Windows**:
```bash
.\run.bat setup-vlc  # Downloads VLC 3.0.21 portable (~100MB)
```

**Linux/macOS**:
```bash
# VLC optional; Qt backend sufficient
# Install VLC if needed: apt install vlc (Linux), brew install vlc (macOS)
```

### Production Builds

**Windows**:
- Detects system-installed VLC automatically (python-vlc)
- No bundling (keeps executable ~80MB)
- Shows helpful dialog with download link if VLC missing
- Fallback to Qt/WMF if unavailable

**macOS/Linux**:
- Qt backend sufficient (no VLC detection needed)
- Users can optionally install VLC system-wide

### Backend Detection Logic

```python
# src/services/media/backend_factory.py
def create_backend(config: Config) -> MediaBackend:
    if sys.platform == "win32":
        # Try VLC first on Windows
        if _is_vlc_available():
            return VlcBackendAdapter(config)
        else:
            logger.warning("VLC unavailable, falling back to Qt (WMF may freeze)")
            return QtBackendAdapter(config)
    else:
        # Use Qt backend on macOS/Linux (native engines)
        return QtBackendAdapter(config)
```

## Known Issues & Workarounds

### Windows Media Foundation Deadlocks (Qt Backend)

**Symptom**: UI freezes when clicking gap buttons in vocals mode

**Root Cause**: WMF deadlocks when QtMultimedia tries to unload media while tracks playing

**Workaround**: Use VLC backend (default on Windows)

**Mitigation** (if Qt backend required):
- Stop playback before mode switches
- Add delay between stop and unload
- ⚠️ Not recommended; use VLC instead

### VLC Seek Position Coarseness

**Symptom**: Cursor jumps to full-second positions after seeking, not exact requested millisecond

**Root Cause**: VLC's `get_time()` updates only 3-4x per second (300ms intervals)

**Expected Behavior**: This is NOT a bug. When you seek to 1234ms:
1. VLC receives `set_time(1234)` command (accurate)
2. Playback starts from 1234ms internally
3. Next `get_time()` call returns coarse position (e.g., 1500ms)
4. UI displays interpolated positions between VLC updates

**Why This Happens**:
- VLC's internal position queries are optimized for performance (not 1ms accuracy)
- Position interpolation smooths playback line movement but can't retroactively correct seek display
- After seek, first VLC update may be up to 300ms later

**Workaround**: None needed; behavior is correct. Users will see smooth playback after the brief seek adjustment.

### Position Update Frequency

**Dynamic Detection** (Both Backends):
- Both VLC and Qt backends measure actual position update frequency during playback
- Rolling average calculated from last 10 update intervals
- VLC: Automatically disables interpolation if backend provides ≥20 FPS (unlikely but possible)
- Qt: Tracks native update rate for diagnostics and potential future optimizations

**Typical Frequencies**:

**Qt Backend** (native signal-based):
- Windows (WMF): ~10 updates/second (100ms intervals)
- macOS (AVFoundation): ~30 updates/second (33ms intervals)
- Linux (GStreamer): ~20 updates/second (50ms intervals)

**VLC Backend** (polling with adaptive interpolation):
- Native VLC updates: 3-4 updates/second (250-330ms intervals)
- Interpolated output: 30 FPS smooth updates (33ms intervals)
- Interpolation automatically disabled if VLC provides ≥20 FPS

## Testing Backends

### Manual Testing

```bash
# Windows - test VLC backend
.\run.bat start  # Should use VLC automatically

# Test Qt fallback (rename VLC runtime to disable)
move vlc_runtime vlc_runtime_disabled
.\run.bat start  # Falls back to Qt/WMF

# Restore VLC
move vlc_runtime_disabled vlc_runtime
```

### Automated Testing

```bash
# Backend tests included in test suite
.\run.bat test

# Specific backend tests
pytest tests/services/media/test_backends.py
pytest tests/services/media/test_vlc_backend.py
pytest tests/services/media/test_qt_backend.py
```

## Performance Characteristics

### Memory Usage

| Backend | Idle | Playing | Notes |
|---------|------|---------|-------|
| **VLC** | ~100MB | ~120MB | Includes VLC runtime overhead |
| **Qt (WMF)** | ~20MB | ~40MB | Native Windows codecs |
| **Qt (AVFoundation)** | ~15MB | ~35MB | Native macOS codecs |
| **Qt (GStreamer)** | ~30MB | ~50MB | Includes GStreamer plugins |

### CPU Usage

| Backend | Idle | Playing (30 FPS) | Notes |
|---------|------|------------------|-------|
| **VLC** | <1% | 2-3% | Position/status polling overhead |
| **Qt** | <1% | 1-2% | Signal-based updates (no polling) |

### Seek Latency

| Backend | Average Seek Time | Notes |
|---------|------------------|-------|
| **VLC** | 50-100ms | Millisecond-precise `set_time()` |
| **Qt (WMF)** | 100-200ms | Ratio-based positioning |
| **Qt (AVFoundation)** | 50-100ms | Native seek support |
| **Qt (GStreamer)** | 100-150ms | Pipeline seek overhead |

## Future Improvements

## References

- **Backend Protocol**: `src/services/media/backend.py`
- **VLC Backend**: `src/services/media/vlc_backend.py`
- **Qt Backend**: `src/services/media/qt_backend.py`
- **Factory**: `src/services/media/backend_factory.py`
- **VLC Setup**: `docs/VLC_RUNTIME_SETUP.md`
- **Release Notes**: `docs/releases/v1.3.0.md`

## FAQ

**Q: Why not use VLC on all platforms?**
A: macOS/Linux have stable native backends (AVFoundation/GStreamer) without the deadlock issues seen on Windows. VLC would add ~100MB overhead with no stability benefit.

**Q: Can I force Qt backend on Windows?**
A: Yes, remove the `vlc_runtime/` directory. Not recommended due to deadlock risk.

**Q: Will VLC backend come to macOS/Linux?**
A: It's available as a fallback but not recommended. Qt backends are optimized for those platforms.

**Q: Why does the cursor jump after seeking?**
A: VLC's position updates are coarse (3-4x/second, ~300ms intervals). After seeking, the display snaps to the **nearest** VLC-reported position (forward or backward within ~150ms). This is expected behavior as the system uses actual VLC positions for accuracy. Playback position is correct; display adjusts to VLC's reporting granularity, then smoothly interpolates forward.

**Q: Can I reduce VLC's memory usage?**
A: VLC is already in audio-only mode with minimal plugins. Memory footprint is optimized.

**Q: Does interpolation affect seek accuracy?**
A: No. Seeking uses VLC's precise `set_time(ms)` command. Interpolation only affects position display between updates, not the actual playback position.
