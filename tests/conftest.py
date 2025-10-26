import os
import sys
import asyncio
import pytest
from unittest.mock import Mock
from typing import Optional

# Ensure src directory is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(PROJECT_ROOT, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# Add tests directory to path for test utilities
TESTS_DIR = os.path.join(PROJECT_ROOT, 'tests')
if TESTS_DIR not in sys.path:
    sys.path.append(TESTS_DIR)

from model.song import Song
from model.gap_info import GapInfo
from test_utils.note_factory import create_basic_notes
from test_utils import separation_stub
from utils.providers.mdx.config import MdxConfig


# ============================================================================
# Platform-specific test markers
# ============================================================================

def pytest_collection_modifyitems(config, items):
    """
    Automatically skip Windows-only tests when running on non-Windows platforms.
    """
    skip_on_non_windows = pytest.mark.skipif(
        sys.platform != 'win32',
        reason="Windows-only test - requires Windows APIs (os.add_dll_directory, ctypes.WinDLL, os.startfile)"
    )

    windows_only_keywords = [
        '_windows', 'windll', 'startfile', 'dll_director',
        'enable_gpu_runtime_wheel',  # Uses os.add_dll_directory
        'feature_flag',  # GPU feature flags use Windows-specific code
        'url_format_for_python',  # Tests expect Windows URLs
        'open_config_file',  # Uses os.startfile
        'no_config_uses_legacy'  # Part of FeatureFlagIntegration, uses os.add_dll_directory
    ]

    for item in items:
        # Skip tests with windows-specific names
        test_name = item.nodeid.lower()
        if any(keyword in test_name for keyword in windows_only_keywords):
            item.add_marker(skip_on_non_windows)


def validate_detected_gap(detected_ms: Optional[float], test_name: str = "unknown") -> None:
    """
    Validate that a detected gap meets basic sanity checks.

    This is a universal assertion that ALL gap detection tests should call
    to catch regression bugs like negative gaps.

    Args:
        detected_ms: The detected gap value (or None if no detection)
        test_name: Name of the test for better error messages

    Raises:
        AssertionError: If detected gap fails validation
    """
    if detected_ms is None:
        return  # None is valid (no vocals detected)

    # CRITICAL: Gap must NEVER be negative
    assert detected_ms >= 0.0, (
        f"[{test_name}] Gap must be non-negative! Detected={detected_ms:.0f}ms. "
        f"Negative gaps indicate a bug (likely hysteresis lookback before chunk start)."
    )

    # Sanity check: Gap shouldn't be absurdly large (> 10 minutes)
    MAX_REASONABLE_GAP_MS = 600000  # 10 minutes
    assert detected_ms <= MAX_REASONABLE_GAP_MS, (
        f"[{test_name}] Gap seems unreasonably large: {detected_ms:.0f}ms ({detected_ms/1000:.1f}s). "
        f"Expected < {MAX_REASONABLE_GAP_MS/1000:.0f}s. This might indicate a bug."
    )


@pytest.fixture(scope="session", autouse=True)
def cleanup_asyncio_thread():
    """
    Session-scoped fixture to properly cleanup asyncio thread after all tests.

    This prevents the "QThread: Destroyed while thread is still running" warning
    that occurs when the test process exits with the asyncio event loop thread
    still active.
    """
    yield  # Run all tests

    # After all tests complete, shutdown the asyncio thread
    try:
        from utils.run_async import shutdown_asyncio
        shutdown_asyncio()
    except Exception as e:
        # Log but don't fail tests if shutdown has issues
        print(f"Warning: asyncio shutdown error: {e}")


@pytest.fixture
def app_data(tmp_path):
    """
    Create a mock AppData object with standard test configuration.

    Provides:
        - songs.updated.emit mock
        - worker_queue.add_task mock
        - config object with method='mdx', auto_normalize=False
        - tmp_path attribute for filesystem operations
    """
    data = Mock()

    # Songs collection with signal mocks
    data.songs = Mock()
    data.songs.updated = Mock()
    data.songs.updated.emit = Mock()

    # Worker queue mock
    data.worker_queue = Mock()
    data.worker_queue.add_task = Mock()

    # Configuration
    data.config = Mock()
    data.config.method = 'mdx'
    data.config.auto_normalize = False

    # Filesystem access
    data.tmp_path = tmp_path

    return data


