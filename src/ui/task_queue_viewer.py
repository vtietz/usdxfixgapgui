import logging
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton
from PySide6.QtCore import QMetaObject, Qt, QThread
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
        # Save current scroll position
        vscroll_pos = self.tableWidget.verticalScrollBar().value() if self.tableWidget.verticalScrollBar() else 0
        
        # Get current tasks
        running_tasks = list(self.workerQueueManager.running_tasks.items())
        queued_tasks = list(self.workerQueueManager.queued_tasks)
        
        # Create a map of task IDs to their data
        task_map = {}
        for task_id, worker in running_tasks:
            task_map[task_id] = (worker.description, worker.status.name)
        for worker in queued_tasks:
            task_map[worker.id] = (worker.description, worker.status.name)
            
        # Process existing rows first
        rows_to_remove = []
        for row in range(self.tableWidget.rowCount()):
            # Get the task ID stored in the first column
            desc_item = self.tableWidget.item(row, 0)
            if not desc_item:
                rows_to_remove.append(row)
                continue
                
            task_id = desc_item.data(Qt.ItemDataRole.UserRole)
            if not task_id or task_id not in task_map:
                rows_to_remove.append(row)
                continue
                
            # Update the existing row
            description, status = task_map[task_id]
            desc_item.setText(description)
            
            status_item = self.tableWidget.item(row, 1)
            if status_item:
                status_item.setText(status)
                
            # Update button state
            button = self.tableWidget.cellWidget(row, 2)
            if button:
                if status == WorkerStatus.CANCELLING.name or task_id in self.cancelling_tasks:
                    button.setText("Cancelling...")
                    button.setEnabled(False)
                else:
                    button.setText("Cancel")
                    button.setEnabled(True)
            
            # Mark this task as handled
            del task_map[task_id]
        
        # Remove rows in reverse order to avoid index issues
        for row in sorted(rows_to_remove, reverse=True):
            self.tableWidget.removeRow(row)
            
        # Add rows for remaining tasks
        for task_id, (description, status) in task_map.items():
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
