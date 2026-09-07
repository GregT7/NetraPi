import pca from './stage1Pca.json'
import stage1Features from './stage1Features.json'
import points from './clipPoints.json'

const LABEL_COLORS = {
  'Complete stop': '#34d399',
  Unsafe: '#f97316',
  'Rolling stop': '#fbbf24',
  'Run-through': '#fb7185',
  Unrelated: '#38bdf8',
} as const

export const LABEL_ORDER = [
  'Complete stop',
  'Unsafe',
  'Rolling stop',
  'Run-through',
  'Unrelated',
] as const

export const LABEL_DISPLAY: Record<(typeof LABEL_ORDER)[number], string> = {
  'Complete stop': 'Complete Stop',
  Unsafe: 'Unsafe',
  'Rolling stop': 'Rolling Stop',
  'Run-through': 'Run-through Stop',
  Unrelated: 'Unrelated',
}

type Label = keyof typeof LABEL_COLORS

export type ClusterPoint = { x: number; y: number; label: Label; clipId: number }

function asStage1Label(label: string): Label {
  if (label === 'Rolling / run-through') {
    return 'Unsafe'
  }
  return label as Label
}

export const STAGE1_FEATURE_KEYS = [
  'post_drop_mean_motion',
  'post_drop_min_motion',
  'post_drop_p95_motion',
  'post_drop_stop_fraction',
] as const

export type Stage1FeatureKey = (typeof STAGE1_FEATURE_KEYS)[number]

export const STAGE1_FEATURE_LABELS: Record<Stage1FeatureKey, string> = {
  post_drop_mean_motion: 'Mean Motion',
  post_drop_min_motion: 'Minimum Motion',
  post_drop_p95_motion: 'P95 Motion',
  post_drop_stop_fraction: 'Stop Fraction',
}

export const STAGE1_FEATURE_PAIRS = [
  ['post_drop_mean_motion', 'post_drop_min_motion'],
  ['post_drop_mean_motion', 'post_drop_p95_motion'],
  ['post_drop_mean_motion', 'post_drop_stop_fraction'],
  ['post_drop_min_motion', 'post_drop_p95_motion'],
  ['post_drop_min_motion', 'post_drop_stop_fraction'],
  ['post_drop_p95_motion', 'post_drop_stop_fraction'],
] as const satisfies ReadonlyArray<readonly [Stage1FeatureKey, Stage1FeatureKey]>

type Stage1FeatureRow = {
  clipId: number
  label: Label
} & Record<Stage1FeatureKey, number>

const STAGE1_FEATURE_ROWS = stage1Features as Stage1FeatureRow[]

export function stage1PairPoints(
  xKey: Stage1FeatureKey,
  yKey: Stage1FeatureKey,
): ClusterPoint[] {
  return STAGE1_FEATURE_ROWS.map((row) => ({
    clipId: row.clipId,
    label: asStage1Label(row.label),
    x: row[xKey],
    y: row[yKey],
  }))
}

export const CLUSTER_POINTS = (points as ClusterPoint[]).filter(
  (point) => point.label === 'Rolling stop' || point.label === 'Run-through',
)
export const STAGE1_PCA_POINTS = (pca.points as ClusterPoint[]).map((point) => ({
  ...point,
  label: asStage1Label(point.label),
}))
export const STAGE1_PCA_VARIANCE = pca.explainedVariance as [number, number]
export { LABEL_COLORS }
