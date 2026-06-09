# ner-medical — anonymizing Polish medical documentation

A Named Entity Recognition model that detects **9 types of sensitive entities** in Polish
medical text, for **anonymization**: paste a discharge note → the model finds personal and
medical entities → replace them with a mask, a tag, or a realistic placeholder.

**Live demo:** https://huggingface.co/spaces/michaelo-ponteski/medical-text-anonymizer
**Model:** https://huggingface.co/michaelo-ponteski/ner-medical-pl (HerBERT-base, best)

```
┌─────────────┐   ┌──────────────────────┐   ┌─────────────┐   ┌──────────────┐
│ PII sources │──▶│ Dataset generation   │──▶│ Fine-tuning │──▶│ Anonymizer   │
│ gov.pl, NFZ │   │ injection + LLM      │   │ HerBERT/    │   │ (Gradio app  │
│ ICD-9/11    │   │ (golden-style)       │   │ RoBERTa     │   │  on HF Space)│
└─────────────┘   └──────────────────────┘   └─────────────┘   └──────────────┘
```

## Entities (9 types)

| | Entity | Description |
|---|---|---|
| PII | `PERSON` | full name |
| PII | `ADDRESS` | home address |
| PII | `DATE` | date |
| PII | `PESEL` | Polish national ID number |
| PII | `PHONE` | phone number |
| medical | `DISEASE` | disease / diagnosis / symptom |
| medical | `DRUG` | drug / active substance |
| medical | `TEST` | test / procedure |
| medical | `HOSPITAL` | facility name |

Tagging scheme: **IOB2** (19 classes = 9 types × {B,I} + `O`). Labels are in English;
the generator emits Polish labels and `training/relabel.py` converts them.

## Where the data comes from — a hybrid approach

No public Polish medical NER dataset exists (sensitive data, GDPR). We build a synthetic one
from two complementary tracks, both grounded in real entity dictionaries.

### 1. Real entity values (public sources)

| Placeholder | File | Size | Weighting | Source |
|---|---|---|---|---|
| `<PERSON>` | `data/persons.csv` | 200,000 | weighted (PESEL) | PESEL name lists (gov.pl) — population-like distribution (more Piotrs than Amadeuszes) |
| `<PERSON>` (variants) | `data/persons_variants.csv` | 27,640 | weighted | pan/pani + initial |
| `<DRUG>` | `data/drugs_weighted.csv` | 959 | weighted (NFZ) | NFZ API – 2024 reimbursement |
| `<DISEASE>` | `data/diseases.csv` | 16,387 | uniform | ICD-11 (gov.pl) |
| `<TEST>` | `data/tests.csv` | 9,987 | uniform | ICD-9 (gov.pl) |
| `<HOSPITAL>` | `data/hospitals.csv` | 569 | uniform | hospital registry (gov.pl) |

Plus "popular" lists (`data/najpopularniejsze_*.csv`) for common, colloquial names.
PII (ADDRESS/DATE/PESEL/PHONE) is generated with Faker `pl_PL`. Extraction scripts: `data/raw/`.

### 2. Two generation tracks

**a) Injection (deterministic)** — `src/`. A local LLM (Ollama/Gemma) writes a **template**
with tags (`<PERSON>`, `<DRUG>`…), Python injects real values from the pools and computes
entity offsets **mathematically** → **100% correct labels**, no formatting hallucinations.
Downside: it injects full, formal database names ("electrocardiography at rest"), not
clinical language.

**b) Golden-style (LLM inline markup)** — Claude Haiku generates natural clinical text with
entities marked inline (`<DISEASE>STEMI</DISEASE>`); `training/eval_set.py` deterministically
converts the markup to labels. This yields **short, real clinical forms** (EKG, STEMI, brand
drug names, numeric dates). Downside: label noise (cleaned by `tools/clean_generated.py` —
drop corruption, strip titles, trim lab values).

### 3. Why both — distribution shift (the key finding)

Training **only on injection** scored great on its own test split (~0.98 F1) but **0.39** on
an independent golden set — the model had learned **formal database names, not clinical
language**. Evidence in mean entity length (tokens): injection DATE 3.0 / TEST 5.3 vs real
golden DATE 1.6 / TEST 3.3. Adding golden-style (short forms) to training **closes the gap** —
see Results.

## Datasets — what goes to train vs test

**TRAIN** → `output/ner_dataset_mixed.jsonl` (12,342; built by `tools/build_training_set.py`):

| Source | File | Samples |
|---|---|---|
| Injection | `output/ner_dataset.jsonl` | 8,770 |
| Golden-style (Haiku, 3 batches, cleaned) | `output/ner_dataset_generated{_clean,_2,_3}.jsonl` | 3,772 |
| ⤷ minus 200 held out | | **3,572 into the mix** |

`training/dataset.py` splits the mix 80/10/10 → train 9,874 / val 1,234 / internal-test 1,234.

**TEST / EVAL** (independent, NEVER in training):

| Set | File | Samples | Role |
|---|---|---|---|
| golden | `test/dataset_1.json`, `dataset_2.json` | 220 + 160 | independent human-style (before/after headline) |
| held-out | `output/ner_dataset_golden_heldout.jsonl` | 200 | golden-style outside training (leakage-free) |

