# NetraPi Test Plan (Updated for Full MVS Coverage)

## 1. Purpose
Verify that NetraPi satisfies the full MVS through staged, repeatable tests across the edge device, local persistence layer, cloud storage, backend API, database, frontend, and deployment pipeline.

## 2. How to Use This Plan
This document is ordered by **implementation phase**, not just by subsystem. Earlier tests should be executable before later layers exist.

Each test includes:
- **Reqs**: the requirement IDs covered
- **Prerequisites**: what must already be implemented before the test is valid
- **Pass criteria**: what counts as success

## 3. System Definitions
- **Edge runtime**: Raspberry Pi 5, Coral USB TPU, camera, local scripts/services, local file storage, and local SQLite database
- **Cloud storage**: private AWS S3 bucket used for baseline footage and event clips
- **Backend API**: deployed cloud API that authenticates the edge device, stores metadata in Postgres, and returns signed URLs
- **Database**: cloud-hosted PostgreSQL storing structured metadata and S3 paths, local SQLite db running on pi for immediate storage and cloud upload safety
- **Frontend / UI**: deployed React web app / interactive portfolio used to browse events, view metrics, filter data, view playback, and review project documentation
- **Processing job**: batch or offline logic that computes baseline/post-baseline metrics from stored footage/events
- **Collection phase**: either **baseline** or **post-baseline**

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

---

# Phase 1 — Constraints and Physical Configuration

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
- **Reqs**:
- **Prerequisites**
  - Equipment purchased: Pi, camera, compatible ribbon cable
  - OS loaded on Pi
- **Steps**
  1. Connect the Pi camera to the Raspberry Pi.
  2. Open a terminal on the Pi.
  3. Run `rpicam-hello --list-cameras` and confirm the camera is detected.
  4. Run `libcamera-hello` and observe the temporary preview.
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
  - The internal temperature of the Pi never exceeds 185 °F.
  - The average internal temperature of the Pi across the 3 hours is below 180 °F.

---
# Phase 2 — Edge Capture, Buffering, and Local ML

### TP-10: Coral TPU smoke test
- **Description**: Verifies the Coral USB TPU is detected and usable on the Raspberry Pi.
- **Test level**: Integration
- **Verification approach**: Inspection
- **Reqs**:
- **Prerequisites**
  - Pi, Coral USB TPU, and required cables connected
  - OS and Python installed
- **Steps**
  1. Update system and install Edge TPU runtime:
     ```
     sudo apt update
     sudo apt install libedgetpu1-std
     ```
  2. Verify Python installation: `python3 --version`
  3. Run `lsusb` and confirm Coral device appears.
  4. Run a minimal interpreter script to load the TPU delegate.
- **Pass criteria**
  - Coral appears in `lsusb` (e.g., "Global Unichip Corp.")
  - Delegate loads successfully without errors.

### TP-11: AI inference smoke test (camera + TPU)
- **Description**: Verifies real-time inference runs on live camera feed with object detection output.
- **Test level**: Integration
- **Verification approach**: Demonstration
- **Reqs**:
- **Prerequisites**
  - TPU smoke test passed
  - Camera smoke test passed (Phase 1)
- **Steps**
  1. Run a Coral-compatible detection script with live camera feed.
  2. Observe bounding boxes and classification output.
  3. Point camera at 2 common objects and observe confidence.
  4. Move camera quickly and observe recovery latency.
- **Pass criteria**
  - Live feed displays bounding boxes.
  - Objects detected with ≥70% confidence.
  - Latency for visual update ≤ 3 seconds.

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
- **Description**: Verifies resolution, frame rate, and buffer duration are configurable and applied correctly.
- **Test level**: Integration
- **Verification approach**: Test + Inspection
- **Reqs**: M-2.14
- **Prerequisites**
  - Configurable capture settings implemented
- **Steps**
  1. Set known config values (resolution, FPS, buffer duration).
  2. Start capture.
  3. Inspect logs and output behavior.
- **Pass criteria**
  - System uses configured values correctly.

### TP-14: Rolling buffer and event clip extraction verification
- **Description**: Verifies rolling buffer and event-triggered clip generation produce correct pre/post coverage.
- **Test level**: Integration  
- **Verification approach**: Test  
- **Reqs**: M-2.13, M-3.20  

- **Prerequisites**
  - Rolling buffer implemented
  - Event trigger implemented
  - Post-event recording configured

- **Steps**
  1. Set buffer duration to 10 seconds.
  2. Trigger multiple events (≥5).
  3. Extract generated clips.
  4. Measure duration and inspect content.

- **Pass criteria**
  - Each clip contains:
    - ~5–10 seconds pre-event footage
    - Event moment
    - ~5–10 seconds post-event footage
  - Total duration is ~10–20 seconds.
  - Video is continuous and playable.
  - No missing frames or abrupt cuts.

### TP-15: Unsafe-event detection minimum capability
- **Description**: Verifies the system detects at least one unsafe event class.
- **Test level**: Integration
- **Verification approach**: Demonstration + Test
- **Reqs**: M-3.13
- **Prerequisites**
  - At least one detection rule/model implemented
- **Steps**
  1. Trigger or simulate an unsafe event.
  2. Observe detection output/logs.
- **Pass criteria**
  - System correctly identifies at least one unsafe-event class.

### TP-16: Speaker module feedback verification
- **Description**: Verifies the speaker module produces audible feedback suitable for in-vehicle use.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**:
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

# Phase 3 - Unsafe Event Detection
### TP-17: Stop sign detection trigger activation
- **Description**: Verifies the system enters stop-sign monitoring mode only after a valid stop sign detection is observed.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-4.10
- **Prerequisites**
  - Object detection pipeline operational.
  - Stop-sign trigger logic implemented.
- **Steps**
  1. Run the system on footage containing an approaching stop sign.
  2. Observe detection outputs and system state transitions.
  3. Repeat with footage that contains no stop sign.
- **Pass criteria**
  - The system enters stop-sign monitoring mode only when a stop sign is detected above the configured threshold.
  - The system remains in idle mode when no stop sign is present.

### TP-18: Stop sign persistence filtering
- **Description**: Verifies a stop sign must persist across multiple frames before the system treats it as a valid encounter.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-4.11
- **Prerequisites**
  - Stop-sign persistence logic implemented.
- **Steps**
  1. Run the system on footage where a stop sign appears briefly for fewer frames than the required persistence threshold.
  2. Run the system on footage where a stop sign remains visible for at least the required number of frames.
- **Pass criteria**
  - Brief or spurious detections do not activate a stop-sign encounter.
  - Persistent detections activate a stop-sign encounter.

