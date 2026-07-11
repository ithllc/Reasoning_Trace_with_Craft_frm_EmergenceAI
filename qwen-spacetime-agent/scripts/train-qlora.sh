#!/usr/bin/env bash
set -euo pipefail

python training/validate_dataset.py "${TRAINING_DATASET:-data/trajectories.jsonl}"
python training/train_qlora.py \
  --dataset "${TRAINING_DATASET:-data/trajectories.jsonl}" \
  --model "${TRAINING_MODEL:-Qwen/Qwen3.5-9B}" \
  --output "${LORA_OUTPUT:-artifacts/qwen35-agent-lora}" \
  --max-length "${TRAIN_MAX_LENGTH:-4096}" \
  --epochs "${TRAIN_EPOCHS:-2}" \
  --learning-rate "${TRAIN_LEARNING_RATE:-2e-4}" \
  --batch-size "${TRAIN_BATCH_SIZE:-1}" \
  --gradient-accumulation "${TRAIN_GRADIENT_ACCUMULATION:-8}"
