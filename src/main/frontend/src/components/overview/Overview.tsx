import { LABEL_COLORS, LABEL_DISPLAY } from '../charts/clusterData'
import { HARDWARE_NODE_CARDS } from '../diagrams/hardwareNodeCards'
import MermaidDiagram from '../diagrams/MermaidDiagram'
import { HARDWARE_CHART, SOFTWARE_CHART } from '../diagrams/mermaidCharts'

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
        <div className="text-2xl">
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
              NetraPi is a smart dashcam I built using a Raspberry Pi, Coral
              USB TPU, and some other pieces of hardware. The name is a
              combination of "Netradyne" and "Pi". The "Pi" comes from the
              typical naming scheme used with RaspberryPi affiliated products
              and projects. Netradyne on the other hand, refers to a company
              whose main product is an AI powered camera that autonomously
              detects unsafe driving events. Amazon forces delivery drivers to
              be monitored by this camera so that safety can be enforced at
              scale.
            </p>
            <p>
              NetraPi mimics a small subset of the Netradyne cameras
              functionality. Specifically, it analyzes dash cam footage to
              detect unsafe behavior when passing a stop sign in real time. The
              system is comprised of several subsystems: the edge device,
              frontend, backend, local/cloud database, and cloud file storage.
              These systems work in tandem such that unsafe events are
              recorded, uploaded to the cloud, and are accessible via a public
              website for anyone to view. With my mishaps being public, the
              threat of embarrassment will provide plenty of motivation to
              rebuild my driving discipline!
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
            I wanted to create a machine-learning based project that also
            employed a variety of different technologies to improve my resume.
            The idea was inspired by my time working as a delivery driver for
            an Amazon affiliated DSP (Delivery Service Partner). The job
            responsibilities entailed safe driving which is strictly enforced
            through AI powered cameras mounted inside the cabin. The cameras
            keep drivers honest and while it's a pain to deal with, they do
            improve the driving competency of employees that stick around. I
            learned to appreciate my new found discipline while actively
            working but found myself losing some skills once the season was
            over. Recognizing the technical depth behind the cameras, I thought
            it would be a good idea to replicate the system for my career and
            driving competency.
          </p>
        </div>

        <div className="space-y-8">
          <div className="mx-auto max-w-5xl space-y-3">
            <h3 className="text-2xl font-medium text-amber-400">What It Can Do</h3>
            <p>
              It classifies stops on the Pi, saves 10- to 20-second clips, and
              beeps on unsafe stops. Metadata lives in SQLite on the device.
              Uploads go through Render. Video lands in S3. Longer trip files
              wait for Wi-Fi.
            </p>
          </div>
          <GifSlot
            alt="Stop labeled Complete Stop, Rolling Stop, or Run-through Stop after the approach"
            caption="After an approach, the Pi samples motion for five seconds and names the stop: Complete Stop, Rolling Stop, or Run-through Stop. The banner on the clip is that final label."
            src="/gifs/classification.gif?v=1"
          />
          <GifSlot
            alt="Clip saved locally and uploaded to S3"
            caption="The Pi saves the clip locally and uploads it to S3 when the phone hotspot is up."
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
  return (
    <div className="scroll-mt-20 space-y-5" id="results">
      <h3 className="text-2xl font-medium text-amber-400">Results</h3>
      <p>
        I scored the model with leave-one-out. I built a physical stop sign and
        recorded clips in a quiet parking lot, and I used YouTube driving clips.
        I labeled them by hand, then ran the program on each clip.
      </p>
      <p>
        The set is about 100 unique clips, around 25 per class. I left out the
        duplicate clips I made later (ids 108, 109, 110, and after).
      </p>
      <p className="text-zinc-400">
        The percentages below come from the ap_050 run. That run still included
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
