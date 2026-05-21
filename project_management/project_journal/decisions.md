# Decisions
**Description:** This file will account for the different decisions I make throughout the project

1. Document test results with a simple excel file as the working document. Can decide to transfer data elsewhere for a more suitable presentation.
2. Test results excel file will contain links to videos providing evidence of passing results
3. I will also store things on Notion for easier access and then update excel periodically. If Notion is repeatedly down, will just update local excel copy.
4. Evidence videos will be hosted on YouTube using unlisted links
5. Will create a YouTube channel for hosting videos
6. Naming of files locally will use this template <test-id>_<short-desc>_<result>.<ext>, examples:
    1. TP-01_camera-mount_stable.mp4
    2. TP-10_audio-feedback_6.8s-pass.mp4
    3. TP-14_offline-queue_upload-pass.mp4
7. Videos will have a standardized format
    1. Title naming: Netrapi <TP-##> - <Test Name> - <result:pass/partial/fail>
        1. TP-10 – Audible Feedback Timing – PASS
    2. Video description: Copy + paste test info (description, test level, verification approach, reqs, steps, pass criteria)
    3. The video will have some text overlay of the test info with same info in part above
8. Other types of evidence (images, screenshots, csvs, logs) will be stored on google drive using my github email
9. ~~Each evidence link will map 1:1 for each artifact (ie wont link to a folder)~~
    1. ~~One test may map to multiple pieces of supporting evidence~~
10. Evidence storage will implement structure where a folder exists for every test even if only one file exists for a test.
    1. Will also store videos uploaded to YouTube here
    2. Wont store test scripts on google drive though
    3. Keep test_scripts in separate top level directory
    4. src code directory will only contain code for the actual application
11. Can add more features onto this project later
    1. Wont modify the mvs
    2. Will make it explicitly clear what was the initial project scope and the additional feature scope, dividing documentation
12. Use online driving clips to build test set
13. These types of driving clips will be extracted: rolling stop, run-through stop, irrelevant stop sign, stop queue, and complete stop
14. Continue to simply write tests to ensure isolated, basic functionality works
15. However, when developing the backlog items, try to sprinkle in designing the actual comprehensive system. Near the end, I'll build the full, complete system.
~~16. Ran the 3 hour long driving script and it failed due to heat issues with the battery and pi.~~
    ~~1. Update the physical installation backlog to not reference this test~~
    ~~2. Create a separate backlog item for heat management and getting the system to work in hot environments (ie not in a closed glovebox if possible)~~
17. Centralized config class with subconfig classes will be used.
    1. This object will be the source of truth for all settings
    2. Classes that are dependent on the config object will only reference the data (@property def width(self) -> int: return self._config.width)
18. Don't worry about detecting additional unsafe events once one is already found and the process of managing the event has not finished
    1. Don't need to make a multithreaded model, don't want to overcomplicate things
    2. Its unlikely 2 events would overlap with one another
    3. There is some potential for there to be a gap in recorded frames between the time the unsafe event recording process has finished and once the rolling buffer starts to be populated again


## Chats
1. https://chatgpt.com/g/g-p-68d48c7970cc8191a8e2c4df2f27f171-netrapi/c/69892c74-d2c8-8328-b704-94eeef46577c
2. https://chatgpt.com/g/g-p-68d48c7970cc8191a8e2c4df2f27f171-netrapi/c/69893a62-2830-8329-b38f-a338725a8cc5