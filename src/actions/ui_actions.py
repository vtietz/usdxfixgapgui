import logging
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from actions.base_actions import BaseActions
from model.song import Song

logger = logging.getLogger(__name__)

class UiActions(BaseActions):
    """UI-related actions like opening URLs and folders"""

    def open_usdx(self):
        # Should only work for a single selected song
        if len(self.data.selected_songs) != 1:
            logger.error("Please select exactly one song to open in USDB.")
            return
        song: Song | None = self.data.first_selected_song
        if not song:
            logger.error("No song selected")
            return

        # More robust check for usdb_id validity (usdb_id is Optional[int])
        if not song.usdb_id or song.usdb_id == 0:
            logger.error(f"Song '{song.title}' has no valid USDB ID.")
            return

        logger.info(f"Opening USDB in web browser for {song.txt_file} with ID {song.usdb_id}")
        url = QUrl(f"https://usdb.animux.de/index.php?link=detail&id={song.usdb_id}")
        success = QDesktopServices.openUrl(url)

        if not success:
            logger.error(f"Failed to open URL: {url.toString()}")

    def open_folder(self):
        # Opens the folder of the first selected song
        song: Song | None = self.data.first_selected_song
        if not song:
            logger.error("No song selected to open folder.")
            return
        logger.info(f"Opening folder for {song.path}")
        url = QUrl.fromLocalFile(song.path)
        if not QDesktopServices.openUrl(url):
            logger.error("Failed to open the folder.")
            return False
        return True