# NetraPi edge

Capture, detect, and record stop-sign events on the Raspberry Pi.

## Run capture

From the repo root, with the edge venv active and `src/main/edge/.env` set (`DATABASE_URL`, `NETRAPI_API_URL`, `NETRAPI_API_KEY`):

```bash
# once per device / schema change
alembic -c src/main/db/alembic.ini upgrade head

python src/main/edge/main.py
```

HDMI shows a boot-health overlay (TPU, Wi-Fi, Render, mode), then the live preview. Ctrl+C stops.

## Boot health

Health always runs before capture. `--verify-tpu` is gone.

| Check | Failure |
| ----- | ------- |
| Coral TPU dummy invoke | Process exits 1. Reseat the Coral and rerun. |
| No Wi-Fi association | **OFFLINE**, capture still starts (informational). |
| Associated, but no internet / Render `/health` / `/ready` | **OFFLINE** plus a loud log. Capture still starts. |
| Internet + `/health` + `/ready` | **ONLINE**. |

Offline means local SQLite + MP4s only. The process never upgrades to online later. Online can drop to offline if keep-alive fails.

## Online vs offline

**Online:** session/event JSON and event clips upload during the drive. A keep-alive thread hits `GET /health` every 5 minutes so Render does not idle-sleep. Three failed pings in a row drop this process to offline (no more ingest, no more pings). Trip files still wait for drain.

**Offline:** local only. After you have Wi-Fi, drain leftovers:

```bash
python src/main/edge/main.py --drain-trips both
python src/main/edge/main.py --drain-trips clips
python src/main/edge/main.py --drain-trips trips
```

Pair drain with a scoped local delete of files already in S3 (does not delete S3 objects):

```bash
python src/main/edge/main.py --drain-trips both --delete-after-drain both
python src/main/edge/main.py --drain-trips clips --delete-after-drain clips
python src/main/edge/main.py --drain-trips trips --delete-after-drain trips
```

`--delete-after-drain` can be narrower than drain, e.g. `--drain-trips both --delete-after-drain clips`. Drain wakes Render via `/health` first, then uploads, then deletes. It does not run capture or TPU checks. `--delete-after-drain` requires `--drain-trips`.

## CLI

| Flag | Meaning |
| ---- | ------- |
| `--full-record` / `--no-full-record` | Override trip recording |
| `--drain-trips {clips,trips,both}` | Maintenance upload (required choice) |
| `--delete-after-drain {clips,trips,both}` | After a successful drain, unlink local MP4s already in S3 |
| `--delete-uploaded-local` | Unlink local MP4s already in S3 (no drain) |
| `--delete-all-local` | Unlink finished local MP4s (does not delete S3) |

## What you see

- Overlay + terminal: TPU, Wi-Fi, Render wait, mode
- Online: ingest log lines as events upload
- Drain: counts of clips and/or trip segments uploaded
- Health log: `src/main/edge/logs/health.log`