### TP-19: Stop sign region-of-interest filtering
- **Description**: Verifies only stop signs appearing in the defined driving-path region of interest are considered relevant.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-4.12
- **Prerequisites**
  - Region-of-interest filtering implemented.
- **Steps**
  1. Run the system on footage with a stop sign positioned within the configured valid region.
  2. Run the system on footage with a stop sign positioned outside the configured valid region.
- **Pass criteria**
  - Stop signs inside the valid region are eligible to start an encounter.
  - Stop signs outside the valid region are ignored.

### TP-20: Stop sign approach validation by size or growth
- **Description**: Verifies the system treats a stop sign as relevant only when its apparent size or growth indicates approach toward the intersection.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-4.13
- **Prerequisites**
  - Bounding-box growth or minimum-size logic implemented.
- **Steps**
  1. Run the system on footage where a stop sign grows in apparent size as the vehicle approaches.
  2. Run the system on footage where a distant or irrelevant stop sign remains small or does not grow meaningfully.
- **Pass criteria**
  - Approaching stop signs satisfy encounter criteria.
  - Distant or non-approaching stop signs do not satisfy encounter criteria.

### TP-21: Motion-score computation during stop-sign encounter
- **Description**: Verifies the system computes and records a motion score while a stop-sign encounter is active.
- **Test level**: Integration
- **Verification approach**: Demonstration
- **Reqs**: M-4.20
- **Prerequisites**
  - Motion-estimation logic implemented.
  - Stop-sign encounter state implemented.
- **Steps**
  1. Run the system on footage containing a stop-sign approach.
  2. Observe motion-score output during the encounter window.
- **Pass criteria**
  - Motion scores are produced and updated throughout the active encounter.
  - Motion-score values are logged or otherwise observable for review.

### TP-22: Near-zero motion detection
- **Description**: Verifies the system identifies a near-stop condition when motion remains below the configured stop threshold.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-4.21
- **Prerequisites**
  - Motion threshold logic implemented.
- **Steps**
  1. Run the system on footage where the vehicle comes to a clear stop at a stop sign.
  2. Observe the computed motion score and stop-duration tracking.
- **Pass criteria**
  - The system detects motion below the stop threshold.
  - The low-motion interval is accumulated as stop duration.

### TP-23: Adequate stop-duration verification
- **Description**: Verifies the system classifies an encounter as compliant when low motion is sustained for at least the required minimum duration.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-4.22
- **Prerequisites**
  - Stop-duration threshold logic implemented.
- **Steps**
  1. Run the system on footage where the vehicle stops at the stop sign for at least the configured minimum duration.
  2. Allow the stop-sign encounter to complete.
- **Pass criteria**
  - The encounter is classified as an adequate stop.
  - No unsafe stop-sign event is generated.

### TP-24: Rolling-stop classification
- **Description**: Verifies the system classifies an encounter as a rolling stop when the vehicle slows but does not remain below the stop threshold long enough.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-4.23
- **Prerequisites**
  - Rolling-stop classification logic implemented.
- **Steps**
  1. Run the system on footage where the vehicle slows at the stop sign but does not fully stop for the required duration.
  2. Allow the encounter to complete.
- **Pass criteria**
  - The encounter is classified as a rolling stop.
  - An unsafe event is generated.

### TP-25: Stop-sign bypass classification
- **Description**: Verifies the system classifies an encounter as a stop-sign bypass when the vehicle does not meaningfully slow while passing the sign.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-4.24
- **Prerequisites**
  - Bypass classification logic implemented.
- **Steps**
  1. Run the system on footage where the vehicle passes a relevant stop sign without adequately slowing.
  2. Allow the encounter to complete.
- **Pass criteria**
  - The encounter is classified as a stop-sign bypass.
  - An unsafe event is generated.

### TP-26: Unsafe event clip extraction for stop-sign violation
- **Description**: Verifies the system saves the appropriate video evidence clip when an unsafe stop-sign event is detected.
- **Test level**: Integration
- **Verification approach**: Demonstration
- **Reqs**: M-4.31, M-2.13
- **Prerequisites**
  - Clip extraction implemented.
  - Unsafe event trigger implemented.
- **Steps**
  1. Trigger a rolling-stop or stop-sign bypass event.
  2. Inspect the saved clip.
- **Pass criteria**
  - A clip is saved for the unsafe event.
  - The clip contains the relevant stop-sign encounter footage.

### TP-27: Audible feedback on unsafe stop-sign event
- **Description**: Verifies the system emits audible feedback when a rolling stop or stop-sign bypass event is detected.
- **Test level**: System
- **Verification approach**: Demonstration
- **Reqs**: M-4.32
- **Prerequisites**
  - Audible feedback mechanism implemented.
- **Steps**
  1. Trigger a rolling-stop event.
  2. Trigger a stop-sign bypass event.
- **Pass criteria**
  - Audible feedback is produced for each unsafe event type.
  - Feedback occurs within the configured response window.

### TP-28: No false unsafe event for compliant stop
- **Description**: Verifies the system does not generate a stop-sign violation event when the driver performs an adequate stop.
- **Test level**: System
- **Verification approach**: Test
- **Reqs**: M-4.22, M-4.33
- **Prerequisites**
  - Full stop-sign detection and classification pipeline operational.
- **Steps**
  1. Run the system on footage containing a clearly compliant stop at a relevant stop sign.
  2. Review event outputs and logs.
- **Pass criteria**
  - No rolling-stop or bypass event is generated.
  - Encounter is recorded as compliant or ignored without error.

### TP-29: False-positive resistance for irrelevant stop sign
- **Description**: Verifies the system does not generate an unsafe event for a stop sign that is visible but not relevant to the vehicle’s path.
- **Test level**: System
- **Verification approach**: Test
- **Reqs**: M-4.12, M-4.13, M-4.33
- **Prerequisites**
  - Region-of-interest and relevance filtering implemented.
- **Steps**
  1. Run the system on footage where a stop sign is visible off to the side or otherwise not applicable to the vehicle path.
  2. Review encounter and event outputs.
- **Pass criteria**
  - The stop sign does not trigger an unsafe-event classification.
  - No irrelevant stop-sign violation event is logged.

### TP-30: Audible feedback timing
- **Description**: Ensures audible feedback is delivered in response to unsafe-event detection within timing constraints.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-3.30, M-3.31
- **Prerequisites**
  - Audible feedback implemented.
  - Event detection trigger available.
- **Steps**
  1. Trigger unsafe events.
  2. Record event time and audible feedback time.
- **Pass criteria**
  - Audible feedback occurs.
  - Feedback occurs within 10 seconds of the detected event.

