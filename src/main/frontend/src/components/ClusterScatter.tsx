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
import { CLUSTER_POINTS, LABEL_COLORS } from './clusterData'

const series = (Object.keys(LABEL_COLORS) as Array<keyof typeof LABEL_COLORS>).map(
  (label) => ({
    label,
    color: LABEL_COLORS[label],
    data: CLUSTER_POINTS.filter((point) => point.label === label),
  }),
)

export default function ClusterScatter() {
  return (
    <div className="h-96 w-full min-w-[20rem]">
      <ResponsiveContainer height={360} minWidth={320} width="100%">
        <ScatterChart margin={{ bottom: 12, left: 8, right: 8, top: 8 }}>
          <CartesianGrid stroke="#3f3f46" strokeDasharray="3 3" />
          <XAxis
            dataKey="x"
            label={{ fill: '#d4d4d8', offset: -4, position: 'insideBottom', value: 'Min motion' }}
            name="Min motion"
            stroke="#a1a1aa"
            tick={{ fill: '#d4d4d8', fontSize: 14 }}
            type="number"
          />
          <YAxis
            dataKey="y"
            label={{
              angle: -90,
              fill: '#d4d4d8',
              position: 'insideLeft',
              value: 'Sign area',
            }}
            name="Sign area"
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
          <Legend
            formatter={(value) => (
              <span className="text-zinc-100">{value}</span>
            )}
          />
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
