"""Podmiana polskich nazw encji na angielskie w datasecie NER (JSONL).

Generator (src/) produkuje etykiety po polsku (CHOROBA, LEK, ...). Studiujemy po
angielsku, więc kanoniczny dataset trzymamy z angielskimi etykietami. Ten skrypt
to boundary: surowy polski JSONL od generatora -> angielski JSONL do treningu.

Mapuje tylko część encyjną tagu, zachowuje prefiks BIOU (B-/I-/U-) i `O`.
Tekst i tokeny bez zmian — etykiety niosą tylko tagi.

Użycie:
    python -m training.relabel --input output/ner_dataset_pl.jsonl --output output/ner_dataset.jsonl
"""

import argparse
import json
import re
from pathlib import Path

# polska nazwa encji -> angielska (PESEL zostaje — nazwa własna, jak PL_PESEL w Presidio)
LABEL_MAP = {
    "PERSON": "PERSON",
    "SZPITAL": "HOSPITAL",
    "CHOROBA": "DISEASE",
    "LEK": "DRUG",
    "BADANIE": "TEST",
    "ADRES": "ADDRESS",
    "DATA": "DATE",
    "TELEFON": "PHONE",
    "PESEL": "PESEL",
}


# podmiana nazw w inline markup: <SZPITAL>..</SZPITAL> -> <HOSPITAL>..</HOSPITAL>
_MARKUP_RE = re.compile(r"<(/?)(" + "|".join(LABEL_MAP) + r")>")


def relabel_markup_text(text: str) -> str:
    return _MARKUP_RE.sub(lambda m: f"<{m.group(1)}{LABEL_MAP[m.group(2)]}>", text)


def relabel_markup_file(input_path: Path, output_path: Path) -> int:
    """Golden set w formacie inline markup (lista {text} albo str) — podmiana nazw tagów."""
    data = json.loads(input_path.read_text(encoding="utf-8"))
    for i, item in enumerate(data):
        if isinstance(item, dict) and "text" in item:
            item["text"] = relabel_markup_text(item["text"])
        elif isinstance(item, str):
            data[i] = relabel_markup_text(item)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(data)


def relabel_tag(tag: str) -> str:
    if tag == "O":
        return tag
    prefix, entity = tag.split("-", 1)  # "B-CHOROBA" -> ("B", "CHOROBA")
    if entity not in LABEL_MAP:
        raise ValueError(f"Nieznana encja '{entity}' w tagu '{tag}' (mapa: {sorted(LABEL_MAP)})")
    return f"{prefix}-{LABEL_MAP[entity]}"


def relabel_file(input_path: Path, output_path: Path) -> tuple[int, set[str]]:
    n = 0
    seen_out: set[str] = set()
    with open(input_path, encoding="utf-8") as fin, open(output_path, "w", encoding="utf-8") as fout:
        for line_no, line in enumerate(fin, start=1):
            line = line.strip()
            if not line:
                continue
            sample = json.loads(line)
            if len(sample["tokens"]) != len(sample["tags"]):
                raise ValueError(f"Linia {line_no}: tokens != tags")
            try:
                sample["tags"] = [relabel_tag(t) for t in sample["tags"]]
            except ValueError as e:
                raise ValueError(f"Linia {line_no}: {e}") from None
            seen_out.update(t for t in sample["tags"] if t != "O")
            fout.write(json.dumps(sample, ensure_ascii=False) + "\n")
            n += 1
    return n, seen_out


def main() -> None:
    parser = argparse.ArgumentParser(description="Podmiana PL->EN nazw encji")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markup", action="store_true",
                        help="Wejście to golden set w inline markup (JSON), nie JSONL z tagami")
    args = parser.parse_args()

    if args.markup:
        n = relabel_markup_file(args.input, args.output)
        print(f"Przepisano markup w {n} próbkach -> {args.output}")
    else:
        n, seen = relabel_file(args.input, args.output)
        types = sorted({t.split("-", 1)[1] for t in seen})
        print(f"Przepisano {n} próbek -> {args.output}")
        print(f"Typy encji w wyjściu: {types}")


if __name__ == "__main__":
    main()
