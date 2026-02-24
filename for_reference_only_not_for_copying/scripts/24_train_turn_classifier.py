#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import torch
from datasets import Dataset
from sklearn.metrics import accuracy_score
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
    TrainerCallback,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ri_attr.gpu_safety import GPUSafetyController, load_gpu_safety  # noqa: E402


def _patch_accelerate_dispatch_batches() -> None:
    try:
        import inspect
        import accelerate

        if "dispatch_batches" in inspect.signature(accelerate.Accelerator).parameters:
            return

        class AcceleratorPatched(accelerate.Accelerator):  # type: ignore[misc]
            def __init__(self, *args, dispatch_batches=None, **kwargs):
                super().__init__(*args, **kwargs)

        accelerate.Accelerator = AcceleratorPatched  # type: ignore[assignment]
        try:
            import transformers.trainer as trainer_mod

            trainer_mod.Accelerator = AcceleratorPatched  # type: ignore[attr-defined]
        except Exception:
            pass
    except Exception:
        return

MODEL_NAME = "distilbert-base-uncased"
MAX_LENGTH = 256
PER_DEVICE_TRAIN_BATCH = 8
PER_DEVICE_EVAL_BATCH = 8
NUM_EPOCHS = 2
LEARNING_RATE = 3e-5

LABEL_MAP = {"NARRATION": 0, "TURN_CONTINUE": 1, "TURN_START": 2}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train turn predictor")
    parser.add_argument(
        "--windows",
        type=Path,
        default=Path("data/processed/windows/windows.jsonl"),
        help="Windows JSONL",
    )
    parser.add_argument(
        "--labels",
        type=Path,
        default=Path("data/processed/turns/turn_labels.jsonl"),
        help="Turn labels JSONL",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("models/turn_classifier"),
        help="Output model directory",
    )
    parser.add_argument(
        "--gpu-config",
        type=Path,
        default=Path("data/system/gpu_safety.json"),
        help="GPU safety config JSON",
    )
    parser.add_argument(
        "--gpu-safety",
        dest="gpu_safety",
        action="store_true",
        help="Enable GPU safety (default)",
    )
    parser.add_argument(
        "--no-gpu-safety",
        dest="gpu_safety",
        action="store_false",
        help="Disable GPU safety",
    )
    parser.set_defaults(gpu_safety=True)
    return parser.parse_args()


def _format_window(window: dict) -> str:
    prev = " ".join(window.get("prev") or [])
    cur = window.get("cur", "")
    next_ = " ".join(window.get("next") or [])
    return f"PREV: {prev}\nCUR: {cur}\nNEXT: {next_}"


def _load_windows(path: Path) -> dict[str, dict]:
    windows: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            entry = json.loads(line)
            sid = entry.get("sid")
            if sid:
                windows[sid] = entry
    return windows


def _load_labels(path: Path) -> dict[str, str]:
    labels: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            entry = json.loads(line)
            sid = entry.get("sid")
            label = entry.get("label")
            if sid and label in LABEL_MAP:
                labels[sid] = label
    return labels


class GPUSafetyCallback(TrainerCallback):
    def __init__(self, controller: GPUSafetyController) -> None:
        self.controller = controller
        self.start_time = None
        self.steps = 0

    def on_train_begin(self, args, state, control, **kwargs):
        self.start_time = time.time()
        self.steps = 0

    def on_step_end(self, args, state, control, **kwargs):
        if self.start_time is None:
            self.start_time = time.time()
        self.steps += 1
        if self.steps % 20 == 0:
            elapsed = max(time.time() - self.start_time, 1e-6)
            steps_per_sec = self.steps / elapsed
            self.controller.update(steps_per_sec)


def main() -> int:
    args = parse_args()
    _patch_accelerate_dispatch_batches()
    windows_path = REPO_ROOT / args.windows
    labels_path = REPO_ROOT / args.labels
    output_dir = REPO_ROOT / args.output_dir
    gpu_config_path = REPO_ROOT / args.gpu_config

    if not windows_path.exists():
        raise SystemExit(f"Missing windows file: {windows_path}")
    if not labels_path.exists():
        raise SystemExit(f"Missing labels file: {labels_path}")

    windows = _load_windows(windows_path)
    labels = _load_labels(labels_path)

    examples = []
    for sid, label in labels.items():
        window = windows.get(sid)
        if not window:
            continue
        examples.append({"text": _format_window(window), "labels": LABEL_MAP[label]})

    if not examples:
        raise SystemExit("No training examples found")

    dataset = Dataset.from_list(examples)
    dataset = dataset.train_test_split(test_size=0.1, seed=42)
    train_dataset = dataset["train"]
    eval_dataset = dataset["test"]

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=MAX_LENGTH)

    train_dataset = train_dataset.map(tokenize, batched=True, remove_columns=["text"])
    eval_dataset = eval_dataset.map(tokenize, batched=True, remove_columns=["text"])

    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=len(LABEL_MAP)
    )

    args_train = TrainingArguments(
        output_dir=str(output_dir),
        per_device_train_batch_size=PER_DEVICE_TRAIN_BATCH,
        per_device_eval_batch_size=PER_DEVICE_EVAL_BATCH,
        num_train_epochs=NUM_EPOCHS,
        learning_rate=LEARNING_RATE,
        fp16=torch.cuda.is_available(),
        evaluation_strategy="epoch",
        save_strategy="epoch",
        logging_strategy="steps",
        logging_steps=25,
        report_to="none",
    )

    def _compute_metrics(eval_pred):
        logits, labels_arr = eval_pred
        preds = logits.argmax(axis=-1)
        return {"accuracy": accuracy_score(labels_arr, preds)}

    gpu_config = load_gpu_safety(gpu_config_path)
    gpu_config["enabled"] = bool(args.gpu_safety)
    gpu_controller = GPUSafetyController(gpu_config, baseline_throughput=None, mode="turn_train")
    gpu_controller.apply_initial_limit()

    trainer = Trainer(
        model=model,
        args=args_train,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=data_collator,
        compute_metrics=_compute_metrics,
    )
    trainer.add_callback(GPUSafetyCallback(gpu_controller))

    trainer.train()

    output_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    counts = Counter(train_dataset["labels"])
    print(f"[INFO] Train label counts: {dict(counts)}")
    print(f"[INFO] Model saved: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