### TP-31: Stop-sign Beep Test
- **Description**: Verifies speaker will integrate with ai inference detection by driving past stop sign, having stop sign be recognized, and then activating the speaker.
- **Test level**: Integration
- **Verification approach**: Demonstration + Test
- **Reqs**: 
- **Prerequisites**
  - camera smoke test pass
  - 3 hour memory + endurance test pass
  - speaker smoke test pass
  - tpu inference smoke test pass
- **Steps**
  1. Setup system in car (raspberry pi secured and powered on, camera mounted, tpu plugged in)
  2. Run script that records the experience until 3 beeps occurs (and waits 10 seconds afterwards)
  3. Start recording audio on phone immediately after running script
  3. Drive past three different stop signs and listen for speaker activation
- **Pass criteria**
  - Speaker activates three times for 1.5 seconds each time
  - Exactly three different stop signs are approached

---

# Phase 4 — Offline-First Operation and Local Persistence
### TP-32: Local database schema validation
- **Description**: Verifies the local SQLite schema is structured correctly for event storage and queued uploads.
- **Test level**: Inspection
- **Verification approach**: Analysis
- **Reqs**: M-5.20, M-5.21
- **Prerequisites**
  - SQLite schema defined.
- **Steps**
  1. Review the SQLite schema for event and queue-related tables.
  2. Confirm tables, keys, and required fields exist.
- **Pass criteria**
  - Schema is normalized to a reasonable level for the project.
  - Event and queue tables contain all required fields for local persistence and upload tracking.

### TP-33: Local database write/read smoke test
- **Description**: Verifies the application can persist and retrieve dummy records from SQLite.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-5.20
- **Prerequisites**
  - SQLite schema initialized.
- **Steps**
  1. Insert dummy event and queue records into SQLite.
  2. Read the inserted records back.
- **Pass criteria**
  - Records are inserted successfully.
  - Retrieved values match what was written.

### TP-34: SQLite availability and connection verification
- **Description**: Verifies the application can successfully connect to the SQLite database file before performing any storage operations.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-5.20
- **Prerequisites**
  - SQLite database path configured.
  - Database initialization script already executed (TP-62 or TP-63 depending on flow).
- **Steps**
  1. Start the application or a small test script.
  2. Attempt to open a connection to the SQLite database file.
  3. Execute a simple query (e.g., `SELECT 1` or query a known table).
- **Pass criteria**
  - Database connection is successfully established.
  - Query executes without error.
  - Application confirms database is ready before continuing.

### TP-35: Event metadata local storage verification
- **Description**: Verifies unsafe stop-sign events are stored in SQLite with required metadata.
- **Test level**: Integration
- **Verification approach**: Demonstration + Inspection
- **Reqs**: M-4.30, M-5.20
- **Prerequisites**
  - Stop-sign detection and classification pipeline implemented.
  - Local SQLite database initialized.
- **Steps**
  1. Run the system and trigger a rolling-stop or stop-sign bypass event.
  2. Query the most recent SQLite event row.
- **Pass criteria**
  - Event row exists in SQLite.
  - Row contains valid timestamp, event type, and clip identifier or path.
  - Row contains stop-sign-related metadata such as stop duration, minimum motion, and detection confidence.

### TP-36: Queue record creation verification
- **Description**: Verifies that when an uploadable event is stored locally, a corresponding queued-upload record is created.
- **Test level**: Integration
- **Verification approach**: Test + Inspection
- **Reqs**: M-5.20, M-5.21
- **Prerequisites**
  - Local event storage implemented.
  - Queue table implemented.
- **Steps**
  1. Trigger an event that produces a saved clip and local metadata record.
  2. Inspect SQLite for the corresponding queue row.
- **Pass criteria**
  - A queue row is created for the stored event.
  - Queue row references the correct clip or event record.
  - Initial upload state is set correctly (for example: pending).

### TP-37: Queue schema completeness verification
- **Description**: Verifies queued-upload records contain all required fields for upload tracking and retry handling.
- **Test level**: Integration
- **Verification approach**: Inspection
- **Reqs**: M-5.20, M-5.21
- **Prerequisites**
  - Queue record creation implemented.
- **Steps**
  1. Trigger an event that creates a queued-upload row.
  2. Inspect the queued row in SQLite.
- **Pass criteria**
  - Queue row includes clip identifier or event reference, local file path, upload status, retry count, and timestamps.

### TP-38: Offline queue retention verification
- **Description**: Verifies queued uploads remain stored locally when network connectivity is unavailable.
- **Test level**: Integration
- **Verification approach**: Demonstration + Inspection
- **Reqs**: M-5.10, M-5.21
- **Prerequisites**
  - Queue creation implemented.
  - Upload attempt logic implemented.
- **Steps**
  1. Disable network connectivity.
  2. Trigger an uploadable event.
  3. Inspect the queue record after the upload attempt window.
- **Pass criteria**
  - Capture and detection continue offline.
  - Queue row remains stored locally.
  - Upload is not marked as successful.
  - No queued data is lost.

### TP-39: Single queued upload processing verification
- **Description**: Verifies the upload processor can successfully process one pending queued-upload record when connectivity is available.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-5.21
- **Prerequisites**
  - Queue processor implemented.
  - One valid pending queue record exists.
  - Connectivity available.
- **Steps**
  1. Insert or create one valid pending queue record.
  2. Start the upload processor.
  3. Observe upload result and resulting queue state.
- **Pass criteria**
  - Pending record is processed.
  - Upload succeeds.
  - Queue status updates correctly after success.

### TP-40: Queue retry/status update verification
- **Description**: Verifies failed upload attempts update queue status and retry metadata correctly.
- **Test level**: Integration
- **Verification approach**: Test + Inspection
- **Reqs**: M-5.21
- **Prerequisites**
  - Queue processor implemented.
  - Retry/status fields implemented.
- **Steps**
  1. Force an upload failure for a pending queued record.
  2. Inspect the row after the failed attempt.
- **Pass criteria**
  - Queue record remains available for future retry.
  - Retry count or failure metadata updates correctly.
  - Record is not falsely marked as uploaded.

### TP-41: Offline capture and detection verification
- **Description**: Verifies capture and event detection continue without network connectivity.
- **Test level**: Integration
- **Verification approach**: Demonstration
- **Reqs**: M-5.10
- **Prerequisites**
  - Capture and detection pipeline operational.
- **Steps**
  1. Disable network connectivity.
  2. Run the system and manually trigger an event.
- **Pass criteria**
  - Video capture and detection continue offline.

