import AreaMotionChart from './AreaMotionChart'
import ClusterScatter from './ClusterScatter'
import MermaidDiagram from '../diagrams/MermaidDiagram'
import { EVENT_STATE_CHART } from '../diagrams/mermaidCharts'
import { CLUSTER_POINTS } from '../data/clusterData'

export default function HowItWorks() {
  return (
    <section className="scroll-mt-20 px-6 py-16" id="how-it-works">
      <div className="mx-auto max-w-3xl space-y-8">
        <h2 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">
          How it works
        </h2>
        <p>
          The system works by constantly reading from the camera to understand
          what's going on. It's looking for a consistent, repeatable event that
          always occurs, regardless of the driver's ultimate decision:
          Complete Stop, Rolling Stop, or Run-through Stop.
          If we can identify and consistently detect this common event, then we
          will know when and what to record. Capturing a mixed set of clips
          that doesn't concern the driver will distract them, making it more
          difficult for them to improve. We want to avoid that problem. The
          ultimate goal is to make the application as useful and painless as
          possible. This common event is easiest to see by thinking through an
          example.
        </p>
        <p>
          Imagine this scenario: someone driving a car turns onto a long street
          where at the end, there is a stop sign before an intersection. They
          continue driving forward towards the sign. As the distance decreases,
          the size of the stop sign increases from the perspective of the
          camera. Eventually, the size hits a peak and then completely
          disappears once the car advances past it. At this moment, there is a
          3-pronged fork in the road. The driver can follow the law and stop,
          slow down a little but keep driving anyways, or completely drive past
          the sign without any consideration. The three branching outcomes all
          share the approach of the stop sign. This is the event we need the Pi
          to look for. The diagram below is that loop: stay in monitoring until
          an Approach Stop Sign is detected, sample the car's motion for 5
          seconds, sort the stop into Complete Stop, Rolling Stop, or
          Run-through Stop, then return to monitoring. Before we dive into
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
          Throughout the drive, the camera is constantly reading in frames and
          passing them to a downloaded object detector stored as a pretrained
          TFLite model. The object detector looks at the image, and tries to
          identify what is in the image and where it's located. When a
          detection occurs, a rectangle that outlines the area of interest is
          generated. Plotting the area calculations of these rectangles over
          time creates a "shark-fin" like pattern which can be
          observed in the graph below. Identifying this pattern means identifying
          the approach. Any person inspecting the graph could recognize this
          shape but the challenge is getting the computer to accomplish this
          independently.
        </p>
        <AreaMotionChart />
        <p>
          The Pi can algorithmically locate this pattern by constantly
          searching for exponential growth in area over a short time frame
          followed by a steep drop to an empty reading. The point where the
          area calculation transitions from a global or local maximum to an
          empty reading is called the "peak." Locating the peak is at
          the heart of this recipe and is considered the time when we
          officially have found the approach pattern. However, it is likely
          that many false peaks present themselves while driving. Each
          potential peak candidate has a series of strict criteria applied to
          it which filters out most candidates until a singular valid one
          remains. While we've finally found the approach pattern, this
          is not the end of the story. We still need to sort the driver's
          decision into the 3 bins shown in the diagram.
        </p>
        <p>
          At the moment of the peak, we know the driver must make a decision
          so we start paying closer attention. Evaluating the motion of the car
          is the key which is where the Farneback Optical Flow Algorithm comes
          into the picture. The algorithm can approximate motion by evaluating
          the rate of change in pixel intensity. If the pixel intensity
          changes at a higher rate, whatever is in the image is likely moving
          faster in real life and vice versa for slower deltas. The 3 different
          decisions all possess unique motion profiles that can be easily
          understood: Complete Stop overall has lower motion scores, Rolling
          Stop has a little more motion, and Run-through Stop has the most
          motion (this is overly simplified for easier explanation). If we
          sample the car's motion after an approach is detected, we can
          then compare the live data with the results of previous examples to
          see which category the event most closely aligns with. The
          comparisons are driven by the machine learning algorithm k-nearest
          neighbors (k-NN), which is ideal for this scenario. That k-NN is
          multi-stage and uses five features in total. Other features help
          earlier in the pipeline; the second stage uses just two of those
          values, shown in the plot below.
        </p>
        <ClusterScatter
          points={CLUSTER_POINTS}
          title="Rolling Stop vs Run-through Stop by Minimum Motion and Total Sign Area"
          xLabel="Minimum Motion (px / Frame)"
          yLabel="Total Sign Area (%)"
        />
        <p>
          Finally, the event has been identified, now we need to wrap things
          up and record the footage. The Pi will record the footage and save
          it to the cloud through the cellular hotspot my phone is hosting.
          The footage will immediately be available for viewing on the hosted
          frontend for anyone curious about my driving. After that, it returns
          to monitoring and waits for the next approach.
        </p>
      </div>
    </section>
  )
}
