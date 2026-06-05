import random
import re
import time
import ollama
from .prompt import PROMPT_TEMPLATE, SCENARIOS, SPECIALIZATIONS, TONES


MODEL_NAME = "gemma4:e4b"
PLACEHOLDER_ANY_PATTERN = re.compile(r"<[^>]+>")


def build_prompt() -> tuple[str, list[str]]:
    scenario = random.choice(SCENARIOS)
    specialization = random.choice(SPECIALIZATIONS)
    tone = random.choice(TONES)
    required_tags = scenario["required_tags"]
    tags_str = ", ".join(required_tags)
    prompt = PROMPT_TEMPLATE.format(
        specialization=specialization,
        doc_type=scenario["doc_type"],
        tone=tone,
        required_tags=tags_str,
    )
    return prompt, required_tags


def clean_template_text(result_text: str) -> str:
    cleaned = result_text.strip()
    cleaned = cleaned.replace("```text", "").replace("```", "").strip()
    if cleaned.startswith("\"") and cleaned.endswith("\""):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def validate_template(template: str, required_tags: list[str]) -> bool:
    found = set(PLACEHOLDER_ANY_PATTERN.findall(template))
    required = set(required_tags)
    return required.issubset(found) and found.issubset(required)


def generate_template(max_retries: int = 3) -> tuple[str, list[str]] | None:
    for attempt in range(max_retries):
        prompt, required_tags = build_prompt()
        try:
            response = ollama.chat(model=MODEL_NAME, messages=[
                {"role": "user", "content": prompt}
            ])

            result_text = response["message"]["content"]
            template = clean_template_text(result_text)
            if not validate_template(template, required_tags):
                print(f"  [proba {attempt + 1}] Brakuje placeholderow, powtarzam...")
                continue
            return template, required_tags

        except Exception as e:
            print(f"  [proba {attempt + 1}] Blad: {e}")
            time.sleep(0.2)

    return None
