# Resume Support Document - NetraPi

## What This Document Is
This document tracks the resume-ready accomplishments of the NetraPi project and helps confirm that each claim is backed by implemented, tested, and demonstrated work. It is the bridge between the project proposal (`pop.md`) and the final concise resume bullets.

This file will be used to:
- map proposed outcomes to concrete implementation evidence,
- maintain ongoing/new accomplishment bullets as work evolves,
- and produce a final concise set of polished resume points.

## Section 1: Initial Resume Bullets to Fulfill (Derived from `pop.md`)
These are the initial target bullets derived from the project overview proposal and stack definitions.

- Built an end-to-end stop-sign event detection system that runs from Raspberry Pi 5 at the edge to cloud services for storage and dashboard reporting.
- Used Python, TensorFlow Lite (`tflite-runtime`), and Google Coral USB TPU to classify stop-sign encounters (run-through, rolling stop, complete stop) in real time on-device.
- Built the video pipeline with OpenCV and SQLite for local event metadata, then uploaded clips one at a time when online via a FastAPI backend (presigned S3 PUT + Postgres metadata; no offline upload queue).
- Collected 10+ hours of driving footage after system bring-up with fixed model settings, manual ground-truth labeling, and model accuracy evaluation.
- Deployed a Dockerized FastAPI backend on Render for API key authentication, presigned upload URL issuance, metadata ingestion to Postgres, and analytics/video endpoints.
- Stored videos in private AWS S3 buckets with signed URL access, and stored event metadata in Supabase PostgreSQL with linked S3 object paths.
- Deployed a React + Tailwind dashboard on Vercel with event browsing, clip selection, accuracy metrics, and at least one evaluation visualization.
- Set up GitHub Actions for lint, test, build, and deployment checks, and ran the edge app as a `systemd` service for reliable startup and recovery.

## Section 2: Ongoing / New Bullet Points
This section captures work completed or in progress beyond Section 1 targets.

- Designed the full in-car hardware stack (Raspberry Pi 5, Coral USB TPU, USB camera, portable battery) and manually installed it in a 2010 Mazda3 with routed wiring and reversible mounting.
- Iterated 3D-printed windshield camera mount prototypes and installed the final mount with screws and adhesive for stable, road-legal forward-facing video.
- Produced hardware and software architecture diagrams plus Mermaid UML/flow documentation for the recording, inference, and event-clip pipeline (`event_clip_pipeline.md`).
- Got Coral TPU inference working on Raspberry Pi by resolving TensorFlow Lite dependency and runtime issues (`tflite-runtime` instead of PyCoral).
- Switched from PiCam to a USB camera so capture libraries stay compatible with the edge inference stack.
- Validated live on-device object detection and inference timing with dedicated edge test scripts (TPU smoke tests, live USB inference, realtime detection loop).
- Prototyped rolling-buffer event-clip extraction and multi-hour in-car recording endurance with OpenCV-based test scripts and recorded pass evidence.
- Added real-time audible feedback with a GPIO buzzer that triggers when an unsafe stop-sign event is detected.
- Defined requirements and acceptance tests in `mvs.md` and `test.md` (sprint sections through E), including narrowing scope to stop-sign events and model-accuracy evaluation.

## Section 3: Final Concise Resume Points
This section contains the polished final set intended for direct resume use, written to be concise and high signal.

- to be determined...
