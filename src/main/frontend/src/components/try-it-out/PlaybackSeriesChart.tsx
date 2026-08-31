import { type RefObject } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

type ChartPoint = { t: number; value: number }

type PlaybackSeriesChartProps = {
  color: string
  emptyLabel: string
  playheadRef: RefObject<HTMLDivElement | null>
  points: ChartPoint[]
  title: string
  xMax: number
  yLabel: string
}

const AXIS_TEXT = { fill: '#d4d4d8', fontSize: 11 }

function formatValue(value: number | string) {
  const n = Number(value)
  return Number.isFinite(n) ? n.toFixed(2) : String(value)
}

export default function PlaybackSeriesChart({
  color,
  emptyLabel,
  playheadRef,
  points,
  title,
  xMax,
  yLabel,
}: PlaybackSeriesChartProps) {
  if (points.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-3 text-center text-sm text-zinc-400">
        {emptyLabel}
      </div>
    )
  }
  const domainMax = Math.max(xMax, points[points.length - 1]?.t ?? 0, 0.01)
  return (
    <div className="relative h-full min-h-0">
      <p className="absolute left-0 right-0 top-0 z-10 text-center text-xs font-medium text-zinc-200">
        {title}
      </p>
      <div className="h-full pt-5">
        <ResponsiveContainer height="100%" width="100%">
          <LineChart data={points} margin={{ bottom: 4, left: 4, right: 8, top: 8 }}>
            <CartesianGrid stroke="#3f3f46" strokeDasharray="3 3" />
            <XAxis
              dataKey="t"
              domain={[0, domainMax]}
              stroke="#a1a1aa"
              tick={AXIS_TEXT}
              tickFormatter={formatValue}
              type="number"
            />
            <YAxis
              stroke={color}
              tick={AXIS_TEXT}
              tickFormatter={formatValue}
              width={40}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#09090b',
                border: '1px solid #fbbf24',
                color: '#fafafa',
                fontSize: 12,
              }}
              formatter={(value) => formatValue(value as number)}
              labelFormatter={(label) => `Time (s): ${formatValue(label)}`}
            />
            <Line
              dataKey="value"
              dot={false}
              isAnimationActive={false}
              name={yLabel}
              stroke={color}
              strokeWidth={2}
              type="monotone"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div
        aria-hidden
        className="pointer-events-none absolute bottom-5 top-7 w-px bg-zinc-50"
        ref={playheadRef}
        style={{ left: '48px' }}
      />
      <span className="sr-only">{yLabel}</span>
    </div>
  )
}
