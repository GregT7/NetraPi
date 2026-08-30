import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import series from '../data/ap050AreaMotion.json'

type SeriesPoint = { t: number; area: number; motion: number }

const points = (series.points as SeriesPoint[]).map((point) => ({
  t: point.t,
  areaPct: point.area * 100,
  motion: point.motion,
}))

const AXIS_TEXT = { fill: '#d4d4d8', fontSize: 12 }

function formatValue(value: number | string) {
  const n = Number(value)
  return Number.isFinite(n) ? n.toFixed(2) : String(value)
}

function T0Marker({
  viewBox,
  x,
  y,
}: {
  viewBox?: { x?: number; y?: number }
  x?: number
  y?: number
}) {
  const px = viewBox?.x ?? x
  const py = viewBox?.y ?? y
  if (px == null || py == null) {
    return null
  }
  return (
    <g transform={`translate(${px}, ${py})`}>
      <text
        dy={-20}
        fill="#fafafa"
        fontSize={16}
        fontWeight={700}
        textAnchor="middle"
      >
        T0
      </text>
      <polygon fill="#fafafa" points="-7,-12 7,-12 0,0" />
    </g>
  )
}

export default function AreaMotionChart() {
  return (
    <figure className="space-y-2">
      <figcaption className="text-center text-lg font-medium text-zinc-50">
        Sign Area and Motion
      </figcaption>
      <div className="flex">
        <div className="flex w-8 shrink-0 items-center justify-center">
          <span className="text-sm text-sky-300 [writing-mode:vertical-rl] rotate-180">
            Sign Area
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <div className="h-104 w-full min-w-[20rem]">
            <ResponsiveContainer height={400} minWidth={320} width="100%">
              <LineChart data={points} margin={{ bottom: 28, left: 4, right: 8, top: 36 }}>
                <CartesianGrid stroke="#3f3f46" strokeDasharray="3 3" />
                <XAxis
                  dataKey="t"
                  stroke="#a1a1aa"
                  tick={AXIS_TEXT}
                  tickFormatter={formatValue}
                  tickMargin={8}
                  type="number"
                />
                <YAxis
                  stroke="#38bdf8"
                  tick={AXIS_TEXT}
                  tickFormatter={formatValue}
                  tickMargin={8}
                  width={44}
                  yAxisId="area"
                />
                <YAxis
                  orientation="right"
                  stroke="#fbbf24"
                  tick={AXIS_TEXT}
                  tickFormatter={formatValue}
                  tickMargin={8}
                  width={44}
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
                  labelFormatter={(label) => `Time (s): ${formatValue(label)}`}
                />
                <Legend
                  align="center"
                  iconSize={10}
                  verticalAlign="bottom"
                  wrapperStyle={{ color: '#d4d4d8', fontSize: 12, paddingTop: 4 }}
                />
                <Line
                  dataKey="areaPct"
                  dot={false}
                  name="Sign Area"
                  stroke="#38bdf8"
                  strokeWidth={2}
                  type="monotone"
                  yAxisId="area"
                />
                <Line
                  dataKey="motion"
                  dot={false}
                  name="Motion"
                  stroke="#fbbf24"
                  strokeWidth={2}
                  type="monotone"
                  yAxisId="motion"
                />
                <ReferenceLine
                  label={<T0Marker />}
                  stroke="#fafafa"
                  strokeDasharray="6 4"
                  strokeWidth={2}
                  x={series.t0}
                  yAxisId="area"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-1 text-center text-sm text-zinc-200">Time (s)</p>
        </div>
        <div className="flex w-8 shrink-0 items-center justify-center">
          <span className="text-sm text-amber-300 [writing-mode:vertical-rl]">
            Motion
          </span>
        </div>
      </div>
    </figure>
  )
}
