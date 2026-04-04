# NetraPi Implementation Phases and Requirement/Test Mapping

## 1. Purpose
This document turns the MVS into a clearer execution roadmap. Each phase lists:
- what should be implemented before moving forward
- which requirements are primarily addressed in that phase
- which tests validate those requirements

Use this file to answer two questions:
1. **What needs to be built next?**
2. **Which tests become valid after that work is done?**

---

## Phase 1 — Constraints and Physical Configuration

### Summary of what needs to be accomplished
- Finalize the bill of materials and stay within budget.
- Confirm the design fits a 2010 Mazda3.
- Choose safe, reversible mounting positions.
- Secure the camera, Pi, TPU, wiring, and battery.
- Ensure the Pi runs exclusively from the portable battery.
- Confirm the system can be removed/reinstalled.
- Confirm the system can operate and record for 3 hours.
- Validate supervised operation in hot-weather conditions.

### Requirements covered
- C-1.10, C-1.11, C-1.12, C-1.13
- M-1.10, M-1.11, M-1.12, M-1.13
- M-1.20, M-1.21, M-1.22

### Corresponding tests
- C-1.10 → TP-01
- C-1.11 → TP-02
- C-1.12, C-1.13 → TP-03
- M-1.10 → TP-04
- M-1.11 → TP-05
- M-1.12 → TP-06
- M-1.13 → TP-07
- M-1.20 → TP-08
- M-1.21 → TP-09
- M-1.22 → TP-10

### Minimum implementation checkpoint before moving on
- Physical layout is selected and safe.
- Portable battery powering works.
- System can survive a 3-hour run and 3-hour recording test.

---

## Phase 2 — Edge Capture, Buffering, and Local ML

### Summary of what needs to be accomplished
- Implement manual recording start/stop.
- Implement continuous forward-facing capture.
- Implement a rolling video buffer.
- Make resolution, frame rate, and buffer duration configurable.
- Install and validate the Coral TPU runtime.
- Load a TPU-compiled TFLite model.
- Implement a stable detection loop with logging.

### Requirements covered
- M-2.10, M-2.11, M-2.12, M-2.13, M-2.14
- M-3.10, M-3.11, M-3.12

### Corresponding tests
- M-2.10, M-2.11 → TP-11
- M-2.12 → TP-12
- M-2.13 → TP-13
- M-2.14 → TP-14
- M-3.11, M-3.12 → TP-15
- M-3.10, M-3.11, M-3.12 → TP-16

### Minimum implementation checkpoint before moving on
- Edge runtime can capture video and run stable inference loops.

---

## Phase 3 — Unsafe Event Detection

### Summary of what needs to be accomplished
- Detect at least one unsafe event class.
- Implement stop-sign detection logic.
- Apply persistence filtering.
- Apply region-of-interest filtering.
- Validate approach using size or growth.
- Compute motion score.
- Detect near-zero motion and stop duration.
- Classify rolling stop, full stop, and bypass events.
- Extract event clips with required pre/post windows.
- Trigger audible feedback within timing limits.
- Prevent false positives.

### Requirements covered
- M-3.13
- M-3.20, M-3.21
- M-3.30, M-3.31
- M-4.10, M-4.11, M-4.12
- M-4.20, M-4.21
- M-4.30, M-4.31, M-4.32

### Corresponding tests
- M-3.13 → TP-17
- M-3.20 → TP-18
- M-3.21 → TP-19
- M-3.30, M-3.31 → TP-20

### Minimum implementation checkpoint before moving on
- Unsafe event detection pipeline produces correct classifications and clips.

---

## Phase 4 — Offline-First Operation and Local Persistence

### Summary of what needs to be accomplished
- Make capture and detection independent of network connectivity.
- Implement local SQLite storage for event metadata and upload queue state.
- Store queue records with clip identifier, path, upload state, retry count, and timestamps.
- Reload queue records on restart.
- Resume uploads automatically after connectivity returns.

### Requirements covered
- M-5.10, M-5.20, M-5.21, M-5.22
- M-10.21, M-10.22