@pytest.fixture
def song_factory(tmp_path):
    """
    Factory fixture for creating Song objects with sensible defaults.

    Usage:
        song = song_factory(title="Test Song", gap=1000)

    Returns:
        A callable that creates Song objects
    """
    def _create_song(
        txt_file: Optional[str] = None,
        title: str = "Test Song",
        artist: str = "Test Artist",
        gap: int = 1000,
        bpm: int = 120,
        is_relative: bool = False,
        audio_file: Optional[str] = None,
        with_notes: bool = True
    ) -> Song:
        """
        Create a Song object with specified parameters.

        Args:
            txt_file: Path to .txt file (default: temp file in tmp_path)
            title: Song title
            artist: Artist name
            gap: Gap value in milliseconds
            bpm: Beats per minute
            is_relative: Whether timing is relative
            audio_file: Path to audio file (default: None)
            with_notes: Whether to populate notes (default: True)

        Returns:
            A Song object with gap_info and owner hook configured
        """
        if txt_file is None:
            txt_file = str(tmp_path / f"{title}.txt")

        song = Song(txt_file=txt_file)
        song.title = title
        song.artist = artist
        song.gap = gap
        song.bpm = bpm
        song.is_relative = is_relative
        song.audio_file = audio_file or ""

        # Attach gap_info with owner hook
        gap_info = GapInfo()
        song.gap_info = gap_info  # This triggers the owner hook setter

        # Add notes if requested
        if with_notes:
            song.notes = create_basic_notes()

        return song

    return _create_song


@pytest.fixture
def fake_run_async():
    """
    Fixture providing synchronous executor for run_async in tests.

    This fixture ensures coroutines scheduled via run_async are immediately
    awaited and resolved during test execution, preventing RuntimeWarnings
    about unawaited coroutines.

    Usage:
        with patch('actions.gap_actions.run_async') as mock_run_async:
            mock_run_async.side_effect = fake_run_async
            # Test code that calls run_async(coro, callback)

    Returns:
        Callable that executes coroutine synchronously and invokes callback
    """
    def _executor(coro, callback=None):
        """Execute coroutine synchronously and invoke optional callback."""
        result = asyncio.run(coro)
        if callback:
            callback(result)
        return result

    return _executor


# ============================================================================
# Tier-2 Scanner Test Fixtures
# ============================================================================

@pytest.fixture
def patch_separator(monkeypatch):
    """
    Fixture to patch separate_vocals_chunk with stub for Tier-2 tests.

    The stub returns the right channel (ground-truth vocals) as separation result,
    simulating perfect separation without running Demucs.
    """
    # Patch where it's used, not where it's defined
    monkeypatch.setattr(
        'utils.providers.mdx.scanner.onset_detector.separate_vocals_chunk',
        separation_stub.stub_separate_vocals_chunk
    )
    yield  # Allow tests to execute


@pytest.fixture
def mdx_config_tight():
    """
    Tight MDX configuration for fast scanner tests.

    Automatically loads from tests/custom_config.ini if it exists,
    otherwise uses hard-coded test values for predictable results.
    """
    custom_config_path = os.path.join(os.path.dirname(__file__), "custom_config.ini")

    if os.path.exists(custom_config_path):
        # Load from custom config for experimentation
        from common.config import Config
        cfg = Config(custom_config_path=custom_config_path)
        return MdxConfig.from_config(cfg)

    # Default hard-coded test values
    return MdxConfig(
        chunk_duration_ms=12000,
        chunk_overlap_ms=6000,
        start_window_ms=20000,  # 20s initial window
        start_window_increment_ms=10000,  # 10s increments
        start_window_max_ms=60000,  # 60s max
        initial_radius_ms=7500,
        radius_increment_ms=7500,
        max_expansions=2,
        early_stop_tolerance_ms=500
    )


@pytest.fixture
def mdx_config_loose():
    """
    Loose MDX configuration for edge case tests.

    Automatically loads from tests/custom_config.ini if it exists,
    otherwise uses hard-coded test values for predictable results.
    """
    custom_config_path = os.path.join(os.path.dirname(__file__), "custom_config.ini")

    if os.path.exists(custom_config_path):
        # Load from custom config for experimentation
        from common.config import Config
        cfg = Config(custom_config_path=custom_config_path)
        return MdxConfig.from_config(cfg)

    # Default hard-coded test values
    return MdxConfig(
        chunk_duration_ms=12000,
        chunk_overlap_ms=6000,
        start_window_ms=30000,  # 30s initial window
        start_window_increment_ms=15000,  # 15s increments
        start_window_max_ms=90000,  # 90s max
        initial_radius_ms=10000,
        radius_increment_ms=10000,
        max_expansions=3,
        early_stop_tolerance_ms=500
    )


