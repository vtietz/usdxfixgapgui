"""
Tests for WorkerQueueManager FIFO ordering, instant lane, and cancellation behavior.
"""
import pytest
from unittest.mock import Mock, patch
from collections import deque

from managers.worker_queue_manager import (
    WorkerQueueManager,
    IWorker,
    IWorkerSignals,
    WorkerStatus
)


class MockWorker(IWorker):
    """Mock worker for testing"""
    def __init__(self, description: str, is_instant: bool = False):
        super().__init__(is_instant=is_instant)
        self.signals = IWorkerSignals()
        self.description = description
        self._run_called = False

    async def run(self):
        """Mock run that just marks as called"""
        self._run_called = True
        # Simulate work
        import asyncio
        await asyncio.sleep(0.01)


class TestFIFOOrdering:
    """Test FIFO ordering in standard and instant lanes"""

    def test_standard_lane_uses_deque(self):
        """Verify standard lane uses deque for FIFO operations"""
        manager = WorkerQueueManager()
        assert isinstance(manager.queued_tasks, deque)
        assert isinstance(manager.queued_instant_tasks, deque)

    def test_standard_tasks_processed_fifo(self):
        """Verify standard tasks are processed oldest-first (FIFO)"""
        manager = WorkerQueueManager()

        # Prevent auto-start by mocking start_next_task
        with patch.object(manager, 'start_next_task'):
            # Add three standard tasks
            worker_a = MockWorker("Task A", is_instant=False)
            worker_b = MockWorker("Task B", is_instant=False)
            worker_c = MockWorker("Task C", is_instant=False)

            manager.add_task(worker_a, start_now=False)
            manager.add_task(worker_b, start_now=False)
            manager.add_task(worker_c, start_now=False)

            # Verify order in queue (oldest first)
            assert len(manager.queued_tasks) == 3
            assert list(manager.queued_tasks)[0].description == "Task A"
            assert list(manager.queued_tasks)[1].description == "Task B"
            assert list(manager.queued_tasks)[2].description == "Task C"

    def test_instant_tasks_processed_fifo(self):
        """Verify instant tasks are processed oldest-first (FIFO)"""
        manager = WorkerQueueManager()

        # Create a fake running instant task to prevent auto-start
        fake_running = MockWorker("Fake Running", is_instant=True)
        manager.running_instant_task = fake_running

        # Add three instant tasks
        worker_a = MockWorker("Instant A", is_instant=True)
        worker_b = MockWorker("Instant B", is_instant=True)
        worker_c = MockWorker("Instant C", is_instant=True)

        manager.add_task(worker_a, start_now=False)
        manager.add_task(worker_b, start_now=False)
        manager.add_task(worker_c, start_now=False)

        # Verify order in queue (oldest first)
        assert len(manager.queued_instant_tasks) == 3
        assert list(manager.queued_instant_tasks)[0].description == "Instant A"
        assert list(manager.queued_instant_tasks)[1].description == "Instant B"
        assert list(manager.queued_instant_tasks)[2].description == "Instant C"


class TestInstantLane:
    """Test instant lane scheduling and parallel execution"""

    def test_instant_task_starts_immediately_when_slot_free(self):
        """Verify instant tasks start immediately when instant slot is free"""
        manager = WorkerQueueManager()

        # Add instant task with slot free
        worker = MockWorker("Instant Task", is_instant=True)

        with patch.object(manager, 'start_next_instant_task') as mock_start:
            manager.add_task(worker, start_now=False)
            # Should start immediately regardless of start_now
            mock_start.assert_called_once()

    def test_instant_task_queues_when_slot_busy(self):
        """Verify instant tasks queue when instant slot is occupied"""
        manager = WorkerQueueManager()

        # Occupy instant slot
        running_worker = MockWorker("Running Instant", is_instant=True)
        manager.running_instant_task = running_worker

        # Add another instant task
        queued_worker = MockWorker("Queued Instant", is_instant=True)
        manager.add_task(queued_worker, start_now=False)

        # Should be queued, not started
        assert len(manager.queued_instant_tasks) == 1
        assert manager.queued_instant_tasks[0].description == "Queued Instant"

    def test_instant_lane_independent_from_standard_lane(self):
        """Verify instant lane operates independently from standard lane"""
        manager = WorkerQueueManager()

        # Add standard task and verify it's running
        standard_worker = MockWorker("Standard Task", is_instant=False)
        with patch('managers.worker_queue_manager.run_async'):
            manager.add_task(standard_worker, start_now=True)
            manager.running_tasks[standard_worker.id] = standard_worker

        # Add instant task - should start despite standard task running
        instant_worker = MockWorker("Instant Task", is_instant=True)

        with patch.object(manager, 'start_next_instant_task') as mock_start:
            manager.add_task(instant_worker, start_now=False)
            # Should start immediately even with standard task running
            mock_start.assert_called_once()

    def test_instant_slot_limited_to_one(self):
        """Verify instant lane allows max 1 concurrent task"""
        manager = WorkerQueueManager()

        # Occupy instant slot
        running_instant = MockWorker("Running Instant", is_instant=True)
        manager.running_instant_task = running_instant

        # Try to add another instant task
        queued_instant = MockWorker("Queued Instant", is_instant=True)
        manager.add_task(queued_instant, start_now=False)

        # Should be queued, not started
        assert manager.running_instant_task is running_instant
        assert len(manager.queued_instant_tasks) == 1


