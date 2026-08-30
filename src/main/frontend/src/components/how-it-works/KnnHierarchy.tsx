import { useEffect, useRef, useState, type ReactNode } from 'react'

type NodeId =
  | 'polling'
  | 'detected'
  | 'collect'
  | 'stage1'
  | 'complete'
  | 'unsafe'
  | 'stage2'
  | 'rolling'
  | 'runThrough'

type NodeDef = {
  title: string
  body: ReactNode
  accent?: string
  filled?: boolean
  diamond?: boolean
}

const NODES: Record<NodeId, NodeDef> = {
  polling: {
    title: 'Keep Polling',
    body: (
      <p>
        Idle loop. Watches each frame for a stop sign. Classification does not
        run until an approach is detected.
      </p>
    ),
  },
  detected: {
    title: 'Approach Detected?',
    diamond: true,
    body: (
      <p>
        True if the stop sign grew then shrank in the frame. False if not —
        go back to Keep Polling. Labeled unrelated clips in the test set are
        this False branch: the sign was in view, but it was not a real stop.
      </p>
    ),
  },
  collect: {
    title: 'Collect Motion (5 s)',
    body: (
      <p>
        After the approach drop (T0), the Pi records motion for 5 seconds.
        Those numbers go to stage 1.
      </p>
    ),
  },
  stage1: {
    title: 'Stage 1 KNN',
    body: (
      <>
        <p>
          K-nearest neighbors with k=3. Looks at motion in a short window after
          the approach ends (the drop). Splits Complete Stop vs Unsafe.
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>
            <span className="font-medium text-zinc-100">Mean motion</span> —
            average motion in that window. Lower means the scene stayed still.
          </li>
          <li>
            <span className="font-medium text-zinc-100">Min motion</span> — the
            quietest moment in the window. A full stop drives this down.
          </li>
          <li>
            <span className="font-medium text-zinc-100">P95 motion</span> — a
            high-but-typical motion value (95th percentile), so a brief jolt
            does not dominate.
          </li>
          <li>
            <span className="font-medium text-zinc-100">Stop fraction</span> —
            share of the window where motion is low enough to count as stopped.
          </li>
        </ul>
      </>
    ),
  },
  complete: {
    title: 'Complete Stop',
    accent: '#34d399',
    filled: true,
    body: (
      <p>Stage 1 says the vehicle stopped. Stage 2 does not run.</p>
    ),
  },
  unsafe: {
    title: 'Unsafe',
    accent: '#f97316',
    body: (
      <p>
        Stage 1 says it was not a complete stop. Stage 2 then splits Rolling
        Stop vs Run-Through.
      </p>
    ),
  },
  stage2: {
    title: 'Stage 2 KNN',
    body: (
      <>
        <p>k=3 again. Only runs on the Unsafe branch.</p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>
            <span className="font-medium text-zinc-100">Min motion</span> —
            same quietest-moment number from stage 1. Rolling stops tend to be
            lower than run-throughs.
          </li>
          <li>
            <span className="font-medium text-zinc-100">Sign area</span> — how
            large the stop sign got during the approach (sum of sign-box size).
            Used with min motion to separate rolling from run-through.
          </li>
        </ul>
      </>
    ),
  },
  rolling: {
    title: 'Rolling Stop',
    accent: '#fbbf24',
    filled: true,
    body: <p>Slowed a lot but did not fully stop.</p>,
  },
  runThrough: {
    title: 'Run-Through',
    accent: '#fb7185',
    filled: true,
    body: <p>Did not slow enough at the sign.</p>,
  },
}

function ArrowDown() {
  return (
    <div
      aria-hidden
      className="-mt-px h-0 w-0 border-x-[4px] border-t-[6px] border-x-transparent border-t-zinc-400"
    />
  )
}

function Stem({ arrow = true }: { arrow?: boolean }) {
  return (
    <div aria-hidden className="flex shrink-0 flex-col items-center">
      <div className={`w-px bg-zinc-400 ${arrow ? 'h-4' : 'h-5'}`} />
      {arrow ? <ArrowDown /> : null}
    </div>
  )
}

function HangLeftRow({
  left,
  center,
}: {
  left: ReactNode
  center: ReactNode
}) {
  return (
    <div className="w-full">
      <div className="flex justify-center">
        <Stem arrow={false} />
      </div>
      <div className="grid grid-cols-3">
        <div className="relative flex min-w-0 flex-col items-center">
          <div
            aria-hidden
            className="absolute top-0 right-0 left-1/2 h-px bg-zinc-400"
          />
          <Stem />
          {left}
        </div>
        <div className="relative flex min-w-0 flex-col items-center">
          <div
            aria-hidden
            className="absolute top-0 right-1/2 left-0 h-px bg-zinc-400"
          />
          <Stem />
          {center}
        </div>
        <div />
      </div>
    </div>
  )
}

