import { type RefObject } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

type SeriesPoint = { t: number; value: number }

type PlaybackSeriesChartProps = {
  areaPoints: SeriesPoint[]
  emptyLabel: string
  motionPoints: SeriesPoint[]
  playheadOff: boolean
  playheadRef: RefObject<HTMLDivElement | null>
  xMax: number
}

type ChartRow = { t: number; area?: number; motion?: number }

const AXIS_TEXT = { fill: '#d4d4d8', fontSize: 11 }
const AREA_COLOR = '#38bdf8'
const MOTION_COLOR = '#fbbf24'

function formatValue(value: number | string) {
  const n = Number(value)
  return Number.isFinite(n) ? n.toFixed(2) : String(value)
}

function mergeSeries(areaPoints: SeriesPoint[], motionPoints: SeriesPoint[]): ChartRow[] {
  const byT = new Map<number, ChartRow>()
  for (const point of areaPoints) {
    byT.set(point.t, { t: point.t, area: point.value })
  }
  for (const point of motionPoints) {
    const existing = byT.get(point.t)
    if (existing) {
      existing.motion = point.value
    } else {
      byT.set(point.t, { t: point.t, motion: point.value })
    }
  }
  return [...byT.values()]
    .filter((row) => row.t >= 0)
    .sort((left, right) => left.t - right.t)
}

function windowedSeries(points: ChartRow[], xMax: number): ChartRow[] {
  const rows = points.filter((row) => row.t <= xMax)
  if (rows.length === 0) {
    return rows
  }
  if (rows[0].t > 0) {
    rows.unshift({ t: 0 })
  }
  if (rows[rows.length - 1].t < xMax) {
    rows.push({ t: xMax })
  }
  return rows
}

export default function PlaybackSeriesChart({
  areaPoints,
  emptyLabel,
  motionPoints,
  playheadOff,
  playheadRef,
  xMax,
}: PlaybackSeriesChartProps) {
  const domainMax = Math.max(xMax, 0.01)
  const points = windowedSeries(mergeSeries(areaPoints, motionPoints), domainMax)
  if (points.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-3 text-center text-sm text-zinc-400">
        {emptyLabel}
      </div>
    )
  }
  return (
    <div className="relative h-full min-h-0 overflow-hidden">
      <p className="absolute left-0 right-0 top-0 z-10 text-center text-xs font-medium text-zinc-200">
        Sign Area and Motion
      </p>
      <div className="h-full pt-5">
        <ResponsiveContainer height="100%" width="100%">
          <LineChart
            data={points}
            margin={{ bottom: 4, left: 4, right: 8, top: 8 }}
          >
            <CartesianGrid stroke="#3f3f46" strokeDasharray="3 3" />
            <XAxis
              allowDataOverflow
              dataKey="t"
              domain={[0, domainMax]}
              includeHidden
              stroke="#a1a1aa"
              tick={AXIS_TEXT}
              tickFormatter={formatValue}
              type="number"
            />
            <YAxis
              stroke={AREA_COLOR}
              tick={AXIS_TEXT}
              tickFormatter={formatValue}
              width={40}
              yAxisId="area"
            />
            <YAxis
              orientation="right"
              stroke={MOTION_COLOR}
              tick={AXIS_TEXT}
              tickFormatter={formatValue}
              width={40}
              yAxisId="motion"
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#09090b',
                border: '1px solid #fbbf24',
                color: '#fafafa',
                fontSize: 12,
              }}
              formatter={(value) => formatValue(value as number)}
              labelFormatter={(label) => `Time (s): ${formatValue(label as number)}`}
            />
            <Legend
              align="center"
              iconSize={10}
              verticalAlign="bottom"
              wrapperStyle={{ color: '#d4d4d8', fontSize: 11, paddingTop: 0 }}
            />
            <Line
              connectNulls
              dataKey="area"
              dot={false}
              isAnimationActive={false}
              name="Sign Area (% of Frame)"
              stroke={AREA_COLOR}
              strokeWidth={2}
              type="monotone"
              yAxisId="area"
            />
            <Line
              connectNulls
              dataKey="motion"
              dot={false}
              isAnimationActive={false}
              name="Motion (px / Frame)"
              stroke={MOTION_COLOR}
              strokeWidth={2}
              type="monotone"
              yAxisId="motion"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div
        aria-hidden
        className={`pointer-events-none absolute bottom-8 top-7 w-px bg-zinc-50 ${
          playheadOff ? 'invisible' : ''
        }`}
        ref={playheadRef}
      />
    </div>
  )
}
