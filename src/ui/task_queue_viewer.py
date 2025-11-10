import logging
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton
from PySide6.QtCore import Qt, QTimer
from managers.worker_queue_manager import WorkerQueueManager, WorkerStatus

logger = logging.getLogger(__name__)


class TaskQueueViewer(QWidget):

    def __init__(self, workerQueueManager: WorkerQueueManager, parent=None):
        super().__init__(parent)
        self.workerQueueManager = workerQueueManager
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(200)  # ms; coalesce frequent updates
        self._update_timer.timeout.connect(self.apply_diff_update)
        self.cancelling_tasks = set()
        self._row_for_task_id = {}
        self._button_for_task_id = {}
        self.initUI()
        # Initial population
        self.apply_diff_update()
        # Debounced updates from manager
        self.workerQueueManager.on_task_list_changed.connect(self.schedule_update)

    def initUI(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.tableWidget = QTableWidget()
        self.tableWidget.setColumnCount(3)
        self.tableWidget.setHorizontalHeaderLabels(["Task", "Status", ""])
        self.tableWidget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tableWidget.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.layout.addWidget(self.tableWidget)

        # Adjust the initial width of the first and third columns, and let the second column take the remaining space
        self.tableWidget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tableWidget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.tableWidget.setColumnWidth(1, 100)  # Set width of "Status" column

    def schedule_update(self):
        # Restart the timer to coalesce multiple rapid emits
        if self._update_timer.isActive():
            self._update_timer.stop()
        self._update_timer.start()

    def compute_ordered_tasks(self):
        """
        Return ordered list of (task_id, description, status, lane)
        1) Running fast lane (instant)
        2) Running standard
        3) Queued fast (oldest first)
        4) Queued standard (oldest first)
        """
        ordered = []
        # Running instant task
        if self.workerQueueManager.running_instant_task:
            w = self.workerQueueManager.running_instant_task
            ordered.append((w.id, w.description, w.status.name, "instant"))
        # Running standard tasks
        for task_id, w in self.workerQueueManager.running_tasks.items():
            ordered.append((task_id, w.description, w.status.name, "standard"))
        # Queued instant tasks
        for w in self.workerQueueManager.queued_instant_tasks:
            ordered.append((w.id, w.description, w.status.name, "instant"))
        # Queued standard tasks
        for w in self.workerQueueManager.queued_tasks:
            ordered.append((w.id, w.description, w.status.name, "standard"))
        return ordered

    def apply_diff_update(self):
        # Save current scroll position
        vscroll = self.tableWidget.verticalScrollBar() if self.tableWidget.verticalScrollBar() else None
        vpos = vscroll.value() if vscroll else 0

        self.tableWidget.setUpdatesEnabled(False)

        desired = self.compute_ordered_tasks()
        desired_ids = [tid for (tid, _, _, _) in desired]

        # Rebuild current row map from the table
        current_ids = []
        self._row_for_task_id.clear()
        for row in range(self.tableWidget.rowCount()):
            item = self.tableWidget.item(row, 0)
            tid = item.data(Qt.ItemDataRole.UserRole) if item else None
            if tid is not None:
                current_ids.append(tid)
                self._row_for_task_id[tid] = row

        # Add missing rows
        for index, (task_id, description, status, lane) in enumerate(desired):
            if task_id not in self._row_for_task_id:
                self.tableWidget.insertRow(index)
                # Description item
                desc_item = QTableWidgetItem(description)
                desc_item.setData(Qt.ItemDataRole.UserRole, task_id)
                self.tableWidget.setItem(index, 0, desc_item)
                # Status item
                status_item = QTableWidgetItem(status)
                self.tableWidget.setItem(index, 1, status_item)
                # Cancel button (create once)
                btn = self._button_for_task_id.get(task_id)
                if btn is None:
                    btn = QPushButton("Cancel")
                    btn.clicked.connect(lambda checked=False, tid=task_id: self.cancel_task(tid))
                    self._button_for_task_id[task_id] = btn
                # Set initial button state
                if status == WorkerStatus.CANCELLING.name or task_id in self.cancelling_tasks:
                    btn.setText("Cancelling...")
                    btn.setEnabled(False)
                else:
                    btn.setText("Cancel")
                    btn.setEnabled(True)
                self.tableWidget.setCellWidget(index, 2, btn)
                # Update mapping
                # Shift existing rows mapping for rows >= index
                for tid, row_idx in list(self._row_for_task_id.items()):
                    if row_idx >= index:
                        self._row_for_task_id[tid] = row_idx + 1
                self._row_for_task_id[task_id] = index

        # Update existing cells
        for index, (task_id, description, status, lane) in enumerate(desired):
            row = self._row_for_task_id.get(task_id)
            if row is None:
                continue
            # Description text
            desc_item = self.tableWidget.item(row, 0)
            if desc_item and desc_item.text() != description:
                desc_item.setText(description)
            # Status text
            status_item = self.tableWidget.item(row, 1)
            if status_item and status_item.text() != status:
                status_item.setText(status)
            # Button state
            btn = self._button_for_task_id.get(task_id)
            if btn:
                if status == WorkerStatus.CANCELLING.name or task_id in self.cancelling_tasks:
                    if btn.text() != "Cancelling...":
                        btn.setText("Cancelling...")
                    if btn.isEnabled():
                        btn.setEnabled(False)
                else:
                    if btn.text() != "Cancel":
                        btn.setText("Cancel")
                    if not btn.isEnabled():
                        btn.setEnabled(True)

        # Remove rows that are no longer desired
        for tid in list(self._row_for_task_id.keys()):
            if tid not in desired_ids:
                row = self._row_for_task_id[tid]
                # Remove button mapping
                self._button_for_task_id.pop(tid, None)
                self.tableWidget.removeRow(row)
                # Update mapping: decrement rows above removed
                for other_tid, other_row in list(self._row_for_task_id.items()):
                    if other_row > row:
                        self._row_for_task_id[other_tid] = other_row - 1
                self._row_for_task_id.pop(tid, None)

        # Reorder rows in place to match desired order
        # Refresh mapping before moves
        self._row_for_task_id.clear()
        current_order = []
        for row in range(self.tableWidget.rowCount()):
            item = self.tableWidget.item(row, 0)
            tid = item.data(Qt.ItemDataRole.UserRole) if item else None
            if tid is not None:
                current_order.append(tid)
                self._row_for_task_id[tid] = row

        def move_row(src, dst):
            if src == dst:
                return
            items = [self.tableWidget.takeItem(src, c) for c in range(2)]
            btn = self.tableWidget.cellWidget(src, 2)
            if btn:
                self.tableWidget.removeCellWidget(src, 2)
            self.tableWidget.removeRow(src)
            self.tableWidget.insertRow(dst)
            for c, it in enumerate(items):
                self.tableWidget.setItem(dst, c, it)
            if btn:
                self.tableWidget.setCellWidget(dst, 2, btn)
            # Update mapping after move
            # Recompute mapping for simplicity
            self._row_for_task_id.clear()
            for r in range(self.tableWidget.rowCount()):
                it0 = self.tableWidget.item(r, 0)
                t = it0.data(Qt.ItemDataRole.UserRole) if it0 else None
                if t is not None:
                    self._row_for_task_id[t] = r

        for target_index, tid in enumerate(desired_ids):
            cur_row = self._row_for_task_id.get(tid)
            if cur_row is None:
                continue
            if cur_row != target_index:
                move_row(cur_row, target_index)

        # Restore scroll position
        if vscroll:
            vscroll.setValue(vpos)

        self.tableWidget.setUpdatesEnabled(True)

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
