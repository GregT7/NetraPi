import {
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { LABEL_COLORS, LABEL_DISPLAY, LABEL_ORDER, type ClusterPoint } from '../data/clusterData'

type ClusterScatterProps = {
  points: ClusterPoint[]
  title: string
  xLabel: string
  yLabel: string
  xDomain?: [number, number]
}

function ticksBetween(min: number, max: number, count = 5): number[] {
  const step = (max - min) / (count - 1)
  return Array.from({ length: count }, (_, index) =>
    Number((min + step * index).toFixed(2)),
  )
}

function formatValue(value: number | string) {
  const n = Number(value)
  return Number.isFinite(n) ? n.toFixed(2) : String(value)
}

const AXIS_TEXT = { fill: '#d4d4d8', fontSize: 12 }
const YAXIS_WIDTH = 44

export default function ClusterScatter({
  points,
  title,
  xLabel,
  yLabel,
  xDomain,
}: ClusterScatterProps) {
  const present = new Set(points.map((point) => point.label))
  const series = LABEL_ORDER.filter((label) => present.has(label)).map((label) => ({
    label,
    color: LABEL_COLORS[label],
    data: points.filter((point) => point.label === label),
  }))

  const plotAlign = { marginLeft: YAXIS_WIDTH }

  return (
    <figure>
      <div className="flex">
        <div className="flex w-12 shrink-0 items-center justify-center">
          <span className="text-sm text-zinc-300 [writing-mode:vertical-rl] rotate-180">
            {yLabel}
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <figcaption
            className="mb-0.5 text-center text-base font-medium text-zinc-50"
            style={plotAlign}
          >
            {title}
          </figcaption>
          <div className="h-104 w-full min-w-[20rem]">
            <ResponsiveContainer height={400} minWidth={320} width="100%">
              <ScatterChart margin={{ bottom: 2, left: 4, right: 12, top: 22 }}>
                <CartesianGrid stroke="#3f3f46" strokeDasharray="3 3" />
                <XAxis
                  allowDataOverflow={Boolean(xDomain)}
                  dataKey="x"
                  domain={xDomain}
                  name={xLabel}
                  stroke="#a1a1aa"
                  tick={AXIS_TEXT}
                  tickFormatter={formatValue}
                  tickMargin={4}
                  ticks={xDomain ? ticksBetween(xDomain[0], xDomain[1]) : undefined}
                  type="number"
                />
                <YAxis
                  dataKey="y"
                  name={yLabel}
                  stroke="#a1a1aa"
                  tick={AXIS_TEXT}
                  tickFormatter={formatValue}
                  tickMargin={6}
                  type="number"
                  width={YAXIS_WIDTH}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    const point = payload?.[0]?.payload as
                      | { x: number; y: number }
                      | undefined
                    if (!active || !point) {
                      return null
                    }
                    return (
                      <div className="border border-amber-400 bg-zinc-950 px-2.5 py-2 text-xs text-zinc-50">
                        <p className="mb-1 text-zinc-200">{payload[0].name}</p>
                        <p>
                          {xLabel}: {formatValue(point.x)}
                        </p>
                        <p>
                          {yLabel}: {formatValue(point.y)}
                        </p>
                      </div>
                    )
                  }}
                  cursor={{ strokeDasharray: '3 3' }}
                />
                <Legend
                  align="center"
                  iconSize={10}
                  verticalAlign="top"
                  wrapperStyle={{ color: '#d4d4d8', fontSize: 12, paddingBottom: 2 }}
                />
                {series.map((group) => (
                  <Scatter
                    fill={group.color}
                    key={group.label}
                    name={LABEL_DISPLAY[group.label]}
                    data={group.data}
                  />
                ))}
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <p className="text-center text-sm text-zinc-200" style={plotAlign}>
            {xLabel}
          </p>
        </div>
      </div>
    </figure>
  )
}
