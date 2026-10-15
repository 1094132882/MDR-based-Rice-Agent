#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/load_env.sh"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11501}"
exec ollama serve
