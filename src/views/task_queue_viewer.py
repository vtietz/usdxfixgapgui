from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView

from utils.worker_queue_manager import WorkerQueueManager

class TaskQueueViewer(QWidget):

    def __init__(self, workerQueueManager:WorkerQueueManager, parent=None):
        super().__init__(parent)
        self.workerQueueManager = workerQueueManager
        self.initUI()
        self.updateTaskList()
        self.workerQueueManager.onTaskListChanged.connect(self.updateTaskList)

    def initUI(self):
        self.layout = QVBoxLayout(self)
        self.tableWidget = QTableWidget()
        self.tableWidget.setColumnCount(3) 
        self.tableWidget.setHorizontalHeaderLabels(["Task ID", "Description", "Status"])
        self.layout.addWidget(self.tableWidget)

        # Adjust the initial width of the first and third columns, and let the second column take the remaining space
        self.tableWidget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.tableWidget.setColumnWidth(0, 100)  # Set width of "Task ID" column
        self.tableWidget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tableWidget.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.tableWidget.setColumnWidth(2, 100)  # Set width of "Status" column


    def updateTaskList(self):
        print("Updating task list")
        print(f"Queue length: {len(self.workerQueueManager.queue)}")
        # Clear the table and repopulate
        self.tableWidget.setRowCount(0)
        for worker in self.workerQueueManager.queue:
            print(f"Adding task to table: {worker.id}, {worker.task_description}")
            self.addTaskToTable(worker.id, worker.task_description, worker.status.name)

    def addTaskToTable(self, task_id, description, status):
        rowPosition = self.tableWidget.rowCount()
        self.tableWidget.insertRow(rowPosition)
        self.tableWidget.setItem(rowPosition, 0, QTableWidgetItem(task_id))
        self.tableWidget.setItem(rowPosition, 1, QTableWidgetItem(description))
        self.tableWidget.setItem(rowPosition, 2, QTableWidgetItem(status))