"""
Background Task Manager - Safe fire-and-forget task spawning with error handling
Step 2.5: Memory ↔ LLM Integration
"""
import asyncio
import logging
from typing import Coroutine, Set

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """
    Safe background task spawner with automatic cleanup and error logging.

    Usage:
        bg = BackgroundTaskManager()
        bg.spawn(some_async_function(), name="save_memory")

        # On shutdown:
        await bg.shutdown()
    """

    def __init__(self):
        self.tasks: Set[asyncio.Task] = set()
        self.error_count = 0
        self._shutdown = False

    def spawn(self, coro: Coroutine, name: str = None) -> asyncio.Task:
        """
        Spawn a background task with automatic cleanup and error logging.

        Args:
            coro: Coroutine to run in background
            name: Optional name for debugging

        Returns:
            The created Task object
        """
        if self._shutdown:
            logger.warning(f"Attempted to spawn task {name} during shutdown")
            return None

        task = asyncio.create_task(coro, name=name)
        self.tasks.add(task)
        task.add_done_callback(self._task_done)

        logger.debug(f"Spawned background task: {name or task.get_name()}")
        return task

    def _task_done(self, task: asyncio.Task):
        """Cleanup and error handling for completed tasks"""
        self.tasks.discard(task)

        # Check if task was cancelled
        if task.cancelled():
            logger.debug(f"Background task {task.get_name()} was cancelled")
            return

        # Check for exceptions
        exc = task.exception()
        if exc:
            self.error_count += 1
            task_name = task.get_name()
            logger.error(
                f"Background task {task_name} failed with error: {exc}",
                exc_info=exc
            )
            # Note: Could add metrics counter here if needed
            # metrics_counter("bg_task_errors_total", 1, labels={"task": task_name})
        else:
            logger.debug(f"Background task {task.get_name()} completed successfully")

    async def shutdown(self, timeout: float = 5.0):
        """
        Gracefully shutdown all background tasks.

        Args:
            timeout: Maximum time to wait for tasks to complete (seconds)
        """
        if not self.tasks:
            logger.info("No background tasks to shutdown")
            return

        self._shutdown = True
        task_count = len(self.tasks)
        logger.info(f"Shutting down {task_count} background tasks...")

        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()

        # Wait for cancellation with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*self.tasks, return_exceptions=True),
                timeout=timeout
            )
            logger.info(f"All {task_count} background tasks shut down successfully")
        except asyncio.TimeoutError:
            logger.warning(
                f"Shutdown timeout after {timeout}s, "
                f"{len(self.tasks)} tasks may still be running"
            )

        self.tasks.clear()

    def get_stats(self) -> dict:
        """Get statistics about background tasks"""
        return {
            "active_tasks": len(self.tasks),
            "total_errors": self.error_count,
            "task_names": [t.get_name() for t in self.tasks if not t.done()]
        }


# Global instance (singleton pattern)
_global_bg_manager: BackgroundTaskManager = None


def get_background_manager() -> BackgroundTaskManager:
    """Get the global background task manager instance"""
    global _global_bg_manager
    if _global_bg_manager is None:
        _global_bg_manager = BackgroundTaskManager()
    return _global_bg_manager


# Simple alias for compatibility
class Bg:
    """Simple wrapper for background task spawning"""
    def __init__(self):
        self._manager = get_background_manager()

    def spawn(self, coro, name=None):
        """Spawn a background task"""
        return self._manager.spawn(coro, name)
