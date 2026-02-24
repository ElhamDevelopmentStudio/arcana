#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch
from datasets import Dataset
from collections import Counter

from sklearn.metrics import accuracy_score, confusion_matrix
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


MODEL_NAME = "microsoft/deberta-v3-base"
MAX_LENGTH = 512
PER_DEVICE_TRAIN_BATCH = 1
PER_DEVICE_EVAL_BATCH = 1
GRAD_ACCUM_STEPS = 16
NUM_EPOCHS = 3
LEARNING_RATE = 2e-5

LABEL_MAP = {
    "NARRATION": 0,
    "INTERNAL_THOUGHT": 1,
    "EXTERNAL_SPEECH": 2,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train mode classifier")
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
        help="Enable GPU safety controls (default)",
    )
    parser.add_argument(
        "--no-gpu-safety",
        dest="gpu_safety",
        action="store_false",
        help="Disable GPU safety controls",
    )
    parser.set_defaults(gpu_safety=True)
    parser.add_argument(
        "--gpu-power-limit-percent",
        type=float,
        default=0.0,
        help="Override GPU power limit percent (0 = use config)",
    )
    parser.add_argument(
        "--gpu-max-temp",
        type=float,
        default=0.0,
        help="Override GPU max temp in C (0 = use config)",
    )
    parser.add_argument(
        "--gpu-util-target-min",
        type=float,
        default=0.0,
        help="Override GPU util target min (0 = use config)",
    )
    parser.add_argument(
        "--gpu-util-target-max",
        type=float,
        default=0.0,
        help="Override GPU util target max (0 = use config)",
    )
    parser.add_argument(
        "--gpu-max-slowdown",
        type=float,
        default=0.0,
        help="Override max slowdown ratio (0 = use config)",
    )
    parser.add_argument(
        "--gpu-autotune",
        dest="gpu_autotune",
        action="store_true",
        help="Enable GPU autotune (default)",
    )
    parser.add_argument(
        "--no-gpu-autotune",
        dest="gpu_autotune",
        action="store_false",
        help="Disable GPU autotune",
    )
    parser.set_defaults(gpu_autotune=True)
    parser.add_argument(
        "--perf-baseline",
        type=Path,
        default=Path("data/benchmarks/perf_baseline.json"),
        help="Perf baseline JSON (steps/sec)",
    )
    parser.add_argument(
        "--write-perf-baseline",
        action="store_true",
        help="Write steps/sec to perf baseline after training",
    )
    return parser.parse_args()

def _format_window(window: dict) -> str:
    prev = " ".join(window.get("prev") or [])
    cur = window.get("cur", "")
    next_ = " ".join(window.get("next") or [])
    return f"PREV: {prev}\nCUR: {cur}\nNEXT: {next_}"


