# TP-41 — Trip segment local persist

Full-session trip recording (`full_record`) writes at least one MP4 segment.
`run_loop` stop finalizes the open segment; SQLite gets a `trip_segment` row
(`local_path` on disk, `s3_stored` null).

```bat
python src\tests\integration\tp_41\tp_41_trip_segment_sqlite.py
```

Needs the same Pi venv as TP-31 (Coral, ffmpeg). Camera is mocked. Leaves
`src/tests/integration/tp_41/netrapi.db` and `trips/`.
