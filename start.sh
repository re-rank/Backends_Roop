#!/bin/bash
set -e

echo "=== Running migrations ==="
python -m app.migrate 2>&1 || echo "Migration failed (non-fatal)"

echo "=== Testing app import ==="
python -c "
import traceback
try:
    from app.main import app
    print('IMPORT OK')
except Exception:
    traceback.print_exc()
    print('IMPORT FAILED')
" 2>&1

echo "=== Starting uvicorn on port $PORT ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --log-level info 2>&1