### TP-42: Queue upload on connectivity restoration verification
- **Description**: Verifies pending queued uploads are successfully processed after network connectivity returns.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-5.21, M-5.22
- **Prerequisites**
  - Pending queued uploads exist.
  - Upload processor implemented.
- **Steps**
  1. Disable network connectivity and create one or more queued uploads.
  2. Restore connectivity.
  3. Start or observe the queue processor.
- **Pass criteria**
  - Previously pending uploads are processed after connectivity returns.
  - Queue state updates correctly.
  - No duplicate or corrupted uploads are observed.

### TP-43: Queue reload and automatic resume after restart
- **Description**: Confirms queued records reload from SQLite and uploads resume automatically after restart.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-5.22, M-10.21, M-10.22
- **Prerequisites**
  - SQLite queue implemented.
  - Resume logic implemented.
- **Steps**
  1. Create queued uploads while offline.
  2. Restart the system.
  3. Restore connectivity.
- **Pass criteria**
  - Queue records are reloaded from SQLite after restart.
  - Pending uploads resume automatically.
  - No data corruption is observed.
---

# Phase 5 — Cloud Upload and Cloud Persistence
### TP-44: S3 bucket connectivity and upload smoke test
- **Description**: Verifies the Raspberry Pi can authenticate with AWS and upload a file to the S3 bucket.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-6.10
- **Prerequisites**
  - S3 bucket created.
  - AWS credentials configured on Pi.
- **Steps**
  1. Connect Pi to internet.
  2. Upload a small test file.
  3. Verify file appears in bucket.
- **Pass criteria**
  - Upload succeeds.
  - File appears at expected path.

### TP-45: Direct-to-cloud upload over hotspot/mobile data
- **Description**: Verifies uploads work over cellular/hotspot connection.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-6.10
- **Prerequisites**
  - TP-44 passed.
- **Steps**
  1. Connect Pi to hotspot/mobile data.
  2. Upload a test file or clip.
- **Pass criteria**
  - Upload succeeds over mobile connection.

### TP-46: Private bucket access control verification
- **Description**: Ensures uploaded objects are not publicly accessible.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-6.20
- **Prerequisites**
  - At least one object in bucket.
- **Steps**
  1. Attempt to access object URL directly (unsigned).
  2. Generate and access signed URL.
- **Pass criteria**
  - Unsigned access fails.
  - Signed access succeeds.

### TP-47: S3 lifecycle retention configuration verification
- **Description**: Verifies lifecycle rules are configured for storage management.
- **Test level**: Integration
- **Verification approach**: Inspection
- **Reqs**: M-6.30, M-6.31
- **Prerequisites**
  - Lifecycle rules configured.
- **Steps**
  1. Inspect S3 lifecycle configuration.
- **Pass criteria**
  - Rules exist and match intended policy.

### TP-48: Stable S3 object path generation verification
- **Description**: Verifies consistent and stable object key generation.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-6.11
- **Prerequisites**
  - Upload logic implemented.
- **Steps**
  1. Upload multiple clips.
  2. Inspect object keys.
- **Pass criteria**
  - Keys follow consistent structure.
  - Keys are stable and deterministic.
  - No reliance on signed URLs for storage.

### TP-49: Supabase/Postgres connectivity smoke test
- **Description**: Verifies connection to Supabase PostgreSQL instance.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-8.10
- **Prerequisites**
  - Supabase project created.
- **Steps**
  1. Connect and run `SELECT 1`.
- **Pass criteria**
  - Connection succeeds.
  - Query executes.

### TP-50: Supabase schema deployment verification
- **Description**: Verifies schema is correctly deployed to Supabase.
- **Test level**: Integration
- **Verification approach**: Test + Inspection
- **Reqs**: M-8.10
- **Prerequisites**
  - Schema defined.
- **Steps**
  1. Deploy schema.
  2. Inspect tables.
- **Pass criteria**
  - Tables and fields exist as expected.

### TP-51: Cloud metadata write/read verification
- **Description**: Verifies metadata persistence in Supabase.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-8.10
- **Prerequisites**
  - Schema deployed.
- **Steps**
  1. Insert dummy record.
  2. Query record.
- **Pass criteria**
  - Data persists and matches input.

### TP-52: Pi-to-Supabase metadata transmission verification
- **Description**: Verifies Pi can send metadata directly to Supabase.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-8.10
- **Prerequisites**
  - Pi configured with Supabase connection.
- **Steps**
  1. Send metadata from Pi.
  2. Query Supabase.
- **Pass criteria**
  - Metadata successfully stored.
  - Data integrity maintained.

### TP-53: S3 and metadata linkage verification
- **Description**: Verifies metadata correctly references S3 object keys.
- **Test level**: Integration
- **Verification approach**: Test + Inspection
- **Reqs**: M-8.11
- **Prerequisites**
  - S3 upload working.
  - Supabase metadata working.
- **Steps**
  1. Upload clip.
  2. Store metadata with object key.
  3. Verify linkage.
- **Pass criteria**
  - Metadata contains correct S3 object key.
  - Key maps to valid object in S3.

### TP-54: Mid-upload interruption queue retention verification
- **Description**: Verifies uploads interrupted by connectivity loss remain recoverable locally.
- **Test level**: Integration
- **Verification approach**: Test + Inspection
- **Reqs**: M-5.21, M-5.22, M-6.10
- **Prerequisites**
  - Upload queue implemented.
- **Steps**
  1. Start upload.
  2. Disable connectivity mid-upload.
  3. Inspect local queue/state.
- **Pass criteria**
  - Upload does not falsely succeed.
  - Event remains queued locally.
  - Retry state is correct.

### TP-55: Queue recovery after connectivity restoration
- **Description**: Verifies queued uploads complete after connectivity returns.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-5.22, M-6.10, M-8.10
- **Prerequisites**
  - Pending queued upload exists.
- **Steps**
  1. Restore connectivity.
  2. Allow retry processing.
- **Pass criteria**
  - Upload completes successfully.
  - S3 and Supabase updated.
  - Local state updated correctly.

### TP-56: End-to-end driving event cloud persistence verification
- **Description**: Verifies full pipeline from driving event to cloud persistence across SQLite, S3, and Supabase.
- **Test level**: System
- **Verification approach**: Demonstration + Test + Inspection
- **Reqs**: M-4.30, M-5.20, M-6.10, M-8.10, M-8.11
- **Prerequisites**
  - Full pipeline implemented.
- **Steps**
  1. Drive and trigger stop-sign unsafe event.
  2. Verify local SQLite record.
  3. Verify S3 upload.
  4. Verify Supabase metadata.
- **Pass criteria**
  - Event persists correctly across all layers.
  - Records are consistent.

