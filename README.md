# ner-medical

Generator danych treningowych NER dla polskiej dokumentacji medycznej.

## Przepływ danych

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Źródła danych    │ ──→│  Skrypty ekstrakcji│ ──→│  CSV z encjami   │
│  (gov.pl, NFZ)    │    │  data/raw/         │    │  data/            │
└──────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                            ↓
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Template z      │ ←──│  Generator        │ ←──│  src/main.py     │
│  placeholderami  │     │  (Ollama)         │     │  (pule + ważenie)│
└──────────────────┘     └──────────────────┘     └──────────────────┘
                                                            ↓
                                                  ┌──────────────────┐
                                                  │  Dataset JSON    │
                                                  │  (output/)       │
                                                  └──────────────────┘
```

## Zbiory danych

### Encje główne

| Placeholder | Plik | Rozmiar | Ważenie | Źródło |
|---|---|---|---|---|
| `<PERSON>` | `data/persons.csv` | 200 000 | weighted (PESEL) | Listy PESEL (gov.pl) |
| `<PERSON>` (warianty) | `data/persons_variants.csv` | 27 640 | weighted (PESEL) | Warianty nazwisk (pan/pani + inicjał) |
| `<DRUG>` | `data/drugs_weighted.csv` | 959 | weighted (NFZ) | API NFZ – refundacja apteczna 2024 |
| `<DISEASE>` | `data/diseases.csv` | 16 387 | uniform | ICD-11 (gov.pl) |
| `<TEST>` | `data/tests.csv` | 9 987 | uniform | ICD-9 (gov.pl) |
| `<HOSPITAL>` | `data/hospitals.csv` | 569 | uniform | Wykaz szpitali (gov.pl) |
| `<HOSPITAL>` (norm.) | `data/hospitals_normalized.csv` | 569 | uniform | Wersja znormalizowana |

### Listy popularne (częste/ogólnikowe nazwy)

Służą do urozmaicenia generacji o powszechnie znane terminy medyczne, obok specjalistycznych nazw z głównych zbiorów.

| Placeholder | Plik | Rozmiar |
|---|---|---|
| `<DRUG>` | `data/najpopularniejsze_leki.csv` | 100 |
| `<DISEASE>` | `data/najpopularniejsze_choroby.csv` | 97 |
| `<TEST>` | `data/najpopularniejsze_zabiegi_badania.csv` | 99 |
| `<TEST>` | `data/najpopularniejsze_zabiegi_badania_300.csv` | 301 |
| `<TEST>` (razem, dedup) | — | 351 |

## Strategia selekcji (mixed pools)

Podczas wypełniania placeholderów w template każda encja ma swoją strategię:

| Placeholder | P(common) | Główna pula | Popularna pula |
|---|---|---|---|
| `<DRUG>` | **30%** | `drugs_weighted.csv` (ważony NFZ) | `najpopularniejsze_leki.csv` (uniform) |
| `<DISEASE>` | **30%** | `diseases.csv` (uniform) | `najpopularniejsze_choroby.csv` (uniform) |
| `<TEST>` | **30%** | `tests.csv` (uniform) | merge 2 plików popularnych (uniform) |
| `<PERSON>` | **5%** | `persons.csv` (ważony PESEL) | `persons_variants.csv` (ważony PESEL) |
| `<HOSPITAL>` | — | `hospitals.csv` (uniform) | — |

Algorytm dla encji z pulą mieszaną:
1. Losuj `r = random.random()`
2. Jeśli `r < P(common)` → wybierz losowo z listy popularnej (uniform lub weighted)
3. W przeciwnym razie → wybierz z głównej puli (weighted lub uniform)

Wszystkie wystąpienia tego samego placeholdera w jednym template otrzymują tę samą wartość (cache'owanie).

## Skrypty ekstrakcji

| Skrypt | Opis |
|---|---|
| `data/raw/extract.py` | Ekstrakcja DRUG (CSV), DISEASE (XML ICD-11), TEST (XLSX ICD-9) z gov.pl |
| `data/raw/extract_persons.py` | Ekstrakcja PERSON z list PESEL + generowanie wariantów |
| `data/raw/extract_hospitals.py` | Ekstrakcja HOSPITAL z 3 źródeł (top50, spis2, spis1) |
| `data/raw/normalize_hospitals.py` | Normalizacja wielkości liter w nazwach szpitali |
| `data/raw/extract_drugs_weighted.py` | Pobranie wag leków z API NFZ (refundacja apteczna 2024) + cache |

## Użycie

```bash
# Generowanie datasetu (domyślnie 100 próbek)
python -m src.main

