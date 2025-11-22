from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QComboBox, QSizePolicy, QListView, QLineEdit
from PySide6.QtCore import Qt, Signal, QTimer  # Changed from pyqtSignal
from PySide6.QtGui import QStandardItemModel, QStandardItem, QMouseEvent


class ToggleComboBox(QComboBox):
    """QComboBox that properly toggles popup on text field click without reopen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._popup_visible_on_press = False

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            # Record popup state and consume event
            self._popup_visible_on_press = self.view().isVisible()
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            # Toggle based on state when pressed (prevents close-reopen)
            if self._popup_visible_on_press:
                self.hidePopup()
            else:
                self.showPopup()
            ev.accept()
            return
        super().mouseReleaseEvent(ev)


class CheckableComboBoxListView(QListView):
    def mousePressEvent(self, event: QMouseEvent):
        index = self.indexAt(event.position().toPoint())
        if index.isValid():
            item = self.model().itemFromIndex(index)
            if item.checkState() == Qt.CheckState.Checked:
                item.setCheckState(Qt.CheckState.Unchecked)
            else:
                item.setCheckState(Qt.CheckState.Checked)


class ClickableLineEdit(QLineEdit):
    """Read-only line edit that forwards events to parent combo via event posting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.combo = parent
        self.setReadOnly(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def mousePressEvent(self, event: QMouseEvent):
        # Trigger parent combo's mouse handler directly
        if self.combo and isinstance(self.combo, ToggleComboBox):
            # Map position to combo's coordinate system
            global_pos = self.mapToGlobal(event.position().toPoint())
            combo_pos = self.combo.mapFromGlobal(global_pos)
            # Create new event for combo
            new_event = QMouseEvent(
                event.type(),
                combo_pos,
                event.globalPosition(),
                event.button(),
                event.buttons(),
                event.modifiers()
            )
            self.combo.mousePressEvent(new_event)
            event.accept()
        else:
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        # Trigger parent combo's mouse handler directly
        if self.combo and isinstance(self.combo, ToggleComboBox):
            # Map position to combo's coordinate system
            global_pos = self.mapToGlobal(event.position().toPoint())
            combo_pos = self.combo.mapFromGlobal(global_pos)
            # Create new event for combo
            new_event = QMouseEvent(
                event.type(),
                combo_pos,
                event.globalPosition(),
                event.button(),
                event.buttons(),
                event.modifiers()
            )
            self.combo.mouseReleaseEvent(new_event)
            event.accept()
        else:
            event.accept()


class MultiSelectComboBox(QWidget):
    selectionChanged = Signal(list)  # Changed from pyqtSignal

    def __init__(self, items=[], parent=None):
        super().__init__(parent=parent)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.filterDropdown = ToggleComboBox()
        # Use the custom CheckableComboBoxListView
        self.filterDropdown.setView(CheckableComboBoxListView())

        # Set a readonly line edit that forwards events to ToggleComboBox
        self.displayLineEdit = ClickableLineEdit(self.filterDropdown)
        self.filterDropdown.setLineEdit(self.displayLineEdit)

        self.filterDropdown.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.model = QStandardItemModel()
        for item in items:
            self.addItem(item)

        self.filterDropdown.setModel(self.model)
        self.model.itemChanged.connect(self.onItemChanged)

        # Debounce timer to prevent rapid-fire updates
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(50)  # 50ms debounce
        self._update_timer.timeout.connect(self._performUpdate)

        layout.addWidget(self.filterDropdown)

    def addItem(self, text):
        item = QStandardItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        item.setData(Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
        self.model.appendRow(item)

    def setSelectedItems(self, selectedItems: list[str]):
        """
        Set the selected items programmatically.

        Args:
            selectedItems: A list of strings representing the items to be selected.
                          Must match item text exactly (case-sensitive).
        """
        # Block signals to prevent cascading itemChanged events during programmatic update
        self.model.blockSignals(True)
        try:
            for i in range(self.model.rowCount()):
                item = self.model.item(i)
                if item.text() in selectedItems:
                    item.setCheckState(Qt.CheckState.Checked)
                else:
                    item.setCheckState(Qt.CheckState.Unchecked)
        finally:
            self.model.blockSignals(False)

        # Update the QLineEdit to show the selected items (no debounce for programmatic updates)
        self._performUpdate()

    def updateLineEdit(self):
        """
        Update the QLineEdit to show the currently selected items.
        Deprecated: Use _performUpdate() directly or trigger via debounce timer.
        """
        # Restart debounce timer for user-initiated changes
        self._update_timer.start()

    def _performUpdate(self):
        """
        Immediately update display text and emit selection change signal.
        Called after debounce timer expires or during programmatic updates.
        """
        selectedItems = [
            self.model.item(i).text()
            for i in range(self.model.rowCount())
            if self.model.item(i).checkState() == Qt.CheckState.Checked
        ]
        # Update the line edit display
        self.displayLineEdit.setText(", ".join(selectedItems) if selectedItems else "")
        self.selectionChanged.emit(selectedItems)

    def onItemChanged(self, _):
        # Debounce updates to prevent rapid-fire signal emissions during multi-checkbox changes
        self.updateLineEdit()


# Example usage
if __name__ == "__main__":
    import sys  # Added import sys for example usage

    app = QApplication(sys.argv)
    # Example list of strings to be used as items in the combo box
    items = ["Item 1", "Item 2", "Item 3", "Item 4"]
    multiSelectCombo = MultiSelectComboBox(items)
    multiSelectCombo.setSelectedItems(["Item 1", "Item 3"])

    # Connect the custom signal to a lambda function to print the selected items
    multiSelectCombo.selectionChanged.connect(lambda selected: print("Selected items:", selected))

    multiSelectCombo.show()
    sys.exit(app.exec())
