#!/usr/bin/env bash
# Assemble the submission image as "UNMODIFIED mandated base layers + 2 layers" (model, app+deps) with crane,
# without pulling the ~29 GiB base locally. Equivalent Dockerfile: ./Dockerfile.
# usage: scripts/assemble.sh <target ref, e.g. ghcr.io/solar-depin-hub/amd-match4-agent:v1>
# needs: crane, python3 + pip, a registry login for the target, and model weights in ./models/qwen (scripts/fetch_model.sh)
set -euo pipefail
TARGET="$1"
BASE="index.docker.io/rocm/pytorch:rocm10.0_ubuntu26.04_py3.14_pytorch_release_2.13.0"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
W="${WORK:-$(mktemp -d)}"; mkdir -p "$W"
test -f "$ROOT/models/qwen/config.json" || { echo "no weights in models/qwen"; exit 1; }

# layer 1: weights (changes rarely)
mkdir -p "$W/m"; ln -sfn "$ROOT/models" "$W/m/models"
tar -C "$W/m" -h --owner=0 --group=0 --numeric-owner --mtime=2026-10-01 --sort=name -cf "$W/models.tar" models
# layer 2: app + python deps for the base interpreter (CPython 3.14 venv at /opt/venv), installed --no-deps
L="$W/a"; rm -rf "$L"; mkdir -p "$L/app/output" "$L/opt/deps"
cp -r "$ROOT/app/." "$L/app/"; find "$L/app" -name __pycache__ -prune -exec rm -rf {} +
python3 -m pip install --quiet --no-deps --only-binary=:all: --target "$L/opt/deps" \
  --python-version 3.14 --implementation cp --abi cp314 --abi abi3 --abi none \
  --platform manylinux2014_x86_64 --platform manylinux_2_17_x86_64 --platform manylinux_2_28_x86_64 --platform any \
  -r "$ROOT/app/requirements.txt"
rm -rf "$L/opt/deps/bin"
tar -C "$L" --owner=0 --group=0 --numeric-owner --sort=name -cf "$W/app.tar" app opt

crane append -b "$BASE" -f "$W/models.tar" -f "$W/app.tar" -t "$TARGET.tmp"
crane mutate "$TARGET.tmp" \
  --env PYTHONPATH=/opt/deps --env PYTHONDONTWRITEBYTECODE=1 --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 \
  --env HF_HUB_DISABLE_TELEMETRY=1 --env AGENT_LLM=transformers --env AGENT_MODEL=/models/qwen --env AGENT_BUDGET_S=25 \
  --label org.opencontainers.image.source=https://github.com/Solar-DePIN-Hub/amd-match4-agent \
  --label org.opencontainers.image.description="AMD AI League Match 4 web retrieval agent" \
  --workdir /app --cmd python3,/app/app.py,--serve -t "$TARGET"


# checks: base layers identical and first, uncompressed size
python3 - "$BASE" "$TARGET" "$W" <<'PY'
import json, os, subprocess, sys
base, tgt, w = sys.argv[1:]
m = lambda r: json.loads(subprocess.check_output(["crane", "manifest", r]))
b, t = m(base)["layers"], m(tgt)["layers"]
assert [l["digest"] for l in t[:len(b)]] == [l["digest"] for l in b], "BASE LAYERS CHANGED"
add = os.path.getsize(f"{w}/models.tar") + os.path.getsize(f"{w}/app.tar")
print(f"layers={len(t)} (base {len(b)}) compressed={sum(l['size'] for l in t)/2**30:.2f} GiB; "
      f"added uncompressed={add/2**30:.2f} GiB; total ≈ 29.2 + {add/2**30:.2f} = {29.2+add/2**30:.2f} GiB (limit 60)")
print("digest", subprocess.check_output(["crane", "digest", tgt], text=True).strip())
PY
