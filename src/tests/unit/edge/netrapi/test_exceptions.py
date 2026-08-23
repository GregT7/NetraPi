import pytest

from netrapi.exceptions import (
    BufferError,
    CameraError,
    CaptureError,
    ClassificationError,
    EventError,
    IngestAuthError,
    NetraPiError,
)


def test_exception_hierarchy():
    assert issubclass(CameraError, NetraPiError)
    assert issubclass(CaptureError, NetraPiError)
    assert issubclass(BufferError, NetraPiError)
    assert issubclass(ClassificationError, NetraPiError)
    assert issubclass(EventError, NetraPiError)
    assert issubclass(IngestAuthError, NetraPiError)


def test_exceptions_are_raiseable():
    with pytest.raises(CameraError, match="device"):
        raise CameraError("device unavailable")
