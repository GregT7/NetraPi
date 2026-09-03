# NetraPi edge

Capture, detect, and record stop-sign events on the Raspberry Pi.

Capture can run under **systemd** (manual start only on this Pi). Trip MP4s
(and any leftover clips) are uploaded with a **separate** `main.py --drain-trips`
command — not by the systemd unit. `main.py` runs Alembic `upgrade head` on the
local SQLite URL at start (capture and drain).

---

## Everyday

### Drive: start / watch / stop capture

```bash
sudo systemctl start netrapi-edge
sudo systemctl status netrapi-edge
journalctl -u netrapi-edge -f    # follow logs (Ctrl+C stops the follow only)
sudo systemctl stop netrapi-edge
```

- `start` / `stop` do not enable boot auto-start.
- Logs for the **service** go to the journal (not your interactive terminal).
- After code changes under `edge/`, `sudo systemctl restart netrapi-edge` to pick them up.

Without systemd (edge venv active): from repo root `python src/main/edge/main.py`,
or from `src/main/edge` run `python main.py`. HDMI shows a boot-health overlay,
then the live preview. Ctrl+C stops.

### After a drive: drain to S3

Event **clips** usually upload during an ONLINE drive. **Trip** segments are
saved locally and only PUT to S3 when you drain.

Stop capture first (avoids fighting over SQLite / USB):

```bash
sudo systemctl stop netrapi-edge

cd ~/Desktop/NetraPi/src/main/edge
source venv/bin/activate

python main.py --drain-trips both    # clips then trips
# or
python main.py --drain-trips trips
python main.py --drain-trips clips
```

Drain is **not** part of `netrapi-edge.service`. Output prints in that terminal
(not `journalctl -u netrapi-edge`). It wakes Render via `GET /health`, then
uploads pending media. Example lines:

```text
[drain] target=both; waking Render via GET /health ...
[drain] Render is up
[drain] trips: 2 pending, 1 already in S3
[ingest] trip_segment 3: PUT trip_….mp4 (... bytes) ...
[ingest] trip_segment 3 uploaded (...)
```

Optional: after a successful drain, unlink local MP4s that are already in S3
(does **not** delete S3 objects):

```bash
python main.py --drain-trips both --delete-after-drain both
python main.py --drain-trips trips --delete-after-drain trips
```

`--delete-after-drain` requires `--drain-trips`.

### Check what’s pending locally

```bash
sqlite3 ~/Desktop/NetraPi/src/main/db/netrapi.db \
  "SELECT id, init_local_stored, s3_stored, s3_key FROM trip_segment ORDER BY id;"
```

Finished trips ready to drain: `init_local_stored=1` and `s3_stored` null.

---

## Setup (once)

### Prerequisites

- Edge venv at `src/main/edge/venv`
- `src/main/edge/.env` with `DATABASE_URL`, `NETRAPI_API_URL`, `NETRAPI_API_KEY`
  (`DATABASE_URL` is local SQLite only, e.g. `sqlite:///netrapi.db`)
- Camera + Coral attached; HDMI session logged in if you want the OpenCV preview
  (`DISPLAY=:0`)

### Install the unit

From the **repo root**:

```bash
sudo cp src/main/edge/netrapi-edge.service /etc/systemd/system/
sudo systemctl daemon-reload
```

Unit paths are for user `terrelgat` and this clone under
`/home/terrelgat/Desktop/NetraPi`. Edit the unit if those change, then
`daemon-reload` again.

**Do not** `systemctl enable netrapi-edge` unless you want capture at every boot.
State should stay `disabled`.

---

## Reference

### Boot health

Health always runs before capture. `--verify-tpu` is gone.

| Check | Failure |
| ----- | ------- |
| Coral TPU dummy invoke | Process exits 1. Reseat the Coral and rerun. |
| No Wi-Fi association | **OFFLINE**, capture still starts (informational). |
| Associated, but no internet / Render `/health` / `/ready` | **OFFLINE** plus a loud log. Capture still starts. |
| Internet + `/health` + `/ready` | **ONLINE**. |

Offline means local SQLite + MP4s only. The process never upgrades to online later. Online can drop to offline if keep-alive fails.

### Online vs offline

**Online:** session/event JSON and event clips upload during the drive. A keep-alive thread hits `GET /health` every 5 minutes so Render does not idle-sleep. Three failed pings in a row drop this process to offline (no more ingest, no more pings). Trip files still wait for drain (see Everyday above).

**Offline:** local only. After Wi-Fi is back, use `--drain-trips` as above.

### CLI

| Flag | Meaning |
| ---- | ------- |
| `--full-record` / `--no-full-record` | Override trip recording |
| `--drain-trips {clips,trips,both}` | Maintenance upload (required choice) |
| `--delete-after-drain {clips,trips,both}` | After a successful drain, unlink local MP4s already in S3 |
| `--delete-uploaded-local` | Unlink local MP4s already in S3 (no drain) |
| `--delete-all-local` | Unlink finished local MP4s (does not delete S3) |

### What you see

- Overlay / journal: TPU, Wi-Fi, Render wait, mode
- Online: `[ingest] event N (rolling-stop|…) …` as events sync / upload
- Drain: `[drain]` inventory + `[ingest] trip_segment … uploaded`
- Health log file: `src/main/edge/logs/health.log`
