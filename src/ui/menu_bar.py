# button_bar.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QFileDialog, QSizePolicy, QLineEdit, QMessageBox
from PySide6.QtCore import Signal
from typing import List # Import List
from actions import Actions
from app.app_data import AppData
import logging
import os # Import os for path checks
import sys
import subprocess

from model.song import Song, SongStatus
from ui.multi_select_box import MultiSelectComboBox

logger = logging.getLogger(__name__)

class MenuBar(QWidget):

    loadSongsClicked = Signal()
    # Remove specific action signals if actions are called directly
    # extractVocalsClicked = Signal()
    # detectClicked = Signal()
    # deleteClicked = Signal()

    _selected_songs: List[Song] = [] # Use List[Song]

    def __init__(self, actions:Actions, data:AppData, parent=None):

        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        # Explicitly set the layout to avoid shadowing QWidget.layout()
        self.setLayout(self._layout)
        # Avoid shadowing QWidget.actions() by renaming attribute
        self._actions = actions
        self.data = data
        self.config = data.config

        # Load Songs Button
        self.loadSongsButton = QPushButton("Load Songs")
        self.loadSongsButton.clicked.connect(self.choose_directory)
        self._layout.addWidget(self.loadSongsButton)

        # Detect Button - Now triggers action for multiple songs
        self.detectButton = QPushButton("Detect") # Renamed for clarity
        self.detectButton.clicked.connect(lambda: self._actions.detect_gap(overwrite=True)) # Action handles iteration
        self._layout.addWidget(self.detectButton)

        # Open song folder - Opens folder of the first selected song
        self.openFolderButton = QPushButton("Open Folder")
        self.openFolderButton.clicked.connect(lambda: self._actions.open_folder()) # Action handles logic
        self._layout.addWidget(self.openFolderButton)

        # Open usdx webseite - Only enabled for single selection
        self.open_usdx_button = QPushButton("Open in USDB")
        self.open_usdx_button.clicked.connect(lambda: self._actions.open_usdx()) # Action handles logic
        self._layout.addWidget(self.open_usdx_button)

        # Reload song - Reloads all selected songs
        self.reload_button = QPushButton("Reload") # Renamed for clarity
        self.reload_button.clicked.connect(lambda: self._actions.reload_song()) # Action handles iteration
        self._layout.addWidget(self.reload_button)

        # Normalize song - Normalizes all selected songs
        self.normalize_button = QPushButton("Normalize") # Renamed for clarity
        self.normalize_button.clicked.connect(lambda: self._actions.normalize_song()) # Action handles iteration
        self._layout.addWidget(self.normalize_button)

        # Delete song - Deletes all selected songs after confirmation
        self.delete_button = QPushButton("Delete") # Renamed for clarity
        self.delete_button.clicked.connect(self.onDeleteButtonClicked)
        self._layout.addWidget(self.delete_button)

        # Config button - Opens config.ini in default text editor
        self.config_button = QPushButton("Config")
        self.config_button.setToolTip("Open config.ini in text editor")
        self.config_button.clicked.connect(self.open_config_file)
        self._layout.addWidget(self.config_button)

        self.searchBox = QLineEdit()
        self.searchBox.setPlaceholderText("Search")
        self.searchBox.setMinimumWidth(200)
        self.searchBox.textChanged.connect(self.onSearchChanged)
        self._layout.addWidget(self.searchBox)

        # Convert SongStatus values to a list of strings
        status_values = [status.value for status in SongStatus]
        self.filterDropdown = MultiSelectComboBox(items=status_values)
        self.filterDropdown.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.filterDropdown.setMinimumWidth(200)
        self.filterDropdown.setSelectedItems(self._actions.data.songs.filter)
        self.filterDropdown.selectionChanged.connect(self.onFilterChanged)
        self._layout.addWidget(self.filterDropdown)

        self.loadSongsClicked.connect(lambda: self._actions.set_directory(self.data.directory)) # Or use choose_directory

        self._actions.data.selected_songs_changed.connect(self.onSelectedSongsChanged)

        self.onSelectedSongsChanged([]) # Initial state

    def onDeleteButtonClicked(self):
        if not self._selected_songs:
            return

        count = len(self._selected_songs)
        if count == 1:
            msg_text = f"Are you sure you want to delete the following directory?\r\n{self._selected_songs[0].path}?"
        else:
            msg_text = f"Are you sure you want to delete the {count} selected song directories?"
            # Optionally list the first few?
            # msg_text += "\r\nIncluding:\r\n" + "\r\n".join([s.path for s in self._selected_songs[:3]])
            # if count > 3: msg_text += "\r\n..."


        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Icon.Warning) # Use Warning for deletion
        msgBox.setText(msg_text)
        msgBox.setWindowTitle("Delete Confirmation")
        msgBox.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)

        returnValue = msgBox.exec()
        if returnValue == QMessageBox.StandardButton.Ok:
            self._actions.delete_selected_song() # Action handles iteration

    def updateLoadButtonState(self, isLoading: bool):
        self.loadSongsButton.setEnabled(not isLoading)

    def onSearchChanged(self, text):
        self._actions.data.songs.filter_text = text

    # Renamed method to reflect it handles a list
    def onSelectedSongsChanged(self, songs: List[Song]): # Use List[Song]
        self._selected_songs = songs
        num_selected = len(songs)
        first_song = songs[0] if num_selected > 0 else None

        # Enable buttons if at least one song is selected
        has_selection = num_selected > 0
        self.openFolderButton.setEnabled(has_selection)
        self.reload_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

        # Enable detect/normalize if at least one selected song is suitable
        # Detection works with any method (spleeter, vad_preview, hq_segment)
        can_detect = has_selection and any(s.audio_file for s in songs)
        self.detectButton.setEnabled(can_detect)

        can_normalize = has_selection and any(s.audio_file for s in songs)
        self.normalize_button.setEnabled(can_normalize)

        # Enable USDB only if exactly one song is selected and has a valid usdb_id
        # Improved check to ensure usdb_id is a non-empty string
        can_open_usdb = bool(
            (num_selected == 1)
            and (first_song is not None)
            and (first_song.usdb_id is not None)
            and (first_song.usdb_id != "")
            and (first_song.usdb_id != "0")
        )
        self.open_usdx_button.setEnabled(can_open_usdb)

        # Disable player/editor related buttons if multiple songs are selected
        # Assuming these actions require a single song context
        # Example:
        # self.playButton.setEnabled(num_selected == 1)
        # self.editButton.setEnabled(num_selected == 1)

    def open_config_file(self):
        """Open config.ini in the default text editor (cross-platform)"""
        config_path = self.config.config_path

        if not os.path.exists(config_path):
            QMessageBox.warning(
                self,
                "Config Not Found",
                f"Configuration file not found at:\n{config_path}"
            )
            return

        try:
            if sys.platform == 'win32':
                # Windows - use default associated program
                os.startfile(config_path)
            elif sys.platform == 'darwin':
                # macOS
                subprocess.run(['open', config_path], check=True)
            else:
                # Linux and other Unix-like systems
                # Try xdg-open first (most common), fall back to common editors
                try:
                    subprocess.run(['xdg-open', config_path], check=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    # Fallback to common text editors
                    for editor in ['gedit', 'kate', 'nano', 'vi']:
                        try:
                            subprocess.Popen([editor, config_path])
                            break
                        except FileNotFoundError:
                            continue
                    else:
                        raise FileNotFoundError("No suitable text editor found")

            logger.info(f"Opened config file: {config_path}")
        except Exception as e:
            logger.error(f"Failed to open config file: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "Cannot Open Config",
                f"Failed to open configuration file:\n{str(e)}\n\nPath: {config_path}"
            )

    def choose_directory(self):
        # Use the last directory from config if available, otherwise use the current directory
        start_dir = self.data.directory if self.data.directory else self.config.last_directory

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Directory",
            start_dir
        )
        if directory:  # Check if a directory was selected
            self.on_directory_selected(directory)

    def on_directory_selected(self, directory: str):
        self._actions.set_directory(directory)

    def onFilterChanged(self, selectedStatuses):
        self._actions.data.songs.filter=selectedStatuses
