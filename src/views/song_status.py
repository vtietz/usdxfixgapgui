from PyQt6.QtWidgets import QWidget, QApplication, QHBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
import sys
from enum import Enum

from model.info import SongStatus
from model.songs import Songs

# Assuming SongStatus and Songs are defined elsewhere

class SongsStatusVisualizer(QWidget):
    def __init__(self, songs: Songs, parent=None):
        super().__init__(parent)
        self.songs = songs
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setFixedHeight(3)

        # Optional: Store labels for updating without recreation
        self.status_labels = {}

        # Initialize visualization
        self.update_visualization()

        # Connect signals
        self.songs.added.connect(self.update_visualization)
        self.songs.updated.connect(self.update_visualization)

    def update_visualization(self):
        counts = self.calculate_status_counts()
        total_songs = sum(counts.values())

        if total_songs == 0:
            # Optionally handle the case when there are no songs at all
            for label in self.status_labels.values():
                label.hide()
            return

        for status in SongStatus:
            if status == SongStatus.ALL:
                continue  # Skip the ALL category

            count = counts.get(status, 0)
            proportion = (count / total_songs) if total_songs > 0 else 0

            if status not in self.status_labels:
                label = QLabel(self)
                label.setStyleSheet(f"background-color: {self.get_color_for_status(status).name()};")
                self.status_labels[status] = label
                self.layout.addWidget(label)
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
            else:
                label.setVisible(False)  # Hide labels for statuses with 0 count

        # Refresh layout and widget to reflect changes
        self.layout.update()
        self.update()


    def calculate_status_counts(self):
        # Implement logic to count songs by their status, returning a dictionary
        counts = {status: 0 for status in SongStatus}
        for song in self.songs:
            counts[song.info.status] += 1
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
