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
import { LABEL_COLORS, LABEL_ORDER, type ClusterPoint } from './clusterData'

type ClusterScatterProps = {
  points: ClusterPoint[]
  xLabel: string
  yLabel: string
  xDomain?: [number, number]
  showLegend?: boolean
}

function ticksBetween(min: number, max: number, count = 5): number[] {
  const step = (max - min) / (count - 1)
  return Array.from({ length: count }, (_, index) => min + step * index)
}

export default function ClusterScatter({
  points,
  xLabel,
  yLabel,
  xDomain,
  showLegend = true,
}: ClusterScatterProps) {
  const present = new Set(points.map((point) => point.label))
  const series = LABEL_ORDER.filter((label) => present.has(label)).map((label) => ({
    label,
    color: LABEL_COLORS[label],
    data: points.filter((point) => point.label === label),
  }))

  return (
    <div className="h-96 w-full min-w-[20rem]">
      <ResponsiveContainer height={360} minWidth={320} width="100%">
        <ScatterChart margin={{ bottom: 12, left: 8, right: 8, top: 8 }}>
          <CartesianGrid stroke="#3f3f46" strokeDasharray="3 3" />
          <XAxis
            allowDataOverflow={Boolean(xDomain)}
            dataKey="x"
            domain={xDomain}
            label={{ fill: '#d4d4d8', offset: -4, position: 'insideBottom', value: xLabel }}
            name={xLabel}
            stroke="#a1a1aa"
            tick={{ fill: '#d4d4d8', fontSize: 14 }}
            ticks={xDomain ? ticksBetween(xDomain[0], xDomain[1]) : undefined}
            type="number"
          />
          <YAxis
            dataKey="y"
            label={{
              angle: -90,
              fill: '#d4d4d8',
              position: 'insideLeft',
              value: yLabel,
            }}
            name={yLabel}
            stroke="#a1a1aa"
            tick={{ fill: '#d4d4d8', fontSize: 14 }}
            type="number"
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#09090b',
              border: '1px solid #fbbf24',
              color: '#fafafa',
            }}
            cursor={{ strokeDasharray: '3 3' }}
          />
          {showLegend ? (
            <Legend
              formatter={(value) => (
                <span className="text-zinc-100">{value}</span>
              )}
            />
          ) : null}
          {series.map((group) => (
            <Scatter
              fill={group.color}
              key={group.label}
              name={group.label}
              data={group.data}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}
