"""Capability-gated LoRA/full fine-tuning request construction."""

from __future__ import annotations


def build_request(*, exact_model: str, training_file: str, validation_file: str | None,
                  training_mode: str, hyperparameters: dict, capabilities: dict, seed: int, suffix: str) -> dict:
    if training_mode not in {"lora", "full"}:
        raise ValueError("training_mode must be lora or full")
    if not capabilities.get(f"{training_mode}_supported", False):
        raise ValueError(f"exact model does not support {training_mode} training")
    resolved = dict(hyperparameters)
    resolved["lora"] = training_mode == "lora"
    if training_mode == "full":
        for key in ("lora_r", "lora_alpha", "lora_dropout"):
            resolved.pop(key, None)
    request = {"model": exact_model, "training_file": training_file, "suffix": suffix,
               "hyperparameters": resolved, "seed": seed}
    if validation_file:
        request["validation_file"] = validation_file
    return request
