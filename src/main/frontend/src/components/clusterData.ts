const LABEL_COLORS = {
  'Complete stop': '#34d399',
  'Rolling stop': '#fbbf24',
  'Run-through': '#fb7185',
  Unrelated: '#38bdf8',
} as const

type Label = keyof typeof LABEL_COLORS

type Point = { x: number; y: number; label: Label }

function mulberry32(seed: number) {
  let state = seed
  return () => {
    state = (state + 0x6d2b79f5) | 0
    let t = Math.imul(state ^ (state >>> 15), 1 | state)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const clusterSeeds: { label: Label; cx: number; cy: number; spreadX: number; spreadY: number; n: number }[] =
  [
    { label: 'Complete stop', cx: 0.12, cy: 9, spreadX: 0.06, spreadY: 1.6, n: 22 },
    { label: 'Rolling stop', cx: 0.42, cy: 11, spreadX: 0.08, spreadY: 1.8, n: 20 },
    { label: 'Run-through', cx: 0.78, cy: 10, spreadX: 0.09, spreadY: 1.7, n: 20 },
    { label: 'Unrelated', cx: 0.28, cy: 2.4, spreadX: 0.1, spreadY: 0.9, n: 22 },
  ]

function buildPoints(): Point[] {
  const rand = mulberry32(50)
  const points: Point[] = []
  for (const cluster of clusterSeeds) {
    for (let i = 0; i < cluster.n; i += 1) {
      points.push({
        label: cluster.label,
        x: Math.max(0, cluster.cx + (rand() - 0.5) * 2 * cluster.spreadX),
        y: Math.max(0.2, cluster.cy + (rand() - 0.5) * 2 * cluster.spreadY),
      })
    }
  }
  return points
}

export const CLUSTER_POINTS = buildPoints()
export { LABEL_COLORS }
