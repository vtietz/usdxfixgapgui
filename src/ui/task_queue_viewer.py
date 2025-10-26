import logging
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton
from PySide6.QtCore import Qt
from managers.worker_queue_manager import WorkerQueueManager, WorkerStatus

logger = logging.getLogger(__name__)

class TaskQueueViewer(QWidget):

    def __init__(self, workerQueueManager:WorkerQueueManager, parent=None):
        super().__init__(parent)
        self.workerQueueManager = workerQueueManager
        self.initUI()
        self.updateTaskList()
        self.workerQueueManager.on_task_list_changed.connect(self.updateTaskList)
        # Track the tasks that are being cancelled to prevent UI flicker
        self.cancelling_tasks = set()

    def initUI(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.tableWidget = QTableWidget()
        self.tableWidget.setColumnCount(3)
        self.tableWidget.setHorizontalHeaderLabels(["Task", "Status", ""])
        self.tableWidget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tableWidget.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.layout.addWidget(self.tableWidget)

        # Adjust the initial width of the first and third columns, and let the second column take the remaining space
        self.tableWidget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tableWidget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.tableWidget.setColumnWidth(1, 100)  # Set width of "Status" column

    def updateTaskList(self):
        """
        Update task list with explicit FIFO ordering:
        1. Running instant task (if any)
        2. Running standard tasks
        3. Queued instant tasks (oldest first)
        4. Queued standard tasks (oldest first)
        """
        # Save current scroll position
        vscroll_pos = self.tableWidget.verticalScrollBar().value() if self.tableWidget.verticalScrollBar() else 0

        # Build ordered list of (task_id, description, status, lane) tuples
        ordered_tasks = []

        # 1. Running instant task (single slot)
        if self.workerQueueManager.running_instant_task:
            worker = self.workerQueueManager.running_instant_task
            ordered_tasks.append((worker.id, worker.description, worker.status.name, "instant"))

        # 2. Running standard tasks (dict - use values in insertion order)
        for task_id, worker in self.workerQueueManager.running_tasks.items():
            ordered_tasks.append((task_id, worker.description, worker.status.name, "standard"))

        # 3. Queued instant tasks (deque - oldest first)
        for worker in self.workerQueueManager.queued_instant_tasks:
            ordered_tasks.append((worker.id, worker.description, worker.status.name, "instant"))

        # 4. Queued standard tasks (deque - oldest first)
        for worker in self.workerQueueManager.queued_tasks:
            ordered_tasks.append((worker.id, worker.description, worker.status.name, "standard"))

        # Clear and rebuild table to ensure correct ordering
        self.tableWidget.setRowCount(0)

        for task_id, description, status, lane in ordered_tasks:
            row = self.tableWidget.rowCount()
            self.tableWidget.insertRow(row)

            # Create and populate description item with task_id
            desc_item = QTableWidgetItem(description)
            desc_item.setData(Qt.ItemDataRole.UserRole, task_id)
            self.tableWidget.setItem(row, 0, desc_item)

            # Create status item
            self.tableWidget.setItem(row, 1, QTableWidgetItem(status))

            # Create cancel button
            cancel_button = QPushButton("Cancel")
            cancel_button.clicked.connect(lambda checked=False, tid=task_id: self.cancel_task(tid))

            # Set button state based on status
            if status == WorkerStatus.CANCELLING.name or task_id in self.cancelling_tasks:
                cancel_button.setText("Cancelling...")
                cancel_button.setEnabled(False)

            self.tableWidget.setCellWidget(row, 2, cancel_button)

        # Restore scroll position
        if self.tableWidget.verticalScrollBar():
            self.tableWidget.verticalScrollBar().setValue(vscroll_pos)

    def cancel_task(self, task_id):
        logger.debug(f"Cancelling task {task_id}")

        # Mark this task as being cancelled
        self.cancelling_tasks.add(task_id)

        # Update the UI immediately for better feedback
        for row in range(self.tableWidget.rowCount()):
            desc_item = self.tableWidget.item(row, 0)
            if desc_item and desc_item.data(Qt.ItemDataRole.UserRole) == task_id:
                button = self.tableWidget.cellWidget(row, 2)
                if button:
                    button.setText("Cancelling...")
                    button.setEnabled(False)
                break

        # Actually cancel the task
        self.workerQueueManager.cancel_task(task_id)