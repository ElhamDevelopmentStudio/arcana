#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import torch
from datasets import Dataset
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding


MODEL_DIRNAME = "models/mode_classifier"
LABEL_MAP_PATH = "models/artifacts/mode_label_map.json"
WINDOWS_PATH = "data/processed/windows/windows.jsonl"
OUTPUT_PATH = "data/processed/predictions/mode_preds.jsonl"
MAX_LENGTH = 512
BATCH_SIZE = 4


def _format_window(window: dict) -> str:
    prev = " ".join(window.get("prev") or [])
    cur = window.get("cur", "")
    next_ = " ".join(window.get("next") or [])
    return f"PREV: {prev}\nCUR: {cur}\nNEXT: {next_}"


def _load_windows(path: Path) -> list[dict]:
    windows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            entry = json.loads(line)
            windows.append(entry)
    return windows


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    windows_path = repo_root / WINDOWS_PATH
    model_dir = repo_root / MODEL_DIRNAME
    label_map_path = repo_root / LABEL_MAP_PATH
    output_path = repo_root / OUTPUT_PATH

    if not windows_path.exists():
        print("[ERROR] Missing data/processed/windows/windows.jsonl (fatal)", file=sys.stderr)
        return 1
    if not model_dir.exists():
        print("[ERROR] Missing models/mode_classifier (fatal)", file=sys.stderr)
        return 1
    if not label_map_path.exists():
        print("[ERROR] Missing models/artifacts/mode_label_map.json (fatal)", file=sys.stderr)
        return 1

    with label_map_path.open("r", encoding="utf-8") as handle:
        label_map = json.load(handle)
    id_to_label = {idx: label for label, idx in label_map.items()}
    label_order = [id_to_label[i] for i in range(len(id_to_label))]

    windows = _load_windows(windows_path)
    if not windows:
        print("[ERROR] windows.jsonl is empty (fatal)", file=sys.stderr)
        return 1

    records = [
        {"sid": entry["sid"], "text": _format_window(entry)}
        for entry in windows
        if "sid" in entry
    ]
    dataset = Dataset.from_list(records)

    tokenizer = None
    try:
        tokenizer = AutoTokenizer.from_pretrained(str(model_dir), use_fast=True)
    except Exception as exc:
        print(f"[WARN] Fast tokenizer failed ({exc}); trying slow tokenizer")
        try:
            tokenizer = AutoTokenizer.from_pretrained(str(model_dir), use_fast=False)
        except Exception as slow_exc:
            print(f"[WARN] Slow tokenizer failed ({slow_exc}); trying base model tokenizer")

    if tokenizer is None:
        fallback_name = None
        try:
            with (model_dir / "config.json").open("r", encoding="utf-8") as handle:
                cfg = json.load(handle)
                fallback_name = cfg.get("_name_or_path")
        except Exception:
            fallback_name = None
        if not fallback_name:
            fallback_name = "microsoft/deberta-v3-base"
        tokenizer = AutoTokenizer.from_pretrained(fallback_name, use_fast=True)

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=MAX_LENGTH)

    dataset = dataset.map(tokenize, batched=True, remove_columns=["text"])

    collator = DataCollatorWithPadding(tokenizer=tokenizer)

    def collate_fn(batch):
        sids = [item.pop("sid") for item in batch]
        model_batch = collator(batch)
        model_batch["sid"] = sids
        return model_batch

    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, collate_fn=collate_fn)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    model.to(device)
    model.eval()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        with torch.no_grad():
            for batch in dataloader:
                sids = batch.pop("sid")
                batch = {k: v.to(device) for k, v in batch.items()}
                logits = model(**batch).logits
                probs = torch.softmax(logits, dim=-1).cpu().tolist()
                for sid, prob in zip(sids, probs):
                    handle.write(
                        json.dumps(
                            {
                                "sid": sid,
                                "probs": {label: prob[i] for i, label in enumerate(label_order)},
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )

    print(f"[INFO] Wrote predictions to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
