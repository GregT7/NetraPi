# NetraPi edge

## Commands

```bash
# capture
sudo systemctl start netrapi-edge
sudo systemctl status netrapi-edge
journalctl -u netrapi-edge -f
sudo systemctl stop netrapi-edge
sudo systemctl restart netrapi-edge

# without systemd (from src/main/edge, venv on)
python main.py

# drain + cleanup (stop capture first)
cd ~/Desktop/NetraPi/src/main/edge
source venv/bin/activate

python main.py --drain-trips both
python main.py --drain-trips both --delete-after-drain both

python main.py --delete-uploaded-local   # local only; already in S3
python main.py --delete-all-local        # all finished locals; S3 untouched

# pending trips
sqlite3 ~/Desktop/NetraPi/src/main/db/netrapi.db \
  "SELECT id, init_local_stored, s3_stored, s3_key FROM trip_segment ORDER BY id;"
```

Logs: `journalctl` live · `src/main/data/logs/trip_session_*/` (`trip.log`, `stats.csv`)

---

## Notes

- Clips upload online during the drive; **trips** need `--drain-trips`.
- `--delete-after-drain` only with `--drain-trips`. Never deletes S3 objects.
- TPU fail → exit. No Wi‑Fi / Render → OFFLINE capture still runs.
- Flags: `--full-record` / `--no-full-record`, `--drain-trips {clips,trips,both}`, `--delete-after-drain {…}`, `--delete-uploaded-local`, `--delete-all-local`
