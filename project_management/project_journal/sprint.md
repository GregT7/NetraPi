# NetraPi Sprint Report (`sprint_rep.md`)

This file is the single planning source of truth, combining the sprint cadence format with phase-based requirement and test traceability.

---

# Sprint 1 - Foundation and Edge Bring-Up

## 📝 Overview
- Dates: January 24th - May 20 (2026)
- Status: Completed
- Backlog Progress: 4 backlogs completed / 4 backlogs assigned (100%)
- Backlogs Assigned:
  - Physical Installation
  - Inference Smoke Test
  - Initial System Design
  - Rolling Buffer Design
- Goal: Build a safe and stable in-car foundation and prove edge ML bring-up.
- Objective: Complete core system design, physically secure hardware, verify capture quality/endurance, and validate camera-to-TPU inference path.

### Milestones
1. Complete hardware/software architecture diagrams.
2. Securely install camera, Pi, TPU, battery, and wiring in a reversible way.
3. Validate clear recording and endurance under expected conditions.
4. Bring up Coral TPU and run live inference smoke tests.
5. Finalize rolling buffer design for later clip extraction.

### Requirements covered
- C-1.10, C-1.11, C-1.12, C-1.13
- M-1.10, M-1.11, M-1.12, M-1.13, M-1.20, M-1.21, M-1.22
- M-2.10, M-2.13, M-2.14
- M-3.10, M-3.11, M-3.12

### Corresponding tests
- TP-01 to TP-15

---
# Sprint 2 -

## 📝 Overview
- Dates: May 20 - Month day (2026)
- Status: Started
- Backlog Progress: # backlogs completed / 1 backlog assigned (X%)
- Backlogs Assigned:
  - Recording System Design
  - Detector
  - Recording Manager
- Goal: Start building the infrastructure needed to continuously record and detect unsafe events.
- Objective: Create a rough design for the system using uml diagrams and flowcharts. Next implement the designed classes needed for event detection and recording the unsafe event. This will not include the logic for detecting an unsafe event.

### Milestones
1. The event_clip_pipeline.md file is finished with the rough design of the recording/inference system.
2. The project tree structure plan is defined with reasoning
3. All config files created
4. Script for loading config files is created and working
5. Detector classes and subclasses defined with passing unit/integration tests
6. E2E test using Detector class to hold, process, and correctly classify an image passes
7. All RecordingManager subclasses defined with passing unit tests
8. All the methods for RecordingManager work
9. Live integration/e2e test works while recording footage live, and manually triggering an event

### Requirements covered
- M-3.13, M-3.20, M-3.21, M-3.30, M-3.31
- M-4.21 (classification/metric primitives used later in experimentation)
- M-4.32 (event clip/metadata retention behavior)

### Corresponding tests
- TP-16 to TP-24

---

# Sprint A - Unsafe Event Detection Core

## 📝 Overview
- Dates: Month day - Month day (2026)
- Status: Not Started
- Backlog Progress: # backlogs completed / 1 backlog assigned (X%)
- Backlogs Assigned:
  - Unsafe Event Detection (stop-sign focused pipeline)
- Goal: Implement the full unsafe-event logic deeply and correctly.
- Objective: Build robust detection/classification logic, event extraction, and timely audible feedback with low false-positive behavior.

### Milestones
1. Implement stop-sign encounter lifecycle (triggering, filtering, relevance).
2. Implement motion-based stop quality classification (full stop, rolling stop, bypass).
3. Produce event clips and metadata on unsafe events.
4. Trigger audible feedback within timing targets.
5. Validate false-positive resistance.

### Requirements covered
- M-3.13, M-3.20, M-3.21, M-3.30, M-3.31
- M-4.21 (classification/metric primitives used later in experimentation)
- M-4.32 (event clip/metadata retention behavior)

### Corresponding tests
- TP-25 to TP-30

---

# Sprint B - Offline-First Local Persistence

## 📝 Overview
- Dates: Month day - Month day (2026)
- Status: Not Started
- Backlog Progress: # backlogs completed / 2 backlogs assigned (X%)
- Backlogs Assigned:
  - Local DB design and setup
  - Upload queue
- Goal: Make the edge system durable without relying on constant connectivity.
- Objective: Persist event and queue state in SQLite and support retry-safe queue behavior.

### Milestones
1. Finalize SQLite schema for events and queue records.
2. Store queue state with identifiers, file path, status, retries, timestamps.
3. Validate offline queue retention and retry behavior.
4. Confirm queue reload and resume logic on restart.

