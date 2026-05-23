# 🌀 Retrospective #1 – First Sprint While Working

## 🧭 Review
* **Dates:** January 24th - May 20 (2026)
* **Standup Participation:** 44%
  * **Total Days Worked:** 51 days
  * **Total Days:** 116 days
  
## 📋 Summary
**Date:** Wednesday, May 20, 2026

**What Went Well**
- Was able to get the system physically setup and working
  - Physically installing anything is not something I have a lot of experience in
  - Adapted to the challenge by 3D printing my own design
  - Realized some designs were bad and needed to be redone, was willing to put in the effort to get this done even though I really didn't want to
  - Attempted several different physical approaches until finding one that is ideal which took some patience
- Bought items off Amazon for rapid testing instead of doing a ton of research -- much faster to figure out what works and what doesn't by physically having the item.
- Got the TPU hardware & software working which was a huge pain to figure out. Had to do a lot of troubleshooting
- Didn't give up due to frustration over troubleshooting the initial setup of everything
- Started using cursor to speed up the dev process
- Designed things before actually writing any code
  - Made flowcharts and uml diagrams which will make writing the code a lot easier
- Was disciplined on scope hardening -- decided on just implementing rolling stop/run-through stop unsafe event
- Created a dedicated decisions.md file to help organize my thoughts and the direction of the project.
- Centralized sprints/retrospectives into just a singular file each
- Less focus on documenting sprints/standups -- shouldn't take that much time
- Recorded evidence for all my tests
- Wrote specialized tests to capture specific functionality needed -- really helpful when I drafted the design and putting everything together
  - This lessens the mental load
- Still able to contribute to this project while working 9-5
- Didn't start working on a separate project

**What Didn't Go Well**
- Didn't consistently work on the project
- Planned on doing weekly presentations, but pretty much have only done 2 or 3
- It's taking me significantly longer to complete each backlog than I had originally intended
- Multiple different sources of truth makes it confusing where to look/what to implement
  - Notion: backlog items
  - GitHub: sprint.md, decisions.md, tests.md, mvs.md
- Spent too long on "one" sprint -- probably should have been 2 or 3 sprints
- Kept changing test/backlog items

## 🧩 Problems

**Issues Identified**
- Trying to plan too far ahead
  - ruins the excitement
  - the details don't line up when its time to execute
  - creates more work in the long term (having to shift things around, delete things, create new tasks)
  - forget what needs to be accomplished after making the plan and some time passes
- Confusion/overwhelm over which documents to follow for implementation advice
- It doesn't make sense to do the post improvement study unless I detect more unsafe event types other than just stopping at stop signs. I already do this pretty well, so trying to improve my driving wont help that much.
- design.md is not updated
- event_clip_pipeline.md contains the design for a bunch of stuff.

**Root Cause**
- Using AI for test/backlog creation: if it doesn't make full sense to me at the time of creation, its not going to make sense later
- Writing out specific details for the work items at the very beginning of the project
- The purpose/approach to using the documents (test.md, mvs.md, sprint.md, decisions.md) is a little bit confusing/overwhelming
- Trying to perfect a bunch of small things doesn't necessarily amount to big or notable accomplishments of the project.

## 🛠️ Solutions
- Using cursor to create tests/backlog items is fine as long as it makes sense to me at the time of creation.
  - If it doesn't make sense to me, keep asking questions until it does and then add a human readable explanation that I can understand before moving on
  - If it never makes sense, don't use it
- Remove the study aspect from mvs + test.md
- For any proposed change: ask myself if it would help the resume bullet points.
- It's fine to update documents, just ensure the dependency items are also updated
  - Consider creating a dependency diagram in mermaid, and then feeding to cursor so it knows when to automatically update other items 
    - If we change mvs.md, then well need to update test.md, test_matrix, sprint, decisions but some updates for decisions.md might not prompt any additional changes
  - test_matrix.xlsx, tests.md, sprint.md, decisions.md, mvs.md
  - Look into creating a cursor rule or skill to make this process easier
- Break up event_clip_pipeline.md
  - There are a bunch of design ideas combined into a singular document
  - Maybe we could create a subfolder for system design where event_clip_pipeline.md can reside
  - Create a bunch of sub diagrams

**Action Plan**
- Remove study aspect + potentially other related items from documentation
  - decisions.md
  - mvs.md
  - test.md
  - test_matrix.md
  - resume.md
- Quick documentation updates
  - Create dependency diagram for documentations
  - Start using cursor rules/skills
  - Test out the rules, if they don't work well, discard them
- Update the out of sync test_matrix.xlsx
- Update resume.md with any new items
- Break up clip_event_pipeline.md into individual diagrams

---

# 🌀 Retrospective #1 – Insert title here

## 🧭 Review
* **Dates:** 
* **Standup Participation:**
  * **Total Standups:**  
  * **Total Days:**
  
## 📋 Summary
**Date:** Day of Week, Month Day, Year (Tuesday, June 17, 2025)

**What Went Well**

**What Didn't Go Well**

## 🧩 Problems

**Issues Identified**

**Root Cause**

## 🛠️ Solutions

**Proposed Solutions**

**Action Plan**


---