## Training

Fine-tuning an encoder (`AutoModelForTokenClassification`). We compare 3 Polish/multilingual base models.

```bash
mamba create -n nlp-ner python=3.12 -y && mamba activate nlp-ner
pip install -r requirements.txt
wandb login

# full training (default HerBERT-base, on the mix); eval on split/golden/held-out
python -m training.train --data output/ner_dataset_mixed.jsonl
python -m training.evaluate --checkpoint models/herbert-base-cased/best --test-file output/ner_dataset_golden_heldout.jsonl

# ready-to-go on Colab T4:
#   notebooks/train_colab.ipynb  (builds the mix, trains 3 models, evaluates, pushes to Hub)
```

| Step | File | Description |
|---|---|---|
| Build dataset | `tools/build_training_set.py` | mix injection + golden-style, leakage-free held-out |
| Cleaning | `tools/clean_generated.py` | drop corruption / strip titles / trim lab values |
| Tag conversion + split | `training/dataset.py` | BIOU→IOB2, 80/10/10 split (seed 42), subword alignment |
| Training | `training/train.py` | lr 2e-5, warmup 10%, fp16, best-checkpoint by F1, W&B artifact |
| Metrics | `training/metrics.py` | entity-level P/R/F1 (seqeval, strict, IOB2) |
| Evaluation | `training/evaluate.py` | split or `--test-file`; `eval_set.py` for golden (markup) |

## Results

Entity-level micro F1 (seqeval, strict, IOB2). Three eval sets (see *Datasets*): **split**
(in-distribution, sanity), **golden** (independent, before/after headline), **held-out**
(golden-style, leakage-free).

### Effect of adding golden-style data (golden set, micro F1)

| Model | injection only | + golden-style |
|---|---|---|
| HerBERT-base | 0.39 | **0.61** |
| polish-roberta-base-v2 | 0.40 | 0.60 |
| XLM-R-base | 0.40 | 0.60 |

Adding short clinical forms to training lifts the independent golden F1 by ~0.22 — confirming the
bottleneck was the training distribution, not the model.

### Model comparison (micro F1, trained on the mix)

| Model | split | golden | held-out | >512 tok |
|---|---|---|---|---|
| **HerBERT-base** | 0.954 | **0.611** | **0.870** | 9% |
| polish-roberta-base-v2 | 0.933 | 0.603 | 0.846 | 31% |
| XLM-R-base | 0.953 | 0.597 | 0.860 | 21% |

**HerBERT-base wins** on both independent sets (golden, held-out) and truncates the fewest
samples (best Polish subword fit) — it is the model deployed in the app. Differences on golden
are small (~0.01), confirming the bottleneck is data, not architecture.

### HerBERT-base — F1 per entity

| Type | golden | held-out |
|---|---|---|
| PERSON | 0.77 | 0.99 |
| ADDRESS | 0.99 | 0.99 |
| DATE | 0.95 | 0.98 |
| PESEL | 1.00 | 1.00 |
| PHONE | 0.99 | 0.99 |
| HOSPITAL | 0.96 | 0.91 |
| DRUG | 0.79 | 0.89 |
| DISEASE | 0.12 | 0.62 |
| TEST | 0.24 | 0.68 |

PII identifiers (PERSON/ADDRESS/DATE/PESEL/PHONE) — what matters for anonymization — are strong.
DISEASE/TEST are low on golden but ~0.6–0.7 on the clean held-out: the gap is mostly label noise
in the (uncleaned, LLM-generated) golden set, not the model. Model choice (HerBERT vs RoBERTa vs
XLM-R) is secondary — the bottleneck is data.

> **Methodology note.** *split* shares the training distribution (optimistic — sanity only).
> *golden* is independent samples but shares the LLM-generation style, so absolute numbers
> overstate real-world performance; the relative before/after is the trustworthy signal. No
> human-annotated test exists yet — a fully out-of-distribution measure would require real
> annotated clinical text.

## Application

A Gradio app on HF Spaces — paste Polish medical text, pick an anonymization mode:
**mask** (`****`), **tag** (`[PERSON_1]`), or **realistic placeholder** (repo pools + Faker),
with an optional consistency toggle (same entity → same replacement). A regex catch-net backs
up PESEL/phone/date. Code: `app/`.

https://huggingface.co/spaces/michaelo-ponteski/medical-text-anonymizer

## Repo structure

```
data/          entity dictionaries (CSV) + extraction scripts (data/raw/)
src/           injection generator (Ollama/Gemma) + pools (src/pools.py)
prompts/       prompt for golden-style generation (test_set_generation.md)
training/      dataset, train, evaluate, metrics, relabel, eval_set
tools/         clean_generated, build_training_set, push_to_hub
app/           anonymizer (Gradio): anonymizer, replacements, app
test/          independent golden test sets (markup)
notebooks/     train_colab.ipynb (ready-to-go)
```

Experiments: [W&B project `nlp-ner`](https://wandb.ai/ocr-pl-med/nlp-ner).
