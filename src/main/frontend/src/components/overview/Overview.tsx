import { useEffect, useState } from 'react'
import { fetchPublicClips } from '@/api/publicPlayback'
import { LABEL_COLORS, LABEL_DISPLAY } from '../charts/clusterData'
import { HARDWARE_NODE_CARDS } from '../diagrams/hardwareNodeCards'
import MermaidDiagram from '../diagrams/MermaidDiagram'
import { HARDWARE_CHART, SOFTWARE_CHART } from '../diagrams/mermaidCharts'
import {
  formatClassLine,
  formatFalsePositives,
  formatOverallLine,
  liveAccuracySnapshot,
  type LiveAccuracyBlock as AccuracyBlock,
} from '@/lib/clipAccuracy'
import {
  accuracySnapshotsEqual,
  readAccuracyCache,
  writeAccuracyCache,
} from '@/lib/accuracyCache'

const looAccuracy = [
  { key: 'Unrelated', value: '96.2%', count: 26 },
  { key: 'Complete stop', value: '75.9%', count: 29 },
  { key: 'Run-through', value: '85.7%', count: 21 },
  { key: 'Rolling stop', value: '76.9%', count: 26 },
] as const

const looOverall = { value: '83.3%', count: 102 }

const LIVE_COLOR_KEY: Record<string, keyof typeof LABEL_COLORS> = {
  'Complete Stop': 'Complete stop',
  'Rolling Stop': 'Rolling stop',
  'Run-through Stop': 'Run-through',
  Unrelated: 'Unrelated',
}

function GifSlot({
  caption,
  src,
  alt,
}: {
  caption: string
  src?: string
  alt?: string
}) {
  return (
    <figure className="mx-auto max-w-3xl">
      {src ? (
        <img
          alt={alt ?? caption}
          className="w-full rounded-lg border border-zinc-800 bg-zinc-900"
          loading="lazy"
          src={src}
        />
      ) : (
        <div className="flex aspect-video max-w-3xl items-center justify-center rounded-lg border border-dashed border-zinc-600 bg-zinc-900 text-sm text-zinc-400">
          GIF coming soon
        </div>
      )}
      <figcaption className="mt-2 text-pretty text-center text-zinc-400">{caption}</figcaption>
    </figure>
  )
}

function ArchitectureFigures() {
  return (
    <div className="mx-auto max-w-6xl space-y-14">
      <figure className="mx-auto max-w-6xl">
        <div className="text-xl">
          <MermaidDiagram
            chart={HARDWARE_CHART}
            nodeCards={HARDWARE_NODE_CARDS}
            plainLinks
          />
        </div>
        <figcaption className="mt-2 text-center text-zinc-400">
          Hardware Architecture
        </figcaption>
      </figure>
      <figure className="mx-auto max-w-6xl">
        <div className="text-xl [&_svg]:w-full">
          <MermaidDiagram chart={SOFTWARE_CHART} />
        </div>
        <figcaption className="mt-2 text-center text-zinc-400">
          Software Architecture
        </figcaption>
      </figure>
    </div>
  )
}

