---
title: Anonimizator dokumentacji medycznej
emoji: 🩺
colorFrom: blue
colorTo: green
sdk: gradio
app_file: app.py
pinned: false
---

# Anonimizator polskiej dokumentacji medycznej

Wklej tekst medyczny → model NER wykrywa wrażliwe encje (osoba, PESEL, telefon,
adres, data, szpital + choroby/leki/badania) → anonimizacja: maska, numerowany tag
albo realistyczny placeholder. Model: [`michaelo-ponteski/ner-medical-pl`](https://huggingface.co/michaelo-ponteski/ner-medical-pl).

Regex catch-net domyka PESEL/telefon/datę (model ma tam niski recall). Plik ten
jest README **Space'a** — przy deployu nadpisuje README repo (zob. `space/DEPLOY.md`).
