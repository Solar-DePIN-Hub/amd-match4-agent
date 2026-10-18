#!/usr/bin/env bash
# Download open weights into ./models/qwen (run on the AMD notebook or any machine; NOT inside the image build).
set -euo pipefail
MODEL="${1:-Qwen/Qwen3-8B}"   # fallback: Qwen/Qwen3-4B-Instruct-2507 or Qwen/Qwen2.5-7B-Instruct
pip install -q huggingface_hub
python3 -c "from huggingface_hub import snapshot_download as s; s('$MODEL', local_dir='models/qwen', allow_patterns=['*.json','*.safetensors','*.txt','*.model','tokenizer*','merges.txt','vocab.json'])"
du -sh models/qwen