### TP-57: End-to-end interrupted upload recovery during driving verification
- **Description**: Verifies real-world recovery from connectivity loss during event upload.
- **Test level**: System
- **Verification approach**: Demonstration + Test + Inspection
- **Reqs**: M-4.30, M-5.21, M-5.22, M-6.10, M-8.10, M-8.11
- **Prerequisites**
  - Queue and recovery logic implemented.
- **Steps**
  1. Drive and trigger event.
  2. Disconnect connectivity during upload.
  3. Verify local persistence.
  4. Reconnect.
  5. Verify final cloud persistence.
- **Pass criteria**
  - Event not lost during interruption.
  - Upload completes after reconnection.
  - Final state consistent across all systems.

---

# Phase 6 — Deployment, Runtime Management, and CI/CD
### TP-58: Edge managed-service runtime verification
- **Description**: Verifies the edge software runs as a managed service on the Raspberry Pi and can be monitored through the service manager.
- **Test level**: System
- **Verification approach**: Inspection + Demonstration
- **Reqs**: M-10.10
- **Prerequisites**
  - Managed service configured, such as systemd.
- **Steps**
  1. Inspect the service definition.
  2. Start the service through the service manager.
  3. Check service status.
  4. Confirm the edge runtime process is active.
- **Pass criteria**
  - Edge runtime runs under a managed service.
  - Service status shows the runtime as active.
  - Runtime can be started and monitored without manually launching the Python script.

### TP-59: Power-loss recovery and capture resume
- **Description**: Verifies the system restarts automatically after power loss and resumes edge runtime operation.
- **Test level**: System
- **Verification approach**: Test
- **Reqs**: M-10.20
- **Prerequisites**
  - Auto-start or restart logic implemented.
- **Steps**
  1. Run the edge runtime.
  2. Interrupt power to the Raspberry Pi.
  3. Restore power.
  4. Observe startup behavior and runtime recovery.
- **Pass criteria**
  - System starts automatically after power is restored.
  - Edge runtime resumes without manual intervention.
  - Video capture or runtime operation resumes after startup.

### TP-60: Backend Docker container build verification
- **Description**: Verifies the backend can be containerized successfully using Docker and started from the built image.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-10.30, M-10.31
- **Prerequisites**
  - Backend Dockerfile implemented.
- **Steps**
  1. Build the backend Docker image.
  2. Start a container from the image.
  3. Inspect container logs and startup behavior.
- **Pass criteria**
  - Docker image builds successfully.
  - Backend container starts without crash.
  - Backend service is reachable from its exposed port or health endpoint.

### TP-61: Frontend build and deployment artifact verification
- **Description**: Verifies the frontend builds successfully into a deployable artifact for hosting.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-10.30, M-10.31
- **Prerequisites**
  - Frontend build configuration implemented.
- **Steps**
  1. Execute the frontend production build.
  2. Inspect build output.
  3. Confirm the generated artifact is suitable for deployment.
- **Pass criteria**
  - Frontend build completes successfully.
  - Static deployment artifacts are generated.
  - Build output contains the expected application assets.

### TP-62: Backend deployment verification
- **Description**: Verifies the backend deploys successfully to the target hosting environment from the containerized build.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-10.31
- **Prerequisites**
  - Backend deployment target configured.
  - Container deployment workflow implemented.
- **Steps**
  1. Trigger a backend deployment.
  2. Observe deployment logs and completion state.
  3. Access the deployed backend health endpoint or API root.
- **Pass criteria**
  - Backend deployment completes successfully.
  - Deployed backend is reachable.
  - Backend health endpoint or equivalent responds successfully.

### TP-63: Frontend deployment verification
- **Description**: Verifies the frontend deploys successfully to the target hosting environment.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-10.31
- **Prerequisites**
  - Frontend deployment target configured.
- **Steps**
  1. Trigger a frontend deployment.
  2. Observe deployment logs and completion state.
  3. Open the deployed frontend in a browser.
- **Pass criteria**
  - Frontend deployment completes successfully.
  - Deployed frontend loads without crash.
  - Production frontend assets are served correctly.

### TP-64: Frontend-to-backend connectivity verification
- **Description**: Verifies the deployed frontend can successfully communicate with the deployed backend using the intended production configuration.
- **Test level**: System
- **Verification approach**: Test + Demonstration
- **Reqs**: M-10.31, M-10.32
- **Prerequisites**
  - Frontend and backend both deployed.
  - Environment variables and routes configured.
- **Steps**
  1. Open the deployed frontend.
  2. Trigger a frontend action that requires backend communication.
  3. Inspect network activity and frontend behavior.
- **Pass criteria**
  - Frontend sends requests to the correct backend endpoint.
  - Backend responds successfully.
  - Data or health information is rendered correctly in the frontend.
  - No CORS or configuration errors block communication.

### TP-65: CI pipeline gate verification
- **Description**: Verifies automated CI pipelines execute required quality gates such as linting, builds, and tests on repository updates.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-10.30
- **Prerequisites**
  - CI pipeline configured.
- **Steps**
  1. Push a repository update or open a pull request.
  2. Observe CI pipeline execution.
  3. Inspect which checks are run.
- **Pass criteria**
  - Linting executes automatically.
  - Required test suites execute automatically.
  - Required build steps execute automatically.
  - Pipeline reports pass/fail status clearly.

### TP-65: Merge-gated continuous deployment verification
- **Description**: Verifies backend and frontend deploy automatically on merge to main only when required CI checks pass.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-10.31
- **Prerequisites**
  - CD pipeline configured.
  - CI status required before deployment.
- **Steps**
  1. Merge a change to main with passing CI checks.
  2. Observe deployment behavior.
  3. Attempt or inspect a case where required checks fail.
- **Pass criteria**
  - Deployment triggers automatically only after merge to main.
  - Passing CI checks are required before deployment proceeds.
  - Failed required checks prevent deployment.

### TP-66: Post-deployment health check verification
- **Description**: Verifies deployment workflows run post-deployment health checks and only mark deployment successful when those checks pass.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-10.32, M-10.33
- **Prerequisites**
  - Health checks implemented in deployment workflow.
- **Steps**
  1. Trigger a deployment.
  2. Inspect post-deployment health-check execution.
  3. Inspect resulting deployment status.
- **Pass criteria**
  - Post-deployment health checks run automatically.
  - Deployment is considered successful only if health checks pass.
  - Failed health checks cause the deployment to be flagged as failed or incomplete.

---

