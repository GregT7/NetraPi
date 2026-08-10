"""Domain exceptions for the edge pipeline."""


class NetraPiError(Exception):
    """Base class for NetraPi edge runtime errors."""


class CameraError(NetraPiError):
    """Raised when the camera device cannot be opened or read."""


class CaptureError(NetraPiError):
    """Raised when frame validation or processing fails."""


class BufferError(NetraPiError):
    """Raised when buffer operations violate configuration or state rules."""


class RecordingError(NetraPiError):
    """Raised when clip packaging or MP4 write fails."""


class DetectionError(NetraPiError):
    """Raised when model load, TPU verification, or inference fails."""


class ClassificationError(NetraPiError):
    """Raised when stop-sign kNN output does not match expected labels."""


class EventError(NetraPiError):
    """Raised when event evaluation is misused or classification cannot complete."""
