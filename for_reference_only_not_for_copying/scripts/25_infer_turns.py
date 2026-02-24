#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from datasets import Dataset
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding


LABEL_MAP = {"NARRATION": 0, "TURN_CONTINUE": 1, "TURN_START": 2}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Infer turn predictions from windows.jsonl")
    parser.add_argument(
        "--windows",
        type=Path,
        default=Path("data/processed/windows/windows.jsonl"),
        help="Windows JSONL",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("models/turn_classifier"),
        help="Turn classifier directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/turns/turn_preds.jsonl"),
        help="Output predictions JSONL",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Batch size",
    )
    return parser.parse_args()


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
            windows.append(json.loads(line))
    return windows


def main() -> int:
    args = parse_args()
    if not args.windows.exists():
        raise SystemExit(f"Missing windows file: {args.windows}")
    if not args.model_dir.exists():
        raise SystemExit(f"Missing model dir: {args.model_dir}")

    windows = _load_windows(args.windows)
    if not windows:
        raise SystemExit("No windows found")

    records = [
        {"sid": entry["sid"], "text": _format_window(entry)}
        for entry in windows
        if "sid" in entry
    ]
    dataset = Dataset.from_list(records)

    tokenizer = AutoTokenizer.from_pretrained(str(args.model_dir), use_fast=True)

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=256)

    dataset = dataset.map(tokenize, batched=True, remove_columns=["text"])
    collator = DataCollatorWithPadding(tokenizer=tokenizer)

    def collate_fn(batch):
        sids = [item.pop("sid") for item in batch]
        model_batch = collator(batch)
        model_batch["sid"] = sids
        return model_batch

    dataloader = DataLoader(dataset, batch_size=args.batch_size, collate_fn=collate_fn)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = AutoModelForSequenceClassification.from_pretrained(str(args.model_dir))
    model.to(device)
    model.eval()

    id_to_label = {idx: label for label, idx in LABEL_MAP.items()}

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        with torch.no_grad():
            for batch in dataloader:
                sids = batch.pop("sid")
                batch = {k: v.to(device) for k, v in batch.items()}
                logits = model(**batch).logits
                probs = torch.softmax(logits, dim=-1).cpu().tolist()
                for sid, prob in zip(sids, probs):
                    best_idx = int(max(range(len(prob)), key=lambda i: prob[i]))
                    handle.write(
                        json.dumps(
                            {
                                "sid": sid,
                                "label": id_to_label[best_idx],
                                "confidence": float(prob[best_idx]),
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )

    print(f"[INFO] Wrote turn predictions: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
