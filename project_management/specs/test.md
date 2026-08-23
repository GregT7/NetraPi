# NetraPi Test Plan (Updated for Full MVS Coverage)

## 1. Purpose
Verify that NetraPi satisfies the MVS through staged, repeatable tests across the edge device, local persistence, cloud storage, backend API, and deployment. Frontend and later evaluation UI tests are deferred until those layers exist.

## 2. How to Use This Plan
This document is ordered by **sprint section** in this file (Sprint 1–5, then D–E). Earlier tests should be executable before later layers exist. A separate `sprint.md` schedule file was removed; sprint goals live in these section headers until reintroduced.

Each test includes:
- **Reqs**: the requirement IDs covered
- **Prerequisites**: what must already be implemented before the test is valid
- **Pass criteria**: what counts as success

**TP-xx** tests are the baseline verification items defined at project start. **AT-xx** ad-hoc tests are added during development; see [§7 Ad-hoc tests](#7-ad-hoc-tests-at-xx).

## 3. System Definitions
- **Edge runtime**: Raspberry Pi 5, Coral USB TPU, camera, local scripts/services, local file storage, and local SQLite database
- **Cloud storage**: private AWS S3 bucket used for full-session footage and event clips
- **Backend API**: deployed cloud API that authenticates the edge device, issues temporary S3 upload URLs (presigned PUT), persists metadata to Postgres, and returns signed playback URLs
- **Database**: cloud-hosted PostgreSQL (via backend) storing structured metadata and S3 paths; local SQLite on the Pi for offline event metadata until an online upload completes
- **Upload path**: when online, Pi authenticates to the backend → backend issues a short-lived S3 PUT URL and later writes Postgres metadata; Pi does not hold permanent AWS or Postgres credentials
- **Frontend / UI**: deferred — portfolio tests will be added when frontend work starts
- **Ground-truth labeling**: manual review of collected footage to assign run-through, rolling stop, and complete stop categories for accuracy evaluation
- **Event type**: one of **run-through**, **rolling stop**, or **complete stop** (model prediction or manual label)

## 4. Evidence Recording
Record execution results in a separate verification matrix or spreadsheet. Acceptable evidence includes:
- terminal screenshots
- log captures
- short videos
- photos of installed hardware
- SQLite query output
- S3 console screenshots
- Postgres query results
- frontend screenshots
- CI/CD pipeline screenshots

## 5. Test Levels
- **Unit**: individual module or function in isolation
- **Integration**: two or more components interacting
- **System**: full subsystem behavior in one environment
- **Acceptance**: end-to-end validation against user-facing goals

## 6. Verification Approaches
- **Inspection**: visual/structural verification
- **Demonstration**: observed runtime behavior
- **Test**: instrumented execution with measurable pass/fail criteria
- **Analysis**: reasoning over collected data or outputs

## 7. Ad-hoc tests (AT-xx)

**TP-xx** tests were written when the test plan was first defined. Their numbers stay fixed so prerequisites, the test matrix, and cross-references do not change when new verification is added later.

**AT-xx** (**A**d-hoc **T**est) is the ID pattern for tests added **during the project** as gaps or risks show up. Use **`AT-{sprint}.{n}`** (for example **AT-2.3**, **AT-3.3**). An AT test can use any **test level** in §5 (Unit, Integration, System, etc.) — the prefix only marks *when* the test entered the plan, not how many components it touches.

Run AT tests after the relevant sprint **TP** prerequisites unless a specific AT entry says otherwise. Each AT uses the same fields as TP tests (**Description**, **Test level**, **Verification approach**, **Reqs**, **Prerequisites**, **Steps**, **Pass criteria**). Record evidence in the verification matrix / spreadsheet like any other test.

| Sprint | Section in this doc | Ad-hoc tests |
|--------|---------------------|--------------|
| 2 | [Sprint 2 ad-hoc tests](#sprint-2-ad-hoc-tests-non-tp) | AT-2.1–AT-2.5 — recording pipeline resilience, policy, boundaries, preview parity, long-run stability |
| 3 | [Sprint 3 ad-hoc tests](#sprint-3-ad-hoc-tests-non-tp) | AT-3.1, AT-3.3, AT-3.4 — buzzer enclosure wiring, continuous approach Pi bench, live motion + kNN bench (**AT-3.2** withdrawn) |
| 7 | [Sprint 7 ad-hoc tests](#sprint-7-ad-hoc-tests-non-tp) | AT-7.1–AT-7.3 — mocked pipeline; camera + SPACE + stubbed events; in-car live three-maneuver E2E → cloud |

Some AT tests reference scripted entry points under `src/tests/integration/` (same convention as TP integration tests where applicable).

---

# Sprint 1 — Foundation and Edge Bring-Up

*Tests: TP-01 to TP-15*

## Constraints and Physical Configuration
### TP-01: Budget compliance check
- **Description**: Verifies the total NetraPi system cost remains within the allowed budget.
- **Test level**: Inspection
- **Verification approach**: Analysis
- **Reqs**: C-1.10
- **Prerequisites**
  - Bill of materials exists.
- **Steps**
  1. Compile all purchased and planned required components.
  2. Sum total project cost.
- **Pass criteria**
  - Total cost is **$1,000 or less**.

### TP-02: Picam smoke test
- **Description**: Verifies the Raspberry Pi detects the camera and can display clear live output.
- **Test level**: Integration
- **Verification approach**: Demonstration
- **Reqs**: M-2.10
- **Prerequisites**
  - Equipment purchased: Pi, camera, compatible ribbon cable
  - OS loaded on Pi
- **Steps**
  1. Connect the Pi camera to the Raspberry Pi.
  2. Open a terminal on the Pi.
  3. Run `rpicam-hello --list-cameras` and confirm the camera is detected.
  4. Run `rpicam-hello` and observe the temporary preview.
- **Pass criteria**
  - The camera appears in the detected camera list.
  - Temporary preview footage appears.
  - Output is clear and shows no obvious visual issues.

### TP-03: Portable-battery-only power verification
- **Description**: Verifies the Raspberry Pi can boot and operate using only the portable battery.
- **Test level**: System
- **Verification approach**: Demonstration
- **Reqs**: M-1.12
- **Prerequisites**
  - Portable battery power path implemented.
- **Steps**
  1. Power the Pi using the portable battery only.
  2. Confirm the system boots successfully.
  3. Confirm the camera preview or camera test can run.
  4. Confirm no vehicle power connection is used.
- **Pass criteria**
  - System operates solely from the portable battery.

### TP-04: Camera mounting verification
- **Description**: Verifies the camera is mounted securely and provides a stable, usable forward-facing view during driving.
- **Test level**: System
- **Verification approach**: Inspection + Demonstration
- **Reqs**: M-1.10
- **Prerequisites**
  - Camera mounting location selected.
- **Steps**
  1. Install the camera in its intended position.
  2. Capture a 60-second daylight drive video.
- **Pass criteria**
  - Video shows a stable forward roadway view with acceptable visibility and minimal vibration.

### TP-05: Vehicle compatibility inspection
- **Description**: Verifies the planned hardware can be installed and operated within a 2010 Mazda3 sedan.
- **Test level**: System
- **Verification approach**: Inspection + Demonstration
- **Reqs**: C-1.11
- **Prerequisites**
  - Physical mounting approach defined.
- **Steps**
  1. Install the planned hardware in the vehicle.
  2. Confirm camera placement, cable routing, power routing, and battery placement fit the car.
- **Pass criteria**
  - System fits and operates in the 2010 Mazda3 without preventing normal driving use.

### TP-06: Safety and legality review
- **Description**: Verifies the installed system does not obviously violate safety or driving constraints.
- **Test level**: System
- **Verification approach**: Inspection
- **Reqs**: C-1.12, C-1.13, M-1.11
- **Prerequisites**
  - Final physical layout selected.
- **Steps**
  1. Inspect the installed system from driver and passenger viewpoints.
  2. Confirm visibility, controls, cable routing, and hardware placement do not create obvious hazards.
  3. Apply light movement and vibration checks by hand to mounted components.
- **Pass criteria**
  - Driver view is not materially obstructed.
  - Hardware is secured in intended positions.
  - No loose components or cables create an obvious driving hazard.

### TP-07: Reversible removal verification
- **Description**: Verifies the Pi, TPU, and battery can be removed and reinstalled without permanent modification or damage.
- **Test level**: System
- **Verification approach**: Demonstration
- **Reqs**: M-1.13
- **Prerequisites**
  - Reversible mounting mechanism implemented.
- **Steps**
  1. Remove the Pi, TPU, and battery from their mounts.
  2. Reinstall them.
  3. Restore operation.
- **Pass criteria**
  - Removal and reinstallation complete without damage.
  - System returns to operational state.

### TP-08: Three-hour continuous recording to memory
- **Description**: Verifies the system continuously records and writes footage to memory for at least 3 hours.
- **Test level**: System
- **Verification approach**: Test + Inspection
- **Reqs**: M-1.20, M-1.21
- **Prerequisites**
  - Continuous recording implemented.
  - Sufficient storage available.
  - Battery sized for endurance test.
- **Steps**
  1. Start continuous recording.
  2. Allow recording to continue for 3 hours.
  3. Inspect resulting files and storage utilization.
- **Pass criteria**
  - Recording is continuous for at least 3 hours.
  - Files are present and readable.
  - System remains operational for the full 3-hour run without recharge or reinstallation.

### TP-09: Texas-summer supervised operation check
- **Description**: Verifies the system can operate under typical Texas summer temperatures with supervision.
- **Test level**: System
- **Verification approach**: Demonstration + Inspection + Analysis
- **Reqs**: M-1.22
- **Prerequisites**
  - System fully installed and operational.
  - Three-hour recording test completed successfully.
- **Steps**
  1. Operate the system for 3 total hours with an outside temperature of 80° F or greater.
  2. Monitor for overheating, shutdowns, or unsafe temperatures.
- **Pass criteria**
  - The average outside air temperature over the 3 hours is 80 °F or greater.
  - The internal temperature of the Pi never exceeds 85 °C.
  - The average internal temperature of the Pi across the 3 hours is below 82 °C.

## Edge Capture, Buffering, and Local ML

### TP-10: Coral TPU smoke test
- **Description**: Verifies the Coral USB TPU is detected and usable on the Raspberry Pi.
- **Test level**: Integration
- **Verification approach**: Inspection
- **Reqs**: M-3.11, M-3.12
- **Prerequisites**
  - Pi, Coral USB TPU, and required cables connected
  - OS and Python installed
- **Steps**
  1. Update system, download pycoral code
  2. Verify Python installation: `python3 --version`
  3. Run `lsusb` and confirm Coral device appears.
  4. Run a minimal interpreter script to load the TPU delegate.
- **Pass criteria**
  - Coral appears in `lsusb` (e.g., "Global Unichip Corp.")
  - TPU Inference successfully classifies an images

### TP-11: Live camera-to-TPU inference functional smoke test
- **Description**: Verifies the end-to-end live inference pipeline runs using a camera feed and produces valid object detection outputs using the Coral TPU.
- **Test level**: Integration
- **Verification approach**: Demonstration
- **Reqs**: M-3.10, M-3.11, M-3.12
- **Prerequisites**
  - TP-10 passed
  - Camera capture path validated
  - Edge-TPU-compatible detection model available
  - Live inference script available
- **Steps**
  1. Launch the live inference script with camera input.
  2. Confirm frames are continuously received and processed.
  3. Point the camera at one or more supported object classes (e.g., person, car, stop sign).
  4. Observe detection output in the console or annotated frames.
  5. Move the object or camera slightly and confirm detections update over time.
- **Pass criteria**
  - Live pipeline runs continuously without crashing for 30 seconds.
  - Frames are processed repeatedly (multiple frames observed).
  - At least one supported object is detected when clearly visible.
  - Detection output updates across multiple frames (not a single isolated detection).

### TP-11.5: Live inference pipeline throughput and latency benchmark
- **Description**: Measures the performance of the live camera-to-TPU inference pipeline, including effective FPS, processing latency, and identification of system bottlenecks.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-3.10, M-3.11, M-3.12
- **Prerequisites**
  - TP-11 passed
  - Timing instrumentation script available
- **Steps**
  1. Run the timing test script for the active live inference pipeline.
  2. Allow the system to process frames for at least 60–100 frames.
  3. Record the following metrics:
     - effective processed FPS
     - average total loop time (ms)
     - average frame acquisition time (ms), if measured
     - average preprocess time (ms)
     - average inference time (ms)
  4. Identify the dominant contributor to total loop time.
  5. Repeat the test if needed under slightly different conditions.
- **Pass criteria**
  - Performance metrics are successfully recorded and reported.
  - Effective processed FPS meets one of the following thresholds:
    - **preferred target:** ≥ 5 FPS
    - **minimum exploratory threshold:** ≥ 3 FPS
  - Average total loop time is reasonably consistent.
  - The main bottleneck in the tested pipeline is clearly identified.

### TP-12: Detection loop real-time operation
- **Description**: Verifies continuous inference execution without crashes or stalls.
- **Test level**: Integration
- **Verification approach**: Demonstration
- **Reqs**: M-3.10, M-3.11, M-3.12
- **Prerequisites**
  - Detection pipeline implemented
  - Logging includes timestamps and inference counter
- **Steps**
  1. Start detection program.
  2. Verify logs show `[timestamp] inference #N`.
  3. Run system for 10 minutes.
- **Pass criteria**
  - Loop runs continuously for 10 minutes.
  - Inference counter increments consistently.
  - No crashes, freezes, or exits.

### TP-13: Capture configuration validation
- **Description**: Verifies resolution and buffer duration are applied, and FPS behavior matches the negotiated MJPG mode for each resolution.
- **Test level**: Integration
- **Verification approach**: Test + Inspection
- **Reqs**: M-2.14
- **Prerequisites**
  - Configurable capture settings implemented
- **Steps**
  1. Set known config values (resolution, FPS request, buffer duration) using MJPG capture.
  2. Start capture.
  3. Inspect logs/output for measured FPS, CAP_PROP_FPS, and negotiated per-resolution mode FPS.
- **Pass criteria**
  - Actual resolution matches configured resolution (within allowed tolerance).
  - Rolling buffer duration behavior matches configured buffer duration.
  - Measured FPS is consistent with the negotiated MJPG FPS for that resolution mode (not merely the requested FPS value).

### TP-14: Rolling buffer and event clip extraction verification
- **Description**: Verifies rolling buffer and event-triggered clip generation produce correct pre/post coverage.
- **Test level**: Integration  
- **Verification approach**: Test  
- **Reqs**: M-2.13, M-3.20  

- **Prerequisites**
  - Rolling buffer implemented
  - Event trigger implemented
  - Post-event recording configured
  - Live camera preview visible with on-screen timestamp overlay

- **Steps**
  1. Set buffer duration to 10 seconds.
  2. Start camera preview and confirm timestamp is visible.
  3. For each event (3 total), manually trigger the event while simultaneously performing a visible action on camera (for example, wave) to mark activation.
  4. Extract generated clips.
  5. Inspect each clip using the timestamp and locate the wave marker.
  6. Verify timestamp coverage includes at least 5 seconds before the wave and at least 5 seconds after the wave.
  7. Measure duration and inspect continuity.

- **Pass criteria**
  - Each clip contains:
    - Timestamped footage showing at least 5 seconds before the wave/event marker
    - Event moment
    - Timestamped footage showing at least 5 seconds after the wave/event marker
  - Total duration is ~10–20 seconds.
  - Camera preview timestamp and saved clip timeline are consistent around the event marker.
  - Video is continuous and playable.
  - No missing frames or abrupt cuts.

### TP-15: Speaker module feedback verification
- **Description**: Verifies the speaker module produces audible feedback suitable for in-vehicle use.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-3.30
- **Prerequisites**
  - Speaker connected to Pi GPIO
- **Steps**
  1. Run script producing multiple tones and volume levels.
  2. Record output while system is running.
  3. Evaluate audibility inside vehicle environment.
- **Pass criteria**
  - Output is continuous with minimal static.
  - Multiple tones and volume levels function correctly.
  - Selected volume is audible but not excessive.

---

# Sprint 2 — Recording System, Detector, and RecordingManager

*Tests: TP-16 to TP-24*

Backlogs: **Recording System Design** (TP-16–TP-17), **Detector** (TP-18–TP-20), **RecordingManager** (TP-21–TP-24).

## Recording System Design
### TP-16: Event clip pipeline and project layout
- **Description**: Verifies the event/clip pipeline is documented and the repo layout matches the planned `src/` structure for the edge capture path (no DB or cloud wiring required).
- **Test level**: Inspection
- **Verification approach**: Inspection
- **Reqs**: M-2.10, M-2.13, M-2.14, M-3.10
- **Prerequisites**
  - `event_clip_pipeline.md` updated for current design
  - `directory_tree.md` drafted
- **Steps**
  1. Review the pipeline diagram for config loading, core classes, and high-level camera → detect → save-clip flow.
  2. Confirm `directory_tree.md` lists intended modules under `src/`.
  3. Confirm stub files/directories exist as described.
- **Pass criteria**
  - Diagram includes configuration loading and classes needed for the basic on-device pipeline.
  - High-level flow covers capture, unsafe-event handling, and clip save path.
  - `directory_tree.md` matches the populated stub layout.

### TP-17: Config loading unit verification
- **Description**: Verifies JSON config files load into typed config objects used by capture and detector modules.
- **Test level**: Unit
- **Verification approach**: Test
- **Reqs**: M-2.14
- **Prerequisites**
  - Config files under `src/main/edge/config/`
  - Config loader implemented
- **Steps**
  1. Run unit tests for loading valid config fixtures (camera, buffer, detector, etc. as implemented).
  2. Run unit test(s) for at least one invalid or missing required field case, if applicable.
- **Pass criteria**
  - Valid configs deserialize to expected values.
  - Invalid config fails predictably (exception or explicit error result).
  - Tests run without hardware.

## Detector
### TP-18: Detector data model and unit tests
- **Description**: Verifies `Classification`, `FrameRecord`, `FrameBuffer`, and `DetectorConfig` behave per the pipeline design.
- **Test level**: Unit
- **Verification approach**: Test
- **Reqs**: M-3.10, M-3.11, M-3.12
- **Prerequisites**
  - Classes implemented per UML
- **Steps**
  1. Run unit tests for `FrameRecord` (`raw`, `display`, `patch_classifications`).
  2. Run unit tests for `FrameBuffer` (`push`, `latest`, `display_frames` returns display).
  3. Run unit tests for `Detector` in `src/tests/unit/edge/netrapi/detection/test_detector.py` (mocked `_invoke`; no Coral).
- **Pass criteria**
  - All unit tests pass without TPU or camera.
  - `display_frames()` exposes processed (`display`) frames, not `raw`.

### TP-19: Detector inference unit tests (mocked TPU)
- **Description**: Verifies `Detector.classify(raw)` wiring with mocked `_invoke` (no Coral required).
- **Test level**: Unit
- **Verification approach**: Test
- **Reqs**: M-3.10, M-3.11, M-3.12
- **Prerequisites**
  - `Detector` with mocked `_invoke` / `_preprocess`
- **Steps**
  1. Run unit test: `classify(raw)` returns filtered `list[Classification]`.
  2. Run unit test: `_filter_detections` drops sub-threshold, non-allowed, and excess detections (`top_k`).
  3. Run unit test: **RecordingManager** patches latest `FrameRecord` after `classify`.
- **Pass criteria**
  - `classify` returns filtered detections without mutating buffers.
  - **RecordingManager** owns `patch_classifications` on the latest pre-buffer entry.
  - Tests pass without Edge TPU hardware.

### TP-20: Detector on-device smoke
- **Description**: Verifies `load()`, `verify_tpu()`, and one real `classify(raw)` on the Pi with Coral attached.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-3.10, M-3.11, M-3.12
- **Prerequisites**
  - TP-10 passed
  - `Detector` implemented through `classify`
  - Test entry point or script with stub/real `detector.json`
- **Steps**
  1. On the Pi, call `load()` then `verify_tpu()`.
  2. Capture one frame (`raw`) from camera (or test fixture).
  3. Call `classify(raw)` and inspect returned `classifications`.
  4. Optionally: push a `FrameRecord` into `pre_buffer`, patch from `classify` result, confirm **EventManager** path.
- **Pass criteria**
  - `verify_tpu()` succeeds.
  - `classify` returns a `list[Classification]` (may be empty if scene has no allowed classes).
  - No crash; load/invoke errors are logged or raised clearly.

## RecordingManager
### TP-21: RecordingManager capture unit tests
- **Description**: Verifies capture-related classes (`Camera`, `FrameProcessor`, `FrameRecord`, `FrameBuffer`, `Recorder`, `ClipPackage`, `PreviewUI`, etc.) pass unit tests and live under the planned `src/` layout.
- **Test level**: Unit
- **Verification approach**: Test + Inspection
- **Reqs**: M-2.10, M-2.13, M-2.14
- **Prerequisites**
  - Classes implemented per pipeline UML
  - `directory_tree.md` defines locations
- **Steps**
  1. Run unit test suite for capture/pipeline classes (mock camera/tensor inputs where needed).
  2. Confirm class files match paths in `directory_tree.md`.
- **Pass criteria**
  - Unit tests pass without full `run_loop`.
  - File locations align with `directory_tree.md`.

### TP-22: RecordingManager idle run loop integration
- **Description**: Verifies `run_loop()` idle path: camera → `FrameRecord` → `pre_buffer.push` with stub config and without requiring unsafe-event logic.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-2.10, M-2.13, M-2.14
- **Prerequisites**
  - TP-17 passed
  - Thin test entry point with stub config values
  - USB camera available on Pi
- **Steps**
  1. Start the test wrapper that runs `RecordingManager.run_loop()` for a short bounded duration (or N laps).
  2. Confirm ``run_loop`` enters the main lap loop immediately (no FPS warmup phase).
  3. Confirm frames enter `pre_buffer` while `clip_active` is false.
  4. Stop the run cleanly via test harness timeout or documented stop method.
- **Pass criteria**
  - Loop runs without crash for the test duration.
  - `pre_buffer` receives `FrameRecord` entries with populated `display`.
  - No clip file written during idle-only run.
  - When full-trip recording is enabled, trip segment playback duration matches wall time (encoding FPS = frame count / segment elapsed).

### TP-23: RecordingManager clip-active path and MP4 output
- **Description**: Verifies `clip_active` post-roll, `ClipPackage.build`, and `Recorder.write_clip` produce a playable MP4 from buffer `display` frames.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-2.13, M-3.20
- **Prerequisites**
  - TP-21 passed
  - Clip path implemented per `event_clip_pipeline.md`
  - Test hook or simulated unsafe trigger to set `clip_active`
- **Steps**
  1. Run loop until `pre_buffer` has history; trigger `clip_active` (test hook or stub event).
  2. Allow post-roll to complete and clip write to finish.
  3. Open resulting MP4.
- **Pass criteria**
  - MP4 file exists at configured output path.
  - Video is playable and uses processed (`display`) frames.
  - Buffers cleared and `clip_active` false after save (per design).

### TP-24: RecordingManager Ctrl+C and preview controls
- **Description**: Verifies live preview of processed `display` frames and clean shutdown on Ctrl+C (scheduled SIGINT and manual terminal interrupt) with camera release.
- **Test level**: Integration
- **Verification approach**: Demonstration
- **Reqs**: M-2.10
- **Prerequisites**
  - TP-22 passed
  - Test entry point: `src/tests/integration/tp_24/tp_24_preview_ctrl_c_integration.py`
  - USB camera on Pi; interactive terminal (TTY) for manual Ctrl+C; preview and trip recording forced on by the test harness
- **Steps**
  1. Run bounded loop with preview and full trip recording on; confirm preview shows `display` frames and `pre_buffer` holds valid display data; confirm a trip segment is written.
  2. Start loop again; after a short delay send SIGINT (automated, same signal as Ctrl+C); confirm `run_loop` returns and camera/resources release without hang.
  3. Start loop again; press Ctrl+C in the terminal during the live run; confirm the same clean shutdown as step 2.
- **Pass criteria**
  - Preview shows live processed frames in the OpenCV window while enabled.
  - Ctrl+C / SIGINT ends the loop without orphaned process or device lock; camera can reopen after shutdown.
  - Evidence captured for test matrix (screenshot or short video optional).

## Sprint 2 ad-hoc tests (non-TP)

### AT-2.1: Recorder write failure and recovery
- **Description**: Verifies `RecordingManager` handles `Recorder.write_clip(...)` failures safely (writer open fail, mid-write exception, output path issue) and recovers for subsequent clips.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-2.10, M-2.13, M-3.20
- **Prerequisites**
  - TP-23 passed
  - Failure injection hook (or mocked writer) available
- **Steps**
  1. Trigger a clip and force a write failure before/during encode.
  2. Verify failure is surfaced clearly (error/log) and process does not hang.
  3. Trigger another clip with normal writer path.
- **Pass criteria**
  - Failure does not crash the run loop permanently or deadlock resources.
  - Subsequent clip can still be written after recovery.

### AT-2.2: Event gate policy matrix (unsafe vs safe)
- **Description**: Verifies clip-start policy exactly matches design: unsafe events always record; safe events record only when `record_safe_events = true`. Fast gate-only check (`clip_active`); full MP4 matrix is **TP-26**.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-2.13, M-2.14, M-4.20
- **Prerequisites**
  - TP-23 passed
  - Triggerable safe and unsafe `DrivingEvent` fixtures/stubs
- **Steps**
  1. Set `record_safe_events = false`; trigger unsafe event, then safe event.
  2. Set `record_safe_events = true`; trigger safe event.
  3. Check `clip_active` transitions (full clip write optional; prefer TP-26).
- **Pass criteria**
  - Unsafe events always start clips.
  - Safe events start clips only when config enables them.
  - No unexpected clip starts occur.

### AT-2.3: Post-roll completion boundary precision
- **Description**: Verifies post-roll finalization gate is correct at wall-clock threshold boundaries and avoids off-by-one behavior.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-2.13, M-3.20
- **Prerequisites**
  - TP-23 passed
- **Steps**
  1. Run clip capture with post-roll elapsed time just below `post_roll_seconds`.
  2. Run clip capture with post-roll elapsed time exactly at `post_roll_seconds`.
  3. Validate save timing and `ClipResult` coverage for both cases.
- **Pass criteria**
  - Save does not occur below `post_roll_seconds` elapsed.
  - Save occurs at threshold and only once per trigger.

### AT-2.4: Deterministic preview-to-file parity
- **Description**: Verifies `PreviewUI` and saved MP4 carry the same processed `display` frames using deterministic frame markers (not subjective visual comparison).
- **Test level**: Integration
- **Verification approach**: Demonstration + Inspection
- **Reqs**: M-2.10, M-2.13, M-3.20
- **Prerequisites**
  - TP-23 passed
  - Preview enabled
- **Steps**
  1. Run one clip with deterministic visual markers (frame id/timestamp overlay) in `display`.
  2. Capture preview evidence at known marker points.
  3. Compare the same marker points in saved MP4.
- **Pass criteria**
  - Marker sequence and visual processing match between preview and MP4.
  - No transform appears exclusively in one path.

### AT-2.5: Long-run multi-cycle stability and resource hygiene
- **Description**: Verifies repeated `idle -> clip_active -> idle` cycles remain stable over an extended run without state/resource leakage.
- **Test level**: Integration
- **Verification approach**: Soak test
- **Reqs**: M-2.10, M-2.13, M-3.20
- **Prerequisites**
  - TP-22 and TP-23 passed
  - Test entry point: `src/tests/integration/at_2_5/at_2_5_long_run_multi_cycle_integration.py`
- **Steps**
  1. Execute a long session with multiple clip triggers in one process.
  2. Track cycle outcomes, memory trend, writer release behavior, and camera availability.
  3. Confirm each cycle returns cleanly to idle before the next trigger.
- **Pass criteria**
  - Multiple consecutive cycles complete successfully without restart.
  - No sustained memory/resource growth or stale `clip_active`/buffer state across cycles.

---

# Sprint 3 — Unsafe Event Detection Core

*Tests: TP-25 to TP-28*

### TP-25: Stop-sign event classification (recorded clips)
- **Description**: Verifies the classification pipeline assigns the correct stop-sign event type (or no event) across a fixed labeled clip set spanning all four categories: rolling stop, run-through, complete stop, and unrelated stop-sign encounter—and meets a minimum overall accuracy threshold before field testing.
- **Test level**: Integration
- **Verification approach**: Test + Analysis
- **Reqs**: M-3.13, M-4.20, M-4.21, M-4.30
- **Prerequisites**
  - TP-20, TP-21 passed
  - Stop-sign approach + motion classification logic implemented
  - Recorded-footage runner available
  - **~100** labeled clips available: **~25** per category (complete stop, rolling stop, run-through, no event)
- **Steps**
  1. Prepare (or confirm) labeled clips: **~25** per category (**~100** clips total) covering rolling stop, run-through, complete stop, and unrelated stop sign.
  2. Run the classification pipeline on the full labeled set.
  3. Compare predicted event type (or no event) to ground-truth label per clip.
  4. Compute overall accuracy: correct / N (N = clip count in the batch, typically ~100).
  5. Record per-category results for the test matrix (optional breakdown).
- **Pass criteria**
  - Overall classification accuracy is **≥ 75%** across the full batch.
  - Pipeline completes without error on all clips.
  - Per-category counts (correct / total) are recorded for review.

### TP-26: Stubbed event gate — all stop-sign types + `record_safe_events`
- **Description**: Verifies `RecordingManager` clip extraction for every stop-sign `DrivingEvent` type when events are **stub-injected** (real `EventManager.evaluate` not required). Covers unsafe always-record and safe gated by `recording_manager.json` → `record_safe_events`.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-2.13, M-3.20
- **Prerequisites**
  - TP-23 passed
  - Stub / mock that returns a fixed `DrivingEvent` from `evaluate` (same pattern as AT-2.2); no real EventManager classification required
  - Test entry point: `src/tests/integration/tp_26/tp_26_stubbed_event_gate_clips_integration.py`
  - Camera + ffmpeg available for a short live session (or equivalent harness used for TP-23)
- **Steps**
  1. Build the pipeline; replace `EventManager` with a stub that returns a chosen `DrivingEvent` on idle `evaluate`.
  2. With `record_safe_events = false`: for each of **`ROLLING_STOP`** and **`RUN_THROUGH`**, fill pre-roll, stub that event, run until post-roll completes, confirm an MP4 is written under `clips_dir`.
  3. With `record_safe_events = false`: stub **`COMPLETE_STOP`**, run one idle lap (or short loop); confirm **no** clip starts (`clip_active` stays false; no new MP4).
  4. With `record_safe_events = true`: stub **`COMPLETE_STOP`**, fill pre-roll, run until post-roll completes; confirm an MP4 is written.
  5. Open each saved MP4 and confirm it is playable with pre-roll + post-roll content (same bar as TP-23).
- **Pass criteria**
  - **`ROLLING_STOP`** and **`RUN_THROUGH`** always produce a saved clip (independent of `record_safe_events`).
  - **`COMPLETE_STOP`** produces a clip **only** when `record_safe_events = true`; otherwise no clip.
  - Each saved clip is a playable MP4 with pre/post footage; buffers clear and `clip_active` is false after write.

### TP-27: Audible feedback on unsafe stop-sign event
- **Description**: Verifies the real edge pipeline emits audible feedback when a stubbed rolling-stop or run-through `DrivingEvent` is evaluated, within timing constraints (camera and EventManager mocked; real `Buzzer` only).
- **Test level**: System
- **Verification approach**: Demonstration + Test
- **Reqs**: M-3.30, M-3.31
- **Prerequisites**
  - TP-15 passed (buzzer tones validated on GPIO)
  - Buzzer wired (BCM **18**); `buzzer.json` with `play_on.unsafe=true`
  - Coral USB TPU plugged in — `build_pipeline` loads the edgetpu `.tflite` via `Detector.load()` even though EventManager is stubbed (`needs_detection=False`; no live inference)
  - No USB camera required (harness mocks the camera)
  - Test entry point: `src/tests/integration/tp_27/tp_27_stubbed_event_buzzer_integration.py`
- **Steps**
  1. On the Pi (Coral attached), run `python src/tests/integration/tp_27/tp_27_stubbed_event_buzzer_integration.py` (builds real pipeline + real `Buzzer`; mocks camera; stubs `EventManager`).
  2. Confirm an audible beep for stubbed **`ROLLING_STOP`**; note evaluate→beep latency printed by the harness.
  3. Confirm an audible beep for stubbed **`RUN_THROUGH`**; note latency.
  4. Confirm **no** beep for stubbed **`COMPLETE_STOP`** (default `play_on.safe=false`).
- **Pass criteria**
  - Audible feedback is produced for **`ROLLING_STOP`** and **`RUN_THROUGH`**.
  - Each unsafe beep occurs within **10 seconds** of the stubbed `evaluate`.
  - No beep for **`COMPLETE_STOP`** under default `play_on`.

### TP-28: In-car E2E classify + beep + clip (edge pipeline)
- **Description**: End-to-end in-vehicle soak on the **fully integrated edge pipeline** (not the AT-3.4 bench, not stubbed events): one complete stop, one rolling stop, and one run-through at stop signs. Confirms classification labels match operator intent, the buzzer fires for unsafe events only, and evidence clips are saved for unsafe events.
- **Test level**: System
- **Verification approach**: Demonstration + Test
- **Reqs**: M-3.13, M-3.20, M-3.30, M-3.31, M-4.12, M-4.20
- **Prerequisites**
  - AT-3.1, AT-3.4 passed (buzzer secured; motion + classification path proven on Pi)
  - TP-26 / TP-27 passed (clip gate + stubbed beep path proven)
  - Edge EventManager classification path implemented and wired (ap_050 / AT-3.4 recipe ported)
  - TP-23 path available (clip write on unsafe); Pi + camera + Coral + buzzer installed in car
  - Test entry point: `src/tests/integration/tp_28/tp_28_e2e_classify_beep_clip_integration.py`
- **Steps**
  1. Mount and power the system in the vehicle; clips land under `clips_dir/tp_28/`.
  2. On the Pi, run `python src/tests/integration/tp_28/tp_28_e2e_classify_beep_clip_integration.py` (real Detector + EventManager + Buzzer + Recorder; no stubs / no CLI flags).
  3. For each of three fixed phases, focus the preview window and press **SPACE** to arm, then perform **complete stop**, **rolling stop**, and **run-through** in that order. Classifications before SPACE are ignored (no beep/clip).
  4. Confirm console classification matches the intended maneuver; listen for beep on unsafe phases.
  5. Inspect saved clips under `clips_dir/tp_28/` after unsafe encounters.
- **Pass criteria**
  - All three encounters complete without crash or camera/TPU stall.
  - Classification labels match operator intent for complete stop, rolling stop, and run-through.
  - Buzzer activates for **rolling stop** and **run-through** within **10 seconds** of each unsafe event; **no** beep for the complete stop (`play_on.safe=false`).
  - An evidence clip is saved for each unsafe event (rolling stop and run-through); no clip for the complete stop (`record_safe_events=false`).
  - Evidence: harness console log (classify / latency / clip paths), clips directory listing (or clip files).

## Sprint 3 ad-hoc tests (non-TP)

### AT-3.1: Buzzer secured in Pi enclosure (GPIO wiring)
- **Description**: Verifies the buzzer module is physically secured inside the Pi container/enclosure, wired to the documented GPIO pin without loose leads or pin strain, and safe for in-vehicle use.
- **Test level**: Integration
- **Verification approach**: Inspection + Demonstration
- **Reqs**: M-1.11, C-1.13, M-3.30
- **Prerequisites**
  - TP-15 passed (buzzer wiring validated on bench)
  - Pi enclosure / container selected for in-vehicle install
  - Documented buzzer pin assignment (BCM **18**, common GND — same as TP-15 scripts)
- **Steps**
  1. Mount the buzzer inside the Pi container so it cannot shift during normal handling or light vehicle vibration.
  2. Connect buzzer to the GPIO header using a secure connector or soldered lead with strain relief; confirm **BCM 18** and GND match TP-15 wiring.
  3. Route leads so they do not block airflow, cover ports, or contact the TPU/camera cables.
  4. Close the enclosure; confirm the buzzer remains reachable for sound (case opening, vent, or grille as designed).
  5. Apply light hand shake / tap to the mounted assembly; re-open if needed and confirm pins and leads did not loosen.
  6. Capture photo evidence of internal wiring and external mounted unit.
- **Pass criteria**
  - Buzzer and wiring are physically secured inside the Pi container with no obvious loose components.
  - GPIO connection matches the documented pin map (**BCM 18**).
  - No pinched, frayed, or short-risk wiring; install satisfies **M-1.11** and does not create an obvious driving hazard (**C-1.13**).
  - Buzzer can still be exercised with `src/tests/integration/tp_15/tp15_buzzer_smoke_test.py` after enclosure close-up.

> **AT-3.2 withdrawn** (not renumbered): early-boot GPIO idle service for active-buzzer startup noise. Superseded by switching to a **passive** buzzer (PWM-driven; silent until intentional tones). IDs **AT-3.3** / **AT-3.4** stay unchanged.

### AT-3.3: Continuous approach live benchmark (Pi FPS + overlay)
- **Description**: Verifies the planned **continuous approach** path (one `diagnose_approach_drop` per lap on the growing area series) is fast enough for real-time use on the Pi, and that approach-then-drop is visible **in the car** via HDMI overlay without offline analysis.
- **Test level**: Integration
- **Verification approach**: Demonstration + Test (Pi soak)
- **Reqs**: M-3.13, M-4.20 (approach detection path validation; informs edge port go/no-go)
- **Prerequisites**
  - TP-12 passed (camera + EdgeTPU inference loop stable)
  - Pi deployed in vehicle or bench with USB camera + HDMI display
  - Test entry point: `src/tests/integration/at_3_3/at_3_3_continuous_approach_live_benchmark.py`
  - Approach thresholds: `motion_area_1` config with `min_peak_pct = 0.25` (pf_02 / `ex_per_frame.xlsx` winner)
- **Steps**
  1. On the Pi, run `python src/tests/integration/at_3_3/at_3_3_continuous_approach_live_benchmark.py --duration-seconds 120 --show-window --write-status`.
  2. **Phase 1 (baseline):** confirm loop runs ~60s with capture + infer + area append only; note `loop_fps_baseline`.
  3. **Phase 2 (with approach):** confirm loop runs ~60s with `diagnose_approach_drop` each lap; note `loop_fps_approach`, `approach_ms_p95`, and `fps_delta_pct`.
  4. During phase 2, approach at least one real stop sign; confirm HDMI overlay shows **`APPROACH DETECTED @ t=…s`** and console prints the same event.
  5. After parking, review `logs/last_bench_status.json` or `logs/at_3_3_summary_*.json` without transferring footage for apartment analysis.
  6. *(Optional, dev machine)* `--replay-areas` on a `*.areas.json` file — logic sanity only, **not** a substitute for steps 1–5.
- **Pass criteria**
  - Both phases complete without crash or camera/TPU stall.
  - `fps_delta_pct` ≤ **33%** (baseline → with_approach; fail if loop FPS drops more than this).
  - `approach_ms_p95` ≤ **33 ms** at target lap rate.
  - `approach_detected` = **true** (at least one live approach during phase 2; overlay + log).
  - Evidence: `logs/at_3_3_summary_*.json` and optional photo of overlay.

### AT-3.4: Live approach + motion + classification bench (Pi)
- **Description**: Four keypress-started phases (~30s each) on the Pi: baseline drive with AT-3.3-style HUD (approach on, no motion), then three stop-sign maneuvers (complete stop, rolling stop, run-through) with per-frame approach detection, a **5s** post-drop motion window, sklearn two-stage kNN classification, and HDMI banners (blue = complete-stop, red = unsafe). Validates motion + classification path performance and in-car visibility before edge port.
- **Test level**: Integration
- **Verification approach**: Demonstration + Test (Pi soak)
- **Reqs**: M-3.13, M-4.20 (motion + classification path validation; informs edge port go/no-go)
- **Prerequisites**
  - AT-3.3 prerequisites (TP-12, Pi + camera + Coral + HDMI)
  - Laptop: `python src/tests/integration/at_3_4/prepare_at_3_4_config.py` (copies motion_area_2 training cache, bakes ap_050 literal configs, trains kNN joblib)
  - Pi: `scikit-learn`, `joblib`; `at_3_4/config/` present on device (sync joblibs from prep)
  - Test entry point: `src/tests/integration/at_3_4/at_3_4_live_motion_classification_benchmark.py`
  - Frozen config provenance: ap_050 / `ex_motion.xlsx` run `20260705T174249Z` (see `at_3_4/README.md`)
- **Steps**
  1. On a laptop, run `prepare_at_3_4_config.py`; sync `at_3_4/config/` to the Pi if needed.
  2. On the Pi, run `python src/tests/integration/at_3_4/at_3_4_live_motion_classification_benchmark.py --phase-seconds 30 --show-window --write-status`.
  3. **Phase 1:** press SPACE; drive normally ~30s; note baseline HUD `loop_fps`.
  4. **Phases 2–4:** press SPACE before each; perform **one** complete stop, rolling stop, and run-through at a stop sign (one maneuver per phase).
  5. Confirm green approach banner and blue/red classification banners during phases 2–4; banners clear 10s after classification. Each of phases 2–4 must produce **exactly one** approach + classification cycle (no duplicate re-arm or second classification in the same phase).
  6. After parking, review `logs/at_3_4_summary_*.json` and `run_data/<stamp>/events.jsonl`.
  7. Manually compare classification labels in `events.jsonl` to intended maneuver per phase.
- **Pass criteria**
  - All four phases complete without crash or camera/TPU stall.
  - Phases 2–4 each log **exactly one** `approach_detected` and **exactly one** `classification` event in `events.jsonl` (`approach_count` = `classification_count` = 1 per phase in summary JSON).
  - Classification completes within **≤ 10 seconds** from the moment the stop sign leaves the frame (approach detect / drop end ≈ sign exit; T₀ → classify_at_s in `events.jsonl` must be ≤ **10.0 s**; expected ~5 s motion window).
  - Motion-window **average** FPS loss ≤ **40%** vs phase-1 `baseline_fps` (uses `worst_motion_window_fps_avg` in summary JSON; per-lap min is diagnostic only).
  - Phases 2–4 `approach_ms_p95` ≤ **33 ms** (baseline phase excluded).
  - Evidence: `logs/at_3_4_summary_*.json`, `run_data/<stamp>/events.jsonl`, optional overlay photo.
  - Label correctness vs operator intent: **manual** (not an automated fail).

---

# Sprint 4 — Offline Operation and Local Persistence

*Tests: TP-29 to TP-31*
### TP-29: Local database schema validation
- **Description**: Verifies the local SQLite schema is structured correctly for event metadata storage (no upload-queue tables).
- **Test level**: Inspection
- **Verification approach**: Analysis
- **Reqs**: M-5.20
- **Prerequisites**
  - SQLite schema defined.
- **Steps**
  1. Review the SQLite schema for event-related tables.
  2. Confirm tables, keys, and required fields exist.
- **Pass criteria**
  - Schema is normalized to a reasonable level for the project.
  - Event tables contain required fields for local metadata (timestamp, event type, clip path/id, config reference as applicable).
  - No upload-queue / retry-status tables are required.

### TP-30: Local database write/read smoke test
- **Description**: Verifies the application can persist and retrieve dummy event records from SQLite.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-5.20
- **Prerequisites**
  - SQLite schema initialized.
- **Steps**
  1. Insert dummy event records into SQLite.
  2. Read the inserted records back.
- **Pass criteria**
  - Records are inserted successfully.
  - Retrieved values match what was written.

### TP-31: Event metadata local storage verification
- **Description**: Verifies unsafe stop-sign events are stored in SQLite with required metadata.
- **Test level**: Integration
- **Verification approach**: Demonstration + Inspection
- **Reqs**: M-3.21, M-5.20
- **Prerequisites**
  - Stop-sign detection and classification pipeline implemented.
  - Local SQLite database initialized.
- **Steps**
  1. Run the system and trigger a rolling-stop or run-through event.
  2. Query the most recent SQLite event row.
- **Pass criteria**
  - Event row exists in SQLite.
  - Row contains valid timestamp, event type, and clip identifier or path.
  - Row contains stop-sign-related metadata such as stop duration, minimum motion, and detection confidence.

---

# Sprint 5 — Cloud Foundations and Local Backend Setup

*Tests: TP-32 to TP-41*

> **Focus:** Provision S3 and Supabase from the laptop, prove FastAPI locally against SQLite (`/health`, `driving-session`, `driving-event`), boot Compose, confirm the backend can reach S3 and Supabase, then apply the metadata schema. Edge trip-segment persist to SQLite is TP-41. Integration against S3 upload URL + confirm is Sprint 6.

### TP-32: Private S3 bucket provisioning
- **Description**: Verifies a private AWS S3 bucket exists for NetraPi media.
- **Test level**: Integration
- **Verification approach**: Inspection + Test
- **Reqs**: M-6.20
- **Prerequisites**
  - AWS account access.
- **Steps**
  1. Create (or confirm) the project S3 bucket.
  2. Confirm public access is blocked.
  3. Confirm the edge device is not configured with permanent AWS credentials for this bucket.
- **Pass criteria**
  - Bucket exists and is private.
  - Block Public Access (or equivalent) is enabled.
  - Pi config does not store permanent cloud-storage credentials.

### TP-33: Supabase project and Postgres connectivity
- **Description**: Verifies the Supabase (Postgres) project exists and accepts connections from the development machine (admin / `psql` / SQL editor). This is not the FastAPI app connecting.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-8.10
- **Prerequisites**
  - Supabase project created.
  - Database URL / admin credentials available on the development machine (not the Pi).
- **Steps**
  1. From the development machine, connect using `DATABASE_URL` in `src/main/backend/.env` (`psql`, Supabase SQL editor, or the TP-33 harness).
  2. Run `SELECT 1`.
- **Pass criteria**
  - Connection succeeds from the development machine (not via the FastAPI app).
  - Query executes.
  - The Pi is not given a direct cloud Postgres connection string for metadata writes.

### TP-34: Local FastAPI smoke insert (`driving-session`)
- **Description**: Verifies a local FastAPI app (uvicorn, not Docker) can `POST /api/netrapi/driving-session` and insert one SQLite row. `driving_session` is the easiest operational insert: `master_config_id` (seeded) and `start_time`; no extra unique/check constraints. JSON only — no file body.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-7.11
- **Prerequisites**
  - Local SQLite schema and seed applied (Alembic `0001`–`0002`), including at least one `master_config` row.
  - FastAPI app runnable with uvicorn (Compose not required).
- **Steps**
  1. Start FastAPI locally with uvicorn.
  2. `POST /api/netrapi/driving-session` with a dummy JSON body (`master_config_id` from seed, `start_time`).
  3. Confirm the row via the API response and/or a SQLite query.
- **Pass criteria**
  - Endpoint returns success.
  - A `driving_session` row exists with the submitted fields.
  - Request has no file attachment.
  - This test does not require Docker, S3, or Supabase.

### TP-35: Local FastAPI health
- **Description**: Verifies `GET /health` on the local uvicorn app returns liveness and a UTC timestamp.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-7.10
- **Prerequisites**
  - FastAPI runnable with uvicorn (same app as TP-34).
- **Steps**
  1. Start FastAPI locally with uvicorn if it is not already running.
  2. `GET /health`.
- **Pass criteria**
  - Response succeeds.
  - Body includes a status (e.g. `ok`) and a UTC `time`.
  - This test does not require Docker, S3, or Supabase.

### TP-36: Local FastAPI smoke insert (`driving-event`)
- **Description**: Verifies `POST /api/netrapi/driving-event` on local uvicorn inserts one event plus nested children into SQLite (clip local flags, auto classification). JSON only — no file body. Session from TP-34 must exist.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-7.11
- **Prerequisites**
  - TP-34 passed.
  - Seeded `classification_type` rows (Alembic `0002`).
- **Steps**
  1. Start FastAPI locally with uvicorn.
  2. `POST /api/netrapi/driving-event` with one event JSON (`driving_session_id` from TP-34, `time`, nested `clip` without `s3_key` / `s3_stored`, nested auto classification).
  3. Query SQLite for the event and children.
- **Pass criteria**
  - Endpoint returns success.
  - `event` row and nested children exist; `s3_key` / `s3_stored` remain null.
  - Request has no file attachment.
  - This test does not require Docker, S3, or Supabase.

### TP-37: Local backend boots via Docker Compose
- **Description**: Verifies the local FastAPI backend starts from the repo’s local Docker / Compose setup.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-7.10
- **Prerequisites**
  - TP-35 passed.
  - `src/main/backend/Dockerfile` and `src/main/backend/compose.yml` present.
- **Steps**
  1. Build and start the local backend (`docker compose up` from `src/main/backend`, or equivalent).
  2. Hit the health endpoint or API root.
  3. Inspect container logs for clean startup.
- **Pass criteria**
  - Image builds and container starts without crash.
  - `GET /health` responds successfully.

### TP-38: Local backend can reach S3
- **Description**: Verifies the local backend process is configured with AWS credentials and can write a small test object to the private bucket.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-6.20, M-7.15
- **Prerequisites**
  - TP-32 and TP-37 passed.
  - Backend env has AWS credentials (server-side only).
- **Steps**
  1. From the local backend environment, upload a small test object using backend AWS settings (script; no extra HTTP route).
  2. Confirm the object appears in the bucket (HEAD), then delete the smoke object.
- **Pass criteria**
  - Upload from the backend environment succeeds.
  - Object appears at the expected key.

### TP-39: Local backend can reach Supabase
- **Description**: Verifies the local backend can open a Postgres session to Supabase using its configured credentials.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-7.12, M-8.10
- **Prerequisites**
  - TP-33 and TP-37 passed.
  - Backend DB URL configured in the backend env (not on the Pi).
- **Steps**
  1. From the local backend environment, load `DATABASE_URL` via backend Settings (not the Pi; not Compose test Postgres).
  2. Execute `SELECT 1` through app settings / SQLAlchemy.
- **Pass criteria**
  - Backend connects to Supabase successfully.
  - Query executes without error.

### TP-40: Cloud metadata schema deployment
- **Description**: Verifies the event-metadata schema is applied to Supabase Postgres from the running local backend.
- **Test level**: Integration
- **Verification approach**: Test + Inspection
- **Reqs**: M-8.10, M-8.11
- **Prerequisites**
  - Schema / migration scripts defined under `src/main/db/migrations/`.
  - TP-39 passed.
- **Steps**
  1. From the running local backend, apply migrations (Alembic or equivalent) against Supabase.
  2. Inspect tables and required columns (including S3 object path fields).
- **Pass criteria**
  - Expected tables and fields exist.
  - Schema can store event metadata plus an S3 object path.

### TP-41: Trip-segment local insert
- **Description**: Verifies full-session trip recording writes at least one `trip_segment` row with a local MP4 path after the loop stops.
- **Test level**: Integration
- **Verification approach**: Test + Inspection
- **Reqs**: M-5.20, M-3.21, M-4.11
- **Prerequisites**
  - Trip recorder implemented.
  - Local SQLite schema initialized.
- **Steps**
  1. Run the pipeline with full-session recording enabled (mocked camera; no events required).
  2. Stop the loop so the open segment is finalized.
  3. Query SQLite for `trip_segment`.
- **Pass criteria**
  - A `driving_session` row exists from loop start.
  - At least one `trip_segment` with `local_path` on disk, `order_number` set, `s3_key` / `s3_stored` null, and FK to that session.

---

# Sprint 6 — Local Backend Integrations (S3 + Supabase)

*Tests: TP-42 to TP-49*

> **Focus:** API-key auth on `/api/netrapi/*`, `POST /api/netrapi/driving-event` to Postgres, `POST /api/netrapi/s3-upload-url` + Pi PUT to S3, then `POST /api/netrapi/confirm-s3-upload`. JSON only on FastAPI — no file bodies. The edge client uses an API key plus a temporary S3 URL.

### TP-42: Edge API-key authentication
- **Description**: Verifies the local backend authenticates edge clients with an API key and rejects unauthenticated requests.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-7.10
- **Prerequisites**
  - API-key auth implemented (`X-API-Key` / `NETRAPI_API_KEY`).
- **Steps**
  1. `GET /health` without `X-API-Key` (must still succeed).
  2. `POST /api/netrapi/driving-session` without `X-API-Key`.
  3. Call the same route with an invalid `X-API-Key`.
  4. Call the same route with a valid `X-API-Key`.
- **Pass criteria**
  - Unauthenticated `/api/netrapi/*` write is rejected.
  - Authenticated request is accepted.
  - `GET /health` remains unauthenticated.

### TP-43: `s3-upload-url` issuance and edge PUT
- **Description**: Verifies `POST /api/netrapi/s3-upload-url` (JSON only) returns a time-limited S3 PUT URL and object key, and the **client** PUTs bytes to S3 — not to FastAPI. No file attachment on the API request.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-6.10, M-7.10, M-7.15
- **Prerequisites**
  - TP-38 and TP-42 passed.
  - A `clip` (or `trip_segment`) row in Postgres — use `POST /api/netrapi/driving-event` as setup if TP-45 has not run yet.
- **Steps**
  1. Authenticated `POST /api/netrapi/s3-upload-url` with JSON `{ "clip_id": ... }` (no file).
  2. Backend returns `url`, `object_key`, `method: PUT`.
  3. Client PUTs a small file to that S3 URL (not to FastAPI).
  4. Confirm the object exists at the returned key.
- **Pass criteria**
  - URL is issued only when authenticated.
  - FastAPI request body has no file.
  - PUT to S3 succeeds while the URL is valid.
  - Object lands at the backend-assigned key.
  - Client does not use permanent AWS credentials.
  - Postgres `s3_stored` is still false/null until confirm (TP-47).

### TP-44: Stable S3 object key generation
- **Description**: Verifies the backend assigns consistent, deterministic object keys.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-6.10, M-7.15, M-8.11
- **Prerequisites**
  - TP-43 path implemented.
- **Steps**
  1. `POST /api/netrapi/s3-upload-url` for multiple clip identities.
  2. Inspect assigned object keys.
- **Pass criteria**
  - Keys follow `{MMM-YYYY}/driving_session_id_{id}/clips|trips/{clip|trip}-{id}.mp4` (UTC English month from driving session `start_time`, session id, kind folder, clip/trip row id).
  - Keys are stable for a given event identity.
  - Durable references are object keys, not expiring signed URLs.

### TP-45: `driving-event` persist to Supabase
- **Description**: Verifies authenticated `POST /api/netrapi/driving-event` writes one event plus nested children to Postgres. JSON only — no file body. Cloud counterpart of TP-36.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-7.11, M-7.12, M-8.10
- **Prerequisites**
  - TP-39, TP-40, and TP-42 passed.
  - A `driving_session` row in Postgres (same shape as TP-34).
- **Steps**
  1. Authenticated `POST /api/netrapi/driving-event` with one event JSON (nested `clip` with `s3_key` / `s3_stored` omitted or null, auto classification).
  2. Query Postgres for the event and children.
- **Pass criteria**
  - Backend accepts the JSON (no file attachment).
  - Rows persist and match submitted fields.
  - `s3_key` / `s3_stored` remain null until TP-47.
  - Metadata does not bypass the backend (no Pi→Postgres direct write).

### TP-46: Private object access via signed GET
- **Description**: Ensures uploaded objects are not public and are reachable via backend-issued signed GET URLs.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-6.20, M-7.13
- **Prerequisites**
  - At least one object in the bucket (from TP-43).
  - Backend can mint signed GET URLs.
- **Steps**
  1. Attempt unsigned/public access to the object URL.
  2. Authenticated `POST /api/netrapi/s3-download-url` (`clip_id` or `trip_segment_id`) and GET the returned URL.
- **Pass criteria**
  - Unsigned access fails.
  - Signed access succeeds.

### TP-47: `confirm-s3-upload` links S3 object to Postgres
- **Description**: Verifies `POST /api/netrapi/confirm-s3-upload` (JSON only) sets `s3_key` / `s3_stored` after the edge PUT in TP-43.
- **Test level**: Integration
- **Verification approach**: Test + Inspection
- **Reqs**: M-7.12, M-8.11, M-8.12
- **Prerequisites**
  - TP-43 and TP-45 passed.
- **Steps**
  1. Complete TP-43 (JSON `s3-upload-url`, then client PUT to S3).
  2. Authenticated `POST /api/netrapi/confirm-s3-upload` with `clip_id` and `object_key` (no file).
  3. Confirm the Postgres row’s `s3_key` matches the object in S3.
  4. Optional: retrieve via path / signed GET (TP-46).
- **Pass criteria**
  - FastAPI request has no file attachment.
  - Metadata contains the correct S3 object key and `s3_stored` is true.
  - Key maps to a valid private object.

### TP-48: Presigned upload over hotspot/mobile data
- **Description**: Verifies an edge client can complete a backend-orchestrated upload over cellular/hotspot connectivity.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-6.10, M-7.10, M-7.15
- **Prerequisites**
  - TP-43 passed.
  - Backend reachable from the client network (local tunnel, LAN, or deployed preview if already available).
- **Steps**
  1. Connect the Pi (or laptop client) to hotspot/mobile data.
  2. Authenticate, `POST /api/netrapi/s3-upload-url` (JSON only), PUT a small file to the returned S3 URL, then `POST /api/netrapi/confirm-s3-upload`. Client uses `NETRAPI_API_URL` (not loopback) plus `X-API-Key`.
  3. Confirm the object in S3.
- **Pass criteria**
  - Upload succeeds over mobile/hotspot connectivity.
  - Temporary backend-issued URL was used (no permanent AWS keys on device).

### TP-49: Local end-to-end event persistence via backend
- **Description**: Verifies a local event (SQLite + clip) uploads one-at-a-time through the local backend into S3 and Postgres, then drains one primed trip segment the same way.
- **Test level**: System
- **Verification approach**: Demonstration + Test + Inspection
- **Reqs**: M-5.20, M-6.10, M-7.10, M-7.11, M-7.12, M-7.15, M-8.10, M-8.11
- **Prerequisites**
  - Sprint 4 local persistence available (TP-31).
  - TP-43 and TP-45 passed.
- **Steps**
  1. Create or trigger a local event with SQLite row + clip (`LocalStore` / capture loop), and a primed `trip_segment`.
  2. Edge `CloudIngest`: `driving-session` / `driving-event` JSON, clip `s3-upload-url`, PUT to S3, `confirm-s3-upload`.
  3. `drain_trip_segments` (Wi‑Fi job): trip `s3-upload-url` + PUT + confirm.
  4. Inspect S3, Postgres, and local SQLite clip/trip `s3_key` / `s3_stored` / `file_size_bytes`.
- **Pass criteria**
  - Single-event upload succeeds without an offline upload-queue state machine.
  - S3 clip object and Postgres row exist and reference each other.
  - Local SQLite clip `s3_key` / `s3_stored` match the confirmed object (Pi writes its own row; FastAPI never writes Pi SQLite).
  - `file_size_bytes` matches the uploaded clip and trip files on both SQLite and Postgres.
  - Postgres has kNN parameters, approach parameters, `event_trip_location`, and an `operational_exception` row for the harnessed event/session.
  - Local SQLite and Postgres `trip_segment.s3_key` / `s3_stored` match the drained trip object.
  - Edge device used no permanent AWS or Postgres credentials.

---

# Sprint 7 — Backend Deploy + Edge ↔ Deployed Backend E2E (No Frontend)

*Tests: TP-50 to TP-56; AT-7.1, AT-7.2, AT-7.3*

> **Focus:** Deploy the backend (Render), confirm API-key auth still holds on that host, then verify the already-built edge path against the deployed backend. E2E portion is verification only — no new edge/feature work. Do **not** require frontend UI; confirm cloud outcomes via Render API responses and local SQLite `s3_stored` / `s3_key` after `CloudIngest` confirm (optional live Postgres/S3 console check from a laptop). Deployed origin: [https://netrapi.onrender.com](https://netrapi.onrender.com) (override with `NETRAPI_API_URL` in `src/main/edge/.env`). Harnesses load **only** `src/main/edge/.env` — not `src/main/backend/.env` (Render already holds those secrets). Harnesses: `src/tests/integration/tp_50`–`tp_56`, plus Sprint 7 ad-hoc `at_7_1` / `at_7_2` / `at_7_3`. `GET /` is 404; liveness is `GET /health`.

### TP-50: Backend Docker image build
- **Description**: Verifies the backend Docker image builds and runs locally from the production Dockerfile.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-10.20, M-10.21
- **Prerequisites**
  - Backend Dockerfile implemented.
- **Steps**
  1. Build the backend image.
  2. Run a container from the image.
  3. `GET /health` (there is no `/` route).
- **Pass criteria**
  - Build succeeds.
  - Container stays up and `GET /health` returns `{"status":"ok",...}`.

### TP-51: Backend deployment to hosting environment
- **Description**: Verifies the backend deploys successfully to the target host (e.g., Render).
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-10.21, M-10.22, M-10.23
- **Prerequisites**
  - Deployment target configured.
  - TP-50 passed.
- **Steps**
  1. Trigger a backend deployment.
  2. Observe deployment completion.
  3. `GET https://netrapi.onrender.com/health` (or `NETRAPI_API_URL` from `src/main/edge/.env`).
- **Pass criteria**
  - Deployment completes successfully.
  - Deployed backend is reachable (`/health` 200).
  - Render health-check path is `/health` (failed health is not a successful deploy).

### TP-52: Deployed backend API-key authentication
- **Description**: Verifies the deployed backend authenticates edge clients with an API key, rejects unauthenticated requests, and still accepts a valid key (same contract as local TP-42).
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-7.10
- **Prerequisites**
  - TP-51 passed (deployed backend reachable).
  - API-key auth already proven against the local backend (TP-42).
  - `src/main/edge/.env` has `NETRAPI_API_KEY` matching Render (optional `NETRAPI_API_URL`).
- **Steps**
  1. `POST /api/netrapi/driving-event` on the deployed backend without an API key.
  2. Call the same route with an invalid `X-API-Key`.
  3. `POST /api/netrapi/driving-session` then `POST /api/netrapi/driving-event` with a valid `X-API-Key`.
- **Pass criteria**
  - Missing-key and invalid-key requests are rejected (401).
  - Authenticated request is accepted.
  - `GET /health` remains unauthenticated.
  - Deployed auth behavior matches the local backend; the public API is not left open.

### TP-53: Unsafe event to cloud via deployed backend
- **Description**: Verifies an unsafe stop-sign event is detected on the edge, alerts locally, and uploads through the deployed backend to S3 + Postgres.
- **Test level**: System
- **Verification approach**: Test + Demonstration
- **Reqs**: M-3.10, M-5.20, M-6.10, M-7.10, M-7.11, M-7.12, M-7.15
- **Prerequisites**
  - Edge runtime operational (existing bring-up; no new edge features in this sprint).
  - Deployed backend upload path operational (TP-50–52).
  - `src/main/edge/.env` pointed at Render.
  - Speaker/buzzer connected.
- **Steps**
  1. Run the edge harness / system pointed at the deployed backend (`src/main/edge/.env` only).
  2. Trigger an unsafe stop-sign event (harness seeds LocalStore + CloudIngest, or live capture).
  3. Observe local alert + SQLite/clip.
  4. Confirm upload via local SQLite `s3_stored` / `s3_key` after Render confirm (optional Postgres/S3 console on a laptop).
- **Pass criteria**
  - Unsafe event detected; buzzer activates (live path) or harness completes CloudIngest.
  - Local clip + SQLite row exist.
  - Clip/trip marked `s3_stored` with keys after backend-orchestrated confirm.

### TP-54: Cross-layer metadata consistency
- **Description**: Verifies event identity and fields stay consistent across the TP-53 SQLite artifact (session / event / clip / trip / `s3_key`) after a successful CloudIngest confirm (no frontend; no backend `.env` on the Pi).
- **Test level**: System
- **Verification approach**: Inspection + Test
- **Reqs**: M-5.20, M-7.12, M-8.11
- **Prerequisites**
  - At least one completed edge→cloud event (TP-53).
- **Steps**
  1. Inspect the TP-53 local SQLite row (event, clip, trip, `event_trip_location`).
  2. Confirm `s3_stored`, keys, and sizes are present and internally consistent.
  3. Optional: inspect Postgres/S3 from a laptop (AT-7.1 README).
- **Pass criteria**
  - Identifiers and key fields match across the local event graph.
  - Clip and trip references point at distinct confirmed object keys.

### TP-55: Restart recovery then upload
- **Description**: Verifies local event data survives an edge restart and can upload later via the deployed backend.
- **Test level**: System
- **Verification approach**: Test
- **Reqs**: M-5.20, M-6.10, M-7.15
- **Prerequisites**
  - Edge runtime and upload path already implemented (no new runtime work in this sprint).
  - `src/main/edge/.env` pointed at Render.
- **Steps**
  1. Trigger an event so local clip + SQLite row exist.
  2. Restart the edge process/device before upload completes.
  3. Confirm local data survives.
  4. When online, complete backend-orchestrated upload; confirm via local `s3_stored` / `s3_key`.
- **Pass criteria**
  - Local clip and metadata are preserved across restart.
  - Upload succeeds afterward; local SQLite reflects confirmed S3 keys.

### TP-56: Deployed system smoke (API/cloud evidence)
- **Description**: Verifies a minimal real-world flow from detection through deployed-backend upload, confirmed without a frontend.
- **Test level**: System
- **Verification approach**: Demonstration
- **Reqs**: M-10.21, M-10.22, M-6.10
- **Prerequisites**
  - Fully deployed backend.
  - `src/main/edge/.env` pointed at Render.
  - Speaker/buzzer connected.
- **Steps**
  1. Trigger one unsafe event (harness or live).
  2. Allow process + upload via deployed backend.
  3. Confirm success via `/health` + local SQLite `s3_stored` / `s3_key` after CloudIngest.
- **Pass criteria**
  - Buzzer activates on detection (live path) or harness completes CloudIngest.
  - Pipeline completes without manual cloud console surgery.
  - Event is confirmed locally after backend upload (optional Postgres/S3 console).

## Sprint 7 ad-hoc tests (non-TP)

### AT-7.1: Mocked Pi pipeline to deployed cloud
- **Description**: Verifies the **real** edge pipeline (`build_pipeline` → `RecordingManager.run_loop` → `LocalStore` persist → `CloudIngest`) can upload one unsafe event through Render to S3 + Postgres when the camera and EventManager are mocked. Unlike TP-53/TP-56, this does **not** seed rows or call ingest APIs from the harness.
- **Test level**: System
- **Verification approach**: Test + Inspection
- **Reqs**: M-5.20, M-6.10, M-7.11, M-7.12, M-7.15
- **Prerequisites**
  - TP-51 / TP-52 passed (Render `/health` + API key).
  - TP-27 / TP-31 path proven (stubbed event through `RecordingManager`).
  - Pi edge venv; Coral USB TPU; buzzer on BCM 18; `src/main/edge/.env` has SQLite `DATABASE_URL` plus `NETRAPI_API_URL` / `NETRAPI_API_KEY` for Render.
  - No USB camera required (harness mocks the camera).
  - Test entry point: `src/tests/integration/at_7_1/at_7_1_mocked_pipeline_deployed_cloud.py`
- **Steps**
  1. On the Pi, run `python src/tests/integration/at_7_1/at_7_1_mocked_pipeline_deployed_cloud.py`.
  2. Confirm the script builds `build_pipeline`, stubs camera + EventManager, and lets `run_loop` persist + ingest a stubbed **rolling-stop**.
  3. Confirm local SQLite clip `s3_stored` is true (printed event id / `s3_key`).
  4. From the laptop, inspect Postgres and S3 with the README `python -c` commands; check Render logs for `driving-session`, `driving-event`, `s3-upload-url`, `confirm-s3-upload`.
- **Pass criteria**
  - Harness does not insert events or call FastAPI except through `RecordingManager` / `CloudIngest`.
  - SQLite has the event + clip; clip `s3_stored` is true and `s3_key` is set.
  - Matching Postgres row and S3 object exist.
  - Render logs show the ingest POSTs (not only `/health` probes).

### AT-7.2: Camera + SPACE + stubbed events to deployed cloud
- **Description**: Dry-run before live AT-7.3. Same three SPACE-armed phases as TP-28 / AT-7.3 (complete stop → rolling stop → run-through) with **real camera + preview**, but EventManager is **stubbed** so SPACE injects the intended event. Persist and upload still go through `RecordingManager` / `LocalStore` / `CloudIngest`.
- **Test level**: System
- **Verification approach**: Demonstration + Test
- **Reqs**: M-3.13, M-5.20, M-6.10, M-7.11, M-7.12, M-7.15
- **Prerequisites**
  - AT-7.1 passed (mocked persist + ingest through the real pipeline).
  - TP-27 / TP-28 path familiar (SPACE arming + buzzer/clip gating).
  - Pi + camera + Coral + buzzer; `src/main/edge/.env` pointed at Render.
  - Test entry point: `src/tests/integration/at_7_2/at_7_2_camera_stubbed_events_deployed_cloud.py`
- **Steps**
  1. On the Pi (parked / driveway is fine), run `python src/tests/integration/at_7_2/at_7_2_camera_stubbed_events_deployed_cloud.py`.
  2. Click preview for focus. For each phase, press **SPACE**; the stub fires complete stop, then rolling stop, then run-through.
  3. Confirm beep + clip for unsafe phases only; complete stop has neither (metadata still persists).
  4. Confirm three SQLite event rows (complete-stop + two unsafe); unsafe clips have `s3_stored` true.
- **Pass criteria**
  - Preview runs; SPACE arms each phase; stub injects the intended event type.
  - Beep + clip for rolling stop and run-through only (`play_on.safe=false`, `record_safe_events=false`).
  - Complete stop has **no** clip; event metadata **is** persisted (local + cloud JSON, no S3).
  - Rolling-stop and run-through rows exist in harness SQLite with `s3_stored` true and `s3_key` set.

### AT-7.3: In-car three-maneuver E2E to deployed cloud
- **Description**: Full in-vehicle E2E on the **fully integrated** edge pipeline (real camera, Detector, EventManager, Buzzer, Recorder, LocalStore, CloudIngest): one complete stop, one rolling stop, and one run-through, then confirm unsafe events in SQLite, S3, Postgres, and Render logs. Same SPACE-armed phases as TP-28; cloud path is the production ingest, not a seed harness.
- **Test level**: System
- **Verification approach**: Demonstration + Test + Inspection
- **Reqs**: M-3.13, M-3.20, M-3.30, M-3.31, M-5.20, M-6.10, M-7.11, M-7.12, M-7.15
- **Prerequisites**
  - AT-7.2 passed (camera + SPACE + stubbed-events dry-run through the real pipeline).
  - TP-28 passed (in-car classify + beep + clip).
  - TP-51 / TP-52 passed.
  - Pi + camera + Coral + buzzer installed in the car; `src/main/edge/.env` pointed at Render.
  - Test entry point: `src/tests/integration/at_7_3/at_7_3_incar_e2e_deployed_cloud.py`
- **Steps**
  1. Mount and power the system; clips land under `clips_dir/at_7_3/`. Local SQLite is the Pi file (`src/main/db/netrapi.db`).
  2. On the Pi, run `python src/tests/integration/at_7_3/at_7_3_incar_e2e_deployed_cloud.py`.
  3. For each phase, focus preview and press **SPACE**, then perform **complete stop**, **rolling stop**, and **run-through** in that order. Classifications before SPACE are ignored.
  4. Confirm console labels, beep on unsafe only, clips for unsafe only.
  5. Confirm three SQLite event rows; unsafe clips have `s3_stored` true. Inspect Postgres + S3 with the README `python -c` commands; check Render logs.
- **Pass criteria**
  - All three encounters complete without crash.
  - Classification matches operator intent; beep + clip for rolling stop and run-through only (`play_on.safe=false`, `record_safe_events=false`).
  - Complete stop has **no** clip; event metadata **is** persisted (local + cloud JSON, no S3).
  - Rolling-stop and run-through rows exist in Pi SQLite and Postgres with matching `s3_key`; S3 objects exist; Render logs show ingest POSTs for those events.

---

## 8. Coverage Notes
This plan currently covers through **Sprint 7** (edge + local persistence + backend-orchestrated cloud path + deploy + deployed E2E). Deferred for later test generation:
- frontend / portfolio UI tests
- full CI/CD matrix beyond backend deploy health
- 10-hour collection and model-evaluation publication tests
- dedicated edge managed-service (systemd) verification for M-10.10
- dedicated offline capture/detection verification for M-5.10

Covered now:
- constraints and edge bring-up (earlier sprints)
- offline SQLite event metadata (TP-31) and trip-segment local persist (TP-41)
- S3 + Supabase provisioning, local FastAPI ingest smokes (`/health`, `driving-session`, `driving-event`), Compose boot, backend reachability, then schema from the backend
- local backend S3/Postgres integrations (`s3-upload-url` + edge PUT + `confirm-s3-upload` + `driving-event`)
- backend deployment and deployed API-key authentication
- edge ↔ deployed backend E2E (no frontend; verification only)
- Sprint 7 harnesses under `src/tests/integration/tp_50`–`tp_56` against https://netrapi.onrender.com
- Sprint 7 ad-hoc: mocked pipeline (AT-7.1), camera + SPACE + stubbed events (AT-7.2), in-car live three-maneuver cloud E2E (AT-7.3)

**TP range:** TP-01 through TP-56. **Ad-hoc:** AT-7.1, AT-7.2, AT-7.3 (Sprint 7).
