from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QProgressBar
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

from model.songs import Songs, SongStatus
from app.app_data import AppData

# Assuming SongStatus and Songs are defined elsewhere

class SongsStatusVisualizer(QWidget):
    def __init__(self, songs: Songs, data: 'AppData | None' = None, parent=None):
        super().__init__(parent)
        self.songs = songs
        self.data = data  # Optional AppData for loading state
        self._layout = QHBoxLayout()
        self.setLayout(self._layout)
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(0, 0, 0, 0)
        #self.setFixedHeight(5)

        # Optional: Store labels for updating without recreation
        self.status_labels = {}

        # Placeholder (shown when there are no songs)
        self.placeholder_label = QLabel()
        self.placeholder_label.setStyleSheet("background-color: #2E2E2E; color: rgba(255, 255, 255, 0.3);")
        self.placeholder_label.setFixedHeight(20)  # Same height as status bar
        self._layout.addWidget(self.placeholder_label)

        # Initialize visualization
        self.update_visualization()

        # Connect signals
        self.songs.added.connect(self.update_visualization)
        self.songs.updated.connect(self.update_visualization)
        self.songs.deleted.connect(self.update_visualization)
        self.songs.cleared.connect(self.update_visualization)
        self.songs.listChanged.connect(self.update_visualization)  # React to batch adds

    def update_visualization(self):
        counts = self.calculate_status_counts()
        total_songs = sum(counts.values())

        if total_songs == 0:
            # Show placeholder when no songs
            self.placeholder_label.show()
            # Hide all status labels
            for label in self.status_labels.values():
                label.hide()
            return
        else:
            # Hide placeholder when we have songs
            self.placeholder_label.hide()

        for status in SongStatus:

            count = counts.get(status, 0)
            proportion = (count / total_songs) if total_songs > 0 else 0

            if status not in self.status_labels:
                label = QLabel(self)
                label.setStyleSheet(f"background-color: {self.get_color_for_status(status).name()}; color: rgba(255, 255, 255, 0.5); font-size: 8px;")
                self.status_labels[status] = label
                self._layout.addWidget(label)
            else:
                label = self.status_labels[status]

            if count > 0:
                label.setToolTip(f"{status.name}: {count}")
                label.setVisible(True)
                # Adjust the label's size policy to reflect its proportion of the total
                policy = label.sizePolicy()
                policy.setHorizontalStretch(int(proportion * 100))  # Use the proportion to influence the stretch factor
                label.setSizePolicy(policy)
                label.setMinimumWidth(int(proportion * 100))  # This helps in making sure that the QLabel's size changes dynamically based on the proportion
                label.setText(str(count))
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            else:
                label.setVisible(False)  # Hide labels for statuses with 0 count

        # Refresh widget to reflect changes
        self.update()


    def calculate_status_counts(self):
        # Implement logic to count songs by their status, returning a dictionary
        counts = {status: 0 for status in SongStatus}
        for song in self.songs:
            counts[song.status] += 1
        return counts

    def get_color_for_status(self, status):
        # Map each status to a color
        colors = {
            SongStatus.NOT_PROCESSED: QColor("#787E7A"),
            SongStatus.QUEUED: QColor("#335775"),
            SongStatus.PROCESSING: QColor("#165182"),
            SongStatus.UPDATED: QColor("#008716"),
            SongStatus.SOLVED: QColor("#338240"),
            SongStatus.MATCH: QColor("#66896C"),
            SongStatus.MISMATCH: QColor("#90492B"),
            SongStatus.ERROR: QColor("#8A2900"),
        }
        return colors.get(status, QColor("grey"))