### Corresponding tests
- M-5.10 → TP-21
- M-5.20, M-5.21 → TP-22
- M-5.22, M-10.21, M-10.22 → TP-23

### Minimum implementation checkpoint before moving on
- Offline event generation is safe.
- Queue survives reboot and resumes when network returns.

---

## Phase 5 — Cloud Upload, Backend API, and Database

### Summary of what needs to be accomplished
- Upload baseline footage and clips directly from the Pi to S3.
- Configure a private S3 bucket.
- Configure lifecycle retention rules.
- Deploy a backend with API-key authentication.
- Receive metadata uploads from the edge device.
- Persist structured metadata in Postgres.
- Store S3 paths in the database.
- Generate signed URLs.
- Serve frontend requests for metadata and playback.

### Requirements covered
- M-6.10, M-6.20, M-6.30, M-6.31
- M-7.10, M-7.11, M-7.12, M-7.13, M-7.14
- M-8.10, M-8.11, M-8.12

### Corresponding tests
- M-6.10 → TP-24
- M-6.20 → TP-25
- M-6.30, M-6.31 → TP-26
- M-7.10 → TP-27
- M-7.11, M-7.12, M-8.10 → TP-28
- M-8.11, M-8.12 → TP-29
- M-7.13 → TP-30
- M-7.14 → TP-31

### Minimum implementation checkpoint before moving on
- End-to-end path exists from edge event to S3 asset, database row, and backend-served playback link.

---

## Phase 6 — Deployment, Runtime Management, and CI/CD

### Summary of what needs to be accomplished
- Run the edge software as a managed service.
- Resume capture after power loss.
- Reload pending upload records after restart.
- Containerize backend and build frontend artifacts.
- Deploy backend and frontend.
- Ensure frontend and backend connectivity.
- Configure CI pipelines for linting, testing, and builds.
- Enable deployment gating on passing checks.
- Add post-deployment health checks.

### Requirements covered
- M-10.10
- M-10.20, M-10.21, M-10.22
- M-10.30, M-10.31, M-10.32, M-10.33

### Corresponding tests
- M-10.10 → TP-45
- M-10.20 → TP-46
- M-10.30 → TP-47
- M-10.31 → TP-48
- M-10.32, M-10.33 → TP-49

### Minimum implementation checkpoint before moving on
- System deploys successfully and runs reliably.

---

## Phase 7 — End-to-End System Integration

### Summary of what needs to be accomplished
- Validate full pipeline from edge to cloud to frontend.
- Validate offline-first behavior end-to-end.
- Validate metadata consistency across systems.
- Validate video playback via frontend.
- Validate restart and recovery scenarios.

### Requirements covered
- M-5.*, M-9.*, M-10.*

### Corresponding tests
- TP-67 → TP-72

### Minimum implementation checkpoint before moving on
- Full system operates correctly under normal and failure conditions.

---

## Phase 8 — Frontend / Interactive Portfolio

### Summary of what needs to be accomplished
- Deploy the React web app.
- Add project overview content explaining goals, architecture, and constraints.
- Add event filtering by date range and collection phase.
- Display aggregate metrics and comparisons.
- Support video playback via signed URLs.
- Display event metadata and timestamps.
- Add charts over time.
- Clearly distinguish baseline vs post-baseline data.
- Display data-collection configuration parameters.
- Provide source-code and documentation links.

### Requirements covered
- M-9.10, M-9.11
- M-9.20, M-9.21, M-9.22, M-9.23
- M-9.30, M-9.31
- M-9.40, M-9.41
- M-9.50, M-9.51, M-9.52

### Corresponding tests
- M-9.10, M-9.11 → TP-32
- M-9.20 → TP-33
- M-9.21, M-9.50, M-9.51, M-9.52 → TP-34
- M-9.22 → TP-35
- M-9.23 → TP-36
- M-9.30 → TP-37
- M-9.31 → TP-38
- M-9.40 → TP-39
- M-9.41 → TP-40

