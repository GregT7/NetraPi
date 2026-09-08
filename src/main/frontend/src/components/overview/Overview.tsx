import { useEffect, useState } from 'react'
import { fetchPublicClips, type PublicClipRow } from '@/api/publicPlayback'
import { LABEL_COLORS, LABEL_DISPLAY } from '../charts/clusterData'
import { HARDWARE_NODE_CARDS } from '../diagrams/hardwareNodeCards'
import MermaidDiagram from '../diagrams/MermaidDiagram'
import { HARDWARE_CHART, SOFTWARE_CHART } from '../diagrams/mermaidCharts'
import {
  formatClassLine,
  formatOverallLine,
  idealClips,
  overallAccuracy,
  perClassAccuracy,
  type ClassAccuracy,
  type OverallAccuracy,
} from '@/lib/clipAccuracy'

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
              website for anyone to view.
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
              The goal of the NetraPi system is to help users improve driving
              safety in a time-efficient and convenient manner. The system
              automatically detects unsafe stops and uploads the footage to the
              cloud. Within 5 seconds of the event occurring, a small speaker
              will emit a noise to notify the driver. Real time feedback raises
              the awareness of poor performance in real time, enabling quicker
              correction of unsafe behavior. Lastly, anyone can visit the
              website to view clips of my driving in the "Try It Out" section.
              There is a "Detailed Analysis" section there that displays
              several graphs that shed deeper insight into how the system is
              actually working for those curious.
            </p>
          </div>
          <GifSlot
            alt="Stop labeled Complete Stop, Rolling Stop, or Run-through Stop after the approach"
            caption="The system detects the car approaching a stop sign which triggers a 5 second period where motion data is sampled. This motion data is used to classify the stop into 3 types: Complete Stop, Rolling Stop, and Run-through Stop. The banner is only included in gifs and is not part of the normal flow."
            src="/gifs/classification.gif?v=1"
          />
          <GifSlot
            alt="Clip saved locally and uploaded to S3"
            caption="I turn on a phone hotspot, wave at the camera in a remote area, then go home, join regular Wi-Fi, and open the same clip from the cloud — showing it went from the Pi in the car to S3."
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
  const [clips, setClips] = useState<PublicClipRow[]>([])
  const [liveReady, setLiveReady] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    fetchPublicClips(controller.signal)
      .then((result) => {
        if (controller.signal.aborted) {
          return
        }
        setClips(result.clips)
        setLiveReady(true)
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        setClips([])
        setLiveReady(true)
      })
    return () => controller.abort()
  }, [])

  const overall = overallAccuracy(clips)
  const overallClasses = perClassAccuracy(clips)
  const ideal = idealClips(clips)
  const idealStats = overallAccuracy(ideal)
  const idealClasses = perClassAccuracy(ideal)

  const overallPhrase =
    liveReady && overall.percent !== null
      ? `${overall.percent}% (${overall.matches} of ${overall.labeled})`
      : 'not yet available'
  const idealPhrase =
    liveReady && idealStats.percent !== null
      ? `${idealStats.percent}% (${idealStats.matches} of ${idealStats.labeled})`
      : 'not yet available'

  return (
    <div className="scroll-mt-20 space-y-8" id="results">
      <div className="space-y-5">
        <h3 className="text-2xl font-medium text-amber-400">Results</h3>
        <p>
          I scored the classification model using two different approaches. The
          first used the leave-one-out (LOO) algorithm on a static set of 100
          video clips — 25 per category, including a 25-clip control set.
        </p>
        <p>
          Leave-one-out trains the model on almost the entire set, then holds
          out one clip and asks the model to classify it. Because that clip
          already has a known label, the prediction is scored as correct or
          incorrect. Repeating this for every clip and combining the outcomes
          gives a single overall accuracy. I mainly relied on that LOO metric
          to gauge how well the model would perform. After I tried a second
          scoring method, I found a flaw in that picture.
        </p>
        <p className="text-zinc-300">
          {looOverall.value} ({looOverall.count} clips)
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
      </div>

      <div className="space-y-5">
        <p>
          The second approach was to run the system in a real car. I drove for
          a couple of hours, classified stop-sign approaches as they happened,
          and uploaded the clips. Afterward I reviewed the footage and labeled
          it by hand so each automated prediction had a ground truth.
        </p>
        <p>
          On every labeled clip, overall accuracy is the share of predictions
          that match my review: {overallPhrase}. That number is not very good.
        </p>
        <p>
          The training set explains the gap. Most of those clips were
          parking-lot runs past a mock stop sign about one-third the size of a
          real one. I kept the passenger side very close to the sign, and on
          complete stops I halted after only a short distance past it.
        </p>
        <p>
          Real roads are different: larger signs, a longer gap from the sign to
          the halt line, and usually more than one lane. In the middle or left
          lane the model still expects a right-lane, close-up sign, so it
          classifies poorly. The training data never included those conditions.
        </p>
        <p>
          If you keep only the approaches that match training — right-most
          lane, and a white stop line close to the sign — ideal accuracy is{' '}
          {idealPhrase}.
        </p>
        <p>
          Middle- and left-lane approaches, and long gaps to the halt line,
          fail for a mechanical reason. The stop sign leaves the frame earlier,
          so the system treats the approach as over and starts sampling motion
          before there has been time to stop. In that window a complete stop is
          effectively impossible.
        </p>
      </div>

      <LiveAccuracyBlock
        classes={overallClasses}
        definition="Every labeled clip from the live evaluation. The model's prediction vs my review."
        ready={liveReady}
        stats={overall}
        title="Overall accuracy"
      />
      <LiveAccuracyBlock
        classes={idealClasses}
        definition="The same comparison, but only clips in the right-most lane with the stop line close to the sign."
        emptyLabel="No tagged ideal-scenario clips yet"
        ready={liveReady}
        stats={idealStats}
        title="Ideal accuracy"
      />
    </div>
  )
}

function LiveAccuracyBlock({
  classes,
  definition,
  emptyLabel = 'No labeled clips yet',
  ready,
  stats,
  title,
}: {
  classes: ClassAccuracy[]
  definition: string
  emptyLabel?: string
  ready: boolean
  stats: OverallAccuracy
  title: string
}) {
  return (
    <div className="space-y-3">
      <h4 className="text-xl font-medium text-amber-400">{title}</h4>
      <p className="text-zinc-400">{definition}</p>
      <p className="text-zinc-200">
        {!ready
          ? 'Loading live accuracy…'
          : stats.percent === null
            ? emptyLabel
            : formatOverallLine(stats)}
      </p>
      <ul className="grid gap-3 sm:grid-cols-2">
        {classes.map((row) => {
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
