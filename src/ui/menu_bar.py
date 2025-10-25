# button_bar.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QFileDialog, QSizePolicy, QLineEdit, QMessageBox
from PySide6.QtCore import Signal
from typing import List  # Import List
from actions import Actions
from app.app_data import AppData
import logging
import os  # Import os for path checks
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

    def __init__(self, actions: Actions, data: AppData, parent=None):

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

        # Watch Mode toggle button - checkable button for watch mode
        self.watch_mode_button = QPushButton("Watch Mode")
        self.watch_mode_button.setCheckable(True)
        self.watch_mode_button.setChecked(False)
        self.watch_mode_button.setEnabled(False)  # Disabled until requirements met
        self.watch_mode_button.setToolTip("Monitor directory for changes and auto-update")
        # Simple style with dark orange when checked
        self.watch_mode_button.setStyleSheet("""
            QPushButton:checked {
                background-color: #D2691E;
                color: white;
            }
        """)
        self.watch_mode_button.clicked.connect(self.onWatchModeToggled)
        self._layout.addWidget(self.watch_mode_button)

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

        # Or use choose_directory
        self.loadSongsClicked.connect(lambda: self._actions.set_directory(self.data.directory))

        # Connect to watch mode signals
        self._actions.initial_scan_completed.connect(self.onInitialScanCompleted)
        self._actions.watch_mode_enabled_changed.connect(self.onWatchModeEnabledChanged)

    def updateLoadButtonState(self, isLoading: bool):
        self.loadSongsButton.setEnabled(not isLoading)

    def onSearchChanged(self, text):
        self._actions.data.songs.filter_text = text

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
                logger.info(f"Opened config file: {config_path}")
            elif sys.platform == 'darwin':
                # macOS
                subprocess.run(['open', config_path], check=True)
                logger.info(f"Opened config file: {config_path}")
            else:
                # Linux and other Unix-like systems
                # Try xdg-open first (most common), fall back to common editors
                try:
                    subprocess.run(['xdg-open', config_path], check=True)
                    logger.info(f"Opened config file: {config_path}")
                except (subprocess.CalledProcessError, FileNotFoundError):
                    # Fallback to common text editors
                    for editor in ['gedit', 'kate', 'nano', 'vi']:
                        try:
                            subprocess.Popen([editor, config_path])
                            logger.info(f"Opened config file with {editor}: {config_path}")
                            break
                        except FileNotFoundError:
                            continue
                    else:
                        raise FileNotFoundError("No suitable text editor found")

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
        self._actions.data.songs.filter = selectedStatuses

    def onWatchModeToggled(self, checked: bool):
        """Handle watch mode toggle button click."""
        if checked:
            # User wants to enable watch mode
            success = self._actions.start_watch_mode()
            if not success:
                # Failed to start - uncheck the button
                self.watch_mode_button.setChecked(False)
                QMessageBox.warning(
                    self,
                    "Watch Mode Error",
                    "Failed to start watch mode. Check logs for details."
                )
        else:
            # User wants to disable watch mode
            self._actions.stop_watch_mode()

    def onInitialScanCompleted(self):
        """Handle initial scan completion - enables watch mode button."""
        if self._actions.can_enable_watch_mode():
            self.watch_mode_button.setEnabled(True)
            logger.info("Watch mode button enabled after initial scan")

    def onWatchModeEnabledChanged(self, enabled: bool):
        """Handle watch mode state change from actions."""
        # Update button state to match actual watch mode state
        self.watch_mode_button.setChecked(enabled)
        logger.info(f"Watch mode {'enabled' if enabled else 'disabled'}")
