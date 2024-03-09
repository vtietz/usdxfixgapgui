from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal
from enum import Enum

class IWorkerSignals(QObject):
    finished = pyqtSignal()
    canceled = pyqtSignal()
    error = pyqtSignal(tuple)


class WorkerStatus(Enum):
    RUNNING = 1
    WAITING = 2
    CANCELLING = 3

class IWorker:
    """
    Mixin class to provide common interface for worker tasks.
    Developers should ensure the following properties and methods
    are implemented in the worker classes.
    """

    signals: IWorkerSignals = None
    status: WorkerStatus = None
    
    @property
    def id(self):
        """Unique identifier for the worker task."""
        raise NotImplementedError("Worker must have a task_id property.")
    
    @property
    def description(self):
        """A description for the worker task."""
        raise NotImplementedError("Worker must have a task_description property.")
    
    def run(self):
        """Method to execute the worker's task."""
        raise NotImplementedError("Worker must implement a run method.")
    
    def cancel(self):
        """Method to cancel the worker's task."""
        raise NotImplementedError("Worker must implement a cancel method.")
    

class WorkerQueueManager(QObject):

    task_id = 0

    onTaskListChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.queue = []
        self.active_task_ids = set()
        self.threadPool = QThreadPool()
        self.isRunning = False
        self.currentWorker = None

    def addTask(self, worker: IWorker):
        worker.id = self.getUniqueTaskId()
        worker.status = WorkerStatus.WAITING
        self.queue.append(worker)
        self.active_task_ids.add(worker.id)
        worker.signals.finished.connect(lambda: self.onTaskFinished(worker.id))
        worker.signals.error.connect(lambda error_info: self.onTaskError(worker.id, error_info))
        worker.signals.canceled.connect(lambda: self.onTaskCanceled(worker.id))  # Assuming a canceled signal exists
        if not self.isRunning:
            self.startNextTask()
        self.onTaskListChanged.emit()

    def getUniqueTaskId(self):
        self.task_id += 1
        return str(self.task_id)

    def startNextTask(self):
        if self.queue and not self.isRunning:
            self.isRunning = True
            self.currentWorker = self.queue[0]
            self.currentWorker.status = WorkerStatus.RUNNING
            self.threadPool.start(self.currentWorker)
        else:
            self.isRunning = False

    def cancelTask(self, task_id):
        for worker in self.queue:

            if worker.id == task_id:
                worker.status=WorkerStatus.CANCELLING
                self.onTaskListChanged.emit()
                worker.cancel()
                break  # Assume cancellation immediately removes the worker; adjust if needed

    def cancelQueue(self):
        while self.queue:
            worker = self.queue.pop(0)
            worker.cancel()
            self.active_task_ids.remove(worker.id)
        self.isRunning = False
        self.onTaskListChanged.emit()

    def _finalizeTask(self, task_id):
        # Helper method to remove the worker from the queue and active task set
        if self.currentWorker and self.currentWorker.id == task_id:
            self.queue.pop(0)  # Remove the current worker from the queue
            self.active_task_ids.remove(task_id)
            self.currentWorker = None
            self.isRunning = False
            self.startNextTask()
        self.onTaskListChanged.emit()

    def onTaskFinished(self, task_id):
        print(f"Task {task_id} finished")
        self._finalizeTask(task_id)

    def onTaskError(self, task_id, error_info):
        print(f"Task {task_id} error: {error_info[0]}")
        self._finalizeTask(task_id)

    def onTaskCanceled(self, task_id):
        print(f"Task {task_id} canceled")
        self._finalizeTask(task_id)
