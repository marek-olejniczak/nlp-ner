# Deploy appki na Hugging Face Spaces

Model jest już na Hub: `michaelo-ponteski/ner-medical-pl`. Teraz hostujemy UI.

## 1. Utwórz Space (raz)
- Wejdź na **huggingface.co/new-space**
- Owner: `michaelo-ponteski`, nazwa np. `anonimizator-med`
- SDK: **Gradio**, widoczność: **Public**, hardware: **CPU basic** (darmowy — wystarczy)
- Utwórz. Dostajesz git repo: `https://huggingface.co/spaces/michaelo-ponteski/anonimizator-med`

## 2. Wgraj kod (świeża kopia, bez historii i bez output/)
Z katalogu repo (`nlp-ner`):

```bash
git clone https://huggingface.co/spaces/michaelo-ponteski/anonimizator-med hf-space
cp -r app src data app.py requirements.txt hf-space/
cp space/README.md hf-space/README.md        # frontmatter konfiguruje Space
cd hf-space
git add -A && git commit -m "deploy anonimizator" && git push
```

`data/` daje pełne realistyczne placeholdery (bez niego PERSON leci z Faker, a
choroby/leki/badania degradują się do `[LABEL]` — i tak domyślnie ich nie anonimizujemy).
Pomijamy `output/` (duże datasety, niepotrzebne appce).

## 3. Gotowe
Space sam zbuduje (instaluje `requirements.txt`, ściąga model z Hub przy starcie)
i wystawi publiczny URL: `https://huggingface.co/spaces/michaelo-ponteski/anonimizator-med`.
Pierwszy build ~kilka minut (torch + model 0.5 GB).

## Uwagi
- Model nadpisalny zmienną `NER_MODEL_ID` (Space → Settings → Variables) — gdy
  koledzy dowiozą lepszy model z poprawionych danych, podmieniasz tu, zero zmian w kodzie.
- Push uwierzytelniasz tym samym tokenem HF (`huggingface-cli login` już zrobione).
