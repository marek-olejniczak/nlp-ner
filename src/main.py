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
    "<HOSPITAL>": ("hospitals.csv", "nazwa"),
    "<DISEASE>": ("diseases.csv", "nazwa"),
    "<TEST>": ("tests.csv", "nazwa"),
}


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


def load_weighted_list(csv_path: Path, name_col: str, weight_col: str) -> tuple[list[str], list[float]]:
    names: list[str] = []
    weights: list[float] = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            val = (row.get(name_col) or "").strip()
            if not val:
                continue
            w = float(row.get(weight_col, 0) or 0)
            names.append(val)
            weights.append(w)
    if not names:
        raise ValueError(f"Brak danych w kolumnie {name_col} w pliku {csv_path.name}")
    return names, weights


def load_pools(data_dir: Path) -> dict[str, tuple[list[str], list[float] | None]]:
    pools: dict[str, tuple[list[str], list[float] | None]] = {}

    # Load weighted person pools
    persons_csv = data_dir / "persons.csv"
    variants_csv = data_dir / "persons_variants.csv"
    if persons_csv.exists():
        names, weights = load_weighted_list(persons_csv, "nazwa", "prawdopodobienstwo")
        if variants_csv.exists():
            vnames, vweights = load_weighted_list(variants_csv, "nazwa", "prawdopodobienstwo")
            names += vnames
            weights += vweights
        pools["<PERSON>"] = (names, weights)

    # Load weighted drug pool
    drugs_csv = data_dir / "drugs_weighted.csv"
    if drugs_csv.exists():
        names, weights = load_weighted_list(drugs_csv, "nazwa", "prawdopodobienstwo")
        pools["<DRUG>"] = (names, weights)

    # Load remaining entity pools (uniform weight)
    for placeholder, (filename, column) in DATA_FILES.items():
        csv_path = data_dir / filename
        if not csv_path.exists():
            print(f"  [info] Brak pliku {csv_path.name}, pomijam")
            continue
        values = load_simple_list(csv_path, column)
        pools[placeholder] = (values, None)

    return pools


def inject_placeholders(template: str, pools: dict[str, tuple[list[str], list[float] | None]]):
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
        values, weights = pools[placeholder]
        value = mapping.get(placeholder)
        if value is None:
            if weights:
                value = random.choices(values, weights=weights, k=1)[0]
            else:
                value = random.choice(values)
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
