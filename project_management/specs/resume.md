# Resume Support Document - NetraPi

## What This Document Is
This document tracks the resume-ready accomplishments of the NetraPi project and confirms that each claim is backed by implemented, tested, and demonstrated work. It is the bridge between the project proposal (`pop.md`) and the concise bullets in Section 3.

**Still open vs MVS:** TP-74 (10+ hours of driving with a frozen config, trip+clip drain to S3, and labels for evaluation). Do not put that claim in Section 3 until TP-74 passes.

## Section 1: Initial Resume Bullets to Fulfill (Derived from `pop.md`)
These are the original target bullets from the proposal and stack definitions. They are not a claim that every line is done.

- Built an end-to-end stop-sign event detection system that runs from Raspberry Pi 5 at the edge to cloud services for storage and dashboard reporting.
- Used Python, TensorFlow Lite (`tflite-runtime`), and Google Coral USB TPU to classify stop-sign encounters (run-through, rolling stop, complete stop) in real time on-device.
- Built the video pipeline with OpenCV and SQLite for local event metadata, then uploaded clips one at a time when online via a FastAPI backend (presigned S3 PUT + Postgres metadata; no offline upload queue).
- Added a synchronous edge boot health check (Coral TPU, Wi-Fi/internet, Render wake, authenticated `/ready`) that selects online or offline capture, keeps Render awake while online, and later drains leftover clips/trips on Wi-Fi (with optional local delete after a successful drain).
- Collected 10+ hours of driving footage after system bring-up with fixed model settings, manual ground-truth labeling, and model accuracy evaluation. **(TP-74 — not passed yet)**
- Deployed a Dockerized FastAPI backend on Render for API key authentication, presigned upload URL issuance, metadata ingestion to Postgres, and analytics/video endpoints.
- Stored videos in private AWS S3 buckets with signed URL access, and stored event metadata in Supabase PostgreSQL with linked S3 object paths.
- Public demo playback lets visitors browse and play real collected event clips through short-lived signed GET URLs (2-minute TTL), capped at 20 concurrent signatures and rate-limited per client IP, so they can engage with actual footage while unbounded public GETs are less likely to produce a large AWS S3 bill.
- Try-it-out detailed playback (default) replays the stop-sign state machine next to area/motion graphs synchronized to the clip, using JSON sidecars (`areas.json`, `motion.json`, `transitions.json`) stored beside each video in S3.
- Deployed a React + Tailwind dashboard on Vercel with event browsing, clip selection, accuracy metrics, and at least one evaluation visualization.
- Set up GitHub Actions for lint, test, build, and deployment checks, and ran the edge app as a `systemd` service that is started and stopped manually (not on boot).

## Section 2: Completed work (evidence-backed)
Work that is implemented and demonstrated. Hardware, sprints through CI/CD, and public playback are in; the 10-hour collection campaign is not.

- Designed the in-car hardware stack (Raspberry Pi 5, Coral USB TPU, USB camera, portable battery) and installed it in a 2010 Mazda3 with reversible mounts and portable-battery power only.
- Iterated 3D-printed windshield camera mount prototypes and installed a road-legal forward-facing mount.
- Ran Coral TPU inference on the Pi with `tflite-runtime` (not PyCoral) and switched from PiCam to USB camera for library compatibility.
- Built continuous capture with a rolling buffer, stop-sign classification (complete / rolling / run-through), GPIO buzzer feedback, SQLite event metadata, and trip-segment recording.
- Added synchronous boot health (TPU smoke, Wi-Fi/internet, Render `/health`, authenticated `/ready`), one-way online/offline capture, keep-alive, and `--drain clips|trips|both` with optional `--delete-uploaded`.
- Deployed FastAPI on Render (Docker, API key ingest, presigned S3 PUT/GET, Alembic to Supabase). Objects stay in a private S3 bucket; the Pi holds no AWS or Postgres credentials.
- Shipped the public SPA on Vercel (`netrapi.vercel.app`): real-world clip list, 2-minute signed playback, mint caps, detailed vs simple playback, sidecar JSON, Field vs Calibrated Accuracy vs manual labels.
- GitHub Actions runs oxlint, Vitest, pytest unit tests, and a frontend build on every update; `main` deploys Render then Vercel only when those jobs pass, with `/health`, public clips, and homepage curls as the gate (TP-72).
- Defined requirements and tests in `mvs.md` / `test.md` (TP-01–74). systemd start/stop without enable-on-boot is TP-73.

## Section 3: Final Concise Resume Points
Use these on a resume. Do not add the 10-hour collection line until TP-74 passes.

- Built a real-time stop-sign behavior classifier on Raspberry Pi 5 + Coral USB TPU (OpenCV, TFLite, SQLite) that labels complete, rolling, and run-through stops on-device.
- Shipped FastAPI + Docker on Render, private S3 + Supabase Postgres, and a React/TypeScript/Tailwind SPA on Vercel, with GitHub Actions CI/CD gating deploys
