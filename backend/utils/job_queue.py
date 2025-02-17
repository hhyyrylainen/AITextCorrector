import queue
import threading

from .job import Job


class JobQueue:
    """
    A thread-safe job queue that runs one task at a time using a single daemon thread.
    Tasks are executed sequentially in the order they are submitted.
    """

    def __init__(self):
        self.task_queue = queue.Queue()  # Thread-safe queue for tasks
        self.lock = threading.Lock()  # Lock for thread-safe methods
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.shutdown_event = threading.Event()
        self.worker_thread.start()  # Start the daemon worker thread

    def _worker(self):
        """
        Worker method that continuously runs tasks from the queue.
        Exits when the shutdown event is set.
        """
        while not self.shutdown_event.is_set():
            try:
                # Wait for a task, timeout allows graceful shutdown
                task = self.task_queue.get(timeout=0.1)
                try:
                    task.run()  # Execute the task
                except Exception as e:
                    print(f"Unexpected exception caused in task running: {e}")
                finally:
                    self.task_queue.task_done()  # Mark the task as done
            except queue.Empty:
                continue

    def submit(self, task: Job):
        """
        Submits a task to the job queue.

        Args:
            task (Job): A task to be executed by the worker thread.
        """
        with self.lock:  # Ensure thread-safety when accessing the queue
            self.task_queue.put(task)

    def clear(self):
        """
        Clears all pending tasks in the job queue. Thread-safe.
        """
        with self.lock:
            # Clear the queue by repeatedly removing items
            while not self.task_queue.empty():
                try:
                    self.task_queue.get_nowait()
                    self.task_queue.task_done()  # Mark removed task as done
                except queue.Empty:
                    break

    def wait_for_completion(self):
        """
        Blocks until all tasks in the queue have been completed. Thread-safe.
        """
        self.task_queue.join()  # Wait until all tasks are marked as done

    def shutdown(self):
        """
        Gracefully shuts down the job queue by stopping the background thread.
        """
        self.shutdown_event.set()  # Signal the worker thread to exit
        self.worker_thread.join()  # Wait for the worker thread to terminate
