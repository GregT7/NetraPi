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
          The system constantly reads the camera to understand what is going
          on. It looks for a consistent, repeatable event that always occurs,
          regardless of the driver's ultimate decision: Complete Stop, Rolling
          Stop, or Run-through Stop. If we can identify and consistently detect
          this common event, then we will know when and what to record.
          Capturing a mixed set of clips that does not concern the driver will
          distract them and make it harder for them to improve. We want to
          avoid that problem. The goal is to make the application as useful and
          painless as possible. This common event is easiest to see by thinking
          through an example.
        </p>
        <p>
          Imagine this scenario: someone driving a car turns onto a long street
          where, at the end, there is a stop sign before an intersection. They
          continue driving toward the sign. As the distance decreases, the size
          of the stop sign increases from the camera's perspective. Eventually
          the size hits a peak and then disappears once the car passes it. At
          this moment, there is a three-pronged fork in the road. The driver
          can follow the law and stop, slow down a little but keep driving
          anyway, or drive past the sign without stopping. The three branching
          outcomes all share the approach of the stop sign. This is the event
          we need the Pi to look for. The diagram below is that loop: stay in
          monitoring until an Approach Stop Sign is detected, sample the car's
          motion for 5 seconds, sort the stop into Complete Stop, Rolling Stop,
          or Run-through Stop, then return to monitoring. Before we dive into
          how the Pi finds that approach, we need to discuss some additional
          processing details.
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
          The Pi can algorithmically locate this pattern by constantly
          searching for exponential growth in area over a short time frame,
          followed by a steep drop to an empty reading. The point where the
          area calculation transitions from a global or local maximum to an
          empty reading is called the "peak." Locating the peak is at the
          heart of this recipe; that is when we officially have found the
          approach pattern. Many false peaks show up while driving, though.
          Each candidate has a series of strict criteria applied to it, which
          filters out most of them until a single valid peak remains. Finding
          the approach pattern is not the end of the story. We still need to
          sort the driver's decision into the 3 bins shown in the diagram.
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
          At the moment of the peak, we know the driver must make a decision,
          so we start paying closer attention. Evaluating the motion of the car
          is the key, which is where the Farneback Optical Flow Algorithm comes
          in. The algorithm approximates motion by measuring the rate of change
          in pixel intensity. If pixel intensity changes at a higher rate,
          whatever is in the image is likely moving faster in real life, and
          slower deltas mean slower motion. The three decisions have distinct
          motion profiles: Complete Stop has lower motion scores overall,
          Rolling Stop has a little more motion, and Run-through Stop has the
          most (this is simplified for explanation). If we sample the car's
          motion after an approach is detected, we can compare the live data
          with previous examples to see which category the event most closely
          aligns with. The comparisons are driven by k-nearest neighbors
          (k-NN), which is a good fit for this scenario. That k-NN is
          multi-stage and uses five features in total. Other features help
          earlier in the pipeline; the second stage uses just two of those
          values, shown in the plot below.
        </p>
        <ClusterScatter
          points={CLUSTER_POINTS}
          title="Classification Scatterplot for Rolling vs Run-through Stops"
          xLabel="Minimum Motion (px / Frame)"
          yLabel="Total Sign Area (%)"
        />
        <p>
          Finally, the event has been identified. Now we need to wrap things
          up and record the footage. The Pi records the clip and saves it to
          the cloud through the cellular hotspot my phone is hosting. The
          footage is then available on the hosted frontend for anyone curious
          about my driving. After that, it returns to monitoring and waits for
          the next approach.
        </p>
      </div>
    </section>
  )
}
