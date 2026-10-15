#!/usr/bin/env bash
# Source this helper from launch scripts; paths are relative to this checkout.
PUBLIC_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "$PUBLIC_ROOT/.env" ]]; then
  echo 'Copy .env.example to .env and configure it first.' >&2
  exit 1
fi
set -a
source "$PUBLIC_ROOT/.env"
set +a
export PYTHONPATH="$PUBLIC_ROOT${PYTHONPATH:+:$PYTHONPATH}"
cd "$PUBLIC_ROOT"
