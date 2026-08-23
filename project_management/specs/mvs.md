# Minimum Viable Specification (MVS) – NetraPi

## Goal
Build a minimal, end-to-end smart dash cam system that detects stop-sign-related unsafe events using edge-based computer vision, captures and stores relevant video evidence, and presents results through a deployed web interface. The system shall support a single data-collection phase, manual ground-truth labeling of footage, and evaluation of model classification accuracy (run-through, rolling stop, complete stop).

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
- M-3.13: The system shall detect stop-sign-related unsafe events and classify them as run-through, rolling stop, or complete stop.

### R-3.2 Event Triggering and Clip Definition
- M-3.20: When an unsafe event is detected, the system shall extract a video clip consisting of 5 to 10 seconds of footage before and 5 to 10 seconds of footage after the detected event, resulting in 10–20 second clips.
- M-3.21: Each event shall be timestamped and associated with the active configuration parameters.

### R-3.3 Real-Time Feedback
- M-3.30: The system shall provide real-time audible feedback when an unsafe event is detected.
- M-3.31: Audible feedback shall occur within 10 seconds of the detected event.

## R-4 Data Collection and Model Evaluation
### R-4.1 Session Recording
- M-4.10: After the edge system is operational, the system shall record a minimum of 10 hours of driving footage using a fixed ML model and configuration.
- M-4.11: Full-session video shall be uploaded from the edge device to cloud object storage.
- M-4.12: Event-triggered clips and associated metadata shall be retained alongside full-session footage.

### R-4.2 Stop Sign Event Scope
- M-4.20: Unsafe event detection shall be limited to stop-sign-related events (run-through, rolling stop, complete stop).
- M-4.21: Configuration parameters shall remain fixed for the duration of data collection.

### R-4.3 Manual Review and Ground Truth
- M-4.30: The operator (me) shall manually review all collected footage and assign ground-truth categories to events.
- M-4.31: Manual categorization shall support evaluation of model classification accuracy.

## R-5 Offline Operation and Local Persistence
### R-5.1 Offline Operation
- M-5.10: The system shall continue video capture and event detection independently of network connectivity.

### R-5.2 Local Event Metadata
- M-5.20: Event metadata shall be stored locally on the edge device using a SQLite database.

## R-6 Media Upload and Cloud Storage
### R-6.1 Upload Path
- M-6.10: When connectivity is available (cellular hotspot or mobile data), the edge device shall upload video clips and full-session footage one at a time to private cloud object storage using temporary upload credentials issued by the backend API (presigned PUT); the edge device shall not store permanent cloud-storage credentials, and the system shall not maintain an offline upload queue.

### R-6.2 Cloud Storage
- M-6.20: Uploaded video assets shall be stored in a private AWS S3 storage bucket.

## R-7 Backend API
### R-7.1 Backend Responsibilities
- M-7.10: A cloud-deployed backend API shall authenticate edge devices using API keys.
- M-7.11: The backend shall receive metadata uploads from the edge device.
- M-7.12: The backend shall persist structured metadata in a cloud-hosted PostgreSQL database.
- M-7.13: The backend shall generate time-limited signed URLs for secure video playback.
- M-7.14: The backend shall serve the deployed frontend with event metadata from the database and selected video assets from cloud storage via signed URLs.
- M-7.15: The backend shall issue time-limited signed URLs authorizing the edge device to upload media objects to cloud object storage (presigned PUT).

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
- M-9.20: The frontend shall allow filtering of events by date range and event type (run-through, rolling stop, complete stop).
- M-9.21: The frontend shall display model classification accuracy metrics by comparing detected labels against manual ground-truth categories.
- M-9.22: The frontend shall support video playback via signed URLs.
- M-9.23: The frontend shall display event metadata and timestamps.
- M-9.24: The frontend shall allow users to browse and select clips from the collected footage.

### R-9.3 Visualization
- M-9.30: The frontend shall include at least one visualization of collected event or evaluation data.

### R-9.4 Transparency
- M-9.40: The frontend shall display configuration parameters used during data collection.
- M-9.41: The frontend shall provide access to source code and technical documentation.

### R-9.5 Model Evaluation
- M-9.50: The frontend shall present per-class and overall classification accuracy for run-through, rolling stop, and complete stop.
- M-9.51: The interface shall visually communicate agreement and disagreement between model predictions and manual labels.
- M-9.52: The analysis shall frame results as an evaluation of stop-sign event detection performance, not driving-behavior change.

## R-10 Deployment and Reliability
### R-10.1 Edge Runtime
- M-10.10: The edge software shall run as a managed service on the Raspberry Pi.

### R-10.2 CI/CD
- M-10.20: Automated CI pipelines shall execute on repository updates, including linting and test suites.
- M-10.21: Backend and frontend deployments shall occur automatically on merge to the main branch only when all required tests pass.
- M-10.22: Deployment pipelines shall include post-deployment health checks to verify service availability and basic functionality.
- M-10.23: Deployments shall be considered successful only when health checks complete successfully.