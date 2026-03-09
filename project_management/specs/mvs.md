# Minimum Viable Specification (MVS) – NetraPi

## Goal
Build a minimal, end-to-end smart dash cam system that monitors driving behavior using edge-based computer vision, captures and stores relevant video evidence, and presents safety insights through a deployed web interface. The system shall support controlled experimentation by enabling baseline data collection, real-time feedback during driving, and post-hoc analysis to evaluate whether self-monitoring and feedback influence driving behavior.

## Constraints
### C-1 Resource Limitations
- C-1.10: The total budget of this project shall be limited to $1,000 or less.
- C-1.11: The system must be compatible with a 2010 Mazda3 sedan.
- C-1.12: The system shall follow all driving regulations and policies.
- C-1.13: The system shall be safe in its entirety to operate.

## R-1 Physical Configuration
### R-1.1 Installation
- M-1.10: The system shall mount a forward-facing camera with a stable view of the roadway.
- M-1.11: The system shall securely install the Raspberry Pi 5, Coral USB TPU, camera, wiring, and portable battery.
- M-1.12: The raspberry pi shall be powered exclusively by a portable battery.
- M-1.13: The system shall support non-permanent removal of the Raspberry Pi, tpu, and battery using a reversible mounting mechanism.

### R-1.2 Operational Endurance
- M-1.20: The system shall operate continuously for a minimum of 3 hours without requiring battery recharging or physical reinstallation.
- M-1.21: The system shall continuously record and write to memory for a minimum of 3 hours.
- M-1.22: The system shall work during average temperatures experienced in Texas summers with supervision.

## R-2 Video Capture and Buffering (Edge)
### R-2.1 Continuous Capture
- M-2.10: The system shall capture continuous forward-facing video.
- M-2.11: The system shall start recording after some mechanism initiates the recording process (ie running a script, terminal command, etc)
- M-2.12: The system shall end recording after some mechanism initiates the recording process to stop (Ctrl + c in terminal, turning off the pi, removing power from pi)
- M-2.13: The system shall maintain a rolling video buffer to enable retrospective clip extraction.
- M-2.14: Video resolution, frame rate, and buffer duration shall be configurable.

## R-3 Unsafe Event Detection (Machine Learning)
### R-3.1 Detection Method
- M-3.10: Unsafe event detection shall be implemented using a machine learning approach.
- M-3.11: Inference shall run locally on the Raspberry Pi using the Google Coral USB TPU.
- M-3.12: The system shall use TensorFlow Lite models compiled for Edge TPU execution.
- M-3.13: The system shall detect at least one type of unsafe event.

### R-3.2 Event Triggering and Clip Definition
- M-3.20: When an unsafe event is detected, the system shall extract a video clip consisting of 5 to 10 seconds of footage before and 5 to 10 seconds of footage after the detected event, resulting in 10–20 second clips.
- M-3.21: Each event shall be timestamped and associated with the active configuration parameters.

### R-3.3 Real-Time Feedback
- M-3.30: The system shall provide real-time audible feedback when an unsafe event is detected.
- M-3.31: Audible feedback shall occur within 10 seconds of the detected event.

## R-4 Experimentation and Impact Evaluation
### R-4.1 Baseline Data Collection
- M-4.10: The system shall support an experimentation phase during which all captured video is retained.
- M-4.11: Full-session video shall be uploaded from the edge device to cloud object storage during baseline collection.
- M-4.12: The system shall record a minimum of 10 hours of driving footage during baseline collection using a fixed ML model and configuration.

### R-4.2 Baseline Processing
- M-4.20: Baseline driving footage shall be processed to detect unsafe events using the same ML model and parameters used during capture.
- M-4.21: Baseline safety metrics shall be computed from detected events.

### R-4.3 Post-Baseline Collection
- M-4.30: After baseline collection, the system shall transition to clip-based storage.
- M-4.31: The system shall record a minimum of 10 additional hours of driving using the same configuration parameters.
- M-4.32: Event-triggered clips and associated metadata shall be retained during this phase.