class TestCancellation:
    """Test task cancellation behavior"""

    def test_cancel_running_standard_task(self):
        """Verify canceling a running standard task calls worker.cancel()"""
        manager = WorkerQueueManager()

        # Create running standard task
        worker = MockWorker("Standard Task", is_instant=False)
        worker.id = "task-1"
        manager.running_tasks[worker.id] = worker

        # Cancel it
        with patch.object(worker, 'cancel') as mock_cancel:
            manager.cancel_task(worker.id)
            mock_cancel.assert_called_once()

    def test_cancel_queued_standard_task_removes_from_queue(self):
        """Verify canceling a queued standard task removes it from queue"""
        manager = WorkerQueueManager()

        # Prevent auto-start by mocking start_next_task
        with patch.object(manager, 'start_next_task'):
            # Add queued standard tasks
            worker_a = MockWorker("Task A", is_instant=False)
            worker_b = MockWorker("Task B", is_instant=False)
            worker_c = MockWorker("Task C", is_instant=False)

            manager.add_task(worker_a, start_now=False)
            manager.add_task(worker_b, start_now=False)
            manager.add_task(worker_c, start_now=False)

            # Cancel middle task
            manager.cancel_task(worker_b.id)

            # Verify removed
            assert len(manager.queued_tasks) == 2
            assert list(manager.queued_tasks)[0].description == "Task A"
            assert list(manager.queued_tasks)[1].description == "Task C"

    def test_cancel_instant_task(self):
        """Verify canceling instant tasks works correctly"""
        manager = WorkerQueueManager()

        # Occupy instant slot
        running_instant = MockWorker("Running Instant", is_instant=True)
        manager.running_instant_task = running_instant

        # Add queued instant tasks
        queued_a = MockWorker("Queued A", is_instant=True)
        queued_b = MockWorker("Queued B", is_instant=True)

        manager.add_task(queued_a, start_now=False)
        manager.add_task(queued_b, start_now=False)

        # Cancel first queued instant task
        manager.cancel_task(queued_a.id)

        # Verify removed
        assert len(manager.queued_instant_tasks) == 1
        assert manager.queued_instant_tasks[0].description == "Queued B"

    def test_cancel_queue_processes_head_first(self):
        """Verify cancel_queue cancels from head (oldest first) for predictability"""
        manager = WorkerQueueManager()

        # Prevent auto-start by mocking start_next_task
        with patch.object(manager, 'start_next_task'):
            # Add standard tasks (will queue since start is prevented)
            workers = [MockWorker(f"Task {i}", is_instant=False) for i in range(5)]
            for worker in workers:
                manager.add_task(worker, start_now=False)

            # Track cancellation order
            cancelled_order = []

            def track_cancel(worker):
                cancelled_order.append(worker.description)
                worker._is_canceled = True

            # Patch cancel method
            for worker in workers:
                worker.cancel = lambda w=worker: track_cancel(w)

            # Cancel queue
            manager.cancel_queue()

            # Verify cancelled in FIFO order (head first)
            assert cancelled_order == ["Task 0", "Task 1", "Task 2", "Task 3", "Task 4"]

    def test_cancel_task_isolated(self):
        """Verify canceling one task doesn't affect others"""
        manager = WorkerQueueManager()

        # Prevent auto-start by mocking start_next_task
        with patch.object(manager, 'start_next_task'):
            # Add multiple tasks (will queue since start is prevented)
            worker_a = MockWorker("Task A", is_instant=False)
            worker_b = MockWorker("Task B", is_instant=False)
            worker_c = MockWorker("Task C", is_instant=False)

            manager.add_task(worker_a, start_now=False)
            manager.add_task(worker_b, start_now=False)
            manager.add_task(worker_c, start_now=False)

            # Cancel middle task
            manager.cancel_task(worker_b.id)

            # Verify others unaffected
            assert len(manager.queued_tasks) == 2
            assert not worker_a._is_canceled
            assert worker_b._is_canceled
            assert not worker_c._is_canceled


