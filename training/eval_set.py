"""Konwersja golden test setu (inline markup od LLM) -> ewaluacja modelu.

LLM generuje teksty z encjami oznaczonymi inline: `<PERSON>Jan Nowak</PERSON>`.
Ten moduł:
  1. parsuje markup -> czysty tekst + dokładne char spany encji (deterministycznie,
     bez zgadywania pozycji — pozycja wynika wprost z markupu),
  2. tokenizuje (whitespace, jak dane treningowe) i buduje tagi IOB2,
  3. odpala model na CAŁYM zbiorze (bez splitu) i liczy seqeval per typ encji.

Walidacja jest głośna: niezamknięty tag, zagnieżdżenie, nieznana etykieta ->
wyjątek z numerem próbki. Lepszy wybuch niż cichy, wadliwy gold.

Użycie:
    python -m training.eval_set --input golden.json --checkpoint models/herbert-base-cased/best
    python -m training.eval_set --input golden.json --convert-only --save-jsonl golden.jsonl
"""

import argparse
import json
import re
from pathlib import Path

from datasets import Dataset

from .dataset import ID2LABEL, LABEL2ID, LABELS, tokenize_and_align

LABEL_SET = {label[2:] for label in LABELS if label != "O"}  # {PERSON, CHOROBA, ...}
TAG_RE = re.compile(r"<(/?)([A-Z]+)>")
TOKEN_PATTERN = re.compile(r"\S+")


class MarkupError(ValueError):
    """Błąd w strukturze inline markup — zawiera numer próbki."""


def parse_markup(text: str, sample_idx: int) -> tuple[str, list[dict]]:
    """`<TAG>treść</TAG>` -> (czysty tekst, [{label, start, end, text}]).

    Stos głębokości 1 (brak zagnieżdżania). Offsety liczone w czystym tekście.
    """
    clean_parts: list[str] = []
    offset = 0
    entities: list[dict] = []
    open_label: str | None = None
    open_start = 0
    pos = 0

    for m in TAG_RE.finditer(text):
        segment = text[pos:m.start()]
        clean_parts.append(segment)
        offset += len(segment)

        is_close = m.group(1) == "/"
        label = m.group(2)

        if not is_close:
            if open_label is not None:
                raise MarkupError(
                    f"Próbka {sample_idx}: zagnieżdżony <{label}> wewnątrz <{open_label}>"
                )
            if label not in LABEL_SET:
                raise MarkupError(
                    f"Próbka {sample_idx}: nieznana etykieta <{label}> "
                    f"(dozwolone: {sorted(LABEL_SET)})"
                )
            open_label = label
            open_start = offset
        else:
            if open_label is None:
                raise MarkupError(f"Próbka {sample_idx}: </{label}> bez otwarcia")
            if label != open_label:
                raise MarkupError(
                    f"Próbka {sample_idx}: </{label}> zamyka <{open_label}>"
                )
            entities.append({"label": open_label, "start": open_start, "end": offset})
            open_label = None

        pos = m.end()

    clean_parts.append(text[pos:])
    if open_label is not None:
        raise MarkupError(f"Próbka {sample_idx}: niezamknięty <{open_label}>")

    clean_text = "".join(clean_parts)
    for ent in entities:
        ent["text"] = clean_text[ent["start"]:ent["end"]]
    # puste encje (<PERSON></PERSON>) odrzucamy z ostrzeżeniem
    kept = [e for e in entities if e["text"].strip()]
    if len(kept) != len(entities):
        print(f"  [próbka {sample_idx}] pominięto {len(entities) - len(kept)} pustych encji")
    return clean_text, kept


def build_iob2(clean_text: str, entities: list[dict]) -> tuple[list[str], list[str]]:
    """Czysty tekst + char spany -> tokeny (whitespace) + tagi IOB2.

    Token należy do encji, jeśli jego span nachodzi na span encji. Bez U- (IOB2):
    encja jednotokenowa to po prostu B-.
    """
    tokens, spans = [], []
    for m in TOKEN_PATTERN.finditer(clean_text):
        tokens.append(m.group(0))
        spans.append((m.start(), m.end()))

    tags = ["O"] * len(tokens)
    for ent in sorted(entities, key=lambda e: (e["start"], e["end"])):
        indices = [
            i for i, (ts, te) in enumerate(spans)
            if ts < ent["end"] and te > ent["start"]
        ]
        if not indices or any(tags[i] != "O" for i in indices):
            continue  # brak pokrycia lub kolizja z już otagowaną encją
        tags[indices[0]] = f"B-{ent['label']}"
        for idx in indices[1:]:
            tags[idx] = f"I-{ent['label']}"
    return tokens, tags


