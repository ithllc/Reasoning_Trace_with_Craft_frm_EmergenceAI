#!/usr/bin/env bash
set -euo pipefail

server="${LLAMA_SERVER_BIN:-llama-server}"
port="${LLAMA_PORT:-8080}"
context="${LLAMA_CONTEXT_SIZE:-32768}"
gpu_layers="${LLAMA_GPU_LAYERS:-auto}"

model_args=()
if [[ -n "${LLAMA_MODEL_PATH:-}" ]]; then
  model_args=(-m "$LLAMA_MODEL_PATH")
else
  model_args=(-hf "${LLAMA_HF_MODEL:-bartowski/Qwen_Qwen3.5-9B-GGUF:Q4_K_M}")
fi

exec "$server" \
  "${model_args[@]}" \
  --host 127.0.0.1 \
  --port "$port" \
  --ctx-size "$context" \
  --n-gpu-layers "$gpu_layers" \
  --jinja \
  --flash-attn on
