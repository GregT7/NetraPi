import ClusterScatter from './ClusterScatter'
import MermaidDiagram from './MermaidDiagram'
import {
  CLUSTER_POINTS,
  LABEL_COLORS,
  STAGE1_FEATURE_LABELS,
  STAGE1_FEATURE_PAIRS,
  STAGE1_PCA_POINTS,
  STAGE1_PCA_VARIANCE,
  stage1PairPoints,
} from './clusterData'
import { KNN_CHART } from './mermaidCharts'

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
        <h2 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">
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
          <div className="flex aspect-video items-center justify-center rounded-lg border border-dashed border-zinc-600 bg-zinc-900 text-sm text-zinc-400">
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
      <p className="text-zinc-400">
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
        unsafe from four motion numbers. If it was unsafe, a second stage picks
        rolling stop vs run-through from min motion plus how big the sign got.
        Clips that never trigger approach stay unrelated.
      </p>
      <figure>
        <MermaidDiagram chart={KNN_CHART} />
        <figcaption className="mt-2 text-center text-zinc-400">
          Hierarchical kNN
        </figcaption>
      </figure>
      <p>
        Those four stage-1 numbers cannot be drawn as-is, so the plot below is a
        PCA of the standardized motion features. PC1 is{' '}
        {Math.round(STAGE1_PCA_VARIANCE[0] * 100)}% of the variance and tracks
        more motion / less time stopped. PC2 is{' '}
        {Math.round(STAGE1_PCA_VARIANCE[1] * 100)}%. Complete stops should sit
        toward the low-motion side of PC1. Color is the stage-1 split, not the
        final four labels.
      </p>
      <p className="text-zinc-400">
        Axes are principal components, not raw motion. Unrelated clips are
        omitted.
      </p>
      <ClusterScatter
        points={STAGE1_PCA_POINTS}
        xDomain={[-3, 5]}
        xLabel="PC1"
        yLabel="PC2"
      />
      <p>
        The six plots below are every pair of those four raw numbers: mean
        motion, min motion, p95 motion, and stop fraction. Same stage-1 labels
        as the PCA.
      </p>
      <div className="grid gap-8 sm:grid-cols-2">
        {STAGE1_FEATURE_PAIRS.map(([xKey, yKey], index) => (
          <ClusterScatter
            key={`${xKey}-${yKey}`}
            points={stage1PairPoints(xKey, yKey)}
            showLegend={index === 0}
            xLabel={STAGE1_FEATURE_LABELS[xKey]}
            yLabel={STAGE1_FEATURE_LABELS[yKey]}
          />
        ))}
      </div>
      <p>
        Stage 2 is already two numbers, so it needs no PCA: min motion after the
        drop (x) vs sign-area sum on the approach (y).
      </p>
      <p className="text-zinc-400">
        Rolling vs run-through on the same axes the live stage-2 kNN uses.
        Complete stops and unrelated clips are omitted.
      </p>
      <ClusterScatter
        points={CLUSTER_POINTS}
        xLabel="Min motion"
        yLabel="Sign area"
      />
    </div>
  )
}