export default function Overview() {
  return (
    <section className="scroll-mt-20 px-6 pb-16 pt-4" id="overview">
      <div className="mx-auto max-w-6xl space-y-10">
        <h2 className="mx-auto max-w-5xl text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">
          Overview
        </h2>

        <div className="space-y-8">
          <div className="mx-auto max-w-5xl space-y-3">
            <h3 className="text-2xl font-medium text-amber-400">What It Is</h3>
            <p>
              NetraPi is a smart dashcam I built with a Raspberry Pi, a Coral
              USB TPU, and a few other pieces of hardware. The name blends
              "Netradyne" and "Pi": Netradyne makes AI cameras that flag
              unsafe driving (Amazon delivery vans use them), and "Pi"
              follows the usual Raspberry Pi project naming style.
            </p>
            <p>
              It mimics a small slice of a Netradyne camera's job: analyzing
              dashcam footage in real time to catch unsafe stop-sign behavior.
              An edge device, frontend, backend, database, and cloud storage
              work together so those events get recorded, uploaded, and shown
              on this public site.
            </p>
          </div>
          <div className="mx-auto max-w-5xl space-y-3">
            <h3 className="text-2xl font-medium text-amber-400">Constraints</h3>
            <p>
              The build had to stay under $1,000, fit a 2010 Mazda3, and remain
              legal and safe on public roads. The Pi runs on a portable
              battery (no 12V tap). The Pi, TPU, and battery use reversible
              mounts so the car can go back to stock.
            </p>
          </div>
          <ArchitectureFigures />
          <GifSlot
            alt="NetraPi hardware mounted in the car"
            caption="The in-car build: Raspberry Pi 5, Coral TPU, dash camera, portable battery, and windshield mount."
            src="/gifs/hardware-setup.gif?v=1"
          />
        </div>

        <div className="mx-auto max-w-5xl space-y-3">
          <h3 className="text-2xl font-medium text-amber-400">Why I Made It</h3>
          <p>
            I wanted a machine-learning project that also stretched across
            hardware, cloud, and a real product surface. The idea came from
            driving for an Amazon-affiliated DSP, where cabin AI cameras
            enforce safe stops. The cameras are annoying, but they do sharpen
            habits if you stick around. After the season ended, some of that
            discipline faded, and rebuilding a smaller version of the system
            felt like a way to keep the skills and grow as an engineer.
          </p>
        </div>

        <div className="space-y-8">
          <div className="mx-auto max-w-5xl space-y-3">
            <h3 className="text-2xl font-medium text-amber-400">What It Can Do</h3>
            <p>
              NetraPi helps improve stop-sign safety without extra busywork. It
              automatically detects unsafe stops and uploads the footage to the
              cloud. Within five seconds of an event, a small speaker alerts the
              driver so the behavior can be corrected immediately. Anyone can
              visit this site to watch clips in Try It Out; Detailed Analysis
              shows the graphs behind each classification.
            </p>
          </div>
          <GifSlot
            alt="Stop labeled Complete Stop, Rolling Stop, or Run-through Stop after the approach"
            caption="When the car approaches a stop sign, NetraPi samples motion for five seconds and classifies the stop as Complete Stop, Rolling Stop, or Run-through Stop."
            src="/gifs/classification.gif?v=1"
          />
          <GifSlot
            alt="Clip saved locally and uploaded to S3"
            caption="Clips save on the Pi over a phone hotspot, then sync to S3 once the car is back on normal Wi-Fi."
            src="/gifs/s3-persist.gif?v=1"
          />
        </div>

        <div className="mx-auto max-w-5xl">
          <Results />
        </div>
      </div>
    </section>
  )
}

