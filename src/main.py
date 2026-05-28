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
    with open(csv_path, encoding="utf-8-sig") as f:
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
    with open(csv_path, encoding="utf-8-sig") as f:
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


def load_unique_from_csvs(data_dir: Path, specs: list[tuple[str, str]]) -> list[str]:
    """Load values from multiple (filename, column) specs, deduplicated in order."""
    seen: set[str] = set()
    result: list[str] = []
    for filename, column in specs:
        for val in load_simple_list(data_dir / filename, column):
            if val not in seen:
                seen.add(val)
                result.append(val)
    return result


def load_pools(data_dir: Path) -> dict[str, dict]:
    pools: dict[str, dict] = {}

    # ---- <PERSON> weighted, with 5% variants ----
    persons_csv = data_dir / "persons.csv"
    if persons_csv.exists():
        names, weights = load_weighted_list(persons_csv, "nazwa", "prawdopodobienstwo")
        common = None
        variants_csv = data_dir / "persons_variants.csv"
        if variants_csv.exists():
            vnames, vweights = load_weighted_list(variants_csv, "nazwa", "prawdopodobienstwo")
            common = {"values": vnames, "weights": vweights, "common_prob": 0.05}
        pools["<PERSON>"] = {
            "values": names,
            "weights": weights,
            "common_values": common["values"] if common else None,
            "common_weights": common["weights"] if common else None,
            "common_prob": common["common_prob"] if common else 0.0,
        }

    # ---- <DRUG> weighted (NFZ), with 30% common ----
    drugs_csv = data_dir / "drugs_weighted.csv"
    common_drugs_csv = data_dir / "najpopularniejsze_leki.csv"
    if drugs_csv.exists():
        names, weights = load_weighted_list(drugs_csv, "nazwa", "prawdopodobienstwo")
        common = None
        if common_drugs_csv.exists():
            common = load_simple_list(common_drugs_csv, "Nazwa_leku_lub_substancji")
        pools["<DRUG>"] = {
            "values": names,
            "weights": weights,
            "common_values": common,
            "common_weights": None,
            "common_prob": 0.3 if common else 0.0,
        }

    # ---- <DISEASE> uniform, with 30% common ----
    disease_csv = data_dir / "diseases.csv"
    common_disease_csv = data_dir / "najpopularniejsze_choroby.csv"
    if disease_csv.exists():
        names = load_simple_list(disease_csv, "nazwa")
        common = None
        if common_disease_csv.exists():
            common = load_simple_list(common_disease_csv, "nazwa_choroby_lub_dolegliwosci")
        pools["<DISEASE>"] = {
            "values": names,
            "weights": None,
            "common_values": common,
            "common_weights": None,
            "common_prob": 0.3 if common else 0.0,
        }

    # ---- <TEST> uniform, with 30% common (merged from 2 files) ----
    test_csv = data_dir / "tests.csv"
    common_test_specs = [
        ("najpopularniejsze_zabiegi_badania.csv", "nazwa_zabiegu_lub_badania"),
        ("najpopularniejsze_zabiegi_badania_300.csv", "zabieg_lub_badanie"),
    ]
    if test_csv.exists():
        names = load_simple_list(test_csv, "nazwa")
        common = None
        try:
            common = load_unique_from_csvs(data_dir, common_test_specs)
        except (FileNotFoundError, ValueError):
            pass
        pools["<TEST>"] = {
            "values": names,
            "weights": None,
            "common_values": common,
            "common_weights": None,
            "common_prob": 0.3 if common else 0.0,
        }

    # ---- <HOSPITAL> uniform ----
    hospital_csv = data_dir / "hospitals.csv"
    if hospital_csv.exists():
        names = load_simple_list(hospital_csv, "nazwa")
        pools["<HOSPITAL>"] = {
            "values": names,
            "weights": None,
            "common_values": None,
            "common_weights": None,
            "common_prob": 0.0,
        }

    return pools


def _pick_value(pool: dict) -> str:
    """Pick from common pool with common_prob chance, otherwise from main pool."""
    cv = pool.get("common_values")
    cp = pool.get("common_prob", 0.0)
    if cv and cp > 0.0 and random.random() < cp:
        cw = pool.get("common_weights")
        if cw:
            return random.choices(cv, weights=cw, k=1)[0]
        return random.choice(cv)
    if pool.get("weights"):
        return random.choices(pool["values"], weights=pool["weights"], k=1)[0]
    return random.choice(pool["values"])


def inject_placeholders(template: str, pools: dict[str, dict]):
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
            value = _pick_value(pools[placeholder])
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
