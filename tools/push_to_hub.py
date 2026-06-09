"""Wypchnij wytrenowany checkpoint NER na Hugging Face Hub (źródło modelu dla appki).

Wymaga zalogowania: `huggingface-cli login` albo env `HF_TOKEN`.

Użycie:
    python -m tools.push_to_hub --checkpoint models/herbert-base-cased/best \
        --repo-id <hf-user-or-org>/herbert-ner-medical-pl [--private]

Na Colabie (gdzie żyje checkpoint) najprościej odpalić to po treningu.
"""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Push checkpointu NER na HF Hub")
    parser.add_argument("--checkpoint", type=Path, required=True, help="np. models/herbert-base-cased/best")
    parser.add_argument("--repo-id", required=True, help="np. user/herbert-ner-medical-pl")
    parser.add_argument("--private", action="store_true")
    args = parser.parse_args()

    from transformers import AutoModelForTokenClassification, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(args.checkpoint)
    model = AutoModelForTokenClassification.from_pretrained(args.checkpoint)

    # id2label/label2id są w config checkpointu — appka polega na nich przy dekodowaniu
    model.push_to_hub(args.repo_id, private=args.private)
    tok.push_to_hub(args.repo_id, private=args.private)
    print(f"Wypchnięto -> https://huggingface.co/{args.repo_id}")
    print(f"Ustaw w appce: export NER_MODEL_ID={args.repo_id}")


if __name__ == "__main__":
    main()
