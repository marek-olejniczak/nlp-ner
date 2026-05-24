import random
import re
import time
import ollama
from .prompt import PROMPT_TEMPLATE, DOCUMENT_TYPES, TONES, PLACEHOLDERS


MODEL_NAME = "gemma4:e2b"
PLACEHOLDER_ANY_PATTERN = re.compile(r"<[^>]+>")


def build_prompt() -> str:
    doc_type = random.choice(DOCUMENT_TYPES)
    tone = random.choice(TONES)
    return PROMPT_TEMPLATE.format(doc_type=doc_type, tone=tone)


def clean_template_text(result_text: str) -> str:
    cleaned = result_text.strip()
    cleaned = cleaned.replace("```text", "").replace("```", "").strip()
    if cleaned.startswith("\"") and cleaned.endswith("\""):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def validate_template(template: str) -> bool:
    found = set(PLACEHOLDER_ANY_PATTERN.findall(template))
    required = set(PLACEHOLDERS)
    return required.issubset(found) and found.issubset(required)


def generate_template(max_retries: int = 3) -> str | None:
    for attempt in range(max_retries):
        prompt = build_prompt()
        try:
            response = ollama.chat(model=MODEL_NAME, messages=[
                {"role": "user", "content": prompt}
            ])

            result_text = response["message"]["content"]
            template = clean_template_text(result_text)
            if not validate_template(template):
                print(f"  [proba {attempt + 1}] Brakuje placeholderow, powtarzam...")
                time.sleep(1)
                continue
            return template

        except Exception as e:
            print(f"  [proba {attempt + 1}] Blad: {e}")
            time.sleep(1)

    return None
