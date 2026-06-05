import csv
import json
import random
import re
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
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
    "<PESEL>": "PESEL",
    "<TELEFON>": "TELEFON",
    "<ADRES>": "ADRES",
    "<DATA>": "DATA",
}

PLACEHOLDER_PATTERN = re.compile(
    r"<(PERSON|HOSPITAL|DISEASE|DRUG|TEST|PESEL|TELEFON|ADRES|DATA)>"
)
TOKEN_PATTERN = re.compile(r"\S+")

DATA_FILES = {
    "<HOSPITAL>": ("hospitals.csv", "nazwa"),
    "<DISEASE>": ("diseases.csv", "nazwa"),
    "<TEST>": ("tests.csv", "nazwa"),
}

# ---- Syntetyczne encje PII (generowane proceduralnie, bez pul CSV) ----

_STREETS = [
    "Kwiatowa", "Słoneczna", "Lipowa", "Polna", "Ogrodowa", "Krótka", "Leśna",
    "Łąkowa", "Brzozowa", "Akacjowa", "Sienkiewicza", "Mickiewicza", "Kościuszki",
    "Piłsudskiego", "Warszawska", "Krakowska", "Główna", "Szkolna", "Spacerowa",
]
_CITIES = [
    "Warszawa", "Kraków", "Łódź", "Wrocław", "Poznań", "Gdańsk", "Szczecin",
    "Bydgoszcz", "Lublin", "Katowice", "Białystok", "Częstochowa", "Radom", "Toruń",
]
_MONTHS_PL = [
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
    "sierpnia", "września", "października", "listopada", "grudnia",
]


def _gen_pesel() -> str:
    """Generate a syntactically valid PESEL (correct date encoding + checksum)."""
    year = random.randint(1940, 2010)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    enc_month = month + 20 if year >= 2000 else month
    serial = random.randint(0, 9999)
    digits = [int(c) for c in f"{year % 100:02d}{enc_month:02d}{day:02d}{serial:04d}"]
    weights = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
    check = (10 - sum(d * w for d, w in zip(digits, weights)) % 10) % 10
    return "".join(map(str, digits)) + str(check)


def _gen_phone() -> str:
    digits = [str(random.randint(0, 9)) for _ in range(9)]
    digits[0] = str(random.choice([5, 6, 7, 8]))
    s = "".join(digits)
    grouped = f"{s[:3]} {s[3:6]} {s[6:]}"
    return random.choice([
        grouped,
        f"+48 {grouped}",
        f"{s[:3]}-{s[3:6]}-{s[6:]}",
        s,
    ])


def _gen_address() -> str:
    prefix = random.choice(["ul.", "ul.", "al."])
    street = random.choice(_STREETS)
    number = str(random.randint(1, 200))
    if random.random() < 0.3:
        number += f"/{random.randint(1, 60)}"
    postal = f"{random.randint(0, 99):02d}-{random.randint(0, 999):03d}"
    city = random.choice(_CITIES)
    return f"{prefix} {street} {number}, {postal} {city}"


def _gen_date() -> str:
    day = random.randint(1, 28)
    month = random.randint(1, 12)
    year = random.randint(2018, 2025)
    return random.choice([
        f"{day:02d}.{month:02d}.{year}",
        f"{day:02d}.{month:02d}.{year} r.",
        f"{year}-{month:02d}-{day:02d}",
        f"{day} {_MONTHS_PL[month - 1]} {year} r.",
    ])


