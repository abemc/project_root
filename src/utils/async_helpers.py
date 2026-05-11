import concurrent.futures
import time
from typing import Any, Callable, Optional

# Shared executor for model loads and other heavy CPU/IO tasks
_MODEL_EXECUTOR: concurrent.futures.ThreadPoolExecutor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


def run_in_executor(func: Callable, *args, **kwargs) -> concurrent.futures.Future:
    """Submit a callable to the shared executor and return a Future."""
    return _MODEL_EXECUTOR.submit(func, *args, **kwargs)


def await_future(fut: concurrent.futures.Future, timeout: Optional[float] = None, poll_interval: float = 0.05) -> Any:
    """Wait for a Future with a short-poll loop (safe for non-async code).

    Args:
        fut: Future returned by `run_in_executor`.
        timeout: overall timeout in seconds (None = wait indefinitely).
        poll_interval: sleep between polls.
    Returns:
        The result of the future.
    Raises:
        concurrent.futures.TimeoutError if timeout elapses.
    """
    start = time.time()
    while True:
        if fut.done():
            return fut.result()
        if timeout is not None and (time.time() - start) > timeout:
            raise concurrent.futures.TimeoutError("Future did not complete within timeout")
        time.sleep(poll_interval)
