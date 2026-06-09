"""Fine-tuning encodera do NER na wygenerowanym datasecie.

Użycie:
    python -m training.train                              # HerBERT-base, pełny trening
    python -m training.train --model sdadas/polish-roberta-base-v2
    python -m training.train --limit 64 --max-steps 20 --no-wandb   # smoke test

Hiperparametry domyślne (uzasadnienie):
- lr 2e-5: pretraining używał ~1e-4; tu przesuwamy wagi mikroskopijnie,
  żeby nie zniszczyć wiedzy o polszczyźnie (catastrophic forgetting).
- warmup 10%: głowa klasyfikacyjna startuje z losowych wag, pierwsze
  gradienty są chaotyczne — warmup chroni pretrenowane warstwy.
- 3 epoki, batch 16: standard dla ~5k próbek; load_best_model_at_end
  wybiera checkpoint z najlepszym F1 na walidacji, nie ostatni.
"""

import argparse
import os
from pathlib import Path

from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
    Trainer,
    TrainingArguments,
)

from .dataset import ID2LABEL, LABEL2ID, LABELS, build_datasets, load_jsonl, report_truncation
from .metrics import compute_metrics

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_DATA = REPO_ROOT / "output" / "ner_dataset.jsonl"
DEFAULT_MODEL = "allegro/herbert-base-cased"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tuning NER")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Domyślnie models/<nazwa-modelu>")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--batch-size", type=int, default=8,
                        help="Fizyczny batch (limit pamięci MPS); efektywny = batch * grad-accum")
    parser.add_argument("--grad-accum", type=int, default=2,
                        help="Gradient accumulation — efektywny batch bez kosztu pamięci")
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int, default=None,
                        help="Użyj tylko N pierwszych próbek (smoke test)")
    parser.add_argument("--max-steps", type=int, default=-1,
                        help="Twardy limit kroków treningu (smoke test)")
    parser.add_argument("--fp16", action="store_true",
                        help="Mixed precision — GPU z tensor cores (T4/V100/A100), nie MPS")
    parser.add_argument("--no-wandb", action="store_true")
    parser.add_argument("--wandb-project", default="nlp-ner")
    parser.add_argument("--wandb-entity", default=None,
                        help="Username/team w W&B — nadpisuje domyślną organizację konta")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    model_short = args.model.split("/")[-1]
    output_dir = args.output_dir or REPO_ROOT / "models" / model_short
    effective_batch = args.batch_size * args.grad_accum
    # nazwa datasetu w run name — runy na różnych przestrzeniach etykiet
    # (5 vs 9 typów encji) muszą być rozróżnialne w W&B
    run_name = (f"{model_short}-{args.data.stem}"
                f"-lr{args.lr}-bs{effective_batch}-ep{args.epochs}")

    if args.no_wandb:
        report_to = "none"
    else:
        report_to = "wandb"
        os.environ["WANDB_PROJECT"] = args.wandb_project
        if args.wandb_entity:
            os.environ["WANDB_ENTITY"] = args.wandb_entity

    tokenizer = AutoTokenizer.from_pretrained(args.model)

    # Raport truncation: ile dokumentów przekracza limit subwordów
    raw_samples = load_jsonl(args.data)
    if args.limit:
        raw_samples = raw_samples[: args.limit]
    n_truncated = report_truncation(raw_samples, tokenizer, args.max_length)
    print(f"Próbki przekraczające {args.max_length} subwordów (obcięte): "
          f"{n_truncated}/{len(raw_samples)}")

    datasets = build_datasets(
        args.data, tokenizer,
        max_length=args.max_length, seed=args.seed, limit=args.limit,
    )
    print({name: len(ds) for name, ds in datasets.items()})

    model = AutoModelForTokenClassification.from_pretrained(
        args.model,
        num_labels=len(LABELS),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        run_name=run_name,
        report_to=report_to,
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        warmup_ratio=0.1,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_steps=25,
        fp16=args.fp16,
        disable_tqdm=False,
        seed=args.seed,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=datasets["train"],
        eval_dataset=datasets["validation"],
        data_collator=DataCollatorForTokenClassification(tokenizer),
        compute_metrics=compute_metrics,
    )

    trainer.train()

    # Zapis najlepszego modelu + tokenizera w jednym miejscu
    final_dir = output_dir / "best"
    trainer.save_model(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))
    print(f"\nNajlepszy model zapisany w {final_dir}")

    metrics = trainer.evaluate()
    print(f"Walidacja (najlepszy checkpoint): {metrics}")

    # Najlepszy checkpoint jako artefakt W&B — sesja Colaba jest ulotna, model nie może zginąć.
    # Logujemy w aktywnym runie (ten proces go stworzył przez WandbCallback).
    if report_to == "wandb":
        import wandb
        if wandb.run is not None:
            artifact = wandb.Artifact(
                name=f"{model_short}-ner",
                type="model",
                metadata={
                    "base_model": args.model,
                    "eval_f1": metrics.get("eval_f1"),
                    "num_labels": len(LABELS),
                    "dataset": args.data.name,
                },
            )
            artifact.add_dir(str(final_dir))
            wandb.log_artifact(artifact)
            print(f"Artefakt W&B: {model_short}-ner (eval_f1={metrics.get('eval_f1'):.4f})")
        else:
            print("UWAGA: brak aktywnego runu W&B — artefakt nie zalogowany")


if __name__ == "__main__":
    main()
