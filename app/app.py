"""Gradio UI for anonymizing Polish medical documentation.

Paste text -> NER model detects entities -> choose how to anonymize them.
Model loaded from HF Hub (NER_MODEL_ID env var). Run: python -m app.app
"""

from __future__ import annotations

import gradio as gr

from app.anonymizer import ALL_TYPES, DEFAULT_TYPES, MODEL_ID, anonymize
from app.replacements import ReplacementProvider

STRATEGIES = {
    "Mask (asterisks)": "mask",
    "Typed tag ([PERSON_1])": "tag",
    "Realistic placeholder": "placeholder",
}

_provider: ReplacementProvider | None = None


def _get_provider() -> ReplacementProvider:
    global _provider
    if _provider is None:
        _provider = ReplacementProvider()
    return _provider


def to_highlight(text: str, ents) -> list[tuple[str, str | None]]:
    """Build (fragment, label|None) segments for gr.HighlightedText."""
    segments, cursor = [], 0
    for e in sorted(ents, key=lambda e: e.start):
        if e.start > cursor:
            segments.append((text[cursor:e.start], None))
        segments.append((text[e.start:e.end], e.label))
        cursor = e.end
    if cursor < len(text):
        segments.append((text[cursor:], None))
    return segments


def run(text, strategy_label, consistent, types, threshold, use_regex):
    if not text.strip():
        return [("(paste some text)", None)], "", []
    strategy = STRATEGIES[strategy_label]
    provider = _get_provider() if strategy == "placeholder" else None
    try:
        result, ents = anonymize(
            text, types=types, strategy=strategy, consistent=consistent,
            threshold=threshold, use_regex=use_regex, provider=provider, model_id=MODEL_ID,
        )
    except Exception as e:  # model unavailable / load error
        return [(f"Error: {e}", None)], "", []
    table = [[e.label, e.text, round(e.score, 3), e.source] for e in ents]
    return to_highlight(text, ents), result, table


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Medical Document Anonymizer") as demo:
        gr.Markdown(
            "# Medical Document Anonymizer\n"
            "**Anonymizes Polish medical text.** Paste a document, pick a mode and which "
            "entity types to hide. The NER model detects entities; a regex catch-net backs up "
            "PESEL / phone / date (where the model's recall is low).\n\n"
            f"Model: `{MODEL_ID}`  ·  Entity types: PERSON, DISEASE, DRUG, TEST, HOSPITAL, "
            "ADDRESS, DATE, PESEL, PHONE."
        )
        with gr.Row():
            with gr.Column(scale=3):
                inp = gr.Textbox(label="Polish medical text", lines=12,
                                 placeholder="Paste a discharge note / clinical note in Polish...")
            with gr.Column(scale=2):
                strategy = gr.Radio(list(STRATEGIES), value="Mask (asterisks)",
                                    label="Anonymization mode")
                consistent = gr.Checkbox(value=True,
                                         label="Consistent (same entity → same replacement)")
                types = gr.CheckboxGroup(ALL_TYPES, value=DEFAULT_TYPES,
                                         label="Entity types to anonymize")
                threshold = gr.Slider(0.0, 1.0, value=0.5, step=0.05,
                                      label="Model confidence threshold")
                use_regex = gr.Checkbox(value=True, label="Regex catch-net (PESEL / phone / date)")
                btn = gr.Button("Anonymize", variant="primary")
        gr.Markdown("### Detected entities")
        highlighted = gr.HighlightedText(label="Preview (original, entities highlighted)")
        out = gr.Textbox(label="Anonymized text", lines=12)
        table = gr.Dataframe(headers=["type", "text", "score", "source"], label="Entity list")

        btn.click(run, [inp, strategy, consistent, types, threshold, use_regex],
                  [highlighted, out, table])
    return demo


if __name__ == "__main__":
    build_ui().launch()
