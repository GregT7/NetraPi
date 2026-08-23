from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from db.models import (
    ApproachConfig,
    BuzzerConfig,
    CameraConfig,
    CameraMode,
    DetectorAllowedClass,
    DetectorConfig,
    DisplayConfig,
    EventManagerConfig,
    EventTriggerLabel,
    FarnebackConfig,
    KnnConfig,
    KnnFeature,
    MasterConfig,
    MotionConfig,
    MotionRoi,
    ObjectLabel,
    PreviewConfig,
    RecordingManagerConfig,
    TripRecorderConfig,
)

DEFAULT_SNAPSHOT_NAME = "edge-json"
DEFAULT_SNAPSHOT_NOTE = "Live edge JSON snapshot."
_TOP_LEVEL_META = frozenset({"id", "name", "created_at", "created", "note"})


def edge_json_config_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "edge" / "config"


def fingerprint(payload: dict[str, Any]) -> str:
    return json.dumps(
        _canon(_strip_for_fingerprint(payload, top=True)),
        sort_keys=True,
        separators=(",", ":"),
    )


def payload_from_json_dir(config_dir: Path | str) -> dict[str, Any]:
    root = Path(config_dir)
    camera_raw = _load_json(root, "camera.json")
    preview_raw = _load_json(root, "preview.json")
    detector_raw = _load_json(root, "detector.json")
    event_raw = _load_json(root, "event_manager.json")
    approach_raw = _load_json(root, "approach_config.json")
    motion_raw = _load_json(root, "motion_config.json")
    knn_raw = _load_json(root, "knn_config.json")
    recording_raw = _load_json(root, "recording_manager.json")
    trip_raw = _load_json(root, "trip_recorder.json")
    buzzer_raw = _load_json(root, "buzzer.json")

    modes = []
    for mode in camera_raw.get("modes") or []:
        if not isinstance(mode, dict):
            raise RuntimeError("camera.json modes must be objects")
        modes.append(
            {
                "mode_key": str(mode["id"]),
                "label": str(mode["label"]),
                "input_format": str(mode["input_format"]),
                "width": int(mode["width"]),
                "height": int(mode["height"]),
                "spec_fps": float(mode["spec_fps"]),
                "recommended_fps": float(mode["recommended_fps"]),
            }
        )
    modes.sort(key=lambda row: row["mode_key"])

    roi = motion_raw.get("motion_roi") or {}
    farneback = motion_raw.get("farneback") or {}
    display = recording_raw.get("display") or {}
    play_on = buzzer_raw.get("play_on") or {}
    features = []
    for order_index, name in enumerate(knn_raw.get("stage1_feature_names") or []):
        features.append(
            {"stage": 1, "order_index": int(order_index), "feature_name": str(name)}
        )
    for order_index, name in enumerate(knn_raw.get("stage2_feature_names") or []):
        features.append(
            {"stage": 2, "order_index": int(order_index), "feature_name": str(name)}
        )
    features.sort(key=lambda row: (row["stage"], row["order_index"]))

    return {
        "camera": {
            "device": str(camera_raw["device"]),
            "ndim": int(camera_raw["ndim"]),
            "channels": int(camera_raw["channels"]),
            "note": str(camera_raw.get("device_note") or camera_raw.get("note") or ""),
            "selected_mode_key": str(camera_raw["mode_id"]),
            "modes": modes,
        },
        "preview": {
            "window_name": str(preview_raw["window_name"]),
            "window_x": int(preview_raw["window_x"]),
            "window_y": int(preview_raw["window_y"]),
            "max_width": int(preview_raw["max_width"]),
            "max_height": int(preview_raw["max_height"]),
            "enabled": bool(preview_raw["enabled"]),
            "toggle_key": str(preview_raw["toggle_key"]),
        },
        "detector": {
            "model_path": str(detector_raw["model_path"]),
            "labels_path": str(detector_raw["labels_path"]),
            "input_width": int(detector_raw["input_width"]),
            "input_height": int(detector_raw["input_height"]),
            "channels": int(detector_raw["channels"]),
            "input_dtype": str(detector_raw["input_dtype"]),
            "score_threshold": float(detector_raw["score_threshold"]),
            "top_k": int(detector_raw["top_k"]),
            "note": str(detector_raw.get("note") or ""),
            "allowed_classes": sorted(
                str(value) for value in (detector_raw.get("allowed_classes") or [])
            ),
        },
        "event_manager": {
            "area_history_seconds": float(event_raw["area_history_seconds"]),
            "note": str(event_raw.get("note") or ""),
            "trigger_labels": sorted(
                str(value) for value in (event_raw.get("trigger_labels") or [])
            ),
        },
        "approach": {
            "min_peak_pct": float(approach_raw["min_peak_pct"]),
            "min_approach_s": float(approach_raw["min_approach_s"]),
            "max_approach_s": float(approach_raw["max_approach_s"]),
            "approach_start_peak_ratio": float(approach_raw["approach_start_peak_ratio"]),
            "min_increasing_fraction": float(approach_raw["min_increasing_fraction"]),
            "min_log_linear_r2": float(approach_raw["min_log_linear_r2"]),
            "drop_within_s": float(approach_raw["drop_within_s"]),
            "drop_to_peak_ratio": float(approach_raw["drop_to_peak_ratio"]),
            "post_drop_peak_ratio": float(approach_raw["post_drop_peak_ratio"]),
            "post_drop_hold_s": float(approach_raw["post_drop_hold_s"]),
        },
        "motion": {
            "flow_scale": float(motion_raw["flow_scale"]),
            "motion_smoothing_window": int(motion_raw["motion_smoothing_window"]),
            "stopped_motion_threshold": float(motion_raw["stopped_motion_threshold"]),
            "crawl_motion_threshold": float(motion_raw["crawl_motion_threshold"]),
            "post_drop_window_s": float(motion_raw["post_drop_window_s"]),
            "roi": {
                "x_min": float(roi["x_min"]),
                "x_max": float(roi["x_max"]),
                "y_min": float(roi["y_min"]),
                "y_max": float(roi["y_max"]),
            },
            "farneback": {
                "pyr_scale": float(farneback["pyr_scale"]),
                "levels": int(farneback["levels"]),
                "winsize": int(farneback["winsize"]),
                "iterations": int(farneback["iterations"]),
                "poly_n": int(farneback["poly_n"]),
                "poly_sigma": float(farneback["poly_sigma"]),
            },
        },
        "knn": {
            "k_neighbors": int(knn_raw["k_neighbors"]),
            "stage1_model_path": str(knn_raw["stage1_model_path"]),
            "stage2_model_path": str(knn_raw["stage2_model_path"]),
            "features": features,
        },
        "recording": {
            "clips_dir": str(recording_raw["clips_dir"]),
            "pre_roll_seconds": float(recording_raw["pre_roll_seconds"]),
            "post_roll_seconds": float(recording_raw["post_roll_seconds"]),
            "coverage_tolerance": float(recording_raw["coverage_tolerance"]),
            "record_safe_events": bool(recording_raw["record_safe_events"]),
            "ffmpeg_crf": int(recording_raw["ffmpeg_crf"]),
            "note": str(recording_raw.get("note") or ""),
            "display": {
                "contrast": float(display["contrast"]),
                "tone_enabled": bool(display["tone_enabled"]),
                "tone_brightness": float(display["tone_brightness"]),
            },
        },
        "trip": {
            "enabled": bool(trip_raw["enabled"]),
            "segments_dir": str(trip_raw["segments_dir"]),
            "segment_seconds": int(trip_raw["segment_seconds"]),
            "ffmpeg_crf": int(trip_raw["ffmpeg_crf"]),
            "note": str(trip_raw.get("note") or ""),
        },
        "buzzer": {
            "gpio_pin": int(buzzer_raw["gpio_pin"]),
            "volume": float(buzzer_raw["volume"]),
            "pitch": float(buzzer_raw["pitch"]),
            "duration_seconds": float(buzzer_raw["duration_seconds"]),
            "play_on_unsafe": bool(play_on["unsafe"]),
            "play_on_safe": bool(play_on["safe"]),
        },
    }


