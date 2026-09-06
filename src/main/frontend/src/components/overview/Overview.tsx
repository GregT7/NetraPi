import { LABEL_COLORS, LABEL_DISPLAY } from '../data/clusterData'
import { HARDWARE_NODE_CARDS } from '../diagrams/hardwareNodeCards'
import MermaidDiagram from '../diagrams/MermaidDiagram'
import { HARDWARE_CHART, SOFTWARE_CHART } from '../diagrams/mermaidCharts'

const gifSlots = [
  {
    src: '/gifs/approach.gif?v=3',
    alt: 'Stop sign growing in the camera view, then dropping away',
    caption:
      'NetraPi waits for a stop sign to grow in view and then drop away. That drop is when a stop is labeled Complete Stop, Rolling Stop, or Run-through Stop. Footage that never shows this pattern is skipped.',
  },
  {
    src: '/gifs/classification.gif?v=1',
    alt: 'Stop labeled Complete Stop, Rolling Stop, or Run-through Stop after the approach',
    caption:
      'After that drop, the Pi records motion for five seconds and then names the stop: Complete Stop, Rolling Stop, or Run-through Stop. The banner on the clip is that final label.',
  },
  { caption: 'Saving the clip' },
] as const

const accuracy = [
  { key: 'Unrelated', value: '96.2%' },
  { key: 'Complete stop', value: '75.9%' },
  { key: 'Run-through', value: '85.7%' },
  { key: 'Rolling stop', value: '76.9%' },
] as const

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

export default function Overview() {
  return (
    <section className="scroll-mt-20 px-6 pb-16 pt-4" id="overview">
      <div className="mx-auto max-w-5xl space-y-10">
        <h2 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">
          Overview
        </h2>

        <div className="space-y-3">
          <h3 className="text-2xl font-medium text-amber-400">What it is</h3>
          <p>
            NetraPi is a dashcam I built on a Raspberry Pi 5 with a Coral USB
            TPU. It watches the road for stop signs and labels what happened:
            a Complete Stop, a Rolling Stop, a Run-through Stop, or Unrelated
            (the sign was in view, but it was not a real stop).
          </p>
          <p>
            When something fires, it saves a short clip and some notes. If the
            Pi is online, those go to a FastAPI backend, then into a private S3
            bucket and Postgres.
          </p>
        </div>

        <div className="space-y-3">
          <h3 className="text-2xl font-medium text-amber-400">Why I made it</h3>
          <p>
            Amazon delivery vans use Netradyne-style cameras. I wanted a
            homemade version that only cares about stop signs, so I could
            actually finish the path from the car to the cloud.
          </p>
        </div>

        <div className="space-y-3">
          <h3 className="text-2xl font-medium text-amber-400">What it can do</h3>
          <p>
            It classifies stops on the Pi, saves 10 to 20 second clips, and
            beeps on unsafe stops. Metadata lives in SQLite on the device.
            Uploads go through Render. Video lands in S3. Longer trip files
            wait for Wi-Fi.
          </p>
          <p>This page does not play live events yet.</p>
        </div>

        <Results />

        <div className="space-y-8">
          {gifSlots.map((slot) => (
            <GifSlot key={slot.caption} {...slot} />
          ))}
        </div>
      </div>

      <div className="mx-auto mt-14 max-w-6xl space-y-14">
        <figure className="mx-auto max-w-6xl">
          <div className="text-2xl">
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
          <div className="text-2xl">
            <MermaidDiagram chart={SOFTWARE_CHART} />
          </div>
          <figcaption className="mt-2 text-center text-zinc-400">
            Software Architecture
          </figcaption>
        </figure>
      </div>
    </section>
  )
}

function Results() {
  return (
    <div className="scroll-mt-20 space-y-5" id="results">
      <h3 className="text-2xl font-medium text-amber-400">Results</h3>
      <p>
        I scored the model with leave-one-out. I built a stop sign and recorded
        clips in a quiet parking lot, and I used YouTube driving clips. I
        labeled them by hand, then ran the program on each clip.
      </p>
      <p>
        The set is about 100 unique clips, around 25 per class. I left out the
        duplicate clips I made later (ids 108, 109, 110, and after).
      </p>
      <p className="text-zinc-400">
        The percents below come from the ap_050 run. That run still included
        those extra ids, so a recount on unique clips only is still pending.
        Overall accuracy on that run was 83.3%.
      </p>
      <ul className="grid gap-3 sm:grid-cols-2">
        {accuracy.map((row) => (
          <li
            className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3"
            key={row.key}
          >
            <span
              className="mr-2 inline-block h-3 w-3 rounded-full"
              style={{ backgroundColor: LABEL_COLORS[row.key] }}
            />
            {LABEL_DISPLAY[row.key]}: {row.value}
          </li>
        ))}
      </ul>
    </div>
  )
}