def _parse_sentence_index(sid: str) -> int:
    parts = sid.split("-", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid sid format: {sid}")
    return int(parts[1])


def _load_windows(path: Path) -> dict[str, dict]:
    windows: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            entry = json.loads(line)
            sid = entry.get("sid")
            if not sid:
                continue
            windows[sid] = entry
    return windows


def _load_labels(path: Path) -> dict[str, dict]:
    labels: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            entry = json.loads(line)
            sid = entry.get("sid")
            if not sid:
                continue
            labels[sid] = entry
    return labels


class WeightedTrainer(Trainer):
    def __init__(self, *args, class_weight_tensor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weight_tensor = class_weight_tensor

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        labels = inputs.pop("labels")
        weights = inputs.pop("sample_weight", None)
        outputs = model(**inputs)
        logits = outputs.logits
        class_weight = None
        if self.class_weight_tensor is not None:
            class_weight = self.class_weight_tensor.to(logits.device)
        loss_values = torch.nn.functional.cross_entropy(
            logits,
            labels,
            reduction="none",
            weight=class_weight,
        )
        if weights is None:
            loss = loss_values.mean()
        else:
            weights = weights.to(loss_values.dtype)
            loss = (loss_values * weights).sum() / weights.sum().clamp_min(1e-8)
        return (loss, outputs) if return_outputs else loss


def _build_datasets(windows_path: Path, labels_path: Path) -> tuple[Dataset, Dataset]:
    windows = _load_windows(windows_path)
    labels = _load_labels(labels_path)

    train_examples = []
    val_examples = []
    missing_windows = 0

    for sid, label in labels.items():
        window = windows.get(sid)
        if window is None:
            missing_windows += 1
            continue

        mode = label.get("mode")
        if mode not in LABEL_MAP:
            raise ValueError(f"Unknown mode label for {sid}: {mode}")

        sentence_index = _parse_sentence_index(sid)
        weight = 0.5 if label.get("ambiguous") else 1.0
        example = {
            "text": _format_window(window),
            "labels": LABEL_MAP[mode],
            "sample_weight": weight,
        }

        if sentence_index % 10 in {0, 1}:
            val_examples.append(example)
        else:
            train_examples.append(example)

    if missing_windows:
        print(f"[WARN] {missing_windows} labels had no matching window")

    if not train_examples or not val_examples:
        raise ValueError("Train/val split resulted in an empty set")

    return Dataset.from_list(train_examples), Dataset.from_list(val_examples)


def _compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = logits.argmax(axis=-1)
    return {"accuracy": accuracy_score(labels, preds)}


class GPUSafetyCallback(TrainerCallback):
    def __init__(self, controller: GPUSafetyController) -> None:
        self.controller = controller
        self.start_time = None
        self.steps = 0

    def on_train_begin(self, args, state, control, **kwargs):  # noqa: D401
        self.start_time = time.time()
        self.steps = 0

    def on_step_end(self, args, state, control, **kwargs):
        if self.start_time is None:
            self.start_time = time.time()
        self.steps += 1
        if self.steps % 10 == 0:
            elapsed = max(time.time() - self.start_time, 1e-6)
            steps_per_sec = self.steps / elapsed
            self.controller.update(steps_per_sec)


def main() -> int:
    args = parse_args()
    _patch_accelerate_dispatch_batches()
    windows_path = REPO_ROOT / "data" / "processed" / "windows" / "windows.jsonl"
    labels_path = REPO_ROOT / "data" / "processed" / "labels" / "labels.jsonl"
    output_dir = REPO_ROOT / "models" / "mode_classifier"
    label_map_path = REPO_ROOT / "models" / "artifacts" / "mode_label_map.json"
    gpu_config_path = args.gpu_config if args.gpu_config.is_absolute() else REPO_ROOT / args.gpu_config
    perf_baseline_path = (
        args.perf_baseline if args.perf_baseline.is_absolute() else REPO_ROOT / args.perf_baseline
    )

    if not torch.cuda.is_available():
        print("[ERROR] CUDA is required for fp16 training (fatal)", file=sys.stderr)
        return 1

    if not windows_path.exists():
        print("[ERROR] Missing data/processed/windows/windows.jsonl (fatal)", file=sys.stderr)
        return 1
    if not labels_path.exists():
        print("[ERROR] Missing data/processed/labels/labels.jsonl (fatal)", file=sys.stderr)
        return 1

    gpu_config = load_gpu_safety(gpu_config_path)
    if args.gpu_power_limit_percent > 0:
        gpu_config["power_limit_mode"] = "percent"
        gpu_config["power_limit_percent"] = float(args.gpu_power_limit_percent)
    if args.gpu_max_temp > 0:
        gpu_config["max_temp_c"] = float(args.gpu_max_temp)
    if args.gpu_util_target_min > 0:
        gpu_config["util_target_min"] = float(args.gpu_util_target_min)
    if args.gpu_util_target_max > 0:
        gpu_config["util_target_max"] = float(args.gpu_util_target_max)
    if args.gpu_max_slowdown > 0:
        gpu_config["max_slowdown_ratio"] = float(args.gpu_max_slowdown)
    gpu_config["autotune"] = bool(args.gpu_autotune)
    gpu_config["enabled"] = bool(args.gpu_safety)
    baseline_steps_per_sec = None
    if perf_baseline_path.exists():
        try:
            data = json.loads(perf_baseline_path.read_text(encoding="utf-8"))
            baseline_steps_per_sec = data.get("training_steps_per_sec")
        except Exception:
            baseline_steps_per_sec = None
    gpu_controller = GPUSafetyController(
        gpu_config,
        baseline_throughput=baseline_steps_per_sec,
        mode="training",
    )
    gpu_controller.apply_initial_limit()

    label_map_path.parent.mkdir(parents=True, exist_ok=True)
    with label_map_path.open("w", encoding="utf-8") as handle:
        json.dump(LABEL_MAP, handle, indent=2, sort_keys=True)
        handle.write("\n")

    train_dataset, val_dataset = _build_datasets(windows_path, labels_path)

    print(f"[INFO] Train samples: {len(train_dataset)}")
    print(f"[INFO] Val samples: {len(val_dataset)}")
    class_counts = Counter(train_dataset["labels"])
    print(f"[INFO] Train class counts: {dict(class_counts)}")
    total = sum(class_counts.values())
    num_classes = len(LABEL_MAP)
    class_weight_tensor = torch.tensor(
        [total / (num_classes * class_counts.get(i, 1)) for i in range(num_classes)],
        dtype=torch.float32,
    )

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=MAX_LENGTH)

    train_dataset = train_dataset.map(tokenize, batched=True, remove_columns=["text"])
    val_dataset = val_dataset.map(tokenize, batched=True, remove_columns=["text"])

    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(LABEL_MAP),
        torch_dtype=torch.float32,
    )

    args = TrainingArguments(
        output_dir=str(output_dir),
        per_device_train_batch_size=PER_DEVICE_TRAIN_BATCH,
        per_device_eval_batch_size=PER_DEVICE_EVAL_BATCH,
        gradient_accumulation_steps=GRAD_ACCUM_STEPS,
        num_train_epochs=NUM_EPOCHS,
        learning_rate=LEARNING_RATE,
        fp16=True,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        logging_strategy="steps",
        logging_steps=10,
        report_to="none",
    )

    train_start = time.time()
    trainer = WeightedTrainer(
        model=model,
        args=args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        data_collator=data_collator,
        compute_metrics=_compute_metrics,
        class_weight_tensor=class_weight_tensor,
    )
    trainer.add_callback(GPUSafetyCallback(gpu_controller))

    trainer.train()

    train_elapsed = max(time.time() - train_start, 1e-6)
    steps_per_sec = trainer.state.global_step / train_elapsed if trainer.state else 0.0
    if args.write_perf_baseline:
        perf_baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline = {}
        if perf_baseline_path.exists():
            try:
                baseline = json.loads(perf_baseline_path.read_text(encoding="utf-8"))
            except Exception:
                baseline = {}
        baseline["training_steps_per_sec"] = round(steps_per_sec, 4)
        perf_baseline_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")

    output_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    preds = trainer.predict(val_dataset)
    pred_labels = preds.predictions.argmax(axis=-1)
    cm = confusion_matrix(preds.label_ids, pred_labels, labels=[0, 1, 2])
    print("[INFO] Confusion matrix (rows=true, cols=pred) for labels [0,1,2]:")
    for row in cm:
        print("  " + " ".join(f"{val:5d}" for val in row))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