def payload_from_db(session: Session, master_config_id: int) -> dict[str, Any]:
    master = session.get(MasterConfig, master_config_id)
    if master is None:
        raise RuntimeError(f"master_config {master_config_id} not found")
    camera = _one(
        session,
        CameraConfig,
        CameraConfig.master_config_id == master_config_id,
        "camera_config",
    )
    selected = session.get(CameraMode, camera.selected_camera_mode_id)
    if selected is None:
        raise RuntimeError(
            f"camera_config {camera.id} has no selected_camera_mode_id"
        )
    modes = [
        {
            "id": mode.id,
            "mode_key": mode.mode_key,
            "label": mode.label,
            "input_format": mode.input_format,
            "width": mode.width,
            "height": mode.height,
            "spec_fps": mode.spec_fps,
            "recommended_fps": mode.recommended_fps,
        }
        for mode in session.exec(
            select(CameraMode).where(CameraMode.camera_config_id == camera.id)
        ).all()
    ]
    modes.sort(key=lambda row: str(row["mode_key"]))
    preview = _one(
        session,
        PreviewConfig,
        PreviewConfig.master_config_id == master_config_id,
        "preview_config",
    )
    detector = _one(
        session,
        DetectorConfig,
        DetectorConfig.master_config_id == master_config_id,
        "detector_config",
    )
    allowed = [
        _label_value(session, row.object_label_id)
        for row in session.exec(
            select(DetectorAllowedClass).where(
                DetectorAllowedClass.detector_config_id == detector.id
            )
        ).all()
    ]
    event_manager = _one(
        session,
        EventManagerConfig,
        EventManagerConfig.master_config_id == master_config_id,
        "event_manager_config",
    )
    triggers = [
        _label_value(session, row.object_label_id)
        for row in session.exec(
            select(EventTriggerLabel).where(
                EventTriggerLabel.event_manager_config_id == event_manager.id
            )
        ).all()
    ]
    approach = _one(
        session,
        ApproachConfig,
        ApproachConfig.master_config_id == master_config_id,
        "approach_config",
    )
    motion = _one(
        session,
        MotionConfig,
        MotionConfig.master_config_id == master_config_id,
        "motion_config",
    )
    roi = _one(
        session, MotionRoi, MotionRoi.motion_config_id == motion.id, "motion_roi"
    )
    farneback = _one(
        session,
        FarnebackConfig,
        FarnebackConfig.motion_config_id == motion.id,
        "farneback_config",
    )
    knn = _one(
        session, KnnConfig, KnnConfig.master_config_id == master_config_id, "knn_config"
    )
    features = [
        {
            "id": feature.id,
            "stage": feature.stage,
            "order_index": feature.order_index,
            "feature_name": feature.feature_name,
        }
        for feature in session.exec(
            select(KnnFeature).where(KnnFeature.knn_config_id == knn.id)
        ).all()
    ]
    features.sort(key=lambda row: (int(row["stage"]), int(row["order_index"])))
    recording = _one(
        session,
        RecordingManagerConfig,
        RecordingManagerConfig.master_config_id == master_config_id,
        "recording_manager_config",
    )
    display = _one(
        session,
        DisplayConfig,
        DisplayConfig.recording_manager_config_id == recording.id,
        "display_config",
    )
    trip = _one(
        session,
        TripRecorderConfig,
        TripRecorderConfig.master_config_id == master_config_id,
        "trip_recorder_config",
    )
    buzzer = _one(
        session,
        BuzzerConfig,
        BuzzerConfig.master_config_id == master_config_id,
        "buzzer_config",
    )
    return {
        "id": master.id,
        "name": master.name,
        "created_at": master.created_at.isoformat() if master.created_at else None,
        "note": master.note,
        "camera": {
            "id": camera.id,
            "device": camera.device,
            "ndim": camera.ndim,
            "channels": camera.channels,
            "note": camera.note,
            "selected_mode_key": selected.mode_key,
            "modes": modes,
        },
        "preview": {
            "id": preview.id,
            "window_name": preview.window_name,
            "window_x": preview.window_x,
            "window_y": preview.window_y,
            "max_width": preview.max_width,
            "max_height": preview.max_height,
            "enabled": preview.enabled,
            "toggle_key": preview.toggle_key,
        },
        "detector": {
            "id": detector.id,
            "model_path": detector.model_path,
            "labels_path": detector.labels_path,
            "input_width": detector.input_width,
            "input_height": detector.input_height,
            "channels": detector.channels,
            "input_dtype": detector.input_dtype,
            "score_threshold": detector.score_threshold,
            "top_k": detector.top_k,
            "note": detector.note,
            "allowed_classes": sorted(allowed),
        },
        "event_manager": {
            "id": event_manager.id,
            "area_history_seconds": event_manager.area_history_seconds,
            "note": event_manager.note,
            "trigger_labels": sorted(triggers),
        },
        "approach": {
            "id": approach.id,
            "min_peak_pct": approach.min_peak_pct,
            "min_approach_s": approach.min_approach_s,
            "max_approach_s": approach.max_approach_s,
            "approach_start_peak_ratio": approach.approach_start_peak_ratio,
            "min_increasing_fraction": approach.min_increasing_fraction,
            "min_log_linear_r2": approach.min_log_linear_r2,
            "drop_within_s": approach.drop_within_s,
            "drop_to_peak_ratio": approach.drop_to_peak_ratio,
            "post_drop_peak_ratio": approach.post_drop_peak_ratio,
            "post_drop_hold_s": approach.post_drop_hold_s,
        },
        "motion": {
            "id": motion.id,
            "flow_scale": motion.flow_scale,
            "motion_smoothing_window": motion.motion_smoothing_window,
            "stopped_motion_threshold": motion.stopped_motion_threshold,
            "crawl_motion_threshold": motion.crawl_motion_threshold,
            "post_drop_window_s": motion.post_drop_window_s,
            "roi": {
                "id": roi.id,
                "x_min": roi.x_min,
                "x_max": roi.x_max,
                "y_min": roi.y_min,
                "y_max": roi.y_max,
            },
            "farneback": {
                "id": farneback.id,
                "pyr_scale": farneback.pyr_scale,
                "levels": farneback.levels,
                "winsize": farneback.winsize,
                "iterations": farneback.iterations,
                "poly_n": farneback.poly_n,
                "poly_sigma": farneback.poly_sigma,
            },
        },
        "knn": {
            "id": knn.id,
            "k_neighbors": knn.k_neighbors,
            "stage1_model_path": knn.stage1_model_path,
            "stage2_model_path": knn.stage2_model_path,
            "features": features,
        },
        "recording": {
            "id": recording.id,
            "clips_dir": recording.clips_dir,
            "pre_roll_seconds": recording.pre_roll_seconds,
            "post_roll_seconds": recording.post_roll_seconds,
            "coverage_tolerance": recording.coverage_tolerance,
            "record_safe_events": recording.record_safe_events,
            "ffmpeg_crf": recording.ffmpeg_crf,
            "note": recording.note,
            "display": {
                "id": display.id,
                "contrast": display.contrast,
                "tone_enabled": display.tone_enabled,
                "tone_brightness": display.tone_brightness,
            },
        },
        "trip": {
            "id": trip.id,
            "enabled": trip.enabled,
            "segments_dir": trip.segments_dir,
            "segment_seconds": trip.segment_seconds,
            "ffmpeg_crf": trip.ffmpeg_crf,
            "note": trip.note,
        },
        "buzzer": {
            "id": buzzer.id,
            "gpio_pin": buzzer.gpio_pin,
            "volume": buzzer.volume,
            "pitch": buzzer.pitch,
            "duration_seconds": buzzer.duration_seconds,
            "play_on_unsafe": buzzer.play_on_unsafe,
            "play_on_safe": buzzer.play_on_safe,
        },
    }


