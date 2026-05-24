# ner-medical

Generator danych treningowych NER dla polskiej dokumentacji medycznej.

## Struktura

```
ner-medical/
├── data/          # pliki wejściowe (CSV z pacjentami)
├── output/        # wygenerowane datasety (JSON)
└── src/
    ├── main.py      # punkt wejścia, pętla generująca
    ├── generator.py # komunikacja z ollama, walidacja
    └── prompt.py    # template promptu
```

## Użycie

```bash
python -m src
```

## Konfiguracja

- `data/patients_dummy.csv` — lista pacjentów (imie, nazwisko)
- `src/prompt.py` — template promptu z placeholderami `{imie}`, `{nazwisko}`
- `src/generator.py` — `MODEL_NAME` do zmiany modelu ollama
- `src/main.py` — `pause` między żądaniami, ścieżki plików
