# Design Specification
**Description:** This file is intended to document the diagrams incorporated in the final design. It provides a concise, visual explanation of the project's functionality.

GitHub’s Mermaid preview cannot register Iconify packs. The landing page uses the same topology with tech logos; this spec uses text labels so the diagrams still preview on GitHub.

## Hardware Architecture Diagram
_Description:_ Three columns around the Pi. Camera stack on the left, Pi and battery in the middle (power cord labeled on the line), Coral and network on the right. Links are plain lines, not arrows.

```mermaid
flowchart LR
  subgraph capture[" "]
    direction TB
    Mount[Windshield Mount]
    Cam[Arducam USB]
    Mount --- Cam
  end
  subgraph hub[" "]
    direction TB
    Pi[Raspberry Pi 5]
    Battery[Portable Battery]
    Pi ---|"Power Cord"| Battery
  end
  subgraph extras[" "]
    direction TB
    Coral[Coral USB TPU]
    Hotspot[Cellular Hotspot]
    S3[AWS S3]
    Phone[Phone]
    Hotspot --- S3
    Hotspot --- Phone
  end
  Cam ---|USB| Pi
  Pi ---|USB| Coral
  Pi --- Hotspot
  style capture fill:none,stroke:none
  style hub fill:none,stroke:none
  style extras fill:none,stroke:none
```

## Software Architecture Diagram
_Description:_ GitHub Actions CI/CD sits above the runtime row and links to Render and Vercel. Edge Pi, persistence, backend, cloud, and frontend sit in one horizontal row under that. Each runtime block stacks its tools vertically. Persistence holds SQLAlchemy, SQLModel, and Alembic and links the Pi to the cloud. Other lines are unlabeled.

```mermaid
flowchart TB
  subgraph cicd [CI/CD]
    GHA[GitHub Actions]
  end
  subgraph stack[" "]
    direction LR
    subgraph edge [Edge Pi]
      direction TB
      Capture[OpenCV]
      Detect[TFLite Coral]
      LocalDb[SQLite]
    end
    subgraph schema [Persistence]
      direction TB
      Sqla[SQLAlchemy]
      Sqlm[SQLModel]
      Alembic[Alembic]
    end
    subgraph backend [Backend]
      direction TB
      Render[Render]
      Api[FastAPI]
      Dock[Docker]
    end
    subgraph cloud [Cloud]
      direction TB
      S3[S3]
      Supabase[Supabase]
    end
    subgraph frontend [Frontend]
      direction TB
      Vercel[Vercel]
      Spa[React]
      Ts[TypeScript]
      Tw[Tailwind]
    end
  end
  GHA --- Render
  GHA --- Vercel
  edge --- backend
  backend --- cloud
  frontend --- backend
  schema --- edge
  schema --- cloud
  style stack fill:none,stroke:none
```

## Physical Installation Layout
_Description:_
