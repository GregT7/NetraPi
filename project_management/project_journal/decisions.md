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


## Chats
1. https://chatgpt.com/g/g-p-68d48c7970cc8191a8e2c4df2f27f171-netrapi/c/69892c74-d2c8-8328-b704-94eeef46577c
2. https://chatgpt.com/g/g-p-68d48c7970cc8191a8e2c4df2f27f171-netrapi/c/69893a62-2830-8329-b38f-a338725a8cc5