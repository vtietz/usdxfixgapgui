"""Test waveform widget placeholder functionality"""
import pytest
from ui.mediaplayer.waveform_widget import WaveformWidget


@pytest.fixture
def app(qapp):
    """Ensure QApplication is available"""
    return qapp


@pytest.fixture
def waveform_widget(app):
    """Create a WaveformWidget for testing"""
    widget = WaveformWidget()
    return widget


def test_placeholder_initially_not_visible(waveform_widget):
    """Test that placeholder is not visible by default"""
    assert waveform_widget.placeholder_visible is False
    assert waveform_widget.placeholder_text == ""


def test_set_placeholder_shows_text(waveform_widget):
    """Test that set_placeholder makes placeholder visible"""
    waveform_widget.set_placeholder("Loading waveform…")

    assert waveform_widget.placeholder_visible is True
    assert waveform_widget.placeholder_text == "Loading waveform…"


def test_clear_placeholder_hides_text(waveform_widget):
    """Test that clear_placeholder hides the placeholder"""
    # Set placeholder first
    waveform_widget.set_placeholder("Loading waveform…")
    assert waveform_widget.placeholder_visible is True

    # Clear it
    waveform_widget.clear_placeholder()

    assert waveform_widget.placeholder_visible is False
    assert waveform_widget.placeholder_text == ""


def test_load_waveform_clears_placeholder_on_success(waveform_widget, tmp_path):
    """Test that loading a waveform clears the placeholder"""
    # Create a dummy image file
    from PySide6.QtGui import QImage

    # Create a small test image
    img = QImage(100, 50, QImage.Format.Format_RGB32)
    img.fill(0)  # Fill with black

    # Save to temp file
    temp_file = tmp_path / "test_waveform.png"
    img.save(str(temp_file))

    # Set placeholder first
    waveform_widget.set_placeholder("Loading waveform…")
    assert waveform_widget.placeholder_visible is True

    # Load waveform
    waveform_widget.load_waveform(str(temp_file))

    # Placeholder should be cleared
    assert waveform_widget.placeholder_visible is False
    assert not waveform_widget.pixmap().isNull()


def test_load_waveform_with_nonexistent_file_preserves_placeholder(waveform_widget):
    """Test that loading a nonexistent file doesn't clear placeholder"""
    # Set placeholder first
    waveform_widget.set_placeholder("Loading waveform…")
    assert waveform_widget.placeholder_visible is True

    # Try to load nonexistent file
    waveform_widget.load_waveform("/nonexistent/file.png")

    # Placeholder should still be visible (caller decides what message to show)
    assert waveform_widget.placeholder_visible is True
    assert waveform_widget.placeholder_text == "Loading waveform…"


def test_multiple_placeholder_changes(waveform_widget):
    """Test changing placeholder text multiple times"""
    # Set first message
    waveform_widget.set_placeholder("Loading waveform…")
    assert waveform_widget.placeholder_text == "Loading waveform…"

    # Change to different message
    waveform_widget.set_placeholder("Run gap detection to generate the vocals waveform.")
    assert waveform_widget.placeholder_text == "Run gap detection to generate the vocals waveform."
    assert waveform_widget.placeholder_visible is True

    # Clear
    waveform_widget.clear_placeholder()
    assert waveform_widget.placeholder_visible is False
