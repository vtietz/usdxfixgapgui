from PySide6.QtCore import QObject, Signal as pyqtSignal

class WorkerSignals(QObject):
    """Signals to be used by the Worker class for inter-task communication."""
    started = pyqtSignal()
    finished = pyqtSignal()
    progress = pyqtSignal()
    canceled = pyqtSignal()
    error = pyqtSignal(Exception)
