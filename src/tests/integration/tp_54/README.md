# TP-54 — Cross-layer metadata consistency

Run **TP-53 first**. This script opens `tp_53/netrapi.db` and checks that
event / clip / trip ids, `s3_stored`, keys, and sizes are consistent after
CloudIngest confirm. Does **not** load backend `.env`.

Optional live Postgres/S3 console check: AT-7.1 README (laptop).

```bash
source src/tests/integration/venv/bin/activate
python src/tests/integration/tp_53/tp_53_unsafe_event_deployed_backend.py
python src/tests/integration/tp_54/tp_54_cross_layer_metadata.py
```