# Z własnymi parametrami
python -c "from src.main import run; run(num_samples=50, pause=0.5, seed=42)"
```

### Parametry `run()`

| Parametr | Domyślnie | Opis |
|---|---|---|
| `num_samples` | 100 | Liczba wygenerowanych próbek |
| `pause` | 1.0 | Przerwa (s) między zapytaniami do Ollama |
| `seed` | `None` | Ziarno losowości (dla reprodukowalności) |

## Format wyjściowy

`output/ner_dataset.json` — lista obiektów:

```json
[
  {
    "text": "Pacjent PAULINA KACZMAREK przyjety do Szpital Śląski ...",
    "tokens": ["Pacjent", "PAULINA", "KACZMAREK", "przyjety", ...],
    "tags": ["O", "B-PERSON", "I-PERSON", "O", ...]
  }
]
```

Tagowanie w notacji BIOU (`B-` początek, `I-` wewnątrz/koniec, `U-` jedno-tokenowa, `O` poza encją). Uwaga: generator **nie** emituje tagów `L-` — przy treningu schemat jest konwertowany do IOB2 (`U-X` → `B-X`), zob. `training/dataset.py`.

## Konfiguracja

- `src/prompt.py` — template promptu, lista placeholderów, typy dokumentów, tony wypowiedzi
- `src/generator.py` — `MODEL_NAME` do zmiany modelu Ollama
- `src/main.py` — `DATA_DIR`, `OUTPUT_DIR`, progi mieszanych pul

## Trening NER

Fine-tuning polskiego encodera (domyślnie `allegro/herbert-base-cased`) na wygenerowanym
datasecie. Dataset wejściowy: `output/ner_dataset_new.jsonl` (JSONL, format jak wyżej;
9 typów encji — 5 medycznych + PII: ADRES, DATA, PESEL, TELEFON).

```bash
# Środowisko
mamba create -n nlp-ner python=3.12 -y
mamba activate nlp-ner
pip install -r requirements.txt

# Logowanie eksperymentów (jednorazowo)
wandb login

# Pełny trening (HerBERT-base, 3 epoki, W&B project: nlp-ner)
python -m training.train

# Inny model do porównania
python -m training.train --model sdadas/polish-roberta-base-v2

# Pełne porównanie 4 modeli na GPU (Colab T4): notebooks/train_colab.ipynb

# Smoke test bez W&B
python -m training.train --limit 64 --max-steps 20 --no-wandb

# Ewaluacja na odłożonym test splicie (10%, model go nigdy nie widział)
python -m training.evaluate --checkpoint models/herbert-base-cased/best
```

### Pipeline treningu

| Krok | Plik | Opis |
|---|---|---|
| Konwersja tagów | `training/dataset.py` | BIOU → IOB2 (`U-X` → `B-X`), 19 klas (9 typów encji) |
| Split | `training/dataset.py` | 80/10/10 train/val/test, deterministyczny (seed 42) |
| Label alignment | `training/dataset.py` | pierwszy subword niesie etykietę słowa, reszta `-100` |
| Trening | `training/train.py` | lr 2e-5, warmup 10%, najlepszy checkpoint wg F1 na walidacji |
| Metryki | `training/metrics.py` | entity-level P/R/F1 (seqeval, strict, IOB2), per typ encji |

Artefakty: `models/<nazwa>/best` (model + tokenizer), raport JSON z ewaluacji obok checkpointu.
Wyniki eksperymentów: [W&B project `nlp-ner`](https://wandb.ai).
