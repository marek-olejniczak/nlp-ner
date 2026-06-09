"""Rdzeń anonimizacji: detekcja encji (model NER) + podmiana wg wybranej strategii.

Detekcja = HuggingFace `pipeline("token-classification", aggregation_strategy="first")`,
co daje encje pogrupowane z offsetami znakowymi. Długie teksty (>limit modelu) są
chunkowane po granicach zdań/linii — inaczej encje za 512. subwordem zostają
niezanonimizowane (= wyciek).

Regex catch-net (PESEL/telefon/data) domyka dziury recall modelu — ewaluacja na
golden secie pokazała DATE recall ~0.04, więc dla tych formatowych typów regex jest
WYMAGANY, nie ozdobny. Działa na pełnym tekście (brak limitu tokenów).

Strategie: mask (gwiazdki), tag (numerowany [PERSON_1]), placeholder (realistyczna
wartość). Flaga `consistent` → ta sama encja dostaje ten sam zamiennik w dokumencie.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

# 9 typów modelu (English)
ALL_TYPES = ["PERSON", "DISEASE", "DRUG", "TEST", "HOSPITAL", "ADDRESS", "DATE", "PESEL", "PHONE"]
# domyślnie anonimizujemy identyfikujące; treść kliniczna (DISEASE/DRUG/TEST) opcjonalnie
DEFAULT_TYPES = ["PERSON", "ADDRESS", "DATE", "PESEL", "PHONE", "HOSPITAL"]

MODEL_ID = os.environ.get("NER_MODEL_ID", "michaelo-ponteski/ner-medical-pl")
_MAX_CHARS = 1000  # budżet znaków na chunk (bezpiecznie pod 512 subwordów dla PL)


@dataclass
class Entity:
    label: str
    start: int
    end: int
    text: str
    score: float
    source: str = "model"  # "model" | "regex"


# ---------- detekcja: model ----------

_PIPELINE = None


def load_pipeline(model_id: str = MODEL_ID):
    global _PIPELINE
    if _PIPELINE is None:
        from transformers import pipeline
        _PIPELINE = pipeline(
            "token-classification", model=model_id, aggregation_strategy="first"
        )
    return _PIPELINE


def _chunks(text: str, max_chars: int = _MAX_CHARS) -> list[tuple[int, str]]:
    """Tnij tekst na granicach linii/zdań, nie przekraczając max_chars. Zwraca (offset, chunk)."""
    if len(text) <= max_chars:
        return [(0, text)]
    # punkty podziału: końce linii i zdań
    breaks = [m.end() for m in re.finditer(r"[.\n]\s+|\n", text)]
    chunks, start = [], 0
    last_break = 0
    for b in breaks:
        if b - start > max_chars and last_break > start:
            chunks.append((start, text[start:last_break]))
            start = last_break
        last_break = b
    chunks.append((start, text[start:]))
    return chunks


def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    """Obetnij wiodącą/końcową interpunkcję i spacje ze spanu (dane treningowe je
    przyklejały, więc model łapie 'Jan Kowalski,' z przecinkiem). Wnętrze zostaje."""
    while start < end and not text[start].isalnum():
        start += 1
    while end > start and not text[end - 1].isalnum():
        end -= 1
    return start, end


def detect_model(text: str, threshold: float = 0.5, model_id: str = MODEL_ID) -> list[Entity]:
    pipe = load_pipeline(model_id)
    out: list[Entity] = []
    for offset, chunk in _chunks(text):
        for e in pipe(chunk):
            if e["score"] < threshold:
                continue
            s, en = offset + e["start"], offset + e["end"]
            nl = text.find("\n", s, en)  # encja nie powinna przechodzić przez nową linię
            if nl != -1:
                en = nl
            s, en = _trim_span(text, s, en)
            if s >= en:  # span był samą interpunkcją
                continue
            out.append(Entity(
                label=e["entity_group"],
                start=s,
                end=en,
                text=text[s:en],
                score=float(e["score"]),
                source="model",
            ))
    return out


# ---------- detekcja: regex catch-net ----------

_PL_MONTHS = ("stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|"
              "września|października|listopada|grudnia")
_DATE_RES = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),                         # 2023-10-15
    re.compile(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b"),           # 15.10.2023 / 15-10-23
    re.compile(rf"\b\d{{1,2}}\s+(?:{_PL_MONTHS})\s+\d{{4}}(?:\s*r\.?)?", re.IGNORECASE),
]
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?48[\s-]?)?\d{3}[\s-]?\d{3}[\s-]?\d{3}(?!\d)")
_PESEL_RE = re.compile(r"(?<!\d)\d{11}(?!\d)")


def _valid_pesel(digits: str) -> bool:
    w = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
    s = sum(int(d) * wi for d, wi in zip(digits, w))
    return (10 - s % 10) % 10 == int(digits[10])


def regex_catch_net(text: str) -> list[Entity]:
    """Deterministyczne wzorce dla typów, gdzie model ma niski recall (PESEL/PHONE/DATE)."""
    found: list[Entity] = []
    for m in _PESEL_RE.finditer(text):
        if _valid_pesel(m.group()):
            found.append(Entity("PESEL", m.start(), m.end(), m.group(), 1.0, "regex"))
    for m in _PHONE_RE.finditer(text):
        found.append(Entity("PHONE", m.start(), m.end(), m.group(), 1.0, "regex"))
    for rx in _DATE_RES:
        for m in rx.finditer(text):
            found.append(Entity("DATE", m.start(), m.end(), m.group().strip(), 1.0, "regex"))
    return found


def _overlaps(a: Entity, b: Entity) -> bool:
    return a.start < b.end and b.start < a.end


def merge(model_ents: list[Entity], regex_ents: list[Entity]) -> list[Entity]:
    """Unia; encja regex dodawana tylko jeśli nie nachodzi na żadną już przyjętą (model ma priorytet)."""
    kept = list(model_ents)
    for r in regex_ents:
        if not any(_overlaps(r, k) for k in kept):
            kept.append(r)
    return kept


# ---------- anonimizacja ----------

def _replacement(ent: Entity, strategy: str, consistent: bool, provider, state: dict) -> str:
    if strategy == "mask":
        return "*" * max(1, len(ent.text))
    if strategy == "tag":
        if consistent:
            key = (ent.label, ent.text.strip().lower())
            if key not in state["map"]:
                state["count"][ent.label] = state["count"].get(ent.label, 0) + 1
                state["map"][key] = state["count"][ent.label]
            n = state["map"][key]
        else:
            state["count"][ent.label] = state["count"].get(ent.label, 0) + 1
            n = state["count"][ent.label]
        return f"[{ent.label}_{n}]"
    if strategy == "placeholder":
        return provider.value(ent.label, ent.text, consistent)
    raise ValueError(f"Nieznana strategia: {strategy}")


def apply(
    text: str,
    ents: list[Entity],
    strategy: str = "mask",
    consistent: bool = True,
    provider=None,
) -> tuple[str, list[Entity]]:
    """Podmień podane encje w tekście wg strategii (niezależne od modelu — testowalne)."""
    if not ents:
        return text, []

    # numerowanie/placeholdery w kolejności czytania (rosnąco)
    ents_asc = sorted(ents, key=lambda e: (e.start, e.end))
    if strategy == "placeholder" and provider is not None:
        provider.reset()
    state = {"count": {}, "map": {}}
    repl = {id(e): _replacement(e, strategy, consistent, provider, state) for e in ents_asc}

    # podmiana od końca, żeby nie psuć offsetów
    result = text
    for e in sorted(ents_asc, key=lambda e: e.start, reverse=True):
        result = result[:e.start] + repl[id(e)] + result[e.end:]
    return result, ents_asc


def anonymize(
    text: str,
    types: list[str],
    strategy: str = "mask",
    consistent: bool = True,
    threshold: float = 0.5,
    use_regex: bool = True,
    provider=None,
    model_id: str = MODEL_ID,
) -> tuple[str, list[Entity]]:
    """Wykryj encje wybranych typów (model + regex) i podmień wg strategii."""
    selected = set(types)
    ents = [e for e in detect_model(text, threshold, model_id) if e.label in selected]
    if use_regex:
        rx = [e for e in regex_catch_net(text) if e.label in selected]
        ents = merge(ents, rx)
    return apply(text, ents, strategy, consistent, provider)
