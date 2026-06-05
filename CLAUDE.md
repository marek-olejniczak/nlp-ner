# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Generator of synthetic NER training data for **Polish medical documentation**. It produces token-labelled samples (BIO-style tags) by (1) asking a local LLM via Ollama to write a realistic medical document *template* containing only placeholder tags, then (2) filling those placeholders with real entity values sampled from curated CSV pools, and (3) computing character offsets and token tags. Output is `output/ner_dataset.json`.

The codebase, comments, and printed messages are in Polish — match that when editing.

## Commands

```bash
# Install (only dependency is the ollama python client)
pip install -r requirements.txt

# Generate forever (4 parallel requests), Ctrl+C to stop — requires a running Ollama server
python -m src.main

# Bounded run
python -c "from src.main import run; run(num_samples=50, workers=4, seed=42)"
```

There is **no test suite, linter, or build step** configured. Generation is parallelised via a thread pool (`workers`, default 4); the server must allow concurrency (`OLLAMA_NUM_PARALLEL`, set as a user env var to 4). With `workers > 1` the order is non-deterministic, so `seed=` only fixes entity sampling, not the exact dataset.

`run(num_samples=None)` (the `python -m src.main` default) **runs forever until Ctrl+C**; an int stops after ~that many samples (may overshoot by up to `workers`). Each sample is **appended immediately** to `output/ner_dataset.jsonl` (one JSON object per line) so progress survives a crash/Ctrl+C; a restart counts existing lines and continues appending.

## Prerequisites

- A local **Ollama** server must be running, serving the model named in `generator.py` (`MODEL_NAME`, currently `gemma4:e2b`). If the model name is wrong or the server is down, every sample fails its retries and the dataset comes out empty.

## Architecture (the two-stage pipeline)

The pipeline is split between *template generation* (LLM, non-deterministic) and *placeholder injection* (local, deterministic given a seed):

1. **`src/prompt.py`** — pure config. `SCENARIOS` (document types + which tags are required), `SPECIALIZATIONS`, `TONES`, and `PROMPT_TEMPLATE`. Editing entity types or document styles happens here.

2. **`src/generator.py`** — talks to Ollama. `build_prompt()` randomly combines a scenario/specialization/tone; `generate_template()` calls `ollama.chat`, strips markdown fences, and **validates** that the returned template contains *exactly* the required tag set (`validate_template`: required ⊆ found ∧ found ⊆ required). Retries up to 3×, returns `None` on failure.

3. **`src/main.py`** — the orchestrator and the deterministic core:
   - `load_pools()` builds an in-memory dict of entity pools from `data/*.csv`. Pools are loaded defensively: a missing CSV silently disables that placeholder (or its "common" sub-pool). Each placeholder maps to a fixed CSV + column (see `DATA_FILES` and the per-entity blocks).
   - **Mixed-pool sampling** (`_pick_value`): each entity may have a *main* pool and a *common* (popular-terms) pool. With probability `common_prob` it draws from the common pool, else the main pool. `weights` (when present, e.g. PESEL frequency for `<PERSON>`, NFZ reimbursement for `<DRUG>`) trigger `random.choices`; otherwise uniform `random.choice`. Probabilities: `<DRUG>`/`<DISEASE>`/`<TEST>` = 0.3, `<PERSON>` = 0.05, `<HOSPITAL>` = none.
   - **Synthetic PII entities** (`SYNTHETIC_GENERATORS`): `<PESEL>`, `<TELEFON>`, `<ADRES>`, `<DATA>` have **no CSV pool** — they are produced procedurally by `_gen_*` functions (PESEL with a valid date encoding + checksum, randomized phone/address/date formats). Their pool dict carries a `generator` callable; `_pick_value` calls it and returns before any list sampling. They are always registered (no file dependency), so the inject step can never fail on them.
   - `inject_placeholders()` replaces tags with sampled values **while tracking character offsets**, and caches one value per placeholder so repeated tags in a single template resolve to the *same* value.
   - `build_biou_tags()` tokenizes on whitespace (`\S+`) and assigns tags by span overlap. Despite the name and the README's "BIOUL" claim, it only emits `B-`, `I-`, `U-` (single-token), and `O` — there is **no `L-` tag**. Overlapping/already-tagged spans are skipped.
   - `generate_sample()` produces one validated sample, retrying the template up to 3× (regenerate if placeholders remain unfilled or tokenization is inconsistent). `run()` keeps a steady pool of `workers` futures in flight (`wait(..., FIRST_COMPLETED)` loop) and, under a lock, appends each finished sample to `OUTPUT_FILE` (`ner_dataset.jsonl`) as a single JSON line — no full-file rewrite, so an interrupt loses nothing.

Tag/label mapping lives in `PLACEHOLDER_LABELS` in `main.py`: the placeholders are English-ish (`<PERSON>`, `<HOSPITAL>`, `<DISEASE>`, `<DRUG>`, `<TEST>`, `<PESEL>`, `<TELEFON>`, `<ADRES>`, `<DATA>`) and the emitted entity labels are Polish (`PERSON`, `SZPITAL`, `CHOROBA`, `LEK`, `BADANIE`, `PESEL`, `TELEFON`, `ADRES`, `DATA`).

## Data

- `data/*.csv` are the tracked entity pools (CSVs read with `utf-8-sig` to tolerate BOM). Column names are hard-coded in `main.py` per file — if you add or rename a CSV, update the matching `load_simple_list`/`load_weighted_list` call.
- `data/raw/` holds the source-extraction scripts and is **gitignored / not present** in checkouts. The README documents what those scripts produced (gov.pl ICD-9/ICD-11, NFZ API, PESEL lists) but you cannot run them from a clean clone.

## Conventions / gotchas

- Entity values for `<PERSON>` are normalized by `_normalize_person_name` (titles via `.title()`, `pan`/`pani` lowercased, single-letter initials like `J.` upper-cased).
- A new entity type requires coordinated edits in **four places**: `PLACEHOLDER_LABELS` + `PLACEHOLDER_PATTERN` (main.py), the relevant `SCENARIOS["required_tags"]` in prompt.py, plus its value source — either a pool-loading block in `load_pools` (CSV-backed) **or** a `_gen_*` function registered in `SYNTHETIC_GENERATORS` (procedural, no CSV).
- The README (`README.md`) is the authoritative spec for data sources and the sampling strategy; it is more detailed than this file on the dataset provenance.
