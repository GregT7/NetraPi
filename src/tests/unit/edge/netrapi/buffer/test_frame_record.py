import numpy as np

from netrapi.buffer import Classification, FrameRecord


def test_frame_record_defaults_display_to_raw_copy():
    raw = np.zeros((2, 3, 3), dtype=np.uint8)
    raw[0, 0, 0] = 7
    record = FrameRecord(raw=raw)

    assert record.display is not raw
    assert np.array_equal(record.display, raw)
    assert record.classifications == []


def test_frame_record_patch_classifications():
    record = FrameRecord(raw=np.zeros((4, 4, 3), dtype=np.uint8))
    labels = [Classification("stop sign", 0.9, (0.1, 0.2, 0.3, 0.4))]

    record.patch_classifications(labels)

    assert record.classifications == labels
    assert record.classifications is not labels
