#!/bin/bash

echo "=== Running migrations ==="
python -m app.migrate || echo "Migration failed (non-fatal)"

echo "=== Testing app import ==="
python -c "
import traceback
try:
    from app.main import app
    print('IMPORT OK')
except Exception:
    traceback.print_exc()
    print('IMPORT FAILED')
"

echo "=== Starting uvicorn on port $PORT ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --log-level info
