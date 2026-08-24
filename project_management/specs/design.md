# Design Specification
**Description:** This file is intended to document the diagrams incorporated in the final design. It provides a concise, visual explanation of the project's functionality.

GitHub’s Mermaid preview cannot register Iconify packs. The landing page uses the same topology with tech logos; this spec uses text labels so the diagrams still preview on GitHub.

## Hardware Architecture Diagram
_Description:_ Raspberry Pi 5 in the center. Arducam on a windshield mount over USB. Coral TPU over USB. Cellular hotspot to S3 and the phone. Pi power cord to a portable battery.

```mermaid
flowchart TB
  Mount[Windshield mount]
  Cam[Arducam USB]
  Pi[Raspberry Pi 5]
  Coral[Coral USB TPU]
  Hotspot[Cellular hotspot]
  S3[AWS S3]
  Phone[Phone]
  Cord[Pi power cord]
  Battery[Portable battery]
  Mount --- Cam
  Cam -->|USB| Pi
  Pi -->|USB| Coral
  Pi --> Hotspot
  Hotspot --> S3
  Hotspot --> Phone
  Pi --> Cord
  Cord --> Battery
```

## Software Architecture Diagram
_Description:_ Larger blocks only: Edge Pi, backend on Render, cloud, and the Vercel frontend. Unlabeled arrows between those blocks. SQLModel is a compact shared-schema node, not a full-width subgraph.

```mermaid
flowchart TB
  subgraph edge [Edge Pi]
    direction LR
    Capture[OpenCV]
    Detect[TFLite Coral]
    LocalDb[SQLite]
  end
  subgraph backend [Backend Render]
    direction LR
    Api[FastAPI]
    Dock[Docker]
  end
  subgraph cloud [Cloud]
    direction LR
    S3[S3]
    Supabase[Supabase]
  end
  subgraph frontend [Frontend Vercel]
    direction LR
    Spa[React]
    Vite[Vite]
    Tw[Tailwind]
    Shad[shadcn]
  end
  SharedDb[SQLModel]
  edge --> backend
  backend --> cloud
  frontend --> backend
  SharedDb --- edge
  SharedDb --- cloud
```

## Physical Installation Layout
_Description:_
