"""Entrypoint dla Hugging Face Spaces (HF szuka app.py w roocie).

Lokalnie równie dobrze: `python app.py`. Model bierze z NER_MODEL_ID
(domyślnie michaelo-ponteski/ner-medical-pl).
"""

from app.app import build_ui

if __name__ == "__main__":
    build_ui().launch()
