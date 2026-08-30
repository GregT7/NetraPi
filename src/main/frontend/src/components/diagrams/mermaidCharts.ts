export const HARDWARE_CHART = `flowchart LR
  subgraph capture[" "]
    direction TB
    Mount@{ icon: "mdi:car-windshield", form: "rounded", label: "Windshield Mount" }
    Cam@{ icon: "mdi:cctv", form: "rounded", label: "Arducam USB" }
    Mount --- Cam
  end
  subgraph hub[" "]
    direction TB
    Pi@{ icon: "logos:raspberry-pi", form: "rounded", label: "Raspberry Pi 5" }
    Battery@{ icon: "mdi:battery-charging", form: "rounded", label: "Portable Battery" }
    Pi ---|"Power Cord"| Battery
  end
  subgraph extras[" "]
    direction TB
    Coral@{ icon: "logos:tensorflow", form: "rounded", label: "Coral USB TPU" }
    Hotspot@{ icon: "mdi:wifi", form: "rounded", label: "Cellular Hotspot" }
    S3@{ icon: "logos:aws-s3", form: "rounded", label: "AWS S3" }
    Phone@{ icon: "mdi:cellphone", form: "rounded", label: "Phone" }
    Hotspot --- S3
    Hotspot --- Phone
  end
  Cam ---|USB| Pi
  Pi ---|USB| Coral
  Pi --- Hotspot
  style capture fill:none,stroke:none
  style hub fill:none,stroke:none
  style extras fill:none,stroke:none`

export const SOFTWARE_CHART = `flowchart LR
  subgraph edge [Edge Pi]
    direction TB
    Capture@{ icon: "logos:opencv", form: "rounded", label: "OpenCV" }
    Detect@{ icon: "logos:tensorflow", form: "rounded", label: "TFLite Coral" }
    LocalDb@{ icon: "logos:sqlite", form: "rounded", label: "SQLite" }
  end
  subgraph schema [Persistence]
    direction TB
    Sqla@{ icon: "logos:sqlalchemy", form: "rounded", label: "SQLAlchemy" }
    Sqlm@{ icon: "logos:sqlmodel", form: "rounded", label: "SQLModel" }
    Alembic@{ icon: "logos:python", form: "rounded", label: "Alembic" }
  end
  subgraph backend [Backend]
    direction TB
    Render@{ icon: "logos:render", form: "rounded", label: "Render" }
    Api@{ icon: "logos:fastapi", form: "rounded", label: "FastAPI" }
    Uvicorn@{ icon: "logos:uvicorn", form: "rounded", label: "Uvicorn" }
    Dock@{ icon: "logos:docker-icon", form: "rounded", label: "Docker" }
  end
  subgraph cloud [Cloud]
    direction TB
    S3@{ icon: "logos:aws-s3", form: "rounded", label: "S3" }
    Supabase@{ icon: "logos:supabase-icon", form: "rounded", label: "Supabase" }
  end
  subgraph frontend [Frontend]
    direction TB
    Vercel@{ icon: "logos:vercel", form: "rounded", label: "Vercel" }
    Spa@{ icon: "logos:react", form: "rounded", label: "React" }
    Ts@{ icon: "logos:typescript", form: "rounded", label: "TypeScript" }
    Vite@{ icon: "logos:vitejs", form: "rounded", label: "Vite" }
    Tw@{ icon: "logos:tailwindcss", form: "rounded", label: "Tailwind" }
    Shad@{ icon: "logos:shadcn", form: "rounded", label: "Shadcn" }
  end
  edge --- backend
  backend --- cloud
  frontend --- backend
  schema --- edge
  schema --- cloud`