### R-4.4 Impact Evaluation
- M-4.40: Post-baseline safety metrics shall be compared against baseline metrics.
- M-4.41: The comparison shall be used to evaluate the impact of real-time feedback and self-monitoring on driving behavior.
- M-4.42: Configuration parameters shall remain consistent across baseline and post-baseline phases.

## R-5 Offline-First Operation and Local Persistence
### R-5.1 Offline Operation
- M-5.10: The system shall continue video capture and event detection independently of network connectivity.

### R-5.2 Upload Queue Persistence
- M-5.20: Event metadata and upload state shall be stored locally using a SQLite database.
- M-5.21: Each queued upload record shall include clip identifier, local file path, upload status, retry count, and timestamps.
- M-5.22: On system restart, queued records shall be reloaded from SQLite and uploads shall resume automatically.

## R-6 Media Upload and Cloud Storage
### R-6.1 Upload Path
- M-6.10: Video clips and baseline footage shall be uploaded directly from the Raspberry Pi to cloud object storage using a cellular hotspot or mobile data connection.

### R-6.2 Cloud Storage
- M-6.20: Uploaded video assets shall be stored in a private AWS S3 storage bucket.

### R-6.3 Retention Policy
- M-6.30: The system shall apply a fixed, time-based retention policy to stored video assets.
- M-6.31: Retention enforcement shall be implemented using cloud lifecycle rules.

## R-7 Backend API
### R-7.1 Backend Responsibilities
- M-7.10: A cloud-deployed backend API shall authenticate edge devices using API keys.
- M-7.11: The backend shall receive metadata uploads from the edge device.
- M-7.12: The backend shall persist structured metadata in a cloud-hosted PostgreSQL database.
- M-7.13: The backend shall generate time-limited signed URLs for secure video playback.
- M-7.14: The backend shall serve the deployed frontend with event metadata from the database and selected video assets from cloud storage via signed URLs.

## R-8 Database
### R-8.1 Data Storage
- M-8.10: Structured event metadata shall be stored in a cloud-hosted PostgreSQL database.
- M-8.11: The paths to the stored video clips within the S3 bucket shall be included in database.
- M-8.12: The paths to stored video clips in the s3 bucket shall be used to retrieve video clips.

## R-9 Web Frontend (Interactive Portfolio)
### R-9.1 Portfolio Presentation
- M-9.10: The frontend shall present the project as an interactive technical artifact suitable for employer review.
- M-9.11: The interface shall include a concise project overview describing system goals, architecture, and constraints.

### R-9.2 Interactivity
- M-9.20: The frontend shall allow filtering of events by date range and collection phase (baseline vs usage).
- M-9.21: The frontend shall display aggregate safety metrics and comparisons.
- M-9.22: The frontend shall support video playback via signed URLs.
- M-9.23: The frontend shall display event metadata and timestamps.

### R-9.3 Visualization
- M-9.30: The frontend shall display charts illustrating safety metrics over time.
- M-9.31: Visualizations shall clearly distinguish baseline and post-baseline data.

### R-9.4 Transparency
- M-9.40: The frontend shall display configuration parameters used during data collection.
- M-9.41: The frontend shall provide access to source code and technical documentation.

### R-9.5 Impact Analysis
- M-9.50: The frontend shall present a comparison of baseline and post-baseline safety metrics.
- M-9.51: The interface shall visually communicate changes in event frequency before and after system deployment.
- M-9.52: The analysis shall frame results as an evaluation of real-time feedback and self-monitoring effects.

## R-10 Deployment and Reliability
### R-10.1 Edge Runtime
- M-10.10: The edge software shall run as a managed service on the Raspberry Pi.

### R-10.2 Power Loss Recovery
- M-10.20: On startup after power loss, the system shall resume video capture.
- M-10.21: Pending upload records shall be reloaded from local storage.
- M-10.22: Pending uploads shall continue without data corruption.

### R-10.3 CI/CD
- M-10.30: Automated CI pipelines shall execute on repository updates, including linting and test suites.
- M-10.31: Backend and frontend deployments shall occur automatically on merge to the main branch only when all required tests pass.
- M-10.32: Deployment pipelines shall include post-deployment health checks to verify service availability and basic functionality.
- M-10.33: Deployments shall be considered successful only when health checks complete successfully.