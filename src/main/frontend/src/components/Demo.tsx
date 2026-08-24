import ClusterScatter from './ClusterScatter'
import { LABEL_COLORS } from './clusterData'

const YOUTUBE_VIDEO_ID = ''

const accuracy = [
  { label: 'Unrelated', value: '96.2%' },
  { label: 'Complete stop', value: '75.9%' },
  { label: 'Run-through', value: '85.7%' },
  { label: 'Rolling stop', value: '76.9%' },
] as const

export default function Demo() {
  const embedUrl = YOUTUBE_VIDEO_ID
    ? `https://www.youtube-nocookie.com/embed/${YOUTUBE_VIDEO_ID}`
    : ''

  return (
    <section className="scroll-mt-20 px-6 py-16" id="demo">
      <div className="mx-auto max-w-3xl space-y-10">
        <h2 className="text-4xl font-semibold tracking-tight text-zinc-50 md:text-5xl">
          Demo
        </h2>

        {embedUrl ? (
          <iframe
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            className="aspect-video w-full rounded-lg border border-zinc-800"
            src={embedUrl}
            title="NetraPi demo"
          />
        ) : (
          <div className="flex aspect-video items-center justify-center rounded-lg border border-dashed border-zinc-600 bg-zinc-900 text-lg text-zinc-400">
            Demo clip coming soon
          </div>
        )}

        <Results />
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
      <p className="text-base text-zinc-400">
        The percents below come from the ap_050 run. That run still included
        those extra ids, so a recount on unique clips only is still pending.
        Overall accuracy on that run was 83.3%.
      </p>
      <ul className="grid gap-3 sm:grid-cols-2">
        {accuracy.map((row) => (
          <li
            className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3"
            key={row.label}
          >
            <span
              className="mr-2 inline-block h-3 w-3 rounded-full"
              style={{ backgroundColor: LABEL_COLORS[row.label] }}
            />
            {row.label}: {row.value}
          </li>
        ))}
      </ul>
      <p>
        The classifier is a two-stage kNN with k=3. First it picks safe vs
        unsafe. If it was unsafe, a second stage picks rolling stop vs
        run-through.
      </p>
      <p>
        Stage 2 only uses two numbers, so that part can be drawn as a scatter
        plot: min motion after the drop (x) vs how big the stop sign got during
        the approach (y). Complete stops sit at low motion. Run-throughs sit at
        high motion. Unrelated clips usually have a weak sign-area signal.
      </p>
      <p className="text-base text-zinc-400">
        This plot is a sketch of those neighborhoods, not the exported 100-clip
        table. Same axes the live kNN uses.
      </p>
      <ClusterScatter />
    </div>
  )
}
