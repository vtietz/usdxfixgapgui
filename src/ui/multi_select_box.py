from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QComboBox, QSizePolicy, QListView, QLineEdit
from PySide6.QtCore import Qt, Signal, QTimer  # Changed from pyqtSignal
from PySide6.QtGui import QStandardItemModel, QStandardItem, QMouseEvent


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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent  # Store reference to the parent widget (the combo box)

    def mousePressEvent(self, event: QMouseEvent):
        super().mousePressEvent(event)
        # Check if the parent is set and is a QComboBox, then show its dropdown list
        if self.parent and isinstance(self.parent, QComboBox):
            self.parent.showPopup()


class MultiSelectComboBox(QWidget):
    selectionChanged = Signal(list)  # Changed from pyqtSignal

    def __init__(self, items=[], parent=None):
        super().__init__(parent=parent)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.filterDropdown = QComboBox()
        # Use the custom CheckableComboBoxListView
        self.filterDropdown.setView(CheckableComboBoxListView())

        # Set the custom ClickableLineEdit
        self.clickableLineEdit = ClickableLineEdit(self.filterDropdown)
        self.clickableLineEdit.setText("")
        self.clickableLineEdit.setReadOnly(True)
        self.filterDropdown.setLineEdit(self.clickableLineEdit)

        self.filterDropdown.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.model = QStandardItemModel()
        for item in items:
            self.addItem(item)

        self.filterDropdown.setModel(self.model)
        self.model.itemChanged.connect(self.onItemChanged)

        # Set placeholder text for when no items are selected
        self.clickableLineEdit.setPlaceholderText("")

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

    def setSelectedItems(self, selectedItems):
        """
        Set the selected items programmatically.
        :param selectedItems: A list of strings representing the items to be selected.
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
        Immediately update the QLineEdit text and emit selection change signal.
        Called after debounce timer expires or during programmatic updates.
        """
        selectedItems = [
            self.model.item(i).text()
            for i in range(self.model.rowCount())
            if self.model.item(i).checkState() == Qt.CheckState.Checked
        ]
        # Explicitly clear text when no items selected (fixes stale text bug)
        self.clickableLineEdit.setText(", ".join(selectedItems) if selectedItems else "")
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
