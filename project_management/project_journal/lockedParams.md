# Locked Parameters
Want to lock down the parameters at least some time before starting recording for the inital baseline phase. This will ensure consistent configuration across the experiment, preventing any potential errors/issues in data analytics. This documetn is created to satisfy the first backlog item "BI-01: Lock MVP Scope & Configuration." This is what it will look like for now.

* Event & Clip Configuration
    * Unsafe driving event: Hard braking (longitudinal deceleration spike)
    * Pre-event buffer: 12 seconds
    * Post-event buffer: 12 seconds
    * Total clip duration: 24 seconds
    * Rolling buffer size: 12 seconds (pre-event capture window)
* Baseline & Post-baseline flags (yaml-like)
    * description: It’s simply a label on every event (and clip) that answers: Was this recorded before feedback existed, or after feedback was enabled?
    * experiment:
        phase: BASELINE # BASELINE | FEEDBACK_ON
        audible_feedback: false
* Recording settings
    * Resolution: 1280×720 (720p)
    * Frame rate: 30 FPS

* Frozen Configuration
    * BASELINE
        - experiment:
            - name: netrapi_hard_braking_v1
            - intervention_phase: BASELINE

        - event_detection:
            - target_event: HARD_BRAKING

        - camera:
            - resolution: 1280x720
            - fps: 30
            - codec: H264

        - clipping:
            - pre_event_buffer_s: 12
            - post_event_buffer_s: 12
            - total_clip_s: 24

        - alerts:
            - audible_feedback: false
    * FEEDBACK_ON
        - experiment:
            - name: netrapi_hard_braking_v1_feedback
            - intervention_phase: FEEDBACK_ON

        - event_detection:
            - target_event: HARD_BRAKING

        - camera:
            - resolution: 1280x720
            - fps: 30
            - codec: H264

        - clipping:
            - pre_event_buffer_s: 12
            - post_event_buffer_s: 12
            - total_clip_s: 24

        - alerts:
            - audible_feedback: true