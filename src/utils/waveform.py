import logging
import os
import subprocess
import platform
from typing import List

from PIL import Image, ImageDraw, ImageFont

from utils.usdx_file import Note

logger = logging.getLogger(__name__)

def create_waveform_image(audio_file, image_path, color, width=1920, height=1080):
    """Create a waveform image for the given audio file."""

    logger.debug(f"Creating waveform '{image_path}'...")
    
    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    os.makedirs(os.path.dirname(image_path), exist_ok=True)

    # Create waveform image
    command = [
        'ffmpeg', '-y', '-loglevel', 'quiet', '-i', audio_file,
        '-filter_complex', f"showwavespic=s={width}x{height}:colors={color}:scale=lin:split_channels=1",
        '-frames:v', '1', image_path
    ]
    
    # Hide command window on Windows
    if platform.system() == 'Windows':
        result = subprocess.run(command, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        result = subprocess.run(command)

    if not os.path.exists(image_path):
        raise Exception(f"Failed to create waveform image '{image_path}'. Error: {result.stderr}")

    return image_path

def draw_silence_periods(image_path, silence_periods, duration_ms, color=(105, 105, 105, 128)):
    """Annotates the waveform image with the silence periods."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Waveform image not found: {image_path}")

    logger.debug(f"Annotating waveform image with silence periods: {silence_periods}")

    # Open the base image
    base = Image.open(image_path).convert("RGBA")
    image_width, image_height = base.size

    # Create a new transparent layer
    txt = Image.new("RGBA", base.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt)

    # Draw semi-transparent rectangles for silence periods
    for start_ms, end_ms in silence_periods:
        start_position = (start_ms / duration_ms) * image_width
        end_position = (end_ms / duration_ms) * image_width
        draw.rectangle([start_position, 0, end_position, image_height], fill=color)

    # Composite the transparent layer onto the base image
    out = Image.alpha_composite(base, txt)

    # Save the modified image
    out.save(image_path)

    
def draw_title(image_path, songname, color="white"):
    """Annotates the waveform image with the song name."""

    if(not os.path.exists(image_path)):
        raise FileNotFoundError(f"Waveform image not found: {image_path}")

    # Load the waveform image
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)

    # Load the font
    font = ImageFont.load_default()

    # Draw the song name at the bottom
    draw.text((100, 50), songname, fill=color, font=font)

    # Save the annotated image
    image.save(image_path)

def draw_gap(image_path, detected_gap_ms, duration_ms, line_color="red"):
    """Annotates the waveform image with the detected gap."""

    if(not os.path.exists(image_path)):
        raise FileNotFoundError(f"Waveform image not found: {image_path}")   

    logger.debug(f"Annotating waveform image with gap: {detected_gap_ms} ms, color: {line_color}")

    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)

    image_width, image_height = image.size
    gap_position = (detected_gap_ms / duration_ms) * image_width

    line_width = 3
    draw.line((gap_position, 0, gap_position, image_height), fill=line_color, width=line_width)

    image.save(image_path)

def note_position(start_ms, duration_ms, image_width):
    return (start_ms / duration_ms) * image_width

def map_pitch_to_vertical_position(pitch, min_pitch, max_pitch, image_height):
    """Map a pitch value to a vertical position around the middle of the image."""
    pitch_range = max_pitch - min_pitch
    if pitch_range == 0:  # Avoid division by zero
        return image_height / 2
    normalized_pitch = (pitch - min_pitch) / pitch_range  # Normalize pitch to 0-1 range
    return (1 - normalized_pitch) * image_height / 2 + image_height / 4

def draw_notes(
        image_path: str, 
        notes: List[Note], 
        duration_ms: int, 
        color: str
    ):

    if(not os.path.exists(image_path)):
        raise FileNotFoundError(f"Waveform image not found: {image_path}")

    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)
    image_width, image_height = image.size

    min_pitch = min(note.Pitch for note in notes)
    max_pitch = max(note.Pitch for note in notes)

    for note in notes:
        start_position_x = note_position(note.start_ms, duration_ms, image_width)
        end_position_x = note_position(note.end_ms, duration_ms, image_width)

        vertical_position = map_pitch_to_vertical_position(note.Pitch, min_pitch, max_pitch, image_height / 2) + (image_height / 4)
        draw.text((start_position_x, vertical_position + 12), note.Text, fill=color)

        line_height = 5
        draw.rectangle([start_position_x, vertical_position - line_height / 2, end_position_x, vertical_position + line_height / 2], fill=color)

    image.save(image_path)
