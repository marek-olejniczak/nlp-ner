---
title: Medical Text Anonymizer
emoji: 🩺
colorFrom: blue
colorTo: green
sdk: gradio
app_file: app.py
pinned: false
---

# Medical Text Anonymizer

**Anonymizes Polish medical text.** Paste a document → the NER model detects sensitive
entities (person, PESEL, phone, address, date, hospital + disease/drug/test) → anonymize:
mask, typed tag, or realistic placeholder. Model: [`michaelo-ponteski/ner-medical-pl`](https://huggingface.co/michaelo-ponteski/ner-medical-pl).

A regex catch-net backs up PESEL / phone / date (where the model's recall is low). This file
is the **Space** README — at deploy it overwrites the repo README (see `space/DEPLOY.md`).
