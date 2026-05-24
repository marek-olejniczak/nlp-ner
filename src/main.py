import csv
import json
import random
import re
import time
from pathlib import Path

from .generator import generate_template


DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

PLACEHOLDER_LABELS = {
    "<PERSON>": "PERSON",
    "<HOSPITAL>": "SZPITAL",
    "<DISEASE>": "CHOROBA",
    "<DRUG>": "LEK",
    "<TEST>": "BADANIE",
}

PLACEHOLDER_PATTERN = re.compile(r"<(PERSON|HOSPITAL|DISEASE|DRUG|TEST)>")
TOKEN_PATTERN = re.compile(r"\S+")

DATA_FILES = {
    "<PERSON>": ("persons.csv", ("imie", "nazwisko")),
    "<HOSPITAL>": ("hospitals.csv", "nazwa"),
    "<DISEASE>": ("diseases.csv", "nazwa"),
    "<DRUG>": ("drugs.csv", "nazwa"),
    "<TEST>": ("tests.csv", "nazwa"),
}


def load_persons(csv_path: Path) -> list[str]:
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        required = {"imie", "nazwisko"}
        if not required.issubset(fieldnames):
            raise ValueError(
                f"Brakuje kolumn {sorted(required)} w pliku {csv_path.name}"
            )
        persons = []
        for row in reader:
            imie = (row.get("imie") or "").strip()
            nazwisko = (row.get("nazwisko") or "").strip()
            if imie and nazwisko:
                persons.append(f"{imie} {nazwisko}")
    if not persons:
        raise ValueError(f"Brak danych osob w pliku {csv_path.name}")
    return persons


def load_simple_list(csv_path: Path, column: str) -> list[str]:
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        if column not in fieldnames:
            raise ValueError(
                f"Brakuje kolumny {column} w pliku {csv_path.name}"
            )
        values = [
            (row.get(column) or "").strip()
            for row in reader
            if (row.get(column) or "").strip()
        ]
    if not values:
        raise ValueError(f"Brak danych w kolumnie {column} w pliku {csv_path.name}")
    return values


def load_pools(data_dir: Path) -> dict[str, list[str]]:
    pools: dict[str, list[str]] = {}
    for placeholder, (filename, column) in DATA_FILES.items():
        csv_path = data_dir / filename
        if not csv_path.exists():
            raise FileNotFoundError(f"Brak pliku: {csv_path}")
        if placeholder == "<PERSON>":
            pools[placeholder] = load_persons(csv_path)
        else:
            pools[placeholder] = load_simple_list(csv_path, column)
    return pools


def inject_placeholders(template: str, pools: dict[str, list[str]]):
    mapping: dict[str, str] = {}
    entities: list[dict] = []
    output_parts: list[str] = []
    cursor = 0
    out_len = 0

    for match in PLACEHOLDER_PATTERN.finditer(template):
        output_parts.append(template[cursor:match.start()])
        out_len += len(template[cursor:match.start()])

        placeholder = match.group(0)
        if placeholder not in pools:
            raise ValueError(f"Brak danych dla placeholdera {placeholder}")
        value = mapping.get(placeholder)
        if value is None:
            value = random.choice(pools[placeholder])
            mapping[placeholder] = value

        start = out_len
        output_parts.append(value)
        out_len += len(value)
        end = out_len

        label = PLACEHOLDER_LABELS[placeholder]
        entities.append({"label": label, "start": start, "end": end, "text": value})
        cursor = match.end()

    output_parts.append(template[cursor:])
    text = "".join(output_parts)
    return text, entities


def tokenize_with_offsets(text: str):
    tokens: list[str] = []
    spans: list[tuple[int, int]] = []
    for match in TOKEN_PATTERN.finditer(text):
        tokens.append(match.group(0))
        spans.append((match.start(), match.end()))
    return tokens, spans


def build_biou_tags(text: str, entities: list[dict]) -> tuple[list[str], list[str]]:
    tokens, spans = tokenize_with_offsets(text)
    tags = ["O"] * len(tokens)

    for entity in sorted(entities, key=lambda e: (e["start"], e["end"])):
        ent_start = entity["start"]
        ent_end = entity["end"]
        label = entity["label"]

        indices = [
            i for i, (tok_start, tok_end) in enumerate(spans)
            if tok_start < ent_end and tok_end > ent_start
        ]
        if not indices:
            continue
        if any(tags[i] != "O" for i in indices):
            continue

        if len(indices) == 1:
            tags[indices[0]] = f"U-{label}"
        else:
            tags[indices[0]] = f"B-{label}"
            for idx in indices[1:]:
                tags[idx] = f"I-{label}"

    return tokens, tags


def run(num_samples: int = 100, pause: float = 1.0, seed: int | None = None):
    if seed is not None:
        random.seed(seed)

    pools = load_pools(DATA_DIR)
    OUTPUT_DIR.mkdir(exist_ok=True)

    dataset = []
    total = num_samples

    for i in range(1, total + 1):
        print(f"\n--- [{i}/{total}] ---")
        sample = None

        for attempt in range(3):
            template = generate_template()
            if template is None:
                continue

            text, entities = inject_placeholders(template, pools)
            if PLACEHOLDER_PATTERN.search(text):
                print(f"  [proba {attempt + 1}] Pozostaly placeholdery, powtarzam...")
                continue

            tokens, tags = build_biou_tags(text, entities)
            if not tokens or len(tokens) != len(tags):
                print(f"  [proba {attempt + 1}] Bledna tokenizacja, powtarzam...")
                continue

            sample = {"text": text, "tokens": tokens, "tags": tags}
            break

        if sample is None:
            print("  Pomijam - nie udalo sie wygenerowac po 3 probach")
            continue

        dataset.append(sample)
        print(f"  Tekst: {sample['text'][:80]}...")
        print(f"  Tokeny: {len(sample['tokens'])}")

        if i < total:
            time.sleep(pause)

    output_path = OUTPUT_DIR / "ner_dataset.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    print(f"\nZakonczono! Wygenerowano {len(dataset)} probek -> {output_path}")


if __name__ == "__main__":
    run()
