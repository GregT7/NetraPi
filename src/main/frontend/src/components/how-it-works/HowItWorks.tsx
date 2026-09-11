import AreaMotionChart from './AreaMotionChart'
import ClusterScatter from './ClusterScatter'
import MermaidDiagram from '../diagrams/MermaidDiagram'
import { EVENT_STATE_CHART } from '../diagrams/mermaidCharts'
import { CLUSTER_POINTS } from '../charts/clusterData'

export default function HowItWorks() {
  return (
    <section className="scroll-mt-20 px-6 py-16" id="how-it-works">
      <div className="mx-auto max-w-3xl space-y-8">
        <h2 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">
          How It Works
        </h2>
        <p>
          This section walks through the live loop on the Pi. Picture turning
          onto a long street with a stop sign at the end. As you drive closer,
          the sign grows in the camera, peaks, then drops out of frame when you
          pass it. That approach is the event NetraPi looks for. At that moment
          the driver has three choices: a Complete Stop, a Rolling Stop, or a
          Run-through Stop. If the Pi can spot the approach reliably, it knows
          when to record and which footage to keep; clips that never show this
          pattern are ignored.
        </p>
        <p>
          The diagram below is that loop: stay in monitoring until an Approach
          Stop Sign is detected, sample the car's motion for five seconds,
          classify the stop, then return to monitoring. Here's how the Pi
          finds the approach.
        </p>
        <figure>
          <MermaidDiagram chart={EVENT_STATE_CHART} />
          <figcaption className="mt-4 text-center text-zinc-400">
            Stop-Sign Encounter States
          </figcaption>
        </figure>
        <p>
          Throughout the drive, the camera reads frames and passes them to an
          object detector stored as a pretrained TFLite model. The detector
          looks at the image and tries to identify what is in the image and
          where it is located. When a detection occurs, a rectangle outlines
          the area of interest. Plotting the area of these rectangles over time
          creates a shark-fin-like pattern, which can be seen in the graph
          below. Identifying this pattern means identifying the approach. A
          person inspecting the graph could recognize this shape, but the
          challenge is getting the computer to do it on its own.
        </p>
        <AreaMotionChart />
        <p>
          The Pi finds that pattern by watching for a short burst of
          exponential growth in bounding-box area, then a steep drop to an
          empty reading. The moment area falls from a local or global maximum
          to empty is the "peak" — that is the official approach. Many false
          peaks show up while driving, so each candidate has to pass a strict
          filter until one valid peak remains. After that, the stop still has
          to be sorted into the three bins in the diagram.
        </p>
        <figure>
          <img
            alt="Stop sign growing in the camera view, then dropping away"
            className="w-full rounded-lg border border-zinc-800 bg-zinc-900"
            loading="lazy"
            src="/gifs/approach.gif?v=3"
          />
          <figcaption className="mt-2 text-pretty text-center text-zinc-400">
            The stop sign grows in view and then drops away. That peak is the
            approach; footage that never shows this pattern is skipped.
          </figcaption>
        </figure>
        <p>
          At the peak, the driver has to decide, so the Pi starts scoring
          motion with Farneback optical flow: how fast pixel intensity changes
          is a stand-in for how fast the car is moving. Complete stops look
          calm, rolling stops have more motion, and run-throughs have the most
          (simplified, but useful). After the approach, those live motion
          features are compared to past examples with k-nearest neighbors
          (k-NN). The full pipeline uses five features across stages; the
          scatterplot below shows the two values used in the later stage —
          minimum motion and total sign area — for rolling vs run-through
          stops.
        </p>
        <ClusterScatter
          points={CLUSTER_POINTS}
          title="Classification Scatterplot for Rolling vs Run-through Stops"
          xLabel="Minimum Motion (px / Frame)"
          yLabel="Total Sign Area (%)"
        />
        <p>
          Once the stop is classified, the Pi saves the clip and uploads it
          over a phone hotspot so it shows up in Try It Out. Then it returns
          to monitoring and waits for the next approach.
        </p>
      </div>
    </section>
  )
}
