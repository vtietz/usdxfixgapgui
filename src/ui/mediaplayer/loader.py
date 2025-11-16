import os
import logging
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtMultimedia import QMediaPlayer

logger = logging.getLogger(__name__)


class MediaPlayerLoader:
    """
    Cancelable, idempotent loader for QMediaPlayer.setSource.

    Replaces one-shot timers with a per-instance QTimer that can be stopped/restarted,
    ensuring 'last request wins' and preventing late setSource calls after unload or
    UI filter transitions.

    Usage:
      - Call load(file) to schedule setting the media source after a short delay
        (coalesces rapid changes).
      - Call unload() to cancel any pending load and clear the source immediately.
      - has_pending() returns whether a load is currently scheduled.
    """

    def __init__(self, media_player: QMediaPlayer):
        self.media_player = media_player
        self._timer = QTimer(self.media_player)  # Parent to player for lifecycle
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._pending_file: str | None = None
        self._delay_ms = 150  # debounce window for rapid mode/status changes

    def load(self, file: str):
        """
        Schedule loading a media file after a short debounce.
        Last-request-wins: any previously scheduled load is canceled.

        Args:
            file: Path to media file
        """
        try:
            # Cancel any prior pending load
            if self._timer.isActive():
                self._timer.stop()

            self._pending_file = file
            logger.debug(
                f"MediaPlayerLoader: scheduled load in {self._delay_ms}ms "
                f"(player_id={id(self.media_player)}, file='{file}')"
            )
            self._timer.start(self._delay_ms)
        except Exception as e:
            logger.error(f"MediaPlayerLoader.load exception: {e}", exc_info=True)

    def unload(self):
        """
        Cancel any pending load and clear the media source immediately.
        """
        try:
            if self._timer.isActive():
                self._timer.stop()
                logger.debug(f"MediaPlayerLoader: canceled pending load " f"(player_id={id(self.media_player)})")
        finally:
            self._pending_file = None
            self.media_player.setSource(QUrl())
            logger.debug(f"MediaPlayerLoader: source cleared " f"(player_id={id(self.media_player)})")

    def cancel(self):
        """
        Cancel any pending load without clearing the current source.
        """
        if self._timer.isActive():
            self._timer.stop()
            logger.debug(f"MediaPlayerLoader: pending load canceled " f"(player_id={id(self.media_player)})")
        self._pending_file = None

    def has_pending(self) -> bool:
        """
        Check if a load operation is currently scheduled.
        """
        return self._timer.isActive()

    def _on_timeout(self):
        """
        Timer callback to apply the pending setSource, if still valid.
        Enforces last-request-wins semantics and guards against stale paths.
        """
        file = self._pending_file
        self._pending_file = None  # consume the pending request

        try:
            if file and os.path.exists(file):
                logger.debug(
                    f"MediaPlayerLoader: applying setSource(file) "
                    f"(player_id={id(self.media_player)}, file='{file}')"
                )
                self.media_player.setSource(QUrl.fromLocalFile(file))
            else:
                # Missing/invalid file → clear
                logger.debug(
                    f"MediaPlayerLoader: missing/invalid file, clearing source "
                    f"(player_id={id(self.media_player)}, file='{file}')"
                )
                self.media_player.setSource(QUrl())
        except Exception as e:
            logger.error(f"MediaPlayerLoader._on_timeout exception: {e}", exc_info=True)
