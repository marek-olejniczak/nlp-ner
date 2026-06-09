"""Złóż finalny dataset treningowy: injection + golden-style (Haiku), z held-out bez leakage.

- łączy plik injection (formalne nazwy) z czystymi pulami golden-style (krótkie kliniczne formy)
- dedup golden-style po tekście (między paczkami v1/v2/v3)
- wydziela held-out z golden-style (NIE trafia do treningu — czysty pomiar generalizacji w stylu)
- miks = (golden-style minus held-out) + injection, przetasowany

Użycie:
    python -m tools.build_training_set \
        --injection output/ner_dataset.jsonl \
        --generated output/ner_dataset_generated_clean.jsonl output/ner_dataset_generated_2.jsonl output/ner_dataset_generated_3.jsonl \
        --heldout-size 200 \
        --out-train output/ner_dataset_mixed.jsonl \
        --out-heldout output/ner_dataset_golden_heldout.jsonl
"""

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def span_stats(samples):
    lens = defaultdict(list)
    for s in samples:
        cur = None; n = 0
        for t in s["tags"] + ["O"]:
            if t == "O" or t.startswith("B-"):
                if cur: lens[cur].append(n)
                cur = None; n = 0
            if t.startswith("B-"): cur = t[2:]; n = 1
            elif t.startswith("I-"): n += 1
    return {k: (len(v), round(sum(v) / len(v), 2)) for k, v in sorted(lens.items())}


def main():
    p = argparse.ArgumentParser(description="Build mixed training set + held-out")
    p.add_argument("--injection", required=True)
    p.add_argument("--generated", nargs="+", required=True)
    p.add_argument("--heldout-size", type=int, default=200)
    p.add_argument("--out-train", required=True)
    p.add_argument("--out-heldout", required=True)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    inj = load(args.injection)

    # zbierz golden-style, dedup po tekście
    seen, gen = set(), []
    dup = 0
    for f in args.generated:
        for s in load(f):
            if s["text"] in seen:
                dup += 1; continue
            seen.add(s["text"]); gen.append(s)

    rng = random.Random(args.seed)
    rng.shuffle(gen)
    heldout = gen[:args.heldout_size]
    train_gen = gen[args.heldout_size:]

    # leakage guard: żaden tekst held-out nie może być w treningu
    held_texts = {s["text"] for s in heldout}
    mixed = inj + [s for s in train_gen if s["text"] not in held_texts]
    rng.shuffle(mixed)

    with open(args.out_train, "w", encoding="utf-8") as f:
        for s in mixed: f.write(json.dumps(s, ensure_ascii=False) + "\n")
    with open(args.out_heldout, "w", encoding="utf-8") as f:
        for s in heldout: f.write(json.dumps(s, ensure_ascii=False) + "\n")

    print(f"injection: {len(inj)} | golden-style unikalne: {len(gen)} (dup usunięte: {dup})")
    print(f"-> TRAIN (mixed): {len(mixed)}  -> {args.out_train}")
    print(f"-> HELD-OUT (golden-style, poza treningiem): {len(heldout)}  -> {args.out_heldout}")
    print(f"\nśr. długość spanu — injection: {span_stats(inj)}")
    print(f"śr. długość spanu — golden-style: {span_stats(gen)}")


if __name__ == "__main__":
    main()
