"""
Task Queue Viewer - Simple, Robust Implementation

Architecture:
- Full rebuild on signal (no differential patching)
- No widget caching (Qt handles lifecycle via parenting)
- Single source of truth: WorkerQueueManager state
- Manager already debounces via heartbeat, so we rebuild directly
"""

import logging
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHeaderView
from PySide6.QtCore import Qt
from managers.worker_queue_manager import WorkerQueueManager

logger = logging.getLogger(__name__)


class TaskQueueViewer(QWidget):
    """
    Displays the task queue in a simple table.

    Design Philosophy:
    - Rebuild everything on manager signal (simple, no edge cases)
    - No widget caching (avoid lifecycle issues)
    - Let Qt manage widget memory (proper parenting)
    - Manager already debounces updates via heartbeat
    """

    def __init__(self, workerQueueManager: WorkerQueueManager, parent=None):
        super().__init__(parent)
        self.workerQueueManager = workerQueueManager

        # UI setup
        self.initUI()

        # Connect to worker queue signal (manager already debounces)
        self.workerQueueManager.on_task_list_changed.connect(self._rebuild_table)

        # Initial build
        self._rebuild_table()

    def initUI(self):
        """Create the table widget with proper configuration."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.tableWidget = QTableWidget(0, 3)
        self.tableWidget.setHorizontalHeaderLabels(["Task", "Status", ""])
        self.tableWidget.horizontalHeader().setStretchLastSection(False)
        self.tableWidget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tableWidget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.tableWidget.setColumnWidth(1, 100)  # Fixed width for Status column
        self.tableWidget.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.tableWidget.setColumnWidth(2, 80)  # Fixed width for button column
        self.tableWidget.verticalHeader().setVisible(False)
        self.tableWidget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tableWidget.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.tableWidget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.layout.addWidget(self.tableWidget)

    def _gather_tasks(self):
        """
        Gather ordered list of tasks from worker queue manager.

        Order:
        1. Running instant task (if present)
        2. Running standard tasks
        3. Queued instant tasks
        4. Queued standard tasks

        Returns:
            List of tuples: (task_id, description, status_string, can_cancel)
        """
        tasks = []

        # 1. Running instant task
        if self.workerQueueManager.running_instant_task:
            worker = self.workerQueueManager.running_instant_task
            description = getattr(worker, 'description', worker.__class__.__name__)
            status_name = getattr(worker.status, 'name', str(worker.status)) if hasattr(worker, 'status') else 'RUNNING'
            can_cancel = status_name not in ('CANCELLING', 'FINISHED', 'ERROR')
            tasks.append((worker.id, description, status_name, can_cancel))

        # 2. Running standard tasks
        for worker_id, worker in self.workerQueueManager.running_tasks.items():
            description = getattr(worker, 'description', worker.__class__.__name__)
            status_name = getattr(worker.status, 'name', str(worker.status)) if hasattr(worker, 'status') else 'RUNNING'
            can_cancel = status_name not in ('CANCELLING', 'FINISHED', 'ERROR')
            tasks.append((worker_id, description, status_name, can_cancel))

        # 3. Queued instant tasks
        for worker in self.workerQueueManager.queued_instant_tasks:
            description = getattr(worker, 'description', worker.__class__.__name__)
            status_name = 'QUEUED'
            can_cancel = True
            tasks.append((worker.id, description, status_name, can_cancel))

        # 4. Queued standard tasks
        for worker in self.workerQueueManager.queued_tasks:
            description = getattr(worker, 'description', worker.__class__.__name__)
            status_name = 'QUEUED'
            can_cancel = True
            tasks.append((worker.id, description, status_name, can_cancel))

        return tasks

    def _rebuild_table(self):
        """
        Rebuild the entire table from the worker queue state.

        This is the ONLY method that modifies the table.
        Simple, predictable, no edge cases.
        """
        try:
            # Save scroll position
            vscroll = self.tableWidget.verticalScrollBar()
            scroll_pos = vscroll.value() if vscroll else 0

            # Disable updates for smoother rebuild
            self.tableWidget.setUpdatesEnabled(False)

            # Clear all rows (Qt automatically destroys child widgets)
            self.tableWidget.setRowCount(0)

            # Gather current tasks
            tasks = self._gather_tasks()

            # Rebuild rows
            for row_idx, (task_id, description, status_string, can_cancel) in enumerate(tasks):
                self.tableWidget.insertRow(row_idx)

                # Column 0: Description
                desc_item = QTableWidgetItem(description)
                desc_item.setData(Qt.ItemDataRole.UserRole, task_id)
                desc_item.setFlags(desc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.tableWidget.setItem(row_idx, 0, desc_item)

                # Column 1: Status
                status_item = QTableWidgetItem(status_string)
                status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.tableWidget.setItem(row_idx, 1, status_item)

                # Column 2: Cancel button
                btn = QPushButton("Cancel")
                btn.setProperty("task_id", task_id)
                btn.setEnabled(can_cancel)
                if not can_cancel:
                    btn.setText("Cancelling..." if status_string == 'CANCELLING' else "Done")
                # Connect clicked signal
                btn.clicked.connect(lambda checked=False, tid=task_id: self._on_cancel_clicked(tid))
                # Parent to table (Qt will auto-cleanup on row removal)
                self.tableWidget.setCellWidget(row_idx, 2, btn)

            # Restore scroll position
            if vscroll:
                vscroll.setValue(scroll_pos)

            # Re-enable updates
            self.tableWidget.setUpdatesEnabled(True)

        except Exception as e:
            logger.exception("Error rebuilding task queue table: %s", e)
            # Ensure updates are re-enabled even on error
            self.tableWidget.setUpdatesEnabled(True)

    def _on_cancel_clicked(self, task_id):
        """Handle cancel button click."""
        try:
            logger.info("User cancelling task: %s", task_id)
            self.workerQueueManager.cancel_task(task_id)
            # Table will rebuild on next manager signal
        except Exception as e:
            logger.exception("Error cancelling task %s: %s", task_id, e)
