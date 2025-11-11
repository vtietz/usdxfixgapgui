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
        vscroll, vpos = self._get_scroll_state()
        self.tableWidget.setUpdatesEnabled(False)

        desired = self.compute_ordered_tasks()
        desired_ids = [tid for (tid, _, _, _) in desired]

        # Current table snapshot
        self._rebuild_row_map()

        # 1) Add any missing rows
        self._add_missing_rows(desired)
        self._rebuild_row_map()

        # 2) Update text/button state for existing rows
        self._update_existing_rows(desired)

        # 3) Remove rows not in desired
        self._remove_missing_rows(desired_ids)
        self._rebuild_row_map()

        # 4) Reorder to match desired_ids
        self._reorder_rows(desired_ids)

        # Restore scroll and re-enable updates
        self._restore_scroll(vscroll, vpos)
        self.tableWidget.setUpdatesEnabled(True)

    # -------------------------
    # Internal helpers (UI ops)
    # -------------------------
    def _get_scroll_state(self):
        vscroll = self.tableWidget.verticalScrollBar() if self.tableWidget.verticalScrollBar() else None
        vpos = vscroll.value() if vscroll else 0
        return vscroll, vpos

    def _restore_scroll(self, vscroll, vpos):
        if vscroll:
            vscroll.setValue(vpos)

    def _rebuild_row_map(self):
        self._row_for_task_id.clear()
        for row in range(self.tableWidget.rowCount()):
            item = self.tableWidget.item(row, 0)
            tid = item.data(Qt.ItemDataRole.UserRole) if item else None
            if tid is not None:
                self._row_for_task_id[tid] = row

    def _ensure_button(self, task_id):
        btn = self._button_for_task_id.get(task_id)
        if btn is None:
            btn = QPushButton("Cancel")
            btn.clicked.connect(lambda checked=False, tid=task_id: self.cancel_task(tid))
            self._button_for_task_id[task_id] = btn
        return btn

    def _set_button_state(self, btn: QPushButton, task_id, status: str):
        cancelling = status == WorkerStatus.CANCELLING.name or task_id in self.cancelling_tasks
        if cancelling:
            if btn.text() != "Cancelling...":
                btn.setText("Cancelling...")
            if btn.isEnabled():
                btn.setEnabled(False)
        else:
            if btn.text() != "Cancel":
                btn.setText("Cancel")
            if not btn.isEnabled():
                btn.setEnabled(True)

    def _add_missing_rows(self, desired):
        for index, (task_id, description, status, _lane) in enumerate(desired):
            if task_id in self._row_for_task_id:
                continue
            self.tableWidget.insertRow(index)
            # Description
            desc_item = QTableWidgetItem(description)
            desc_item.setData(Qt.ItemDataRole.UserRole, task_id)
            self.tableWidget.setItem(index, 0, desc_item)
            # Status
            status_item = QTableWidgetItem(status)
            self.tableWidget.setItem(index, 1, status_item)
            # Button
            btn = self._ensure_button(task_id)
            self._set_button_state(btn, task_id, status)
            self.tableWidget.setCellWidget(index, 2, btn)

    def _update_existing_rows(self, desired):
        for _index, (task_id, description, status, _lane) in enumerate(desired):
            row = self._row_for_task_id.get(task_id)
            if row is None:
                continue
            # Description text
            desc_item = self.tableWidget.item(row, 0)
            if desc_item is not None and desc_item.text() != description:
                desc_item.setText(description)
            # Status text
            status_item = self.tableWidget.item(row, 1)
            if status_item is not None and status_item.text() != status:
                status_item.setText(status)
            # Button state
            btn = self._button_for_task_id.get(task_id)
            if btn is not None:
                self._set_button_state(btn, task_id, status)

    def _remove_missing_rows(self, desired_ids):
        for tid in list(self._row_for_task_id.keys()):
            if tid in desired_ids:
                continue
            row = self._row_for_task_id.get(tid)
            if row is None:
                continue
            self._button_for_task_id.pop(tid, None)
            self.tableWidget.removeRow(row)
            self._row_for_task_id.pop(tid, None)

    def _reorder_rows(self, desired_ids):
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
            # Mapping changes; rebuild to keep logic simple and robust
            self._rebuild_row_map()

        self._rebuild_row_map()
        for target_index, tid in enumerate(desired_ids):
            cur_row = self._row_for_task_id.get(tid)
            if cur_row is None:
                continue
            if cur_row != target_index:
                move_row(cur_row, target_index)

    def cancel_task(self, task_id):
        logger.debug("Cancelling task %s", task_id)
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