@pytest.fixture
def model_placeholder():
    """
    Mock Demucs model for scanner tests.

    Provides minimal attributes expected by scanner code.
    """
    model = Mock()
    model.samplerate = 44100
    model.sources = ['drums', 'bass', 'other', 'vocals']
    model.segment = 4.0  # Segment duration in seconds (required by demucs.apply_model)
    return model


# ============================================================================
# Tier-3 Fixtures (Pipeline + Worker Integration)
# ============================================================================

@pytest.fixture
def audio_scenario(tmp_path):
    """
    Factory fixture for building test audio scenarios.

    Returns a function that creates stereo test audio and returns metadata dict.
    """
    from test_utils.audio_factory import build_stereo_test, VocalEvent, InstrumentBed

    def _build_scenario(
        onset_ms: float = 5000.0,
        duration_ms: float = 30000,
        fade_in_ms: float = 100,
        amp: float = 0.7,
        noise_floor_db: float = -60.0,
        filename: str = "test_audio.wav"
    ):
        """
        Build audio scenario with given parameters.

        Returns:
            dict with keys: audio_path, sr, truth_onset_ms, duration_ms, tmp_root
        """
        audio_result = build_stereo_test(
            output_path=tmp_path / filename,
            duration_ms=duration_ms,
            vocal_events=[
                VocalEvent(onset_ms=onset_ms, duration_ms=duration_ms - onset_ms - 1000,
                          fade_in_ms=fade_in_ms, amp=amp)
            ],
            instrument_bed=InstrumentBed(noise_floor_db=noise_floor_db)
        )

        return {
            "audio_path": str(audio_result.path),
            "sr": audio_result.sr,
            "truth_onset_ms": onset_ms,
            "duration_ms": audio_result.duration_ms,
            "tmp_root": str(tmp_path)
        }

    return _build_scenario


@pytest.fixture
def stub_provider_factory():
    """
    Factory fixture for creating StubProvider instances.

    Returns a function that creates configured StubProvider.
    """
    from test_utils.provider_stub import StubProvider
    from test_utils.config_stub import ConfigStub

    def _create_provider(
        truth_onset_ms: Optional[float] = None,
        confidence_value: float = 0.95,
        raise_on_get_vocals: bool = False,
        raise_on_detect_silence: bool = False,
        raise_on_confidence: bool = False,
        tmp_root: Optional[str] = None
    ):
        """Create StubProvider with given configuration."""
        config = ConfigStub(tmp_root=tmp_root)
        return StubProvider(
            config=config,  # type: ignore  # ConfigStub duck-types Config for testing
            truth_onset_ms=truth_onset_ms,
            confidence_value=confidence_value,
            raise_on_get_vocals=raise_on_get_vocals,
            raise_on_detect_silence=raise_on_detect_silence,
            raise_on_confidence=raise_on_confidence
        )

    return _create_provider


@pytest.fixture
def patch_provider(monkeypatch, stub_provider_factory):
    """
    Fixture to patch get_detection_provider with StubProvider.

    Returns a function that patches the provider factory to return
    a specific StubProvider instance.
    """
    def _patch_with_provider(provider):
        """Patch get_detection_provider to return the given provider."""
        # Patch where it's used (pipeline imports it)
        monkeypatch.setattr(
            'utils.gap_detection.pipeline.get_detection_provider',
            lambda config: provider
        )
        return provider

    return _patch_with_provider


@pytest.fixture
def config_stub(tmp_path):
    """
    Fixture providing minimal Config stub for pipeline tests.
    """
    from test_utils.config_stub import ConfigStub

    return ConfigStub(tmp_root=str(tmp_path))


@pytest.fixture
def write_tier3_docs():
    """
    Fixture to check if Tier-3 docs should be generated.

    Returns True if GAP_TIER3_WRITE_DOCS=1 environment variable is set.
    """
    import os
    return os.environ.get('GAP_TIER3_WRITE_DOCS', '0') == '1'