### Requirements covered
- M-5.10, M-5.20, M-5.21, M-5.22
- M-10.20, M-10.21

### Corresponding tests
- TP-31 to TP-42

---

# Sprint C - Cloud Persistence Foundations

## 📝 Overview
- Dates: Month day - Month day (2026)
- Status: Not Started
- Backlog Progress: # backlogs completed / 3 backlogs assigned (X%)
- Backlogs Assigned:
  - S3 setup (bucket, pathing, path-based retrieval)
  - Cloud DB setup (cluster setup + connectivity)
  - S3 persistence spike (temporary direct writes to S3 + cloud DB)
- Goal: Prove cloud persistence from edge-generated events.
- Objective: Establish stable object keying, cloud metadata storage, and consistent linkage between the two.

### Milestones
1. Provision and harden private S3 bucket.
2. Implement deterministic S3 object path structure.
3. Provision cloud Postgres and deploy schema.
4. Persist metadata including S3 paths and verify retrieval by path.
5. Run direct persistence spike from local program to both stores.

### Requirements covered
- M-6.10, M-6.20
- M-8.10, M-8.11, M-8.12
- M-5.21 (queue-to-cloud handoff checks)

### Corresponding tests
- TP-43 to TP-55

---

# Sprint D - Secure Backend and Integrated Cloud Writes

## 📝 Overview
- Dates: Month day - Month day (2026)
- Status: Not Started
- Backlog Progress: # backlogs completed / 2 backlogs assigned (X%)
- Backlogs Assigned:
  - Deploy secure dockerized backend
  - DB + S3 persistence through backend contracts
- Goal: Move to secure API-mediated cloud writes and reads.
- Objective: Authenticate edge clients, persist metadata via backend, and expose secure playback links.

### Milestones
1. Containerize backend and deploy to cloud runtime.
2. Add API-key auth for edge clients.
3. Persist metadata rows including S3 object paths.
4. Generate signed URLs for playback.
5. Validate backend-served metadata for frontend use.

### Requirements covered
- M-7.10, M-7.11, M-7.12, M-7.13, M-7.14
- M-8.10, M-8.11, M-8.12
- M-10.30, M-10.31 (backend build/deploy pipeline behavior)

### Corresponding tests
- TP-56, TP-58, TP-60, TP-61, TP-62, TP-63, TP-64, TP-65

---

# Sprint E - Security Baseline and One E2E Drive

## 📝 Overview
- Dates: Month day - Month day (2026)
- Status: Not Started
- Backlog Progress: # backlogs completed / 2 backlogs assigned (X%)
- Backlogs Assigned:
  - Basic security (lifecycle retention, signed URLs, metadata request records)
  - Inference-to-cloud E2E drive validation
- Goal: Harden cloud data handling and validate one full real-world path.
- Objective: Confirm end-to-end event generation, upload, persistence, and secure access in one integrated flow.

### Milestones
1. Configure and verify retention lifecycle rules.
2. Verify signed URL access model and private bucket behavior.
3. Add/verify metadata request traceability through backend.
4. Execute one full in-car E2E unsafe-event run from inference to cloud persistence.

### Requirements covered
- M-6.30, M-6.31
- M-7.13, M-7.14
- M-10.32, M-10.33
- M-9.22, M-9.23 (E2E playback/metadata verification path)

### Corresponding tests
- TP-45, TP-46, TP-52, TP-62, TP-65, TP-66, TP-67, TP-68, TP-69

---

# Sprint F - Resilient Persistence and Managed Service Runtime

## 📝 Overview
- Dates: Month day - Month day (2026)
- Status: Not Started
- Backlog Progress: # backlogs completed / 2 backlogs assigned (X%)
- Backlogs Assigned:
  - Resilient persistence (automatic upload resume after connectivity returns)
  - Managed service (edge runtime as service)
- Goal: Make runtime behavior robust and low-touch in real operation.
- Objective: Ensure queue durability, restart safety, and managed execution of edge software.

### Milestones
1. Run edge software as managed service.
2. Validate queue reload/resume after restarts.
3. Validate interrupted upload recovery and eventual consistency.
4. Verify restart/recovery E2E behavior.

### Requirements covered
- M-10.10
- M-10.20, M-10.21
- M-5.21, M-5.22

### Corresponding tests
- TP-42, TP-53, TP-54, TP-57, TP-70

---

# Sprint G - Frontend Design and Core Implementation

