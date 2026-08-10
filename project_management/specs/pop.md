# Project Overview Proposal

## 1. Proposed Project Name
NetraPi -- Homemade Raspberry pi implementation of the AI monitoring dashcam created from Netradyne and used in Amazon delivery vans

## 2. Elevator Pitch
This project is motivated by three factors: improving driving safety, strengthening end-to-end engineering competency, and following through on a scoped technical commitment.

### Safety
While working as a delivery driver for an Amazon Delivery Service Partner, I was continuously monitored by a Netradyne AI dashcam system designed to detect unsafe driving behavior. Exposure to this system forced my driving competency to drastically improve. However, the longer I went without the driving system, the weaker my driving skills got. This project aims to restrengthen this skillset by targeting one easily identifiable bad habit made while driving and try to improve it.

### Competency
Prior to full-time employment, I had attended some career fairs but didn't have much success. Moreover, I completed 100s of applications without getting an internship offer so I figured I needed to do something different. One great way of improving the odds of being selected for a job is by creating a great developer portfolio. With this in mind, I had the idea of replicating the camera system which had potential to be very technical and nice looking on a resume. I bought the equipment and deferred the development of this project until now.

### Follow-through
Although the original career-driven incentive for this project changed after gaining employment, completing NetraPi remains valuable as a disciplined engineering exercise. The project explicitly applies lessons learned from PlanGauge—particularly scope hardening, value extraction, and finishing criteria—to ensure the system is completed, validated, and documented without unnecessary expansion.

---

## 3. Complexity
### 3.1 Physical Configuration (Required)
- Mount a forward-facing camera with a stable road view
- Securely install Raspberry Pi 5, Coral USB TPU, wiring, and power source inside the vehicle
- Manage power safely (portable battery or regulated vehicle power)
- Allow quick removal of the device (e.g., Velcro or quick disconnect)

### 3.2 Safety Event Detection (Edge – Minimal)
- Capture continuous video using a rolling buffer
- Detect **a single, system-defined driving control event** (e.g., abrupt deceleration / hard braking)
- Run on-device inference using:
  - TensorFlow Lite (`tflite-runtime`)
  - `pycoral` Edge TPU delegate
  - TPU-compiled `.tflite` models (or lightweight heuristics where appropriate)
- Extract pre/post-event video clips
- Log event metadata locally
- Continue capture/detection offline; upload clips one at a time when connectivity is available (no offline upload queue)

> Explicitly out of scope:
> - Speeding detection
> - Traffic signal or stop sign violations
> - Multi-class driving behavior detection

### 3.3 Local Persistence (Required)
- Store event metadata in **SQLite** on the device
- Follow proper db migration practices using Liquibase.
- Retain event clips on disk until a direct upload is performed when online

### 3.4 Cloud Storage (Required)
- Store video clips in **AWS S3** private buckets
- Prevent public access to raw media
- Serve clips via **time-limited signed URLs**
- Apply a simple, fixed retention policy (e.g., time-based TTL)

### 3.5 Backend API (Required)
- Cloud-deployed **FastAPI** service
- Ingest authenticated edge-device uploads
- Enforce device-level authentication via API keys
- Persist structured metadata to the database
- Generate signed URLs for secure video playback
- Expose **read-only** endpoints for analytics and demo viewing

### 3.6 Database (Required)
- **Supabase PostgreSQL** for structured event metadata and baseline analytics
- Support basic aggregate queries (events per session, events per hour)

### 3.7 Web Frontend (Minimal Analytics)
- Hosted **React** web application
- Display:
  - Event list
  - Event frequency per session
  - Simple distributions and counts
- Use **Recharts** for data visualization
- Support a public demo view using sanitized or sample data

> Explicitly out of scope:
> - Advanced trend analysis
> - Multi-user roles or RBAC
> - Complex longitudinal dashboards

### 3.8 Deployment & Reliability (Required)
- Deploy backend API to **Render** using Docker
- Host frontend on **Vercel** as a static application
- Run edge software as a **systemd** service on the Raspberry Pi


### 3.9 CI/CD (Minimal)
- **GitHub Actions** for:
  - Linting
  - Basic tests
  - Build checks
- Automated backend deployments on merge to main
- Automated frontend deployments via Vercel

---

## Minimal Tech Stack (Deployed)
- **Edge:** Raspberry Pi 5 running a Python service with TensorFlow Lite (`tflite-runtime`) and `pycoral` accelerated by a Google Coral USB TPU for real-time inference; OpenCV for continuous video capture and pre/post-event clip extraction; SQLite for local event metadata; and `systemd` for reliable boot-time startup and recovery. Cloud uploads are direct and one-at-a-time when connectivity is available (no offline upload queue).
- **Cloud (Supabase + AWS):** Supabase PostgreSQL for structured event metadata and analytics, paired with AWS S3 for scalable, private video clip storage, keeping large media assets decoupled from relational data and served securely via time-limited signed URLs.
- **Backend:** FastAPI service containerized with Docker and deployed on Render, responsible for ingesting authenticated edge device uploads, enforcing device-level API key authentication, generating signed URLs for secure clip playback from AWS S3, and exposing read-only analytics endpoints. SQLLite will be used to store the data locally.
- **Frontend:** React web application styled with Tailwind CSS and deployed on Vercel, using Recharts for analytics visualizations (event frequency, session distributions), with support for secure clip playback and a public demo mode.
- **CI/CD:** GitHub Actions for continuous integration (tests, linting, basic integration checks), automated Docker-based backend deployments to Render on merge to main, static frontend deployments to Vercel.
- **Database**: SQLite for local data storage and Liquibase for db versioning.

---

## Definition of Done (Hard Stop)
- One driving control event detected reliably
- Baseline metrics collected from real-world driving data
- End-to-end pipeline functional (edge → cloud → dashboard)
- Resume bullet points fully supported by implemented functionality