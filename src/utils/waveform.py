
import logging
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

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
    result = subprocess.run(command)

    if not os.path.exists(image_path):
        raise Exception(f"Failed to create waveform image '{image_path}'. Error: {result.stderr}")

    return image_path

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

    # Load the waveform image
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)

    image_width, image_height = image.size

    # Calculate the position of the detected gap on the image
    gap_position = (detected_gap_ms / duration_ms) * image_width

    # Draw a vertical line for the detected gap
    line_width = 3
    draw.line((gap_position, 0, gap_position, image_height), fill=line_color, width=line_width)

    # Save the annotated image
    image.save(image_path)

def calculate_note_position(start_beat, bpm, gap, duration_ms, image_width, is_relative):
    """
    Calculates the pixel position of a note on the image.

    Args:
        start_beat (float): The beat at which the note starts.
        bpm (float): The beats per minute, considering Ultrastar's interpretation (quarter notes).
        gap (int): Initial delay before the song starts, in milliseconds.
        duration_ms (int): Total duration of the song, in milliseconds.
        image_width (int): Width of the image in pixels.
        is_relative (bool): Flag indicating if the timing is relative or absolute.

    Returns:
        float: The pixel position (x-coordinate) on the image where the note should be drawn.
    """
    # Convert BPM to beats per millisecond, accounting for Ultrastar's quarter note interpretation.
    beats_per_ms = (bpm / 60 / 1000) * 4

    # Calculate position in milliseconds, considering if timing is relative or includes the gap.
    if is_relative:
        position_ms = start_beat / beats_per_ms
    else:
        position_ms = gap + (start_beat / beats_per_ms)
    
    # Calculate the position ratio relative to the total duration and map it to the image width.
    position_ratio = position_ms / duration_ms
    position_x = position_ratio * image_width

    return position_x

#def calculate_note_position(beat, bpm, gap, duration_ms, image_width, is_relative=False):
#    beat_duration_ms = (60 / bpm) * 1000
#    time_ms = beat * beat_duration_ms + (0 if is_relative else gap)
#    pixels_per_ms = image_width / duration_ms
#    position_x = time_ms * pixels_per_ms
#    return position_x

def draw_notes(image_path, notes, bpm, gap, duration_ms, color, is_relative=False):
    """
    Annotates a waveform image with notes, adjusting vertical position by pitch and drawing a line for duration.

    :param source_image_path: Path to the source waveform image.
    :param target_image_path: Path to save the annotated waveform image.
    :param notes: A list of note dictionaries parsed from the text file.
    :param bpm: Beats per minute of the song.
    :param gap: The delay before the song starts in milliseconds.
    :param duration_ms: Total duration of the audio in milliseconds.
    :param color: Color of the line to draw.
    :param is_relative: Whether the note timings are relative.
    """

    if(not os.path.exists(image_path)):
        raise FileNotFoundError(f"Waveform image not found: {image_path}")

    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)
    image_width, image_height = image.size

    for note in notes:
        start_position_x = calculate_note_position(note['StartBeat'], bpm, gap, duration_ms, image_width, is_relative)
        end_position_x = calculate_note_position(note['StartBeat'] + note['Length'], bpm, gap, duration_ms, image_width, is_relative)
        
        # Adjust vertical position based on pitch
        pitch_range = 60  # Assuming pitch values range from 0 to 60
        vertical_position = (1 - (note['Pitch'] / pitch_range)) * (image_height / 2)
        
        # Draw the text of the note
        draw.text((start_position_x, vertical_position + 12), note['Text'], fill=color)

        # Draw a line with 5px height representing the note duration
        line_height = 5
        draw.rectangle([start_position_x, vertical_position - line_height / 2, end_position_x, vertical_position + line_height / 2], fill=color)

    image.save(image_path)