# Phase 7 — End-to-End System Integration
### TP-67: End-to-end unsafe event pipeline with alert
- **Description**: Verifies an unsafe event is detected on the edge device, triggers an audible alert, and propagates through the full system.
- **Test level**: System
- **Verification approach**: Test + Demonstration
- **Reqs**: M-3.10, M-5.20, M-5.21, M-5.22, M-9.22
- **Prerequisites**
  - Edge runtime operational.
  - Upload pipeline operational.
  - Backend and frontend deployed.
  - Speaker/buzzer connected.
- **Steps**
  1. Run the edge system.
  2. Trigger an unsafe stop-sign event.
  3. Observe local system behavior.
  4. Observe cloud and frontend results.
- **Pass criteria**
  - Unsafe event is detected.
  - Speaker/buzzer activates immediately upon detection.
  - Clip is saved locally.
  - Metadata is stored locally.
  - Event is uploaded to cloud storage and database.
  - Event appears in the frontend.

### TP-68: End-to-end offline-first event handling with alert
- **Description**: Verifies unsafe events are handled correctly while offline and later synchronized, including alert behavior.
- **Test level**: System
- **Verification approach**: Test
- **Reqs**: M-5.20, M-5.21, M-5.22
- **Prerequisites**
  - Offline queue implemented.
  - Speaker/buzzer connected.
- **Steps**
  1. Disable network connectivity.
  2. Run the edge system.
  3. Trigger an unsafe event.
  4. Restore network connectivity.
- **Pass criteria**
  - Speaker/buzzer activates on event detection while offline.
  - Clip and metadata are stored locally.
  - Upload is queued while offline.
  - Upload resumes automatically after reconnection.
  - Event appears in the frontend after synchronization.

### TP-69: End-to-end metadata consistency verification
- **Description**: Verifies event metadata remains consistent across edge storage, backend, cloud database, and frontend.
- **Test level**: System
- **Verification approach**: Inspection + Test
- **Reqs**: M-5.20, M-5.21, M-9.23
- **Prerequisites**
  - At least one completed end-to-end event.
- **Steps**
  1. Trigger and process an event through the full system.
  2. Inspect the local event record.
  3. Inspect the cloud database record.
  4. Inspect the frontend display.
- **Pass criteria**
  - Event identifiers match across all layers.
  - Timestamps and metadata values are consistent.
  - Clip reference corresponds to the correct event.

### TP-70: End-to-end frontend playback verification
- **Description**: Verifies a captured event clip can be retrieved and played through the deployed frontend.
- **Test level**: System
- **Verification approach**: Demonstration
- **Reqs**: M-9.22, M-10.31, M-10.32
- **Prerequisites**
  - At least one uploaded event clip exists.
  - Frontend playback implemented.
- **Steps**
  1. Trigger and upload an event.
  2. Open the deployed frontend.
  3. Locate the event.
  4. Start playback.
- **Pass criteria**
  - Event is visible in the frontend.
  - Correct clip is retrieved.
  - Clip plays successfully.

### TP-71: End-to-end restart and recovery verification
- **Description**: Verifies the system recovers from a restart without breaking the event pipeline.
- **Test level**: System
- **Verification approach**: Test
- **Reqs**: M-10.10, M-10.20, M-5.22
- **Prerequisites**
  - Managed runtime implemented.
  - Queue persistence implemented.
- **Steps**
  1. Run the system.
  2. Trigger an event but interrupt before upload completes.
  3. Restart the edge device.
  4. Resume operation.
- **Pass criteria**
  - Runtime restarts automatically.
  - Local data is preserved.
  - Pending uploads resume.
  - Event completes full pipeline after restart.

### TP-72: End-to-end deployed system smoke test with alert
- **Description**: Verifies a minimal real-world flow from event detection to frontend display, including alert behavior.
- **Test level**: System
- **Verification approach**: Demonstration
- **Reqs**: M-10.31, M-10.32, M-9.10
- **Prerequisites**
  - Fully deployed system.
  - Speaker/buzzer connected.
- **Steps**
  1. Trigger one unsafe event.
  2. Allow system to process and upload.
  3. Open frontend and inspect result.
- **Pass criteria**
  - Speaker/buzzer activates on detection.
  - Event completes full pipeline without manual intervention.
  - Event is visible and reviewable in frontend.
---

# Phase 8 — Frontend Visualization and Reviewer Experience
### TP-73: Frontend application shell loads
- **Description**: Verifies the frontend launches successfully and presents the base application shell for NetraPi.
- **Test level**: Integration
- **Verification approach**: Demonstration
- **Reqs**: M-9.10
- **Prerequisites**
  - Frontend project initialized.
  - Basic routing or single-page shell implemented.
- **Steps**
  1. Start the frontend application.
  2. Open the application in the browser.
- **Pass criteria**
  - Application loads without crash.
  - A recognizable NetraPi frontend shell is displayed.
  - Core page regions or placeholders are visible.

### TP-74: Event data retrieval from backend
- **Description**: Verifies the frontend can retrieve event records from the backend data source.
- **Test level**: Integration
- **Verification approach**: Test
- **Reqs**: M-9.20, M-9.23
- **Prerequisites**
  - Backend API reachable.
  - At least one event record available.
- **Steps**
  1. Open the frontend.
  2. Trigger the event retrieval flow.
  3. Inspect the returned data in the UI and browser network activity.
- **Pass criteria**
  - Frontend successfully requests event data.
  - Event records are returned without frontend error.
  - Retrieved data is available for rendering.

### TP-75: Event list rendering
- **Description**: Verifies retrieved event records are rendered into a visible event list or table.
- **Test level**: Integration
- **Verification approach**: Demonstration
- **Reqs**: M-9.20, M-9.23
- **Prerequisites**
  - Event retrieval implemented.
- **Steps**
  1. Open the frontend with available event data.
  2. Inspect the main event listing view.
- **Pass criteria**
  - Event records appear in the UI.
  - Each rendered row or card corresponds to a backend event.
  - Empty or missing data does not crash the page.

### TP-76: Event metadata and timestamp display
- **Description**: Verifies the frontend displays key event metadata and timestamps for each event.
- **Test level**: Integration
- **Verification approach**: Inspection
- **Reqs**: M-9.23
- **Prerequisites**
  - Event list or event detail rendering implemented.
- **Steps**
  1. Open an event listing or detail view.
  2. Inspect the displayed event fields.
- **Pass criteria**
  - Event metadata is visible.
  - Event timestamps are visible.
  - Displayed values match the stored event record.

### TP-77: Event detail selection and inspection
- **Description**: Verifies a user can select an event and inspect a more detailed event view.
- **Test level**: Integration
- **Verification approach**: Demonstration
- **Reqs**: M-9.23
- **Prerequisites**
  - Event list implemented.
  - Event detail view implemented.
