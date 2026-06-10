"""Konwersja surowych batchy golden-style (inline markup) -> dataset JSONL.

Agenci Haiku zapisują fragmenty do output/_genN/batch_*.txt, oddzielone linią
`<<<SAMPLE>>>`. Ten skrypt skleja je, parsuje inline markup (`<TAG>...</TAG>`) na
tokeny + tagi IOB2 (reużywając parse_markup/build_iob2 z training.eval_set),
deduplikuje i zapisuje JSONL. Malformed / puste / duplikaty są pomijane i zliczone.

Następny krok w pipeline: tools/clean_generated.py (auto-fix + drop), potem
tools/build_training_set.py (miks z injection).

Użycie:
    python -m tools.batches_to_jsonl --batch-dir output/_gen3 --output output/_gen3_raw.jsonl
"""

import argparse
import glob
import json
import re
from pathlib import Path

from training.eval_set import parse_markup, build_iob2, MarkupError

SEP = "<<<SAMPLE>>>"
_FENCE = re.compile(r"```[a-z]*")


def convert(batch_dir: Path) -> tuple[list[dict], dict]:
    raw = []
    for fn in sorted(glob.glob(str(batch_dir / "batch_*.txt"))):
        text = _FENCE.sub("", Path(fn).read_text(encoding="utf-8"))
        raw += [c.strip() for c in text.split(SEP) if c.strip()]

    samples, seen = [], set()
    stats = {"raw": len(raw), "malformed": 0, "empty": 0, "dup": 0}
    for i, chunk in enumerate(raw):
        try:
            clean, ents = parse_markup(chunk, i)
        except MarkupError:
            stats["malformed"] += 1
            continue
        if not ents:
            stats["empty"] += 1
            continue
        if clean in seen:
            stats["dup"] += 1
            continue
        seen.add(clean)
        tokens, tags = build_iob2(clean, ents)
        samples.append({"text": clean, "tokens": tokens, "tags": tags})
    stats["kept"] = len(samples)
    return samples, stats


def main():
    p = argparse.ArgumentParser(description="Convert golden-style batch files to JSONL")
    p.add_argument("--batch-dir", type=Path, required=True, help="np. output/_gen3")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    samples, stats = convert(args.batch_dir)
    with open(args.output, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"{args.batch_dir}: {stats} -> {args.output}")


if __name__ == "__main__":
    main()
