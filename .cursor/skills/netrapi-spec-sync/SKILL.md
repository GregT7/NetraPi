---
name: netrapi-spec-sync
description: >-
  Keeps NetraPi planning docs consistent (mvs.md, test.md,
  decisions.md, resume.md) and tells the user what to change in test_matrix.xlsx.
  Use when editing any of those files,
  adding/removing requirements (M-x.xx) or tests (TP-xx), changing project
  scope, or when the user asks to sync, align, or propagate documentation
  changes across specs.
---

# NetraPi spec documentation sync

## Document roles (single source of truth)

| File | Role | Owns |
|------|------|------|
| `project_management/specs/mvs.md` | **Requirements truth** | Goal, constraints, M-x.xx IDs, scope |
| `project_management/specs/test.md` | **Verification + sprint groupings** | TP-xx tests, steps, pass criteria, sprint section headers (through Sprint E for now) |
| `project_management/project_journal/decisions.md` | **Process/architecture choices** | How you test, store evidence, stack choices—not duplicate MVS reqs |
| `project_management/specs/resume.md` | **Outcomes narrative** | Section 1 = future targets; Section 2 = done/in progress with evidence |
| `project_management/specs/test_matrix.xlsx` | **Tracking sheet** | Columns: `test_number`, `test_name`, `description`, `status` (rows from TP-16+) |

**Hierarchy:** `mvs.md` → `test.md`. `resume.md` and `test_matrix` follow; they do not drive requirements.

**Note:** `project_journal/sprint.md` was removed. Sprint schedule/milestones currently live as section headers inside `test.md`. Reintroduce a separate schedule doc only if needed later.

## When to run this skill

Run (or offer to run) a **consistency pass** when:

- The user edits any file in the table above
- Requirements or tests are added, removed, renumbered, or reworded
- Scope changes (e.g. baseline study removed, new R-4 focus)
- User says: sync docs, propagate, align specs, update matrix

**Do not** blindly edit every file on every typo. Use the propagation map in [doc-map.md](doc-map.md).

## Workflow

### 1. Identify the change type

| If the user changed… | Start here |
|----------------------|------------|
| Goal, constraints, new M-x.xx, scope | `mvs.md` first |
| Test steps, TP-xx, pass criteria, sprint sections | `test.md` (confirm M IDs still valid) |
| Evidence process, tooling choice | `decisions.md` — if scope-cutting, propagate per doc-map DEC row |
| Resume wording / accomplishments | `resume.md` (do not invent shipped features) |
| Spreadsheet status only | User updates `test_matrix.xlsx` manually (agent instructs only) |

### 2. Propagate using doc-map

Read [doc-map.md](doc-map.md) for the **Yes / Maybe / No** matrix per change type.

**Always check after MVS changes:**
- `test.md` — Reqs fields on affected TP-xx; add/remove tests; sprint section headers; coverage notes (TP-01–55 for current plan)

**Usually check after test.md changes:**
- `test_matrix.xlsx` — Tell the user what to change manually (never edit the file in Cursor)

**Maybe (ask or infer from user intent):**
- `resume.md` Section 1 if scope/stack changed; Section 2 only for completed work
- `decisions.md` if the change records a new process decision

**Rarely:**
- `retro.md` — only when closing a sprint or reflecting process pain

### 3. Apply edits

- Keep **M-x.xx** and **TP-xx** IDs stable when possible. If a requirement or test is **removed**, delete its tests and **renumber** remaining TP-xx to stay contiguous (01…N); instruct user to renumber matrix `test_number` rows to match.
- **`decisions.md`:** Process-only decisions stay local. **Scope-cutting** decisions may require MVS/test/resume/matrix updates—use DEC row in doc-map (all Maybe).
- Match existing tone: shall-statements in MVS, test plan structure in test.md.
- **resume.md Section 1** = targets from `pop.md`/MVS—not claims of done work.
- **resume.md Section 2** = evidence-backed only (tests passed, hardware installed, diagrams written).
- Do not invent frontend/collection tests beyond Sprint E until the user asks; those are deferred.

### 4. test_matrix.xlsx (manual only — do not edit in Cursor)

**Never** open, write, or modify `project_management/specs/test_matrix.xlsx` via tools. The user maintains this file in Excel.

`test.md` is the source for test definitions. The spreadsheet tracks execution status.

When TP-xx definitions change (rows **16+**), add a **Manual test matrix updates** section in chat with:

1. **Add row** — `test_number`, `test_name`, `description` (leave `status` blank unless user already passed it)
2. **Update row** — which `test_number`(s) and which column(s) changed
3. **Delete row** — which `test_number`(s) to remove
4. **Renumber** — old → new test numbers if TP IDs shifted

Optionally include a **copy-paste CSV block** in chat only (user pastes into Excel)—still do not write the xlsx file.

Schema: `test_number`, `test_name`, `description`, `status`

- `test_number`: numeric only (`16` … `55`), not `TP-16`
- Do not restart numbering at 1 when the user keeps TP-01–15 elsewhere in the sheet
- Remind the user to preserve existing **status** values when only name/description changed

### 5. Finish with a consistency report

End the task with a short report:

```markdown
## Doc sync report
- **Source of change:** [file + summary]
- **Updated:** [list]
- **Reviewed, no change needed:** [list]
- **Manual test matrix:** [bulleted instructions for Excel, or “no change”]
- **Follow-ups:** [user decision / not implemented yet]
```

## Anti-patterns

- Do not copy baseline/post-baseline study language unless it exists in current `mvs.md`.
- Do not add tests in `test.md` without at least one `M-x.xx` in **Reqs**.
- Do not put requirements only in sprint section headers—add to `mvs.md` first.
- Do not update Section 1 resume bullets to past tense for unbuilt cloud/frontend features.
- Do not modify `test_matrix.xlsx` through Cursor—only instruct the user in chat.
- Do not recreate a full frontend/CI/collection test suite unless the user asks.

## Quick reference

- Full propagation matrix: [doc-map.md](doc-map.md)
- Dependency diagram: `.cursor/rules/netrapi-spec-docs.mdc` (Documentation dependency map)
