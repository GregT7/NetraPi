import AreaMotionChart from './AreaMotionChart'
import ClusterScatter from './ClusterScatter'
import FeatureGuide from './FeatureGuide'
import KnnHierarchy from './KnnHierarchy'
import {
  CLUSTER_POINTS,
  STAGE1_FEATURE_LABELS,
  STAGE1_FEATURE_PAIRS,
  STAGE1_PCA_POINTS,
  STAGE1_PCA_VARIANCE,
  stage1PairPoints,
} from '../data/clusterData'

export default function HowItWorks() {
  return (
    <section className="scroll-mt-20 px-6 py-16" id="how-it-works">
      <div className="mx-auto max-w-3xl space-y-8">
        <h2 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">
          How it works
        </h2>
        <figure>
          <div className="flex aspect-video items-center justify-center rounded-lg border border-dashed border-zinc-600 bg-zinc-900 text-sm text-zinc-400">
            Video coming soon
          </div>
          <figcaption className="mt-4 text-center text-zinc-400">
            Approach to classification
          </figcaption>
        </figure>
        <p>
          The Pi keeps polling for an approach: a stop sign that grows in the
          frame, then shrinks. If that never happens, it keeps watching. If it
          does, it collects 5 seconds of motion, then a two-stage kNN with k=3
          classifies the stop.
        </p>
        <p>
          Sign area comes from the detector box. Motion comes from Farneback
          optical flow. Farneback estimates how every pixel in a road region
          moved between two frames. The motion score is a high percentile of
          those magnitudes. A low score means the scene looks still.
        </p>
        <AreaMotionChart />
        <p className="text-zinc-400">
          The example above is one complete-stop clip. Sign area rises then
          drops (the approach). T0 is that drop. Motion after T0 is what stage
          1 reads.
        </p>
        <FeatureGuide />
        <figure>
          <KnnHierarchy />
          <figcaption className="mt-4 text-center text-zinc-400">
            Hierarchical KNN
          </figcaption>
        </figure>
        <p>
          Those four stage-1 numbers cannot be drawn as-is, so the plot below
          is a PCA of the standardized motion features. PC1 is{' '}
          {Math.round(STAGE1_PCA_VARIANCE[0] * 100)}% of the variance and
          tracks more motion / less time stopped. PC2 is{' '}
          {Math.round(STAGE1_PCA_VARIANCE[1] * 100)}%. Complete stops should
          sit toward the low-motion side of PC1. Color is the stage-1 split,
          not the final four labels.
        </p>
        <p className="text-zinc-400">
          Axes are principal components, not raw motion. Unrelated clips are
          omitted.
        </p>
        <ClusterScatter
          points={STAGE1_PCA_POINTS}
          title="Stage 1 PCA"
          xDomain={[-3, 5]}
          xLabel="PC1"
          yLabel="PC2"
        />
        <p>
          The six plots below are every pair of those four raw numbers: mean
          motion, min motion, p95 motion, and stop fraction. Same stage-1
          labels as the PCA.
        </p>
        <div className="grid gap-6 sm:grid-cols-2">
          {STAGE1_FEATURE_PAIRS.map(([xKey, yKey]) => (
            <div
              className="rounded-lg border border-zinc-700 bg-zinc-900/50 p-3"
              key={`${xKey}-${yKey}`}
            >
              <ClusterScatter
                points={stage1PairPoints(xKey, yKey)}
                title={`${STAGE1_FEATURE_LABELS[xKey]} vs ${STAGE1_FEATURE_LABELS[yKey]}`}
                xLabel={STAGE1_FEATURE_LABELS[xKey]}
                yLabel={STAGE1_FEATURE_LABELS[yKey]}
              />
            </div>
          ))}
        </div>
        <p>
          Stage 2 is already two numbers, so it needs no PCA: min motion after
          the drop (x) vs sign-area sum on the approach (y).
        </p>
        <p className="text-zinc-400">
          Rolling vs run-through on the same axes the live stage-2 kNN uses.
          Complete stops and unrelated clips are omitted.
        </p>
        <ClusterScatter
          points={CLUSTER_POINTS}
          title="Stage 2 Features"
          xLabel="Min Motion"
          yLabel="Sign Area"
        />
      </div>
    </section>
  )
}
