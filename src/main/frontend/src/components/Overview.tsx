import MermaidDiagram from './MermaidDiagram'
import { HARDWARE_CHART, SOFTWARE_CHART } from './mermaidCharts'

const gifSlots = [
  { caption: 'Finding a stop sign' },
  { caption: 'Labeling the stop' },
  { caption: 'Saving the clip' },
] as const

function GifSlot({ caption }: { caption: string }) {
  return (
    <figure className="mx-auto max-w-3xl">
      <div className="flex aspect-video max-w-3xl items-center justify-center rounded-lg border border-dashed border-zinc-600 bg-zinc-900 text-sm text-zinc-400">
        GIF coming soon
      </div>
      <figcaption className="mt-2 text-center text-zinc-400">{caption}</figcaption>
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
            a complete stop, a rolling stop, a run-through, or unrelated (the
            sign was in view, but it was not a real stop).
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

        <div className="space-y-8">
          {gifSlots.map((slot) => (
            <GifSlot key={slot.caption} caption={slot.caption} />
          ))}
        </div>
      </div>

      <div className="mx-auto mt-14 max-w-6xl space-y-14">
        <figure className="mx-auto max-w-6xl">
          <div className="text-2xl">
            <MermaidDiagram chart={HARDWARE_CHART} plainLinks />
          </div>
          <figcaption className="mt-2 text-center text-zinc-400">
            Hardware architecture
          </figcaption>
        </figure>
        <figure className="mx-auto max-w-6xl">
          <div className="text-2xl">
            <MermaidDiagram chart={SOFTWARE_CHART} />
          </div>
          <figcaption className="mt-2 text-center text-zinc-400">
            Software architecture
          </figcaption>
        </figure>
      </div>
    </section>
  )
}
