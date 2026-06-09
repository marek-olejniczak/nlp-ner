"""Czyszczenie wygenerowanych danych NER (golden-style) + flagowanie do dropu.

Auto-fix (bezpieczne, mechaniczne):
- drop próbek z korupcją znaków (cyrylica / błędne diakrytyki romańskie)
- strip tytułów (dr/lek/prof/Pan...) z początku spanu PERSON
- trim końcowych wartości/jednostek ze spanu TEST/DISEASE ("Glikemia 356 mg/dl" -> "Glikemia")

Flagowanie -> drop (kod nie naprawi bezpiecznie):
- ADDRESS będący lokalizacją anatomiczną LUB bez żadnej liczby (adres ma numer);
  UWAGA: brak "ul." ani kodu pocztowego to NIE błąd (adresy bywają "Miasto, X 12/3")
- TEST/DISEASE z wartością liczbową w środku spanu (nie tylko na końcu)
- jednoznacznie angielskie terminy (Vitamin/Sunscreen/Retinol/cream...) — NIE ibuprofen/insulin (legit PL)

Użycie:
    python -m tools.clean_generated --input output/ner_dataset_generated.jsonl \
        --output output/ner_dataset_generated_clean.jsonl --flags output/flags_for_review.md
"""

import argparse
import json
import re
from collections import Counter

CORRUPT = re.compile("[Ѐ-ӿáàâăŕèêéìíôûäöü]")
TITLE = re.compile(r"^(dr|lek|prof|mgr|pan|pani)\.?$", re.IGNORECASE)
UNIT = {"mg", "ml", "ng/dl", "mg/dl", "mlU/l", "µg", "mmol/l", "%", "ng/ml",
        "g/l", "U/l", "cm", "mm", "mln", "tys"}
ENG_DRUG = re.compile(r"(?i)\b(vitamin|sunscreen|retinol|moisturizer|cream|serum)\b")
HAS_DIGIT = re.compile(r"\d")


def spans(tags):
    out, i = [], 0
    while i < len(tags):
        if tags[i].startswith("B-"):
            lab = tags[i][2:]; j = i + 1
            while j < len(tags) and tags[j] == f"I-{lab}":
                j += 1
            out.append((lab, i, j)); i = j
        else:
            i += 1
    return out


def _is_value(tok):
    t = tok.strip(".,;:")
    return bool(HAS_DIGIT.search(t)) or t in UNIT


def _address_suspect(txt):
    # Jedyny sygnał: brak liczby. Prawdziwy adres ma numer budynku ("ul. Stawna 44",
    # "Poznań, Nowe Miasto 15/7"); lokalizacja anatomiczna ("lewego przedramienia") go nie ma.
    # Świadomie NIE używamy stemów anatomicznych — nazwy ulic (Głowna, Stawna) je zawierają.
    return not HAS_DIGIT.search(txt)


def clean(samples):
    kept, flags = [], []
    stats = Counter()
    for idx, s in enumerate(samples, 1):
        if CORRUPT.search(s["text"]):
            stats["drop_corrupt"] += 1
            continue
        toks, tags = s["tokens"], list(s["tags"])
        for lab, a, b in spans(tags):
            if lab == "PERSON" and b - a > 1 and TITLE.match(toks[a].strip(".,")):
                tags[a] = "O"; tags[a + 1] = "B-PERSON"; stats["fix_title"] += 1
        for lab, a, b in spans(tags):
            if lab in ("TEST", "DISEASE"):
                e = b
                while e - 1 > a and _is_value(toks[e - 1]):
                    e -= 1
                if e < b:
                    for k in range(e, b):
                        tags[k] = "O"
                    stats["fix_labtrim"] += 1
        # flagi -> drop
        sample_flags = []
        for lab, a, b in spans(tags):
            txt = " ".join(toks[a:b])
            if lab == "ADDRESS" and _address_suspect(txt):
                sample_flags.append((idx, "ADDRESS-bez-numeru", lab, txt))
            if lab in ("TEST", "DISEASE") and any(HAS_DIGIT.search(toks[k]) for k in range(a, b)):
                sample_flags.append((idx, "wartosc-wewnatrz-spanu", lab, txt))
        if ENG_DRUG.search(s["text"]):
            m = ENG_DRUG.search(s["text"])
            sample_flags.append((idx, "angielski-lek", None, m.group()))
        if sample_flags:
            flags.extend(sample_flags)
            stats["drop_flagged"] += 1
            continue
        kept.append({"text": s["text"], "tokens": toks, "tags": tags})
    return kept, flags, stats


def main():
    p = argparse.ArgumentParser(description="Auto-clean + drop flagged generated NER data")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--flags", default=None)
    args = p.parse_args()

    samples = [json.loads(l) for l in open(args.input, encoding="utf-8") if l.strip()]
    kept, flags, stats = clean(samples)

    with open(args.output, "w", encoding="utf-8") as f:
        for s in kept:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    if args.flags:
        n_samp = len(set(i for i, *_ in flags))
        lines = [f"# Usunięte próbki ({len(flags)} flag, {n_samp} próbek) — NIE ma ich w czystej puli\n",
                 "USUNIĘTE z czystej puli (dogenerujemy zamiast poprawiać ręcznie). Rejestr błędów do "
                 "uniknięcia przy regeneracji. Numer = indeks w output/generated_review.md.\n"]
        for i, typ, lab, txt in sorted(flags):
            lines.append(f"- [{i:04d}] **{typ}** {(lab+': ' if lab else '')}«{txt[:80]}»")
        open(args.flags, "w", encoding="utf-8").write("\n".join(lines))

    print(f"start {len(samples)} -> czyste {len(kept)}")
    print(f"  {dict(stats)}")
    print(f"  flagi: {len(flags)} ({len(set(i for i,*_ in flags))} próbek)")


if __name__ == "__main__":
    main()
