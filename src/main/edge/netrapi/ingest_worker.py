"""FIFO background worker for CloudIngest calls (capture thread stays off the network)."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from typing import Any

_SENTINEL = object()


class IngestWorker:
    """Single-thread queue: submit(method, *args) → getattr(cloud, method)(*args)."""

    def __init__(
        self,
        cloud: Any,
        *,
        emit: Callable[[str], None] | None = None,
    ) -> None:
        self._cloud = cloud
        self._emit = emit or (lambda message: print(message, flush=True))
        self._queue: queue.Queue[tuple[Any, ...] | object] = queue.Queue()
        self._accepting = True
        self._enabled = True
        self._lock = threading.Lock()
        self._thread = threading.Thread(
            target=self._run,
            name="ingest-worker",
            daemon=True,
        )
        self._thread.start()

    def set_emit(self, emit: Callable[[str], None] | None) -> None:
        self._emit = emit or (lambda message: print(message, flush=True))

    def submit(self, method_name: str, *args: Any) -> None:
        with self._lock:
            if not self._accepting or not self._enabled or self._cloud is None:
                return
            self._queue.put((method_name, args))

    def clear_cloud(self) -> None:
        """Stop accepting new work and drop the cloud client (disable_cloud)."""
        with self._lock:
            self._enabled = False
            self._cloud = None

    def flush(self, timeout_s: float = 120.0) -> bool:
        """Wait until work queued before this call finishes. Returns False on timeout."""
        done = threading.Event()

        def _mark_done() -> None:
            done.set()

        with self._lock:
            accepting = self._accepting
        if not accepting and self._queue.empty():
            return True
        self._queue.put(("__flush__", (_mark_done,)))
        return done.wait(timeout=timeout_s)

    def close(self, *, flush_timeout_s: float = 120.0) -> None:
        with self._lock:
            self._accepting = False
        self.flush(timeout_s=flush_timeout_s)
        self._queue.put(_SENTINEL)
        self._thread.join(timeout=flush_timeout_s + 5.0)

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is _SENTINEL:
                    return
                method_name, args = item  # type: ignore[misc]
                if method_name == "__flush__":
                    callback = args[0]
                    callback()
                    continue
                with self._lock:
                    cloud = self._cloud
                    enabled = self._enabled
                if not enabled or cloud is None:
                    continue
                try:
                    getattr(cloud, method_name)(*args)
                except Exception as exc:
                    self._emit(f"[ingest] {method_name} failed: {exc}")
            finally:
                self._queue.task_done()
