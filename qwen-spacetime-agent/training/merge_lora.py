from __future__ import annotations

import argparse
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoProcessor, Qwen3_5ForConditionalGeneration


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", default="Qwen/Qwen3.5-9B")
    parser.add_argument("--adapter", type=Path, default=Path("artifacts/qwen35-agent-lora"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/qwen35-agent-merged"))
    args = parser.parse_args()

    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        args.base_model, torch_dtype=torch.bfloat16, device_map="cpu", low_cpu_mem_usage=True
    )
    merged = PeftModel.from_pretrained(model, args.adapter).merge_and_unload()
    merged.save_pretrained(args.output, safe_serialization=True, max_shard_size="5GB")
    AutoProcessor.from_pretrained(args.base_model).save_pretrained(args.output)


if __name__ == "__main__":
    main()
