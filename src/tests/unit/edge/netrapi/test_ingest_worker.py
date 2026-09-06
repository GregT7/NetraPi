from unittest.mock import MagicMock

from netrapi.ingest_worker import IngestWorker


def test_ingest_worker_runs_submitted_method() -> None:
    cloud = MagicMock()
    worker = IngestWorker(cloud, emit=lambda _m: None)
    try:
        worker.submit("sync_event", 42)
        assert worker.flush(timeout_s=5.0)
        cloud.sync_event.assert_called_once_with(42)
    finally:
        worker.close(flush_timeout_s=5.0)


def test_ingest_worker_failure_emits_without_raising() -> None:
    cloud = MagicMock()
    cloud.sync_event.side_effect = RuntimeError("backend down")
    messages: list[str] = []
    worker = IngestWorker(cloud, emit=messages.append)
    try:
        worker.submit("sync_event", 7)
        assert worker.flush(timeout_s=5.0)
        assert any("sync_event failed" in message for message in messages)
    finally:
        worker.close(flush_timeout_s=5.0)


def test_ingest_worker_clear_cloud_skips_queued_jobs() -> None:
    cloud = MagicMock()
    worker = IngestWorker(cloud, emit=lambda _m: None)
    try:
        worker.clear_cloud()
        worker.submit("sync_event", 1)
        assert worker.flush(timeout_s=5.0)
        cloud.sync_event.assert_not_called()
    finally:
        worker.close(flush_timeout_s=5.0)
