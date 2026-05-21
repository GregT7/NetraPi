# Resume Support Document - NetraPi

## What This Document Is
This document tracks the resume-ready accomplishments of the NetraPi project and helps confirm that each claim is backed by implemented, tested, and demonstrated work. It is the bridge between the project proposal (`pop.md`) and the final concise resume bullets.

This file will be used to:
- map proposed outcomes to concrete implementation evidence,
- maintain ongoing/new accomplishment bullets as work evolves,
- and produce a final concise set of polished resume points.

## Section 1: Initial Resume Bullets to Fulfill (Derived from `pop.md`)
These are the initial target bullets derived from the project overview proposal and stack definitions.

- Built an end-to-end driving safety monitoring system that runs from Raspberry Pi 5 at the edge to cloud services for storage and dashboard reporting.
- Used Python, TensorFlow Lite (`tflite-runtime`), and Google Coral USB TPU to detect unsafe driving events in real time on-device.
- Built the video pipeline with OpenCV and SQLite to keep recording and queue uploads during outages, then resume uploads after reconnect.
- Collected and processed 10+ hours of baseline driving footage with fixed settings to compute safety metrics and check detection consistency.
- Deployed a Dockerized FastAPI backend on Render for API key authentication, metadata ingestion, and analytics/video endpoints.
- Stored videos in private AWS S3 buckets with signed URL access, and stored event metadata in Supabase PostgreSQL with linked S3 object paths.
- Deployed a React + Tailwind dashboard on Vercel with Recharts views for event frequency, session distributions, and baseline vs post-baseline results.
- Set up GitHub Actions for lint, test, build, and deployment checks, and ran the edge app as a `systemd` service for reliable startup and recovery.

## Section 2: Ongoing / New Bullet Points
This section captures additional bullet points as work progresses beyond the original proposal scope, or as existing bullets are refined for specificity and impact.

- Got Coral TPU inference working reliably on Raspberry Pi by fixing TensorFlow Lite dependency and runtime issues.
- Switched from PiCam to a USB camera to match TPU pipeline compatibility needs.
- Designed and 3D-printed camera mount prototypes, then installed the final windshield mount using screws and adhesive with safe/legal placement.
- Installed the in-car hardware by routing wiring and securing the Raspberry Pi and battery for stable real-world use.
- Added real-time audible feedback with a GPIO buzzer that triggers when an unsafe event is detected.

## Section 3: Final Concise Resume Points
This section contains the polished final set intended for direct resume use, written to be concise and high signal.

- to be determined...
