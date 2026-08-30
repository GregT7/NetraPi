import type { ReactNode } from 'react'

const MOTION =
  'M10 50 L26 46 L42 34 L58 18 L74 26 L90 44 L106 56 L122 48 L138 44 L158 42'

function Plot({ children }: { children: ReactNode }) {
  return (
    <svg aria-hidden className="h-24 w-full" viewBox="0 0 168 72">
      <rect fill="#18181b" height="72" rx="8" width="168" />
      {children}
    </svg>
  )
}

function MeanVisual() {
  return (
    <Plot>
      <path d={MOTION} fill="none" stroke="#fbbf24" strokeWidth="2" />
      <line
        stroke="#e4e4e7"
        strokeDasharray="4 3"
        strokeWidth="1.5"
        x1="10"
        x2="158"
        y1="40"
        y2="40"
      />
      <text fill="#d4d4d8" fontSize="9" x="12" y="36">
        mean
      </text>
    </Plot>
  )
}

function MinVisual() {
  return (
    <Plot>
      <path d={MOTION} fill="none" stroke="#fbbf24" strokeWidth="2" />
      <line stroke="#34d399" strokeWidth="1.25" x1="58" x2="58" y1="18" y2="64" />
      <circle cx="58" cy="18" fill="#34d399" r="3.5" />
      <text fill="#34d399" fontSize="9" x="64" y="16">
        min
      </text>
    </Plot>
  )
}

function P95Visual() {
  return (
    <Plot>
      <path d={MOTION} fill="none" stroke="#fbbf24" strokeWidth="2" />
      <line
        stroke="#fb7185"
        strokeDasharray="4 3"
        strokeWidth="1.5"
        x1="10"
        x2="158"
        y1="52"
        y2="52"
      />
      <circle cx="106" cy="56" fill="#3f3f46" r="3" stroke="#71717a" strokeWidth="1.25" />
      <text fill="#fb7185" fontSize="9" x="12" y="48">
        p95
      </text>
    </Plot>
  )
}

function StopVisual() {
  return (
    <Plot>
      <line
        stroke="#3f3f46"
        strokeDasharray="3 3"
        x1="10"
        x2="158"
        y1="38"
        y2="38"
      />
      <rect fill="#34d399" fillOpacity="0.35" height="26" width="44" x="10" y="38" />
      <rect fill="#34d399" fillOpacity="0.35" height="26" width="28" x="86" y="38" />
      <path d={MOTION} fill="none" stroke="#fbbf24" strokeWidth="2" />
      <text fill="#d4d4d8" fontSize="9" x="12" y="34">
        stop threshold
      </text>
    </Plot>
  )
}

function SignAreaVisual() {
  return (
    <Plot>
      <path
        d="M10 62 L28 58 L46 40 L64 18 L82 22 L100 38 L118 52 L136 58 L158 62 L158 62 L10 62 Z"
        fill="#38bdf8"
        fillOpacity="0.35"
        stroke="#38bdf8"
        strokeWidth="2"
      />
      <line stroke="#fafafa" strokeDasharray="3 3" strokeWidth="1.25" x1="82" x2="82" y1="16" y2="62" />
      <text fill="#fafafa" fontSize="9" x="86" y="16">
        T0
      </text>
    </Plot>
  )
}

function Badge({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-full border border-zinc-600 px-2 py-0.5 text-[11px] text-zinc-400">
      {children}
    </span>
  )
}

const FEATURES = [
  {
    title: 'Mean Motion',
    stages: 'Stage 1',
    visual: <MeanVisual />,
    body: 'Average motion in the 5 s after T0. Lower means the scene stayed still.',
  },
  {
    title: 'Min Motion',
    stages: 'Stage 1 and 2',
    visual: <MinVisual />,
    body: 'Lowest motion in the 5 s window. Stage 2 reads this number again, paired with sign area.',
  },
  {
    title: 'P95 Motion',
    stages: 'Stage 1',
    visual: <P95Visual />,
    body: 'A high-but-typical value (95th percentile), so a brief jolt does not dominate.',
  },
  {
    title: 'Stop Fraction',
    stages: 'Stage 1',
    visual: <StopVisual />,
    body: 'Share of the window where motion is low enough to count as stopped.',
  },
  {
    title: 'Sign Area',
    stages: 'Stage 2',
    visual: <SignAreaVisual />,
    body: 'How large the stop sign got on the approach (sum of box size from start through T0).',
  },
] as const

export default function FeatureGuide() {
  return (
    <div className="space-y-4">
      <h3 className="text-xl font-medium text-zinc-50">The five features</h3>
      <p>
        The traces above are not what kNN sees. After an approach, the Pi
        compresses the clip into five numbers. Stage 1 uses four of them — all
        motion after T0 — to split Complete Stop vs Unsafe. Stage 2 only runs
        on Unsafe and uses two numbers: min motion (again) plus sign area from
        the approach.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        {FEATURES.map((feature) => (
          <article
            className="rounded-lg border border-zinc-700 bg-zinc-950 p-4"
            key={feature.title}
          >
            <div className="mb-3 flex items-start justify-between gap-2">
              <h4 className="font-medium text-zinc-50">{feature.title}</h4>
              <Badge>{feature.stages}</Badge>
            </div>
            {feature.visual}
            <p className="mt-3 text-sm text-zinc-400">{feature.body}</p>
          </article>
        ))}
      </div>
    </div>
  )
}
