from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool

from cli.extract_vocals import VocalExtractionError, extract_vocals_with_spleeter
from utils.worker_queue_manager import IWorker, IWorkerSignals

class WorkerSignals(IWorkerSignals):
    pass

class ExtractVocalsWorker(QRunnable):
    def __init__(self, audio_path, destination_path, max_detection_time):
        super().__init__()
        self.audio_path = audio_path
        self.destination_path = destination_path
        self.max_detection_time = max_detection_time
        self.signals = WorkerSignals()
        self._isCancelled = False
        self.task_description = f"Extracting vocals from {audio_path} to {destination_path}."

    def run(self):
        try:
            result = extract_vocals_with_spleeter(
                self.audio_path, 
                self.destination_path, 
                self.max_detection_time, 
                self.check_cancellation
            )
            print(result)
            self.signals.finished.emit()
        except VocalExtractionError as e:
            self.signals.error.emit((e,))

    def cancel(self):
        self._isCancelled = True

    def check_cancellation(self):
        return self._isCancelled
