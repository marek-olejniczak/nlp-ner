# Anonimizator dokumentacji medycznej

Web app (Gradio): wklej polski tekst medyczny → model NER wykrywa wrażliwe encje
→ wybierasz tryb anonimizacji.

## Encje (9 typów)

Identyfikujące (domyślnie anonimizowane): `PERSON`, `ADDRESS`, `DATE`, `PESEL`,
`PHONE`, `HOSPITAL`. Treść kliniczna (opcjonalnie): `DISEASE`, `DRUG`, `TEST`.

## Tryby

| Tryb | Efekt |
|---|---|
| Maska | encja → `****` (długość zachowana) |
| Tag | encja → `[PERSON_1]`, `[PERSON_2]`… (numerowane per typ) |
| Placeholder | encja → realistyczna wartość tego samego typu (medyczne z pul repo, PII z Faker pl_PL) |

Flaga **spójnie**: ta sama encja dostaje ten sam zamiennik w całym dokumencie.

## Regex catch-net

Model ma niski recall na `DATE` (~0.04 na golden secie), umiarkowany na `ADDRESS`/`PERSON`.
Dla typów formatowych (`PESEL`, `PHONE`, `DATE`) dokłada się deterministyczny regex,
który łapie to, co model przeoczył — działa na pełnym tekście (bez limitu tokenów).
Dziura recall na `PERSON`/`ADDRESS` (brak czystego wzorca) to udokumentowane ograniczenie v1.

## Uruchomienie lokalne

```bash
mamba activate nlp-ner          # lub dowolny venv
pip install -r app/requirements.txt
export NER_MODEL_ID="<hf-user>/herbert-ner-medical-pl"   # model na HF Hub
python -m app.app
```

Bez ustawienia `NER_MODEL_ID` app używa bazowego `allegro/herbert-base-cased`
(NIE dotrenowanego — wykrywa słabo; ustaw na wytrenowany checkpoint).

## Deploy na HF Spaces

1. Wypchnij najlepszy checkpoint na HF Hub (zob. `tools/push_to_hub.py` / komórka w notebooku).
2. Utwórz Gradio Space, wgraj zawartość `app/` + `app/requirements.txt`.
3. Ustaw `NER_MODEL_ID` w sekretach/zmiennych Space. Model ściągnie się przy starcie (CPU wystarcza).

## Testy

```bash
python -m app.test_anonymizer   # część niezależna od modelu (regex, strategie, provider)
```

## Architektura

- `anonymizer.py` — detekcja (pipeline + chunking >512 tokenów), regex catch-net, strategie, podmiana spanów od końca.
- `replacements.py` — pule medyczne (`src.pools`) + Faker PII + cache spójności.
- `app.py` — UI Gradio.
