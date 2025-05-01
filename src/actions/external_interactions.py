import logging
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QDesktopServices
from common.data import AppData

logger = logging.getLogger(__name__)

class ExternalInteractions(QObject):
    """Handles interactions with external applications and resources"""
    
    def __init__(self, data: AppData):
        super().__init__()
        self.data = data

    def open_usdx(self):
        # Should only work for a single selected song
        if len(self.data.selected_songs) != 1:
            logger.error("Please select exactly one song to open in USDB.")
            return
        song = self.data.first_selected_song # Use the first (and only) selected song
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
        song = self.data.first_selected_song
        if not song:
            logger.error("No song selected to open folder.")
            return
        logger.info(f"Opening folder for {song.path}")
        url = QUrl.fromLocalFile(song.path)
        if not QDesktopServices.openUrl(url):
            logger.error("Failed to open the folder.")
            return False
        return True
