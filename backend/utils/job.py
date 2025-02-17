import asyncio
from concurrent.futures import Future
from typing import Callable, Any


class Job:
    """
    A class representing a job to be executed. To be used by JobQueue.
    Integrates with async contexts by using a Future for awaiting the job.
    """

    def __init__(self, task: Callable[[], Any]):
        """
        Initializes a Job instance.

        Args:
            task (Callable): The function to be executed for this job.
                            Must be callable without arguments.
        """
        self.task = task
        self.future = Future()  # Future object represents an asynchronous result
        self.success = None  # Indicates whether the job succeeded (True/False/None)
        self.error_message = None  # Stores an error message if an exception occurs
        self.return_value = None  # The result returned by the task
        self.pending = True  # Indicates whether the job has yet to run (True = not run, False = ran)

    def run(self):
        """
        Executes the task and sets success, return_value, or error_message accordingly.
        """
        try:
            self.return_value = self.task()  # Execute the task and store the result
            self.success = True
            self.future.set_result(self.return_value)  # Success: Set the result in the Future
        except Exception as e:
            self.success = False
            self.error_message = str(e)
            self.future.set_exception(e)  # Failure: Set the exception in the Future
        finally:
            self.pending = False  # Mark as not pending since the job is done

    async def wait(self) -> Any:
        """
        Asynchronously wait for the job to complete.

        Returns:
            Any: The return value of the job, if successful.

        Raises:
            Exception: If the job failed, raises the original exception.
        """
        return await asyncio.wrap_future(self.future)

    def __await__(self):
        """
        Allows the Job object to be directly awaited using the 'await' keyword.
        """
        return self.wait().__await__()

    def __repr__(self):
        """
        Returns a string representation of the Job object.

        Returns:
            str: A string describing the job's status.
        """
        if self.pending:
            return "<Job status=Pending>"
        elif self.success:
            return f"<Job success={self.success}, return_value={self.return_value}>"
        else:
            return f"<Job success={self.success}, error_message={self.error_message}>"
