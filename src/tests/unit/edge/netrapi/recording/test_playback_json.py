from pathlib import Path

from netrapi.events.driving_event import PlaybackSeries
from netrapi.recording.playback_json import write_playback_sidecars


def test_write_playback_sidecars_uses_clip_relative_times(tmp_path: Path) -> None:
    clip_path = tmp_path / "clip_1_stamp" / "clip.mp4"
    clip_path.parent.mkdir()
    clip_path.write_bytes(b"mp4")
    series = PlaybackSeries(
        area_points=((95.0, 0.01), (100.0, 0.02)),
        motion_points=((100.0, 0.4), (105.0, 0.5)),
        anchor_t=100.0,
        evaluate_t=105.0,
    )
    write_playback_sidecars(
        clip_path,
        series,
        pre_roll_seconds=10.0,
        classification="rolling-stop",
    )
    areas = (clip_path.parent / "areas.json").read_text(encoding="utf-8")
    motion = (clip_path.parent / "motion.json").read_text(encoding="utf-8")
    transitions = (clip_path.parent / "transitions.json").read_text(encoding="utf-8")
    assert '"t0_s": 5.0' in areas
    assert '"sample_end_s": 10.0' in areas
    assert '"classification": "rolling-stop"' in areas
    assert '"area": 0.02' in areas
    assert '"score": 0.5' in motion
    assert '"t": 5.0' in motion
    assert '"id": "Monitoring"' in transitions
    assert '"id": "SampleMotion"' in transitions
    assert '"id": "RollingStop"' in transitions
    assert '"t": 5.0' in transitions
    assert '"t": 10.0' in transitions
