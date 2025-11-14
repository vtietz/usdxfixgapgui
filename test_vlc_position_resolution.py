"""
Quick VLC position resolution test.

Tests if VLC's get_time() returns smooth millisecond values or rounds to seconds.
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import vlc
    print(f"✓ VLC imported successfully")
    print(f"  Version: {vlc.libvlc_get_version().decode('utf-8')}")
except Exception as e:
    print(f"✗ VLC import failed: {e}")
    sys.exit(1)

# Test with ABBA sample
sample_file = Path(__file__).parent.parent / "samples" / "ABBA - Dancing Queen" / "ABBA - Dancing Queen.mp3"

if not sample_file.exists():
    print(f"✗ Sample file not found: {sample_file}")
    sys.exit(1)

print(f"\n✓ Sample file: {sample_file.name}")

# Create VLC instance
instance = vlc.Instance('--quiet', '--no-video')
player = instance.media_player_new()

# Load media
media = instance.media_new(str(sample_file))
player.set_media(media)

print(f"\n▶ Starting playback...")
player.play()

# Wait for playback to start
time.sleep(0.5)

print(f"\n📊 Position samples (50ms intervals, 20 samples):")
print(f"{'Sample':<8} {'Time (ms)':<12} {'Diff (ms)':<10} {'Notes'}")
print("-" * 60)

last_pos = 0
for i in range(20):
    pos = player.get_time()
    diff = pos - last_pos

    note = ""
    if diff == 0:
        note = "⚠ STUCK"
    elif diff >= 1000:
        note = "⚠ BIG JUMP"
    elif diff < 40:
        note = "⚠ TOO SMALL"
    elif 40 <= diff <= 60:
        note = "✓ SMOOTH"

    print(f"{i+1:<8} {pos:<12} {diff:<10} {note}")

    last_pos = pos
    time.sleep(0.05)  # 50ms

player.stop()
print(f"\n✓ Test complete")
print(f"\n💡 Analysis:")
print(f"   - Expected diff: ~50ms per sample")
print(f"   - If diff is 0 or >1000ms: VLC position not updating smoothly")
print(f"   - If diff is 40-60ms: VLC is working correctly")
