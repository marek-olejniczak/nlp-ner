"""Pule realistycznych wartości encji (CSV z data/) — wspólne dla generatora i appki.

Wydzielone z main.py, żeby kod inferencyjny/anonimizujący mógł importować bez
wciągania `ollama` (main.py importuje generator -> ollama). Ten moduł zależy tylko
od stdlib.
"""

import csv
import random
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

PLACEHOLDER_LABELS = {
    "<PERSON>": "PERSON",
    "<HOSPITAL>": "SZPITAL",
    "<DISEASE>": "CHOROBA",
    "<DRUG>": "LEK",
    "<TEST>": "BADANIE",
}

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