def find_matching_snapshot_id(session: Session, payload: dict[str, Any]) -> int | None:
    target = fingerprint(payload)
    for master in session.exec(select(MasterConfig)).all():
        if master.id is None:
            continue
        if fingerprint(payload_from_db(session, master.id)) == target:
            return master.id
    return None


def find_or_create_snapshot(
    session: Session, payload: dict[str, Any]
) -> tuple[int, bool]:
    found = find_matching_snapshot_id(session, payload)
    if found is not None:
        return found, False
    return insert_snapshot(session, payload), True


def ensure_snapshot_from_json_dir(
    session: Session, config_dir: Path | str
) -> tuple[int, bool]:
    return find_or_create_snapshot(session, payload_from_json_dir(config_dir))


def insert_snapshot(session: Session, payload: dict[str, Any]) -> int:
    use_ids = _requested_ids_are_free(session, payload)
    camera = dict(payload["camera"])
    preview = dict(payload["preview"])
    detector = dict(payload["detector"])
    event_manager = dict(payload["event_manager"])
    approach = dict(payload["approach"])
    motion = dict(payload["motion"])
    knn = dict(payload["knn"])
    recording = dict(payload["recording"])
    trip = dict(payload["trip"])
    buzzer = dict(payload["buzzer"])
    roi = dict(motion["roi"])
    farneback = dict(motion["farneback"])
    display = dict(recording["display"])

    master = MasterConfig(
        id=_id(payload, use_ids),
        name=str(payload.get("name") or DEFAULT_SNAPSHOT_NAME),
        created_at=_created_at(payload.get("created_at")),
        note=str(payload.get("note") or DEFAULT_SNAPSHOT_NOTE),
    )
    session.add(master)
    session.flush()
    if master.id is None:
        raise RuntimeError("master_config insert did not assign an id")

    camera_row = CameraConfig(
        id=_id(camera, use_ids),
        master_config_id=master.id,
        device=str(camera["device"]),
        ndim=int(camera["ndim"]),
        channels=int(camera["channels"]),
        note=str(camera.get("note") or ""),
        selected_camera_mode_id=None,
    )
    session.add(camera_row)
    session.flush()
    if camera_row.id is None:
        raise RuntimeError("camera_config insert did not assign an id")

    selected_key = str(camera["selected_mode_key"])
    selected_id: int | None = None
    for mode in sorted(camera.get("modes") or [], key=lambda row: str(row["mode_key"])):
        mode_row = CameraMode(
            id=_id(mode, use_ids),
            camera_config_id=camera_row.id,
            mode_key=str(mode["mode_key"]),
            label=str(mode["label"]),
            input_format=str(mode["input_format"]),
            width=int(mode["width"]),
            height=int(mode["height"]),
            spec_fps=float(mode["spec_fps"]),
            recommended_fps=float(mode["recommended_fps"]),
        )
        session.add(mode_row)
        session.flush()
        if mode_row.id is None:
            raise RuntimeError("camera_mode insert did not assign an id")
        if mode_row.mode_key == selected_key:
            selected_id = mode_row.id
    if selected_id is None:
        raise RuntimeError(f"selected camera mode {selected_key!r} is not in modes")
    camera_row.selected_camera_mode_id = selected_id
    session.add(camera_row)
    session.flush()

    session.add(
        PreviewConfig(
            id=_id(preview, use_ids),
            master_config_id=master.id,
            window_name=str(preview["window_name"]),
            window_x=int(preview["window_x"]),
            window_y=int(preview["window_y"]),
            max_width=int(preview["max_width"]),
            max_height=int(preview["max_height"]),
            enabled=bool(preview["enabled"]),
            toggle_key=str(preview["toggle_key"]),
        )
    )
    detector_row = DetectorConfig(
        id=_id(detector, use_ids),
        master_config_id=master.id,
        model_path=str(detector["model_path"]),
        labels_path=str(detector["labels_path"]),
        input_width=int(detector["input_width"]),
        input_height=int(detector["input_height"]),
        channels=int(detector["channels"]),
        input_dtype=str(detector["input_dtype"]),
        score_threshold=float(detector["score_threshold"]),
        top_k=int(detector["top_k"]),
        note=str(detector.get("note") or ""),
    )
    session.add(detector_row)
    session.flush()
    if detector_row.id is None:
        raise RuntimeError("detector_config insert did not assign an id")
    for value in detector.get("allowed_classes") or []:
        session.add(
            DetectorAllowedClass(
                detector_config_id=detector_row.id,
                object_label_id=_object_label_id(session, str(value)),
            )
        )

    event_row = EventManagerConfig(
        id=_id(event_manager, use_ids),
        master_config_id=master.id,
        area_history_seconds=float(event_manager["area_history_seconds"]),
        note=str(event_manager.get("note") or ""),
    )
    session.add(event_row)
    session.flush()
    if event_row.id is None:
        raise RuntimeError("event_manager_config insert did not assign an id")
    for value in event_manager.get("trigger_labels") or []:
        session.add(
            EventTriggerLabel(
                event_manager_config_id=event_row.id,
                object_label_id=_object_label_id(session, str(value)),
            )
        )

    session.add(
        ApproachConfig(
            id=_id(approach, use_ids),
            master_config_id=master.id,
            min_peak_pct=float(approach["min_peak_pct"]),
            min_approach_s=float(approach["min_approach_s"]),
            max_approach_s=float(approach["max_approach_s"]),
            approach_start_peak_ratio=float(approach["approach_start_peak_ratio"]),
            min_increasing_fraction=float(approach["min_increasing_fraction"]),
            min_log_linear_r2=float(approach["min_log_linear_r2"]),
            drop_within_s=float(approach["drop_within_s"]),
            drop_to_peak_ratio=float(approach["drop_to_peak_ratio"]),
            post_drop_peak_ratio=float(approach["post_drop_peak_ratio"]),
            post_drop_hold_s=float(approach["post_drop_hold_s"]),
        )
    )

    motion_row = MotionConfig(
        id=_id(motion, use_ids),
        master_config_id=master.id,
        flow_scale=float(motion["flow_scale"]),
        motion_smoothing_window=int(motion["motion_smoothing_window"]),
        stopped_motion_threshold=float(motion["stopped_motion_threshold"]),
        crawl_motion_threshold=float(motion["crawl_motion_threshold"]),
        post_drop_window_s=float(motion["post_drop_window_s"]),
    )
    session.add(motion_row)
    session.flush()
    if motion_row.id is None:
        raise RuntimeError("motion_config insert did not assign an id")
    session.add(
        MotionRoi(
            id=_id(roi, use_ids),
            motion_config_id=motion_row.id,
            x_min=float(roi["x_min"]),
            x_max=float(roi["x_max"]),
            y_min=float(roi["y_min"]),
            y_max=float(roi["y_max"]),
        )
    )
    session.add(
        FarnebackConfig(
            id=_id(farneback, use_ids),
            motion_config_id=motion_row.id,
            pyr_scale=float(farneback["pyr_scale"]),
            levels=int(farneback["levels"]),
            winsize=int(farneback["winsize"]),
            iterations=int(farneback["iterations"]),
            poly_n=int(farneback["poly_n"]),
            poly_sigma=float(farneback["poly_sigma"]),
        )
    )

    knn_row = KnnConfig(
        id=_id(knn, use_ids),
        master_config_id=master.id,
        k_neighbors=int(knn["k_neighbors"]),
        stage1_model_path=str(knn["stage1_model_path"]),
        stage2_model_path=str(knn["stage2_model_path"]),
    )
    session.add(knn_row)
    session.flush()
    if knn_row.id is None:
        raise RuntimeError("knn_config insert did not assign an id")
    for feature in knn.get("features") or []:
        session.add(
            KnnFeature(
                id=_id(feature, use_ids),
                knn_config_id=knn_row.id,
                stage=int(feature["stage"]),
                order_index=int(feature["order_index"]),
                feature_name=str(feature["feature_name"]),
            )
        )

    recording_row = RecordingManagerConfig(
        id=_id(recording, use_ids),
        master_config_id=master.id,
        clips_dir=str(recording["clips_dir"]),
        pre_roll_seconds=float(recording["pre_roll_seconds"]),
        post_roll_seconds=float(recording["post_roll_seconds"]),
        coverage_tolerance=float(recording["coverage_tolerance"]),
        record_safe_events=bool(recording["record_safe_events"]),
        ffmpeg_crf=int(recording["ffmpeg_crf"]),
        note=str(recording.get("note") or ""),
    )
    session.add(recording_row)
    session.flush()
    if recording_row.id is None:
        raise RuntimeError("recording_manager_config insert did not assign an id")
    session.add(
        DisplayConfig(
            id=_id(display, use_ids),
            recording_manager_config_id=recording_row.id,
            contrast=float(display["contrast"]),
            tone_enabled=bool(display["tone_enabled"]),
            tone_brightness=float(display["tone_brightness"]),
        )
    )
    session.add(
        TripRecorderConfig(
            id=_id(trip, use_ids),
            master_config_id=master.id,
            enabled=bool(trip["enabled"]),
            segments_dir=str(trip["segments_dir"]),
            segment_seconds=int(trip["segment_seconds"]),
            ffmpeg_crf=int(trip["ffmpeg_crf"]),
            note=str(trip.get("note") or ""),
        )
    )
    session.add(
        BuzzerConfig(
            id=_id(buzzer, use_ids),
            master_config_id=master.id,
            gpio_pin=int(buzzer["gpio_pin"]),
            volume=float(buzzer["volume"]),
            pitch=float(buzzer["pitch"]),
            duration_seconds=float(buzzer["duration_seconds"]),
            play_on_unsafe=bool(buzzer["play_on_unsafe"]),
            play_on_safe=bool(buzzer["play_on_safe"]),
        )
    )
    session.flush()
    return master.id