- **Steps**
  1. Open the frontend event list.
  2. Select one event.
  3. Inspect the resulting detail view.
- **Pass criteria**
  - Selected event opens correctly.
  - Detail view corresponds to the chosen event.
  - Additional event information is visible without UI failure.

### TP-78: Video playback via signed URL
- **Description**: Verifies the frontend supports secure playback of an event clip using a signed URL.
- **Test level**: Integration
- **Verification approach**: Demonstration
- **Reqs**: M-9.22
- **Prerequisites**
  - Signed URL playback integrated into frontend.
  - At least one event has a valid stored clip.
- **Steps**
  1. Select an event with a stored clip.
  2. Trigger video playback.
- **Pass criteria**
  - Frontend retrieves or receives a valid signed URL.
  - Clip plays successfully in the frontend.
  - Playback is associated with the selected event.

### TP-79: Event filtering controls
- **Description**: Verifies the frontend supports filtering displayed events by date range and collection phase.
- **Test level**: Integration
- **Verification approach**: Demonstration
- **Reqs**: M-9.20
- **Prerequisites**
  - Filtering UI implemented.
  - Data from both phases exists.
- **Steps**
  1. Apply a date-range filter.
  2. Apply a collection-phase filter.
  3. Clear or change the filters.
- **Pass criteria**
  - Displayed records update correctly by date range.
  - Displayed records update correctly by collection phase.
  - Filter changes do not require manual page recovery.

### TP-80: Aggregate metrics display
- **Description**: Verifies the frontend displays aggregate safety metrics derived from collected event data.
- **Test level**: Integration
- **Verification approach**: Inspection + Demonstration
- **Reqs**: M-9.21
- **Prerequisites**
  - Metrics processing implemented.
  - Metrics view implemented.
- **Steps**
  1. Open the metrics view.
  2. Inspect displayed summary values.
- **Pass criteria**
  - Aggregate safety metrics are displayed.
  - Displayed values correspond to available dataset content.
  - Metrics view loads without crash or missing-state failure.

### TP-81: Metrics-over-time charting
- **Description**: Verifies the frontend displays charts illustrating safety metrics over time.
- **Test level**: Integration
- **Verification approach**: Inspection
- **Reqs**: M-9.30
- **Prerequisites**
  - Charting implemented.
  - Metrics data available.
- **Steps**
  1. Open the charts view.
  2. Inspect at least one time-based visualization.
- **Pass criteria**
  - At least one chart visualizes safety metrics over time.
  - Chart axes, labels, or legends are understandable.
  - Chart renders without distortion or missing data failure.

### TP-82: Baseline vs post-baseline comparison display
- **Description**: Verifies the frontend displays baseline and post-baseline comparison summaries.
- **Test level**: Integration
- **Verification approach**: Inspection + Demonstration
- **Reqs**: M-9.50, M-9.51, M-9.52
- **Prerequisites**
  - Baseline and post-baseline datasets available.
  - Comparison view implemented.
- **Steps**
  1. Open the comparison or metrics summary view.
  2. Review baseline and post-baseline values.
- **Pass criteria**
  - Baseline and post-baseline summaries are shown.
  - Comparison content is understandable to a reviewer.
  - UI frames results as evaluation of feedback and self-monitoring effects.

### TP-83: Baseline vs post-baseline visual distinction
- **Description**: Verifies visualizations clearly distinguish baseline and post-baseline data.
- **Test level**: Integration
- **Verification approach**: Inspection
- **Reqs**: M-9.31
- **Prerequisites**
  - Comparison or chart views implemented.
  - Both baseline and post-baseline data available.
- **Steps**
  1. Open comparison and chart views.
  2. Inspect how each phase is visually represented.
- **Pass criteria**
  - Baseline and post-baseline data are visually distinguishable.
  - Labels, legends, colors, or markers are consistent.
  - A reviewer can tell which data belongs to which phase without ambiguity.

### TP-84: Configuration parameter transparency
- **Description**: Verifies the frontend displays the configuration parameters used during data collection or experimentation.
- **Test level**: Acceptance
- **Verification approach**: Inspection
- **Reqs**: M-9.40
- **Prerequisites**
  - Configuration display implemented.
- **Steps**
  1. Open the configuration or experiment detail view.
  2. Inspect the displayed parameter values.
- **Pass criteria**
  - Data-collection configuration parameters are shown.
  - Displayed parameters are understandable to a reviewer.
  - Values appear tied to the correct dataset, run, or phase.

### TP-85: Source-code and documentation access
- **Description**: Verifies the frontend provides access to source code and technical documentation for reviewer follow-up.
- **Test level**: Acceptance
- **Verification approach**: Inspection
- **Reqs**: M-9.41
- **Prerequisites**
  - Links or references implemented in frontend.
- **Steps**
  1. Open the frontend.
  2. Follow the source-code and documentation references.
- **Pass criteria**
  - Frontend provides access to source code and technical documentation.
  - References are visible and understandable.
  - Linked destinations are relevant to the project.

### TP-86: Project overview page
- **Description**: Verifies the frontend presents NetraPi as an interactive technical artifact with concise project overview content.
- **Test level**: Acceptance
- **Verification approach**: Inspection
- **Reqs**: M-9.10, M-9.11
- **Prerequisites**
  - Frontend deployed.
  - Overview content implemented.
- **Steps**
  1. Open the deployed frontend.
  2. Inspect the overview and explanatory content.
- **Pass criteria**
  - Frontend presents the project clearly for reviewer use.
  - Project goals, architecture, and constraints are described concisely.
  - Overview content reflects the implemented frontend experience rather than placeholder text.

---

# Phase 9 — Experimentation and Impact Evaluation
### TP-87: Baseline mode initialization and configuration verification
- **Description**: Verifies that when baseline mode starts, the system uses full-session recording and saves the exact model and configuration being used for the experiment.
- **Test level**: Integration
- **Verification approach**: Test + Inspection
- **Reqs**: M-4.10, M-4.11, M-4.42
- **Prerequisites**
  - Baseline mode implemented.
  - System capable of storing configuration data (e.g., JSON file or database entry).
- **Steps**
  1. Start the system in baseline mode.
  2. Run the system for a short period (e.g., 1–2 minutes).
  3. Check the output directory or storage location:
     - Confirm that a full video file is being recorded (not just clips).
  4. Locate the stored configuration (e.g., config file, DB entry, or log):
     - Identify model name (e.g., model file used).
     - Identify key parameters (e.g., thresholds, buffer size, etc.).
  5. Restart the system again in baseline mode.
  6. Check the configuration again.
