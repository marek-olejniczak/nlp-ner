"""Ładowanie datasetu NER: JSONL -> HF Dataset z wyrównanymi etykietami.

Decyzje projektowe:
- Konwersja BIOU -> IOB2 (U-X staje się B-X). Mniej klas (11 zamiast 16),
  prostsza "gramatyka" tagów, ta sama informacja — pojedynczy token encji
  to po prostu samotne B-X. seqeval w trybie strict wspiera IOB2 wprost.
- Label alignment: pierwszy subword słowa dostaje etykietę słowa, pozostałe
  subwordy i tokeny specjalne dostają -100 (ignore_index w CrossEntropyLoss),
  więc nie wnoszą nic do lossu.
- Split 80/10/10 deterministyczny (seed), per dokument.
"""

import json
import random
from pathlib import Path

from datasets import Dataset
from tqdm.auto import tqdm

ENTITY_TYPES = [
    "ADDRESS",
    "DATE",
    "DISEASE",
    "DRUG",
    "HOSPITAL",
    "PERSON",
    "PESEL",
    "PHONE",
    "TEST",
]
LABELS = ["O"] + [f"{prefix}-{ent}" for ent in ENTITY_TYPES for prefix in ("B", "I")]
LABEL2ID = {label: i for i, label in enumerate(LABELS)}
ID2LABEL = {i: label for label, i in LABEL2ID.items()}


def biou_to_iob2(tags: list[str]) -> list[str]:
    """U-X -> B-X; B/I/O bez zmian. (Generator nie emituje L-, mimo README.)"""
    return [f"B-{t[2:]}" if t.startswith("U-") else t for t in tags]


def load_jsonl(path: Path) -> list[dict]:
    samples = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            sample = json.loads(line)
            if len(sample["tokens"]) != len(sample["tags"]):
                raise ValueError(
                    f"Linia {line_no}: tokens ({len(sample['tokens'])}) != tags ({len(sample['tags'])})"
                )
            sample["tags"] = biou_to_iob2(sample["tags"])
            unknown = set(sample["tags"]) - set(LABELS)
            if unknown:
                raise ValueError(f"Linia {line_no}: nieznane tagi {unknown}")
            samples.append(sample)
    if not samples:
        raise ValueError(f"Brak próbek w {path}")
    return samples


def split_samples(
    samples: list[dict],
    seed: int = 42,
    val_frac: float = 0.1,
    test_frac: float = 0.1,
) -> dict[str, list[dict]]:
    """Deterministyczny split. Test odkładamy raz i nie dotykamy do końcowej ewaluacji."""
    rng = random.Random(seed)
    indices = list(range(len(samples)))
    rng.shuffle(indices)

    n = len(samples)
    n_test = int(n * test_frac)
    n_val = int(n * val_frac)

    test_idx = indices[:n_test]
    val_idx = indices[n_test : n_test + n_val]
    train_idx = indices[n_test + n_val :]

    return {
        "train": [samples[i] for i in train_idx],
        "validation": [samples[i] for i in val_idx],
        "test": [samples[i] for i in test_idx],
    }


def tokenize_and_align(batch: dict, tokenizer, max_length: int = 512) -> dict:
    """Tokenizacja subwordowa + przypisanie etykiet słów do subwordów.

    word_ids() mapuje każdy subword na indeks słowa wejściowego.
    Pierwszy subword słowa niesie etykietę, reszta dostaje -100.
    """
    encoding = tokenizer(
        batch["tokens"],
        is_split_into_words=True,
        truncation=True,
        max_length=max_length,
    )

    all_labels = []
    for i, tags in enumerate(batch["tags"]):
        word_ids = encoding.word_ids(batch_index=i)
        labels = []
        previous_word_id = None
        for word_id in word_ids:
            if word_id is None:  # [CLS], [SEP], padding
                labels.append(-100)
            elif word_id != previous_word_id:  # pierwszy subword słowa
                labels.append(LABEL2ID[tags[word_id]])
            else:  # kolejny subword tego samego słowa
                labels.append(-100)
            previous_word_id = word_id
        all_labels.append(labels)

    encoding["labels"] = all_labels
    return encoding


def report_truncation(samples: list[dict], tokenizer, max_length: int = 512) -> int:
    """Ile próbek przekracza limit subwordów (tracimy ogon dokumentu przy treningu)."""
    truncated = 0
    for sample in tqdm(samples, desc="Sprawdzanie truncation", unit="próbka"):
        n_subwords = len(
            tokenizer(sample["tokens"], is_split_into_words=True)["input_ids"]
        )
        if n_subwords > max_length:
            truncated += 1
    return truncated


def build_datasets(
    data_path: Path,
    tokenizer,
    max_length: int = 512,
    seed: int = 42,
    limit: int | None = None,
) -> dict[str, Dataset]:
    """Pełny pipeline: JSONL -> split -> tokenizacja -> HF Dataset per split."""
    samples = load_jsonl(data_path)
    if limit is not None:
        samples = samples[:limit]

    splits = split_samples(samples, seed=seed)

    datasets = {}
    for split_name, split_samples_list in splits.items():
        ds = Dataset.from_list(
            [{"tokens": s["tokens"], "tags": s["tags"]} for s in split_samples_list]
        )
        datasets[split_name] = ds.map(
            lambda batch: tokenize_and_align(batch, tokenizer, max_length),
            batched=True,
            remove_columns=["tokens", "tags"],
        )

    return datasets
