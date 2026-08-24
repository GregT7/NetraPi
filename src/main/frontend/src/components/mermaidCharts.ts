export const HARDWARE_CHART = `flowchart TB
  Mount@{ icon: "mdi:car-windshield", form: "rounded", label: "Windshield mount" }
  Cam@{ icon: "mdi:cctv", form: "rounded", label: "Arducam USB" }
  Pi@{ icon: "logos:raspberry-pi", form: "rounded", label: "Raspberry Pi 5" }
  Coral@{ icon: "logos:tensorflow", form: "rounded", label: "Coral USB TPU" }
  Hotspot@{ icon: "mdi:wifi", form: "rounded", label: "Cellular hotspot" }
  S3@{ icon: "logos:aws-s3", form: "rounded", label: "AWS S3" }
  Phone@{ icon: "mdi:cellphone", form: "rounded", label: "Phone" }
  Cord@{ icon: "mdi:power-plug", form: "rounded", label: "Pi power cord" }
  Battery@{ icon: "mdi:battery-charging", form: "rounded", label: "Portable battery" }
  Mount --- Cam
  Cam -->|"USB"| Pi
  Pi -->|"USB"| Coral
  Pi --> Hotspot
  Hotspot --> S3
  Hotspot --> Phone
  Pi --> Cord
  Cord --> Battery`

export const SOFTWARE_CHART = `flowchart TB
  subgraph edge [Edge Pi]
    direction LR
    Capture@{ icon: "logos:opencv", form: "rounded", label: "OpenCV" }
    Detect@{ icon: "logos:tensorflow", form: "rounded", label: "TFLite Coral" }
    LocalDb@{ icon: "logos:sqlite", form: "rounded", label: "SQLite" }
  end
  subgraph backend [Backend Render]
    direction LR
    Api@{ icon: "logos:fastapi", form: "rounded", label: "FastAPI" }
    Dock@{ icon: "logos:docker-icon", form: "rounded", label: "Docker" }
  end
  subgraph cloud [Cloud]
    direction LR
    S3@{ icon: "logos:aws-s3", form: "rounded", label: "S3" }
    Supabase@{ icon: "logos:supabase-icon", form: "rounded", label: "Supabase" }
  end
  subgraph frontend [Frontend Vercel]
    direction LR
    Spa@{ icon: "logos:react", form: "rounded", label: "React" }
    Vite@{ icon: "logos:vitejs", form: "rounded", label: "Vite" }
    Tw@{ icon: "logos:tailwindcss", form: "rounded", label: "Tailwind" }
    Shad@{ icon: "logos:shadcn", form: "rounded", label: "shadcn" }
  end
  SharedDb@{ icon: "logos:python", form: "rounded", label: "SQLModel" }
  edge --> backend
  backend --> cloud
  frontend --> backend
  SharedDb --- edge
  SharedDb --- cloud`
