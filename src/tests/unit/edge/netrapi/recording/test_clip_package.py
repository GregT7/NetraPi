from datetime import datetime

import numpy as np

from netrapi.recording import ClipPackage


def test_build_copies_frame_lists():
    pre = [np.zeros((2, 2, 3), dtype=np.uint8)]
    post = [np.ones((2, 2, 3), dtype=np.uint8)]
    triggered = datetime(2026, 1, 2, 3, 4, 5)

    package = ClipPackage.build(pre, post, triggered_at=triggered, event_index=3)

    assert len(package.pre_frames) == len(pre)
    assert len(package.post_frames) == len(post)
    assert np.array_equal(package.pre_frames[0], pre[0])
    assert np.array_equal(package.post_frames[0], post[0])
    assert package.pre_frames is not pre
    assert package.post_frames is not post
    assert package.pre_frames[0] is not pre[0]
    assert package.post_frames[0] is not post[0]
    assert package.triggered_at == triggered
    assert package.event_index == 3


def test_build_snapshots_frame_pixels():
    pre = [np.zeros((2, 2, 3), dtype=np.uint8)]
    post = [np.ones((2, 2, 3), dtype=np.uint8)]

    package = ClipPackage.build(pre, post, event_index=1)

    pre[0][0, 0, 0] = 99
    post[0][0, 0, 0] = 42

    assert package.pre_frames[0][0, 0, 0] == 0
    assert package.post_frames[0][0, 0, 0] == 1