- **Pass criteria**
  - System records continuous/full-session video during baseline mode.
  - A configuration record is created at the start of the run.
  - The configuration includes at least:
    - model identifier (e.g., model filename or version)
    - key parameters used for detection
  - Configuration values remain the same across restarts (no unexpected changes).

### TP-88: Baseline collection minimum hours
- **Description**: Validates baseline collection retains full-session video and reaches the required duration with fixed configuration.
- **Test level**: Acceptance
- **Verification approach**: Test + Analysis
- **Reqs**: M-4.10, M-4.11, M-4.12, M-4.42
- **Prerequisites**
  - Baseline mode active.
  - Full-session upload path implemented.
- **Steps**
  1. Run baseline drives until at least 10 hours of footage are recorded.
  2. Confirm uploaded full-session footage exists in cloud storage.
  3. Confirm model/configuration remain unchanged during collection.
- **Pass criteria**
  - At least 10 hours of baseline footage are recorded.
  - Full-session video is retained and uploaded.
  - Same model/configuration is used across the baseline phase.

### TP-89: Baseline metrics computation and storage
- **Description**: Verifies baseline footage is processed to produce concrete stop-sign safety metrics and that those metrics are stored correctly.
- **Test level**: Acceptance
- **Verification approach**: Analysis + Inspection
- **Reqs**: M-4.20, M-4.21, M-4.42
- **Prerequisites**
  - Baseline footage exists in cloud storage.
  - Event detection and classification (rolling stop vs full stop) implemented.
  - Metrics computation logic implemented.
  - Metrics persistence implemented.
- **Steps**
  1. Execute the baseline processing job on collected footage.
  2. Inspect generated event records:
     - Verify events are classified (e.g., rolling stop vs full stop).
  3. Inspect computed metrics in storage (database or file):
     - total_events
     - rolling_stop_count
     - full_stop_count
     - rolling_stop_rate
  4. Manually verify a small sample:
     - Count events from raw data.
     - Compare with computed metrics.
- **Pass criteria**
  - Baseline footage is processed using the same model/parameters used during collection.
  - Each event is classified (e.g., rolling stop vs full stop).
  - Metrics are computed correctly:
    - total_events matches detected events
    - rolling_stop_count + full_stop_count = total_events
    - rolling_stop_rate is correctly calculated
  - Metrics in a defined storage location.

### TP-90: Post-baseline mode switch and behavior verification
- **Description**: Verifies that switching from baseline mode to post-baseline mode changes storage behavior from full-session recording to clip-based recording, while keeping the same model and detection settings.
- **Test level**: Integration
- **Verification approach**: Test + Inspection
- **Reqs**: M-4.30, M-4.31, M-4.42
- **Prerequisites**
  - System supports two modes: baseline and post-baseline.
  - Mode can be changed via configuration (e.g., config file or flag).
- **Steps**
  1. Start the system in baseline mode.
  2. Run briefly and confirm:
     - A continuous/full video file is being recorded.
  3. Stop the system.
  4. Change mode to post-baseline (e.g., update config).
  5. Restart the system.
  6. Trigger or simulate at least one stop-sign event.
  7. Inspect stored outputs:
     - Check that only event clips are saved (not full-session video).
  8. Inspect configuration used during both runs:
     - Compare model name and key parameters.
- **Pass criteria**
  - In baseline mode:
    - Continuous/full-session recording is used.
  - In post-baseline mode:
    - Only event-triggered clips are stored.
    - No full-session recording is produced.
  - Model and detection parameters are identical between both modes.

### TP-91: Post-baseline clip-based collection
- **Description**: Verifies the system performs clip-based storage during post-baseline operation under the same fixed configuration.
- **Test level**: Acceptance
- **Verification approach**: Test
- **Reqs**: M-4.30, M-4.31, M-4.32, M-4.42
- **Prerequisites**
  - Post-baseline mode active.
- **Steps**
  1. Run at least 10 additional hours of driving in post-baseline mode.
  2. Inspect stored outputs and metadata.
- **Pass criteria**
  - System uses clip-based retention.
  - Event-triggered clips are stored.
  - Associated metadata is retained.
  - Configuration remains unchanged from baseline.

### TP-92: Phase labeling and metrics separation
- **Description**: Verifies baseline and post-baseline data and metrics are stored with correct phase labels and are not mixed.
- **Test level**: Integration
- **Verification approach**: Inspection + Analysis
- **Reqs**: M-4.20, M-4.30, M-4.40
- **Prerequisites**
  - Baseline and post-baseline data both exist.
  - Metrics persistence implemented.
- **Steps**
  1. Inspect stored event, clip, and metrics records.
  2. Verify phase labels for each dataset.
- **Pass criteria**
  - Baseline records are labeled as baseline.
  - Post-baseline records are labeled as post-baseline.
  - Metrics are associated with the correct phase.
  - No mixing of phase data is observed.

### TP-93: Baseline vs post-baseline metrics comparison
- **Description**: Verifies that baseline and post-baseline safety metrics are compared using the same definitions and that the comparison produces meaningful differences (e.g., change in rolling stop rate).
- **Test level**: Acceptance
- **Verification approach**: Analysis + Inspection
- **Reqs**: M-4.40, M-4.41, M-4.42
- **Prerequisites**
  - Baseline metrics computed and stored.
  - Post-baseline metrics computed and stored.
  - Metrics include at least:
    - total_events
    - rolling_stop_count
    - full_stop_count
    - rolling_stop_rate
- **Steps**
  1. Retrieve baseline metrics from storage.
  2. Retrieve post-baseline metrics from storage.
  3. Compare the following values:
     - rolling_stop_rate (baseline vs post-baseline)
     - rolling_stop_count (baseline vs post-baseline)
     - total_events (for context)
  4. Manually verify calculations:
     - rolling_stop_rate = rolling_stop_count / total_events for both phases
  5. (Optional) Display results in frontend or summary output.
- **Pass criteria**
  - Baseline and post-baseline metrics are both present and labeled correctly.
  - Metrics are computed using the same definitions in both phases.
  - Comparison produces clear values (e.g., difference or percent change in rolling_stop_rate).
  - No mixing of baseline and post-baseline data occurs.
  - Results can be interpreted to assess whether driving behavior improved, worsened, or stayed the same.

--- 

## 7. Coverage Notes
This updated plan covers:
- constraints
- physical installation and endurance
- capture/buffer configurability
- local TPU inference and event handling
- offline-first SQLite persistence
- S3 upload and retention
- backend authentication, persistence, and signed playback
- frontend interactivity, transparency, and visualization
- baseline and post-baseline experimentation
- deployment and reliability