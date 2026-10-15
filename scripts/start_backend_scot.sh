#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/load_env.sh"
: "${NEO4J_PASSWORD:?Set NEO4J_PASSWORD in .env}"
export NEO4J_USER="${NEO4J_USER:-$NEO4J_USERNAME}"
exec python -m flask --app rice_Python.app:app run --host "${BACKEND_HOST:-127.0.0.1}" --port "${BACKEND_PORT:-11500}"
