import logging
import os
from PySide6.QtCore import QObject, QUrl, QTimer
from PySide6.QtGui import QDesktopServices
from typing import List # Import List
from common.data import AppData
from model.song import Song
from utils.run_async import run_async, run_sync
from workers.worker_queue_manager import WorkerQueueManager
from workers.detect_audio_length import DetectAudioLengthWorker
from workers.detect_gap import DetectGapWorker
from workers.load_usdx_files import LoadUsdxFilesWorker
from workers.normalize_audio import NormalizeAudioWorker
from workers.create_waveform import CreateWaveform
from model.song import Song, SongStatus
from model.gap_info import GapInfoStatus
import utils.usdx as usdx

logger = logging.getLogger(__name__)

class Actions(QObject):

    data: AppData = None
    
    def __init__(self, data: AppData):
        super().__init__()
        self.data = data
        self.config = data.config
        self.worker_queue = WorkerQueueManager()

    def set_directory(self, directory: str):
        self.data.directory = directory
        self._claer_songs()
        self._load_songs()

    def _claer_songs(self):
        self.data.songs.clear()

    def _load_songs(self):
        worker = LoadUsdxFilesWorker(self.data.directory, self.data.tmp_path)
        worker.signals.songLoaded.connect(self._on_song_loaded)
        worker.signals.finished.connect(self._on_loading_songs_finished)
        self.worker_queue.add_task(worker, True)

    # Method called by the view when selection changes
    def set_selected_songs(self, songs: List[Song]): # Use List[Song]
        logger.debug(f"Setting selected songs: {[s.title for s in songs]}")
        self.data.selected_songs = songs
        # If single song selection logic is still needed elsewhere:
        # self.data.selected_song = songs[0] if songs else None
        if songs:
            # Create waveforms only for the first selected song for preview?
            # Or should it be done for all? Let's do it for the first one for now.
            self._create_waveforms(songs[0])
        # Else: handle deselection if necessary (e.g., clear detail view)

    # Keep select_song for potential single-selection contexts if needed,
    # but primary selection is handled by set_selected_songs.
    # This might become obsolete depending on how details are handled.
    def select_song(self, path: str):
        logger.warning("select_song(path) called, consider using set_selected_songs(list[Song])")
        song: Song = next((s for s in self.data.songs if s.path == path), None)
        if song:
            self.set_selected_songs([song]) # Wrap in list
        else:
            self.set_selected_songs([])

    def _on_song_loaded(self, song: Song):
        self.data.songs.add(song)
        if(song.status == SongStatus.NOT_PROCESSED):
            song.gap_info.original_gap = song.gap
            if(self.config.spleeter):
                self._detect_gap(song)
        
    def _on_loading_songs_finished(self):
        self.data.is_loading_songs = False

    def _get_audio_length(self, song: Song):
        worker = DetectAudioLengthWorker(song)
        worker.signals.lengthDetected.connect(lambda song: self.data.songs.updated.emit(song))
        self.worker_queue.add_task(worker, True)

    def _detect_gap(self, song: Song, overwrite=False, start_now=False):
        if not song:
            raise Exception("No song given")

        worker = DetectGapWorker(
            song, 
            self.config,
            self.data.tmp_path,
            self.config.default_detection_time,
            overwrite
        )
        
        worker.signals.started.connect(lambda: self._on_song_worker_started(song))
        worker.signals.error.connect(lambda: self._on_song_worker_error(song))
        worker.signals.finished.connect(self._on_detect_gap_finished)
        song.status = SongStatus.QUEUED
        self.data.songs.updated.emit(song)
        self.worker_queue.add_task(worker, start_now)

    def detect_gap(self, overwrite=False):
        selected_songs = self.data.selected_songs
        if not selected_songs:
            logger.error("No songs selected for gap detection.")
            return
        
        logger.info(f"Queueing gap detection for {len(selected_songs)} songs.")
        
        # Save overwrite parameter for the callback
        self._overwrite_gap = overwrite
        
        # Use async queuing to prevent UI freeze
        self._queue_tasks_non_blocking(selected_songs, self._detect_gap_if_valid)
    
    def _detect_gap_if_valid(self, song, is_first):
        if song.audio_file and self.config.spleeter:
            self._detect_gap(song, self._overwrite_gap, is_first)
        else:
            logger.warning(f"Skipping gap detection for '{song.title}': No audio file or Spleeter not configured.")
    
    def _queue_tasks_non_blocking(self, songs, callback):
        """Queue tasks with a small delay between them to avoid UI freeze"""
        if not songs:
            return
            
        # Create a copy of the songs list to avoid modification issues
        songs_to_process = list(songs)
        
        # Process the first song immediately
        first_song = songs_to_process.pop(0)
        callback(first_song, True)  # True = is first song
        
        # If there are more songs, queue them with a small delay
        if songs_to_process:
            QTimer.singleShot(100, lambda: self._process_next_song(songs_to_process, callback))
    
    def _process_next_song(self, remaining_songs, callback):
        """Process the next song in the queue with a delay"""
        if not remaining_songs:
            return
            
        # Process the next song
        next_song = remaining_songs.pop(0)
        callback(next_song, False)  # False = not first song
        
        # If there are more songs, queue the next one with a delay
        if remaining_songs:
            QTimer.singleShot(50, lambda: self._process_next_song(remaining_songs, callback))

    def get_notes_overlap(self, song: Song, silence_periods, detection_time):
        # This likely relates to a single song's detail view/analysis
        # Use first_selected_song if called from a general context
        song_to_process = song or self.data.first_selected_song
        if not song_to_process: return
        # ... rest of the original logic using song_to_process ...
        notes_overlap = usdx.get_notes_overlap(song_to_process.notes, silence_periods, detection_time)
        song_to_process.gap_info.notes_overlap = notes_overlap
        run_async(song_to_process.gap_info.save())
        self.data.songs.updated.emit(song_to_process)

    def update_gap_value(self, song: Song, gap: int):
        # Operates on a single song, likely from detail view
        song_to_process = song or self.data.first_selected_song
        if not song_to_process:
            logger.error("No song selected for updating gap value.")
            return
        # ... rest of the original logic using song_to_process ...
        song_to_process.status = SongStatus.UPDATED
        song_to_process.gap = gap
        song_to_process.gap_info.status = GapInfoStatus.UPDATED
        song_to_process.gap_info.updated_gap = gap
        run_async(song_to_process.usdx_file.write_gap_tag(gap))
        run_async(song_to_process.gap_info.save())
        song_to_process.usdx_file.calculate_note_times()
        self._create_waveforms(song_to_process, True)
        self.data.songs.updated.emit(song_to_process)

    def revert_gap_value(self, song: Song):
        # Operates on a single song
        song_to_process = song or self.data.first_selected_song
        if not song_to_process:
            logger.error("No song selected for reverting gap value.")
            return
        # ... rest of the original logic using song_to_process ...
        song_to_process.gap = song_to_process.gap_info.original_gap
        run_async(song_to_process.usdx_file.write_gap_tag(song_to_process.gap))
        run_async(song_to_process.gap_info.save())
        song_to_process.usdx_file.calculate_note_times()
        self._create_waveforms(song_to_process, True)
        self.data.songs.updated.emit(song_to_process)

    def keep_gap_value(self, song: Song):
        # Operates on a single song
        song_to_process = song or self.data.first_selected_song
        if not song_to_process:
            logger.error("No song selected for keeping gap value.")
            return
        # ... rest of the original logic using song_to_process ...
        song_to_process.status = SongStatus.SOLVED
        song_to_process.gap_info.status = GapInfoStatus.SOLVED
        run_async(song_to_process.gap_info.save())
        self.data.songs.updated.emit(song_to_process)

    def open_usdx(self):
        # Should only work for a single selected song
        if len(self.data.selected_songs) != 1:
            logger.error("Please select exactly one song to open in USDB.")
            return
        song: Song = self.data.first_selected_song # Use the first (and only) selected song
        if not song: # Should not happen if count is 1, but check anyway
            logger.error("No song selected")
            return
        
        # More robust check for usdb_id validity
        if not song.usdb_id or song.usdb_id == "0" or song.usdb_id == "":
            logger.error(f"Song '{song.title}' has no valid USDB ID.")
            return
            
        logger.info(f"Opening USDB in web browser for {song.txt_file} with ID {song.usdb_id}")
        url = QUrl(f"https://usdb.animux.de/index.php?link=detail&id={song.usdb_id}")
        success = QDesktopServices.openUrl(url)
        
        if not success:
            logger.error(f"Failed to open URL: {url.toString()}")

    def open_folder(self):
        # Opens the folder of the first selected song
        song: Song = self.data.first_selected_song
        if not song:
            logger.error("No song selected to open folder.")
            return
        logger.info(f"Opening folder for {song.path}")
        url = QUrl.fromLocalFile(song.path)
        if not QDesktopServices.openUrl(url):
            logger.error("Failed to open the folder.")
            return False
        return True

    def reload_song(self):
        selected_songs = self.data.selected_songs
        if not selected_songs:
            logger.error("No songs selected to reload.")
            return
        logger.info(f"Reloading {len(selected_songs)} selected songs.")
        for song in selected_songs:
            logger.info(f"Reloading song {song.path}")
            try:
                run_sync(song.load())
                self._create_waveforms(song, True) # Recreate waveform after reload
                self.data.songs.updated.emit(song) # Notify update after successful reload
            except Exception as e:
                song.error_message = str(e)
                logger.exception(e)
                self.data.songs.updated.emit(song) # Notify update even on error

    def delete_selected_song(self):
        selected_songs = self.data.selected_songs
        if not selected_songs:
            logger.error("No songs selected to delete.")
            return
        logger.info(f"Attempting to delete {len(selected_songs)} songs.")
        # Confirmation should happen in the UI layer (MenuBar) before calling this
        songs_to_remove = list(selected_songs) # Copy list as we modify the source
        for song in songs_to_remove:
            logger.info(f"Deleting song {song.path}")
            try:
                song.delete() # Assuming song.delete() handles file/folder removal
                self.data.songs.remove(song) # Remove from the model's list
                # No need to emit songs.deleted if the model handles removal correctly
            except Exception as e:
                logger.error(f"Failed to delete song {song.path}: {e}")
                # Optionally notify the user or mark the song as having an error

        # After attempting deletion, clear the selection
        self.set_selected_songs([])
        # Explicitly trigger a list change signal if model doesn't auto-signal on remove
        self.data.songs.list_changed() # Assuming Songs model has such a signal or method

    def normalize_song(self):
        selected_songs = self.data.selected_songs
        if not selected_songs:
            logger.error("No songs selected for normalization.")
            return
        
        logger.info(f"Queueing normalization for {len(selected_songs)} songs.")
        
        # Use async queuing to prevent UI freeze
        self._queue_tasks_non_blocking(selected_songs, self._normalize_song_if_valid)
    
    def _normalize_song_if_valid(self, song, is_first):
        if song.audio_file:
            self._normalize_song(song, is_first)
        else:
            logger.warning(f"Skipping normalization for '{song.title}': No audio file.")

    def _normalize_song(self, song: Song, start_now=False):
        worker = NormalizeAudioWorker(song)
        worker.signals.started.connect(lambda: self._on_song_worker_started(song))
        worker.signals.error.connect(lambda: self._on_song_worker_error(song))
        worker.signals.finished.connect(lambda: self._on_song_worker_finished(song))
        worker.signals.finished.connect(lambda: self._create_waveforms(song, True))
        song.status = SongStatus.QUEUED
        self.data.songs.updated.emit(song)
        self.worker_queue.add_task(worker, start_now)

    def _queue_tasks_non_blocking(self, songs, callback):
        """Queue tasks with a small delay between them to avoid UI freeze"""
        if not songs:
            return
            
        # Create a copy of the songs list to avoid modification issues
        songs_to_process = list(songs)
        
        # Process the first song immediately
        first_song = songs_to_process.pop(0)
        callback(first_song, True)  # True = is first song
        
        # If there are more songs, queue them with a small delay
        if songs_to_process:
            QTimer.singleShot(100, lambda: self._process_next_song(songs_to_process, callback))
    
    def _process_next_song(self, remaining_songs, callback):
        """Process the next song in the queue with a delay"""
        if not remaining_songs:
            return
            
        # Process the next song
        next_song = remaining_songs.pop(0)
        callback(next_song, False)  # False = not first song
        
        # If there are more songs, queue the next one with a delay
        if remaining_songs:
            QTimer.singleShot(50, lambda: self._process_next_song(remaining_songs, callback))

    def _on_detect_gap_finished(self, song: Song):
        # Create waveforms first
        self._create_waveforms(song, True)
        
        # Check if auto-normalization is enabled
        if self.config.auto_normalize and song.audio_file:
            logger.info(f"Auto-normalizing audio for {song.title} after gap detection")
            self._normalize_song(song)

    def _on_song_worker_started(self, song: Song):
        song.status = SongStatus.PROCESSING
        self.data.songs.updated.emit(song)

    def _on_song_worker_error(self, song: Song):
        song.status = SongStatus.ERROR
        self.data.songs.updated.emit(song)

    def _on_song_worker_finished(self, song: Song):
        song.update_status_from_gap_info()
        self.data.songs.updated.emit(song)

    def _create_waveforms(self, song: Song, overwrite: bool = False):
        if not song:
            raise Exception("No song given")
        if overwrite or (os.path.exists(song.audio_file) and not os.path.exists(song.audio_waveform_file)):
            self._create_waveform(song, song.audio_file, song.audio_waveform_file)
        if overwrite or (os.path.exists(song.vocals_file) and not os.path.exists(song.vocals_waveform_file)):
            self._create_waveform(song, song.vocals_file, song.vocals_waveform_file)

    def _create_waveform(self, song: Song, audio_file: str, waveform_file: str):

        logger.debug(f"Creating waveform creation task for '{audio_file}'")
        worker = CreateWaveform(
            song,
            self.config,
            audio_file,
            waveform_file,
        )
        worker.signals.finished.connect(lambda song=song: self.data.songs.updated.emit(song))
        self.worker_queue.add_task(worker, True)
