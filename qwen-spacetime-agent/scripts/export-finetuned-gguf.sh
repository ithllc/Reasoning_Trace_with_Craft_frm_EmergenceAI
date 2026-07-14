#!/usr/bin/env bash
set -euo pipefail

: "${LLAMA_CPP_DIR:?Set LLAMA_CPP_DIR to the llama.cpp checkout}"
merged="${MERGED_MODEL:-artifacts/qwen35-agent-merged}"
f16="${GGUF_F16:-artifacts/qwen35-agent-f16.gguf}"
quantized="${GGUF_OUTPUT:-artifacts/qwen35-agent-q4_k_m.gguf}"

python training/merge_lora.py \
  --base-model "${TRAINING_MODEL:-Qwen/Qwen3.5-9B}" \
  --adapter "${LORA_OUTPUT:-artifacts/qwen35-agent-lora}" \
  --output "$merged"

python "$LLAMA_CPP_DIR/convert_hf_to_gguf.py" "$merged" --outfile "$f16" --outtype f16
"$LLAMA_CPP_DIR/build/bin/llama-quantize" "$f16" "$quantized" Q4_K_M
echo "Created $quantized"