def load_markup_json(path: Path) -> list[str]:
    """Wczytaj JSON od LLM. Toleruje ```json fences oraz listę str / listę {text}."""
    raw = path.read_text(encoding="utf-8").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw).strip()
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("Oczekiwano tablicy JSON na najwyższym poziomie")
    texts = []
    for i, item in enumerate(data):
        if isinstance(item, str):
            texts.append(item)
        elif isinstance(item, dict) and "text" in item:
            texts.append(item["text"])
        else:
            raise ValueError(f"Próbka {i}: oczekiwano str albo obiektu z polem 'text'")
    return texts


def convert(path: Path) -> list[dict]:
    """JSON z markupem -> lista {text, tokens, tags} (jak format treningowy)."""
    texts = load_markup_json(path)
    samples = []
    for i, text in enumerate(texts):
        clean_text, entities = parse_markup(text, i)
        tokens, tags = build_iob2(clean_text, entities)
        samples.append({"text": clean_text, "tokens": tokens, "tags": tags})
    return samples


def _json_default(obj):
    if hasattr(obj, "item"):
        return obj.item()
    raise TypeError(f"Nieserializowalny typ {type(obj)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ewaluacja na golden test secie (inline markup)")
    parser.add_argument("--input", type=Path, required=True, help="JSON od LLM z inline markup")
    parser.add_argument("--checkpoint", type=Path, help="Model do ewaluacji (pomiń przy --convert-only)")
    parser.add_argument("--convert-only", action="store_true", help="Tylko konwersja, bez modelu")
    parser.add_argument("--save-jsonl", type=Path, default=None, help="Zapisz skonwertowany zbiór")
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--report-out", type=Path, default=None)
    args = parser.parse_args()

    samples = convert(args.input)
    from collections import Counter
    ent_counts = Counter(t.split("-", 1)[1] for s in samples for t in s["tags"] if t != "O")
    print(f"Skonwertowano {len(samples)} próbek | encje per typ: {dict(ent_counts.most_common())}")

    if args.save_jsonl:
        with open(args.save_jsonl, "w", encoding="utf-8") as f:
            for s in samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        print(f"Zapisano {args.save_jsonl}")

    if args.convert_only:
        return
    if not args.checkpoint:
        parser.error("--checkpoint wymagany bez --convert-only")

    # import dopiero tu — konwersja sama nie potrzebuje torcha/modelu
    from transformers import (
        AutoModelForTokenClassification,
        AutoTokenizer,
        DataCollatorForTokenClassification,
        Trainer,
        TrainingArguments,
    )
    from .metrics import decode_predictions, full_report

    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint)
    model = AutoModelForTokenClassification.from_pretrained(args.checkpoint)

    # sanity: etykiety checkpointu muszą zgadzać się z naszą przestrzenią
    if model.config.id2label and len(model.config.id2label) != len(LABELS):
        print(f"  UWAGA: model ma {len(model.config.id2label)} klas, oczekiwano {len(LABELS)} "
              f"— inna przestrzeń etykiet niż golden set!")

    ds = Dataset.from_list([{"tokens": s["tokens"], "tags": s["tags"]} for s in samples])
    ds = ds.map(
        lambda b: tokenize_and_align(b, tokenizer, args.max_length),
        batched=True, remove_columns=["tokens", "tags"],
    )

    trainer = Trainer(
        model=model,
        args=TrainingArguments(output_dir="/tmp/ner-eval-golden", report_to="none"),
        data_collator=DataCollatorForTokenClassification(tokenizer),
    )
    predictions = trainer.predict(ds)
    true_seqs, pred_seqs = decode_predictions(predictions.predictions, predictions.label_ids)
    report_text, report_dict = full_report(true_seqs, pred_seqs)
    print(report_text)

    out_path = args.report_out or args.checkpoint / "eval_report_golden.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, ensure_ascii=False, indent=2, default=_json_default)
    print(f"Raport zapisany w {out_path}")


if __name__ == "__main__":
    main()