SYNTHETIC_GENERATORS = {
    "<PESEL>": _gen_pesel,
    "<TELEFON>": _gen_phone,
    "<ADRES>": _gen_address,
    "<DATA>": _gen_date,
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


def _normalize_person_name(name: str) -> str:
    parts = name.split()
    result = []
    for part in parts:
        if len(part) == 2 and part[0].isalpha() and part[1] == '.':
            result.append(part.upper())
        elif part.lower() in ('pan', 'pani'):
            result.append(part.lower())
        else:
            result.append(part.title())
    return ' '.join(result)


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
        names = [_normalize_person_name(n) for n in names]
        common = None
        variants_csv = data_dir / "persons_variants.csv"
        if variants_csv.exists():
            vnames, vweights = load_weighted_list(variants_csv, "nazwa", "prawdopodobienstwo")
            vnames = [_normalize_person_name(n) for n in vnames]
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

    # ---- Syntetyczne encje (PESEL, telefon, adres, data) - bez CSV ----
    for placeholder, generator in SYNTHETIC_GENERATORS.items():
        pools[placeholder] = {"generator": generator}

    return pools


def _pick_value(pool: dict) -> str:
    """Pick from common pool with common_prob chance, otherwise from main pool.

    Synthetic pools carry a `generator` callable instead of value lists.
    """
    generator = pool.get("generator")
    if generator is not None:
        return generator()
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


def generate_sample(pools: dict[str, dict]) -> dict | None:
    """Generate a single validated sample, retrying the template up to 3 times."""
    for attempt in range(3):
        result = generate_template()
        if result is None:
            continue
        template, _ = result

        text, entities = inject_placeholders(template, pools)
        if PLACEHOLDER_PATTERN.search(text):
            print(f"  [proba {attempt + 1}] Pozostaly placeholdery, powtarzam...")
            continue

        tokens, tags = build_biou_tags(text, entities)
        if not tokens or len(tokens) != len(tags):
            print(f"  [proba {attempt + 1}] Bledna tokenizacja, powtarzam...")
            continue

        return {"text": text, "tokens": tokens, "tags": tags}

    return None


OUTPUT_FILE = OUTPUT_DIR / "ner_dataset.jsonl"


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f)


def run(num_samples: int | None = None, workers: int = 4, seed: int | None = None):
    """Generate NER samples with `workers` concurrent Ollama requests, appending
    each sample to a JSONL file as soon as it is ready (crash-safe progress).

    num_samples=None runs forever until Ctrl+C; an int stops after about that many
    new samples (may overshoot by up to `workers`, since in-flight requests finish).
    With workers > 1 the order is non-deterministic, so `seed` only fixes
    the entity sampling, not the exact dataset. Existing samples in the file are
    kept and counted (the run resumes the numbering).
    """
    if seed is not None:
        random.seed(seed)

    pools = load_pools(DATA_DIR)
    OUTPUT_DIR.mkdir(exist_ok=True)

    lock = threading.Lock()
    saved = _count_lines(OUTPUT_FILE)
    start_count = saved
    if saved:
        print(f"Wznawiam - w pliku jest juz {saved} probek")

    def work() -> bool:
        nonlocal saved
        sample = generate_sample(pools)
        if sample is None:
            print("  Pomijam - nie udalo sie wygenerowac po 3 probach")
            return False
        with lock:
            with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
            saved += 1
            print(f"[{saved}] zapisano ({len(sample['tokens'])} tokenow): {sample['text'][:60]}...")
        return True

    def reached_target() -> bool:
        return num_samples is not None and (saved - start_count) >= num_samples

    limit_str = "w nieskonczonosc" if num_samples is None else f"{num_samples} nowych probek"
    print(f"Generuje {limit_str} (workers={workers}). Zatrzymaj: Ctrl+C\n-> {OUTPUT_FILE}")

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(work) for _ in range(workers)}
            while futures:
                done, futures = wait(futures, return_when=FIRST_COMPLETED)
                if not reached_target():
                    for _ in done:
                        futures.add(executor.submit(work))
    except KeyboardInterrupt:
        print("\nPrzerywam, czekam na biezace zadania...")

    print(f"\nZakonczono. Lacznie w pliku: {saved} probek (+{saved - start_count} w tym uruchomieniu) -> {OUTPUT_FILE}")


if __name__ == "__main__":
    run()
