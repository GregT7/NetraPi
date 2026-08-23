# NetraPi documentation propagation map

Use **Yes** = update in same session unless user says doc-only. **Maybe** = confirm intent. **No** = skip unless user asks.

## Files

| Abbrev | Path |
|--------|------|
| MVS | `project_management/specs/mvs.md` |
| TEST | `project_management/specs/test.md` |
| DEC | `project_management/project_journal/decisions.md` |
| RESUME | `project_management/specs/resume.md` |
| MATRIX | `project_management/specs/test_matrix.xlsx` (user-edited only; agent instructs in chat) |
| RETRO | `project_management/project_journal/retro.md` |

**Removed:** `project_journal/sprint.md` — sprint groupings live in `test.md` section headers.

## Change → propagate

### A. MVS goal, constraint, or requirement (M-x.xx / R-x)

| Target | MVS | TEST | DEC | RESUME | MATRIX | RETRO |
|--------|-----|------|-----|--------|--------|-------|
| MVS | — | Yes | Maybe | Maybe S1 | Instruct user | No |
| TEST | Maybe | — | No | No | Yes TP rows | No |
| DEC | Maybe | Maybe | — | Maybe | Maybe | Maybe |
| RESUME | Maybe | No | No | — | No | No |
| MATRIX | No | Instruct user | No | No | — | No |

**Row DEC:** A decision can be process-only (no propagation) or **scope-cutting**—then treat like a mini–scope pivot and check **Maybe** columns. Confirm with the user before editing MVS/tests.

### B. Common change patterns

| Change | MVS | TEST | RESUME | MATRIX | DEC |
|--------|-----|------|--------|--------|-----|
| New M-x.xx requirement | — (source) | Add TP-xx + Reqs | Maybe S1 | Instruct user (new row 16+) | Maybe log process |
| Remove M-x.xx requirement | — (source) | Delete TP-xx that only serve that M; **renumber** remaining tests | Remove/adjust S1 | Instruct user: delete rows + renumber | No |
| Major scope pivot | — (source) | Update affected TP sections + Reqs | S1 targets; S2 only if already done | Instruct user | Maybe record why |
| New TP-xx only (existing M already in MVS) | No | — (source) | No | Instruct user (row 16+) | No |
| Sprint section header wording only | No | — (source) | No | No | No |

### C. Sprint ↔ test alignment (current plan through Sprint 7)

| Sprint (test.md header) | TP range |
|-------------------------|----------|
| Sprint 1 | TP-01–15 |
| Sprint 2 | TP-16–24 |
| Sprint 3 | TP-25–28 |
| Sprint 4 | TP-29–31 |
| Sprint 5 | TP-32–41 |
| Sprint 6 | TP-42–49 |
| Sprint 7 | TP-50–56; AT-7.1, AT-7.2, AT-7.3 |

Frontend, full CI/CD, and collection/evaluation UI tests are **deferred** (generate later).

### D. Resume sections

| Section | Content | Update when |
|---------|---------|-------------|
| S1 | Future targets (pop/MVS) | MVS scope or stack changes |
| S2 | Completed / in progress | Hardware, tests passed, diagrams, prototypes |
| S3 | Final polish | User asks for resume-ready lines |

Never move S1 claim to S2 without implementation + test evidence.

### E. Terminology (keep aligned)

| Concept | Preferred term |
|---------|----------------|
| Study phases | Single collection phase (no baseline/post-baseline) |
| Event classes | run-through, rolling stop, complete stop |
| Cloud persist | Local SQLite → backend-orchestrated one-at-a-time upload when online (presigned PUT to S3; Postgres via backend; no offline queue; no permanent cloud creds on Pi) |
| Evaluation | Model classification accuracy vs manual ground truth |

### F. Coverage index (test.md §8)

After structural changes:

- M-4.10 through M-4.31 (not M-4.42)
- M-10.10, M-10.20–23 (not M-10.30–33)
- TP-01 through TP-56 (current active plan); AT-7.1, AT-7.2, AT-7.3
- M-7.10 through M-7.15 (includes presigned upload URL issuance)