### Minimum implementation checkpoint before moving on
- A reviewer can load the deployed web app and fully explore the system.

---

## Phase 9 — Experimentation and Impact Evaluation

### Summary of what needs to be accomplished
- Implement baseline mode that retains full-session video.
- Record at least 10 hours of baseline driving.
- Keep model and configuration fixed during baseline.
- Process baseline footage into metrics.
- Implement post-baseline mode with clip-based retention.
- Record at least 10 additional hours post-baseline.
- Compare post-baseline results to baseline.
- Frame results as evaluation of real-time feedback and self-monitoring.

### Requirements covered
- M-4.10, M-4.11, M-4.12
- M-4.20, M-4.21
- M-4.30, M-4.31, M-4.32
- M-4.40, M-4.41, M-4.42

### Corresponding tests
- M-4.10, M-4.11, M-4.12, M-4.42 → TP-41
- M-4.20, M-4.21, M-4.42 → TP-42
- M-4.30, M-4.31, M-4.32, M-4.42 → TP-43
- M-4.40, M-4.41, M-4.42 → TP-44

### Minimum implementation checkpoint before project closeout
- Both phases completed with sufficient data for comparison.

## Full Requirement-to-Test Index

### Constraints
- C-1.10 → TP-01
- C-1.11 → TP-02
- C-1.12 → TP-03
- C-1.13 → TP-03

### R-1 Physical Configuration
- M-1.10 → TP-04
- M-1.11 → TP-05
- M-1.12 → TP-06
- M-1.13 → TP-07
- M-1.20 → TP-08
- M-1.21 → TP-09
- M-1.22 → TP-10

### R-2 Video Capture and Buffering
- M-2.10 → TP-11
- M-2.11 → TP-11
- M-2.12 → TP-12
- M-2.13 → TP-13
- M-2.14 → TP-14

### R-3 Unsafe Event Detection
- M-3.10 → TP-16
- M-3.11 → TP-15, TP-16
- M-3.12 → TP-15, TP-16
- M-3.13 → TP-17
- M-3.20 → TP-18
- M-3.21 → TP-19
- M-3.30 → TP-20
- M-3.31 → TP-20

### R-4 Experimentation and Impact Evaluation
- M-4.10 → TP-41
- M-4.11 → TP-41
- M-4.12 → TP-41
- M-4.20 → TP-42
- M-4.21 → TP-42
- M-4.30 → TP-43
- M-4.31 → TP-43
- M-4.32 → TP-43
- M-4.40 → TP-44
- M-4.41 → TP-44
- M-4.42 → TP-41, TP-42, TP-43, TP-44

### R-5 Offline-First Operation and Local Persistence
- M-5.10 → TP-21
- M-5.20 → TP-19, TP-22
- M-5.21 → TP-22
- M-5.22 → TP-23

### R-6 Media Upload and Cloud Storage
- M-6.10 → TP-24
- M-6.20 → TP-25
- M-6.30 → TP-26
- M-6.31 → TP-26

### R-7 Backend API
- M-7.10 → TP-27
- M-7.11 → TP-28
- M-7.12 → TP-28
- M-7.13 → TP-30
- M-7.14 → TP-31

### R-8 Database
- M-8.10 → TP-28
- M-8.11 → TP-29
- M-8.12 → TP-29

### R-9 Web Frontend
- M-9.10 → TP-32
- M-9.11 → TP-32
- M-9.20 → TP-33
- M-9.21 → TP-34
- M-9.22 → TP-35
- M-9.23 → TP-36
- M-9.30 → TP-37
- M-9.31 → TP-38
- M-9.40 → TP-39
- M-9.41 → TP-40
- M-9.50 → TP-34
- M-9.51 → TP-34
- M-9.52 → TP-34

### R-10 Deployment and Reliability
- M-10.10 → TP-45
- M-10.20 → TP-46
- M-10.21 → TP-23
- M-10.22 → TP-23
- M-10.30 → TP-47
- M-10.31 → TP-48
- M-10.32 → TP-49
- M-10.33 → TP-49