function Results() {
  const [snapshot, setSnapshot] = useState<ReturnType<
    typeof liveAccuracySnapshot
  > | null>(() => readAccuracyCache())
  const [fromCache, setFromCache] = useState(() => readAccuracyCache() != null)
  const [liveReady, setLiveReady] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    fetchPublicClips(controller.signal)
      .then((result) => {
        if (controller.signal.aborted) {
          return
        }
        const next = liveAccuracySnapshot(result.clips)
        const cached = readAccuracyCache()
        if (!cached || !accuracySnapshotsEqual(cached, next)) {
          writeAccuracyCache(next)
        }
        setSnapshot(next)
        setFromCache(false)
        setLiveReady(true)
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        const cached = readAccuracyCache()
        setSnapshot(cached)
        setFromCache(cached != null)
        setLiveReady(true)
      })
    return () => controller.abort()
  }, [])

  const field = snapshot?.field
  const ideal = snapshot?.ideal
  const fieldPhrase =
    field?.percent != null
      ? `${field.percent}% (${field.matches} of ${field.labeled})`
      : 'not yet available'
  const idealPhrase =
    ideal?.percent != null
      ? `${ideal.percent}% (${ideal.matches} of ${ideal.labeled})`
      : 'not yet available'

  return (
    <div className="scroll-mt-20 space-y-8" id="results">
      <div className="space-y-5">
        <h3 className="text-2xl font-medium text-amber-400">Results</h3>
        <p>
          I scored the classification model two ways: leave-one-out (LOO) on a
          static clip set, and field testing in a real car. The LOO set had 100
          video clips, 25 per category, including a 25-clip control. Each pass
          trains on almost the entire set, holds out one clip, scores that
          prediction against the known label, and repeats until every clip has
          been held out. I treated that single LOO number as the model's
          accuracy until field testing showed it was too optimistic.
        </p>
        <h4 className="text-xl font-medium text-amber-400">
          Leave-One-Out Accuracy
        </h4>
        <p className="text-zinc-200">
          {looOverall.value} of {looOverall.count} clips predicted correctly
        </p>
        <ul className="grid gap-3 sm:grid-cols-2">
          {looAccuracy.map((row) => (
            <li
              className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3"
              key={row.key}
            >
              <span
                className="mr-2 inline-block h-3 w-3 rounded-full"
                style={{ backgroundColor: LABEL_COLORS[row.key] }}
              />
              {LABEL_DISPLAY[row.key]}: {row.value} ({row.count} clips)
            </li>
          ))}
        </ul>
        <p>
          For field testing I drove a real car for a couple of hours, let the
          Pi classify stop-sign approaches, uploaded the clips, and labeled
          them by hand. Field Accuracy is currently {fieldPhrase} — well below
          the LOO number. The gap mostly comes from training geometry: most
          training clips used a small mock sign in a parking lot, with the car
          passing very close and stopping right after the sign left the frame.
          On real roads the signs are larger, the stop line is farther away,
          and extra lanes are common, so that close-up timing almost never
          happens.
        </p>
        <p>
          Calibrated Accuracy on the same labeled set, limited to right-most
          lane approaches with the stop line close to the sign, is currently{" "}
          {idealPhrase}.
        </p>
      </div>

      {fromCache && liveReady ? (
        <p className="text-sm text-zinc-400">
          Showing last saved Field and Calibrated Accuracy (could not reach the
          API).
        </p>
      ) : null}

      <LiveAccuracyBlock
        block={field}
        definition="Live match rate on labeled complete, rolling, and run-through clips (synthetic / parking-lot clips excluded)."
        ready={liveReady || snapshot != null}
        title="Field Accuracy"
      />
      <LiveAccuracyBlock
        block={ideal}
        definition="Same as Field Accuracy, but only right-most-lane clips where the stop line sits close to the sign."
        emptyLabel="No tagged calibrated clips yet"
        ready={liveReady || snapshot != null}
        title="Calibrated Accuracy"
      />

      <div className="space-y-3">
        <h4 className="text-xl font-medium text-amber-400">Limitations</h4>
        <p>
          LOO overstates on-road behavior because training was mostly
          parking-lot geometry. Field Accuracy is the honest live number;
          Calibrated Accuracy is a smaller operating-envelope subset. Unrelated
          detections are tracked separately as false positives. Live figures
          come from the public clip list and are cached in the browser if the
          API is down.
        </p>
      </div>
    </div>
  )
}

function LiveAccuracyBlock({
  block,
  definition,
  emptyLabel = 'No labeled stop-type clips yet',
  ready,
  title,
}: {
  block: AccuracyBlock | undefined
  definition: string
  emptyLabel?: string
  ready: boolean
  title: string
}) {
  return (
    <div className="space-y-3">
      <h4 className="text-xl font-medium text-amber-400">{title}</h4>
      <p className="text-zinc-400">{definition}</p>
      <p className="text-zinc-200">
        {!ready
          ? 'Loading live Accuracy...'
          : !block || block.percent === null
            ? emptyLabel
            : formatOverallLine(block)}
      </p>
      {block ? (
        <p className="text-sm text-zinc-400">
          {formatFalsePositives(block.falsePositives)}
        </p>
      ) : null}
      <ul className="grid gap-3 sm:grid-cols-2">
        {(block?.classes ?? []).map((row) => {
          const colorKey = LIVE_COLOR_KEY[row.name]
          return (
            <li
              className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3"
              key={row.name}
            >
              {colorKey ? (
                <span
                  className="mr-2 inline-block h-3 w-3 rounded-full"
                  style={{ backgroundColor: LABEL_COLORS[colorKey] }}
                />
              ) : null}
              {formatClassLine(row)}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
