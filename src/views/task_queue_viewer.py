import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton
from PyQt6.QtCore import QMetaObject, Qt, QThread
from workers.worker_queue_manager import WorkerQueueManager

logger = logging.getLogger(__name__)

class TaskQueueViewer(QWidget):

    def __init__(self, workerQueueManager:WorkerQueueManager, parent=None):
        super().__init__(parent)
        self.workerQueueManager = workerQueueManager
        self.initUI()
        self.updateTaskList()
        self.workerQueueManager.on_task_list_changed.connect(self.updateTaskList)

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
        self.tableWidget.setRowCount(0)
        # Take a snapshot of running tasks and then iterate
        running_tasks_snapshot = list(self.workerQueueManager.running_tasks.items())
        for task_id, worker in running_tasks_snapshot:
            self.addTaskToTable(task_id, worker.description, worker.status.name)
        # Take a snapshot of the queue and then iterate
        queue_snapshot = list(self.workerQueueManager.queued_tasks)
        for worker in queue_snapshot:
            self.addTaskToTable(worker.id, worker.description, worker.status.name)


    def addTaskToTable(self, task_id, description, status):
        rowPosition = self.tableWidget.rowCount()
        self.tableWidget.insertRow(rowPosition)
        self.tableWidget.setItem(rowPosition, 0, QTableWidgetItem(description))
        self.tableWidget.setItem(rowPosition, 1, QTableWidgetItem(status))
        # Create and add the Cancel button
        cancelButton = QPushButton("Cancel")
        cancelButton.clicked.connect(lambda: self.cancel_task(task_id))
        self.tableWidget.setCellWidget(rowPosition, 2, cancelButton)
    
    def cancel_task(self, task_id):
        logger.debug(f"Cancelling task {task_id}")
        self.workerQueueManager.cancel_task(task_id)
        self.updateTaskList()
