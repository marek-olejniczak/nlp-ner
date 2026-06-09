import json
import re
import time
from pathlib import Path

from .generator import generate_template
from .pools import (
    DATA_DIR,
    PLACEHOLDER_LABELS,
    DATA_FILES,
    load_simple_list,
    load_weighted_list,
    load_unique_from_csvs,
    load_pools,
    _pick_value,
)


OUTPUT_DIR = Path(__file__).parent.parent / "output"

PLACEHOLDER_PATTERN = re.compile(r"<(PERSON|HOSPITAL|DISEASE|DRUG|TEST)>")
TOKEN_PATTERN = re.compile(r"\S+")


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
        import random
        random.seed(seed)

    pools = load_pools(DATA_DIR)
    OUTPUT_DIR.mkdir(exist_ok=True)

    dataset = []
    total = num_samples

    for i in range(1, total + 1):
        print(f"\n--- [{i}/{total}] ---")
        sample = None

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
