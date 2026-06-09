"""Ewaluacja wytrenowanego modelu na odłożonym splicie testowym.

Użycie:
    python -m training.evaluate --checkpoint models/herbert-base-cased/best

Test split jest odtwarzany deterministycznie (ten sam seed i frakcje co przy
treningu), więc model nigdy nie widział tych próbek. Raport: precision/recall/F1
per typ encji (seqeval, strict, IOB2) + zapis do JSON.
"""

import argparse
import json
from pathlib import Path

from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
    Trainer,
    TrainingArguments,
)

from datasets import Dataset

from .dataset import build_datasets, load_jsonl, tokenize_and_align
from .metrics import decode_predictions, full_report

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_DATA = REPO_ROOT / "output" / "ner_dataset.jsonl"


def _json_default(obj):
    """seqeval zwraca numpy scalars (np.int64 w support) — json.dump ich nie zna."""
    if hasattr(obj, "item"):
        return obj.item()
    raise TypeError(f"Nieserializowalny typ {type(obj)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ewaluacja NER na test splicie")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--test-file", type=Path, default=None,
                        help="Oceń CAŁY ten plik jsonl (bez splitu) — held-out poza treningiem")
    parser.add_argument("--split", choices=["test", "validation"], default="test")
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--seed", type=int, default=42,
                        help="Musi być ten sam co przy treningu (odtwarza split)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--report-out", type=Path, default=None,
                        help="Domyślnie <checkpoint>/eval_report_<split>.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint)
    model = AutoModelForTokenClassification.from_pretrained(args.checkpoint)

    if args.test_file:
        samples = load_jsonl(args.test_file)
        eval_ds = Dataset.from_list(
            [{"tokens": s["tokens"], "tags": s["tags"]} for s in samples]
        ).map(
            lambda b: tokenize_and_align(b, tokenizer, args.max_length),
            batched=True, remove_columns=["tokens", "tags"],
        )
        report_tag = args.test_file.stem
        print(f"Ewaluacja na pliku '{args.test_file.name}' (cały, bez splitu): {len(eval_ds)} próbek")
    else:
        datasets = build_datasets(
            args.data, tokenizer,
            max_length=args.max_length, seed=args.seed, limit=args.limit,
        )
        eval_ds = datasets[args.split]
        report_tag = args.split
        print(f"Ewaluacja na splicie '{args.split}': {len(eval_ds)} próbek")

    trainer = Trainer(
        model=model,
        args=TrainingArguments(output_dir="/tmp/ner-eval", report_to="none"),
        data_collator=DataCollatorForTokenClassification(tokenizer),
    )
    predictions = trainer.predict(eval_ds)

    true_seqs, pred_seqs = decode_predictions(
        predictions.predictions, predictions.label_ids
    )
    report_text, report_dict = full_report(true_seqs, pred_seqs)
    print(report_text)

    out_path = args.report_out or args.checkpoint / f"eval_report_{report_tag}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, ensure_ascii=False, indent=2, default=_json_default)
    print(f"Raport zapisany w {out_path}")


if __name__ == "__main__":
    main()