class TestTaskFinalization:
    """Test task finalization and queue progression"""

    def test_finalize_instant_task_starts_next_queued_instant(self):
        """Verify finalizing instant task starts next queued instant task"""
        manager = WorkerQueueManager()

        # Set up running instant task
        running_instant = MockWorker("Running Instant", is_instant=True)
        running_instant.id = "instant-1"
        manager.running_instant_task = running_instant

        # Queue another instant task
        queued_instant = MockWorker("Queued Instant", is_instant=True)
        manager.queued_instant_tasks.append(queued_instant)

        # Finalize running instant
        with patch.object(manager, 'start_next_instant_task') as mock_start:
            manager._finalize_task(running_instant.id)

            # Should start next queued instant
            assert manager.running_instant_task is None
            mock_start.assert_called_once()

    def test_finalize_standard_task_starts_next_queued_standard(self):
        """Verify finalizing standard task starts next queued standard (if no running)"""
        manager = WorkerQueueManager()

        # Set up running standard task
        running_standard = MockWorker("Running Standard", is_instant=False)
        running_standard.id = "standard-1"
        manager.running_tasks[running_standard.id] = running_standard

        # Queue another standard task
        queued_standard = MockWorker("Queued Standard", is_instant=False)
        manager.queued_tasks.append(queued_standard)

        # Finalize running standard
        with patch.object(manager, 'start_next_task') as mock_start:
            manager._finalize_task(running_standard.id)

            # Should start next queued standard (queue is not empty, running_tasks is now empty)
            assert running_standard.id not in manager.running_tasks
            mock_start.assert_called_once()


class TestUISignaling:
    """Test UI update signal emission"""

    def test_instant_task_no_signal_when_starting_immediately(self):
        """Verify instant tasks don't emit signal when starting immediately (no flicker)"""
        manager = WorkerQueueManager()

        # Mock the signal
        manager.on_task_list_changed = Mock()

        # Add instant task with free slot
        worker = MockWorker("Instant Task", is_instant=True)

        with patch.object(manager, 'start_next_instant_task'):
            # Reset call count before adding task
            manager.on_task_list_changed.reset_mock()

            manager.add_task(worker, start_now=False)

            # Should NOT emit signal in add_task (start_next_instant_task will emit)
            # Note: start_next_instant_task is mocked, so we expect 0 calls from add_task itself
            assert manager.on_task_list_changed.call_count == 0

    def test_instant_task_emits_signal_when_queuing(self):
        """Verify instant tasks emit signal when queuing (slot busy)"""
        manager = WorkerQueueManager()

        # Occupy instant slot
        running_instant = MockWorker("Running Instant", is_instant=True)
        running_instant.id = "999"
        running_instant.status = WorkerStatus.RUNNING
        manager.running_instant_task = running_instant

        # Mock the signal (after manager initialization to avoid init emissions)
        with patch.object(manager, 'on_task_list_changed') as mock_signal:
            # Add instant task (will queue since slot is busy)
            worker = MockWorker("Queued Instant", is_instant=True)
            manager.add_task(worker, start_now=False)

            # Should emit signal when queuing
            assert mock_signal.emit.call_count >= 1
class TestWorkerProperties:
    """Test worker property handling"""

    def test_worker_gets_unique_id(self):
        """Verify each worker gets a unique task ID"""
        manager = WorkerQueueManager()

        worker_a = MockWorker("Task A", is_instant=False)
        worker_b = MockWorker("Task B", is_instant=False)

        manager.add_task(worker_a, start_now=False)
        manager.add_task(worker_b, start_now=False)

        # Verify unique IDs assigned
        assert worker_a.id is not None
        assert worker_b.id is not None
        assert worker_a.id != worker_b.id

    def test_worker_status_set_to_waiting_on_queue(self):
        """Verify worker status is set to WAITING when queued behind another task"""
        manager = WorkerQueueManager()

        # Block the queue with a fake running task to prevent auto-start
        blocking_worker = MockWorker("Blocking Task", is_instant=False)
        blocking_worker.id = "blocking-1"
        blocking_worker.status = WorkerStatus.RUNNING
        manager.running_tasks[blocking_worker.id] = blocking_worker

        # Now add a second task - it should be WAITING because blocking_worker is running
        worker = MockWorker("Task", is_instant=False)
        manager.add_task(worker, start_now=False)

        # Verify it's queued and status is WAITING
        assert worker.status == WorkerStatus.WAITING
        assert len(manager.queued_tasks) == 1
        assert manager.queued_tasks[0] is worker

    def test_get_worker_finds_running_standard_task(self):
        """Verify get_worker finds running standard tasks"""
        manager = WorkerQueueManager()

        worker = MockWorker("Standard Task", is_instant=False)
        worker.id = "task-1"
        manager.running_tasks[worker.id] = worker

        found = manager.get_worker(worker.id)
        assert found is worker

    def test_get_worker_finds_running_instant_task(self):
        """Verify get_worker finds running instant task"""
        manager = WorkerQueueManager()

        worker = MockWorker("Instant Task", is_instant=True)
        worker.id = "instant-1"
        manager.running_instant_task = worker

        found = manager.get_worker(worker.id)
        assert found is worker

    def test_get_worker_returns_none_for_nonexistent(self):
        """Verify get_worker returns None for nonexistent task"""
        manager = WorkerQueueManager()

        found = manager.get_worker("nonexistent-id")
        assert found is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])