## 📝 Overview
- Dates: Month day - Month day (2026)
- Status: Not Started
- Backlog Progress: # backlogs completed / 2 backlogs assigned (X%)
- Backlogs Assigned:
  - Design frontend (Figma or quick sketch)
  - Implement frontend (guided by MVS + test plan)
- Goal: Build a usable reviewer-facing interface for the system.
- Objective: Deliver event browsing, playback, filtering, metrics, and transparency content.

### Milestones
1. Finalize UI structure and navigation.
2. Implement event list/detail + metadata display.
3. Implement signed URL playback flow.
4. Implement filters, metrics, charts, and phase distinction views.
5. Add source/docs links and configuration transparency.

### Requirements covered
- M-9.10, M-9.11
- M-9.20, M-9.21, M-9.22, M-9.23
- M-9.30, M-9.31
- M-9.40, M-9.41
- M-9.50, M-9.51, M-9.52

### Corresponding tests
- TP-72 to TP-85

---

# Sprint H - Frontend Deployment, Integration, and Basic Auth

## 📝 Overview
- Dates: Month day - Month day (2026)
- Status: Not Started
- Backlog Progress: # backlogs completed / 3 backlogs assigned (X%)
- Backlogs Assigned:
  - Deploy frontend
  - Frontend <-> backend connection
  - Basic auth (limited personal access)
- Goal: Put the portfolio in production with controlled access and stable integration.
- Objective: Deploy both sides, verify production connectivity, and enforce basic access controls.

### Milestones
1. Deploy frontend and backend environments.
2. Validate production API wiring and CORS/env setup.
3. Validate secure data retrieval and playback path in production.
4. Enforce basic access restriction for private use.

### Requirements covered
- M-10.31, M-10.32, M-10.33
- M-7.14
- M-9.10, M-9.22, M-9.23

### Corresponding tests
- TP-61, TP-62, TP-63, TP-64, TP-65, TP-69, TP-71

---

# Sprint I - CI/CD Hardening

## 📝 Overview
- Dates: Month day - Month day (2026)
- Status: Not Started
- Backlog Progress: # backlogs completed / 1 backlog assigned (X%)
- Backlogs Assigned:
  - CI/CD setup (lint + build + tests + gated deploy + post-deploy health checks)
- Goal: Make deployments dependable and repeatable with quality gates.
- Objective: Enforce checks, block bad deploys, and verify post-deploy health automatically.

### Milestones
1. Implement CI checks for lint/test/build.
2. Enforce deploy-on-pass gating from main merge.
3. Add health checks and success criteria in deployment workflows.

### Requirements covered
- M-10.30, M-10.31, M-10.32, M-10.33

### Corresponding tests
- TP-63, TP-64, TP-65

---

# Sprint J - Experimentation and Impact Evaluation

## 📝 Overview
- Dates: Month day - Month day (2026)
- Status: Not Started
- Backlog Progress: # backlogs completed / 2 backlogs assigned (X%)
- Backlogs Assigned:
  - Experiment + impact evaluation
  - Frontend update (publish findings)
- Goal: Complete baseline/post-baseline analysis and communicate measurable impact.
- Objective: Run controlled comparison, compute metrics, and present outcomes clearly in the frontend.

### Milestones
1. Execute baseline full-session collection and processing flow.
2. Execute post-baseline clip-based collection flow.
3. Compute and compare phase metrics.
4. Publish findings through frontend visualizations and narrative updates.

### Requirements covered
- M-4.10, M-4.11, M-4.12
- M-4.20, M-4.21
- M-4.30, M-4.31, M-4.32
- M-4.40, M-4.41, M-4.42
- M-9.50, M-9.51, M-9.52

### Corresponding tests
- TP-86 to TP-92
- TP-81 (frontend comparison rendering)

---

## Coverage Index (Global Completeness Check)

### Constraints covered in this plan
- C-1.10, C-1.11, C-1.12, C-1.13

### Requirement coverage in this plan
- M-1.10 through M-1.22
- M-2.10 through M-2.14
- M-3.10 through M-3.31
- M-4.10 through M-4.42
- M-5.10 through M-5.22
- M-6.10 through M-6.31
- M-7.10 through M-7.14
- M-8.10 through M-8.12
- M-9.10 through M-9.52
- M-10.10, M-10.20, M-10.21, M-10.30, M-10.31, M-10.32, M-10.33

### Test coverage in this plan
- TP-01 through TP-92