function SplitRow({ left, right }: { left: ReactNode; right: ReactNode }) {
  return (
    <div className="w-full">
      <div className="flex justify-center">
        <Stem arrow={false} />
      </div>
      <div className="grid grid-cols-3">
        <div className="relative flex min-w-0 flex-col items-center">
          <div
            aria-hidden
            className="absolute top-0 right-0 left-1/2 h-px bg-zinc-400"
          />
          <Stem />
          {left}
        </div>
        <div className="relative">
          <div
            aria-hidden
            className="absolute top-0 right-0 left-0 h-px bg-zinc-400"
          />
        </div>
        <div className="relative flex min-w-0 flex-col items-center">
          <div
            aria-hidden
            className="absolute top-0 right-1/2 left-0 h-px bg-zinc-400"
          />
          <Stem />
          {right}
        </div>
      </div>
    </div>
  )
}

function Card({ open, children }: { open: boolean; children: ReactNode }) {
  if (!open) {
    return null
  }
  return (
    <div
      className="absolute top-full z-10 mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-lg border border-amber-400 bg-zinc-950 p-3 text-left text-sm leading-relaxed text-zinc-300 shadow-lg"
      role="region"
    >
      {children}
    </div>
  )
}

function NodeBox({
  id,
  open,
  onToggle,
}: {
  id: NodeId
  open: boolean
  onToggle: (id: NodeId) => void
}) {
  const node = NODES[id]
  const accent = node.accent ?? '#f59e0b'

  if (node.diamond) {
    return (
      <div className="relative flex h-44 w-44 flex-col items-center">
        <button
          aria-expanded={open}
          className="group relative flex h-44 w-44 items-center justify-center bg-transparent"
          onClick={() => onToggle(id)}
          type="button"
        >
          <span
            aria-hidden
            className="absolute top-1/2 left-1/2 h-[7.75rem] w-[7.75rem] -translate-x-1/2 -translate-y-1/2 rotate-45 rounded-sm border bg-zinc-900 group-hover:bg-zinc-800"
            style={{ borderColor: accent }}
          />
          <span className="relative z-10 max-w-[7.5rem] text-center text-sm font-medium leading-snug text-zinc-50">
            {node.title}
          </span>
        </button>
        <Card open={open}>{node.body}</Card>
      </div>
    )
  }

  return (
    <div className="relative flex w-[min(100%,11rem)] flex-col items-center">
      <button
        aria-expanded={open}
        className={`w-full rounded-lg border px-3 py-2 text-center text-sm font-medium ${
          node.filled
            ? 'text-zinc-950 hover:brightness-110'
            : 'bg-zinc-900 text-zinc-50 hover:bg-zinc-800'
        }`}
        onClick={() => onToggle(id)}
        style={{
          backgroundColor: node.filled ? accent : undefined,
          borderColor: accent,
        }}
        type="button"
      >
        {node.title}
      </button>
      <Card open={open}>{node.body}</Card>
    </div>
  )
}

export default function KnnHierarchy() {
  const rootRef = useRef<HTMLDivElement>(null)
  const [openId, setOpenId] = useState<NodeId | null>(null)

  useEffect(() => {
    function onPointerDown(event: PointerEvent) {
      const target = event.target
      if (!(target instanceof Element)) {
        setOpenId(null)
        return
      }
      const card = rootRef.current?.querySelector('[role="region"]')
      if (card?.contains(target)) {
        return
      }
      const nodeButton = target.closest('button')
      if (nodeButton && rootRef.current?.contains(nodeButton)) {
        return
      }
      setOpenId(null)
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpenId(null)
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [])

  function toggle(id: NodeId) {
    setOpenId((current) => (current === id ? null : id))
  }

  const box = (id: NodeId) => (
    <NodeBox id={id} open={openId === id} onToggle={toggle} />
  )

  return (
    <div
      className="mx-auto flex w-full max-w-2xl flex-col items-center px-14 text-sm"
      ref={rootRef}
    >
      <div className="relative flex flex-col items-center">
        <div
          aria-hidden
          className="absolute top-5 -left-12 bottom-[5.5rem] w-12 rounded-l-md border-t border-b border-l border-zinc-400"
        />
        <div
          aria-hidden
          className="absolute top-5 left-0 h-0 w-0 -translate-x-px -translate-y-1/2 border-y-[5px] border-l-[7px] border-y-transparent border-l-zinc-400"
        />
        <span className="absolute -left-10 bottom-[5.65rem] text-[11px] text-zinc-400">
          False
        </span>
        {box('polling')}
        <Stem />
        {box('detected')}
      </div>
      <div className="relative flex flex-col items-center">
        <Stem />
        <span className="absolute top-1 left-[calc(50%+0.4rem)] text-[11px] text-zinc-400">
          True
        </span>
      </div>
      {box('collect')}
      <Stem />
      {box('stage1')}
      <HangLeftRow left={box('complete')} center={box('unsafe')} />
      <Stem />
      {box('stage2')}
      <SplitRow left={box('rolling')} right={box('runThrough')} />
    </div>
  )
}