def _load_json(config_dir: Path, name: str) -> dict[str, Any]:
    path = config_dir / name
    if not path.is_file():
        raise RuntimeError(f"config file missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} is not a JSON object")
    return data


def _canon(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _canon(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canon(item) for item in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return round(value, 10)
    if isinstance(value, Path):
        return value.as_posix()
    return value


def _strip_for_fingerprint(value: Any, *, top: bool = False) -> Any:
    if isinstance(value, dict):
        skip = {"id"}
        if top:
            skip |= _TOP_LEVEL_META
        return {
            key: _strip_for_fingerprint(item)
            for key, item in value.items()
            if key not in skip
        }
    if isinstance(value, list):
        return [_strip_for_fingerprint(item) for item in value]
    return value


def _one(session: Session, model, where, label: str):
    row = session.exec(select(model).where(where)).first()
    if row is None:
        raise RuntimeError(f"{label} missing")
    return row


def _label_value(session: Session, object_label_id: int) -> str:
    row = session.get(ObjectLabel, object_label_id)
    if row is None:
        raise RuntimeError(f"object_label {object_label_id} not found")
    return row.value


def _object_label_id(session: Session, value: str) -> int:
    row = session.exec(select(ObjectLabel).where(ObjectLabel.value == value)).first()
    if row is not None and row.id is not None:
        return row.id
    row = ObjectLabel(value=value)
    session.add(row)
    session.flush()
    if row.id is None:
        raise RuntimeError("object_label insert did not assign an id")
    return row.id


def _id(payload: dict[str, Any], use_ids: bool) -> int | None:
    if not use_ids:
        return None
    value = payload.get("id")
    if value is None:
        return None
    return int(value)


def _created_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    if isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _requested_ids_are_free(session: Session, payload: dict[str, Any]) -> bool:
    checks: list[tuple[type, int]] = []
    master_id = payload.get("id")
    if master_id is not None:
        checks.append((MasterConfig, int(master_id)))
    camera = payload.get("camera") or {}
    if camera.get("id") is not None:
        checks.append((CameraConfig, int(camera["id"])))
    for mode in camera.get("modes") or []:
        if mode.get("id") is not None:
            checks.append((CameraMode, int(mode["id"])))
    preview = payload.get("preview") or {}
    if preview.get("id") is not None:
        checks.append((PreviewConfig, int(preview["id"])))
    detector = payload.get("detector") or {}
    if detector.get("id") is not None:
        checks.append((DetectorConfig, int(detector["id"])))
    event_manager = payload.get("event_manager") or {}
    if event_manager.get("id") is not None:
        checks.append((EventManagerConfig, int(event_manager["id"])))
    approach = payload.get("approach") or {}
    if approach.get("id") is not None:
        checks.append((ApproachConfig, int(approach["id"])))
    motion = payload.get("motion") or {}
    if motion.get("id") is not None:
        checks.append((MotionConfig, int(motion["id"])))
    roi = motion.get("roi") or {}
    if roi.get("id") is not None:
        checks.append((MotionRoi, int(roi["id"])))
    farneback = motion.get("farneback") or {}
    if farneback.get("id") is not None:
        checks.append((FarnebackConfig, int(farneback["id"])))
    knn = payload.get("knn") or {}
    if knn.get("id") is not None:
        checks.append((KnnConfig, int(knn["id"])))
    for feature in knn.get("features") or []:
        if feature.get("id") is not None:
            checks.append((KnnFeature, int(feature["id"])))
    recording = payload.get("recording") or {}
    if recording.get("id") is not None:
        checks.append((RecordingManagerConfig, int(recording["id"])))
    display = recording.get("display") or {}
    if display.get("id") is not None:
        checks.append((DisplayConfig, int(display["id"])))
    trip = payload.get("trip") or {}
    if trip.get("id") is not None:
        checks.append((TripRecorderConfig, int(trip["id"])))
    buzzer = payload.get("buzzer") or {}
    if buzzer.get("id") is not None:
        checks.append((BuzzerConfig, int(buzzer["id"])))
    for model, row_id in checks:
        if session.get(model, row_id) is not None:
            return False
    return True
