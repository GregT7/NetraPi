# NetraPi
RaspberryPi project emulating the Netradyne cameras used to monitor Amazon delivery drivers and improve driving quality.

<details>
<summary><strong>Assumptions</strong> (click to expand)</summary>

Classification and field use assume:

- **Single stop sign per encounter** — There are not two visible stop signs on the same road separated by distance. The pipeline expects an approach-then-drop pattern: you pass the sign, it leaves the frame, and bounding-box area falls to ~0. If that pattern does not occur (e.g. a second sign stays in view), classification can fail or misfire.
- **North America / right-hand traffic** — The system is intended only where vehicles drive on the right side of the road (camera/ROI framing and encounter geometry).
- **No lead vehicle blocking the view** — There is not a car queued directly in front of the driver that occludes the stop sign or dominates the road ROI used for motion.

More detail on the classification assumptions lives in [`project_management/diagrams/event_detection.md`](project_management/diagrams/event_detection.md) (§2 MVP assumptions).

</details>

<details>
<summary><strong>Limitations</strong> (click to expand)</summary>

Known constraints of the current edge setup:

- **Low / variable FPS** — Capture and inference rate can dip or vary under load, which affects motion sampling and timing.
- **Recording gaps** — Clips or trip segments may have missing frames or discontinuous stretches when the Pi falls behind.
- **Heat / runtime** — Prolonged operation in Texas heat can overheat the device; long continuous runs are unreliable outdoors in high ambient temperature.
- **ROI motion false positives** — Stop quality is inferred from optical-flow motion in a road region of interest. Extra motion in that ROI (e.g. another car crossing while you are fully stopped at a busy intersection) can look like continued travel, so a safe complete stop may be labeled unsafe (rolling stop or run-through).

</details>

## TPU/AI Notes
- I had to use a very specific tech stack for the ai inference and footage capturing subsystems due to the limitations of the Coral USB TPU. Originally, I was using the native picam but the libraries picam uses are not compatible with the python libraries needed by the TPU. Ergo, I swapped to a usb-based camera. I also was not able to get pycoral to work and opted instead to use solely tflite-runtime.
- Model:
    - Name: SSDLite MobileDet
    - Input Size: 320x320x3
    - Latency: 9.1 ms
    - mAP: 32.9%
    - Link: https://gweb-coral-full.uc.r.appspot.com/models/object-detection/
- Dataset: 
    - Name: Berkeley DeepDrive Dataset (BDD100K)
    - Usage: Helpful for gathering sample clips to test my algorithms on
- Dependencies
    - opencv-python==4.8.1.78
    - Pillow==10.4.0
    - tflite-runtime==2.11.0
    - numpy==1.26.4