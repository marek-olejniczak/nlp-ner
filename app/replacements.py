"""Źródła wartości zastępczych dla anonimizacji.

Medyczne encje (PERSON, DISEASE, DRUG, TEST, HOSPITAL) ciągniemy z pul CSV repo
(`src.pools` — reużycie logiki ważenia/common-pool z generatora). PII (ADDRESS,
DATE, PESEL, PHONE) generuje Faker pl_PL (ma poprawny `pesel()` z sumą kontrolną).

Etykiety modelu są po angielsku; mapujemy je na klucze pul (`<PERSON>` itd.).
Tryb spójny: cache `(label, oryginalny_tekst) -> zamiennik`, żeby ten sam
"Jan Kowalski" dostał ten sam zamiennik w całym dokumencie.
"""

from __future__ import annotations

import random

from src.pools import DATA_DIR, load_pools, _pick_value

# angielska etykieta modelu -> klucz puli CSV
EN_TO_POOL = {
    "PERSON": "<PERSON>",
    "HOSPITAL": "<HOSPITAL>",
    "DISEASE": "<DISEASE>",
    "DRUG": "<DRUG>",
    "TEST": "<TEST>",
}
PII_LABELS = {"ADDRESS", "DATE", "PESEL", "PHONE"}


class ReplacementProvider:
    """Dostarcza realistyczne zamienniki encji; opcjonalnie spójne w obrębie dokumentu."""

    def __init__(self, seed: int | None = None):
        # brak data/ (np. lekki deploy) -> pule puste, PII i tak działa przez Faker,
        # a medyczne placeholdery degradują się do [LABEL]
        try:
            self._pools = load_pools(DATA_DIR)
        except (FileNotFoundError, ValueError):
            self._pools = {}
        self._rng = random.Random(seed)
        # Faker importujemy leniwie — dep tylko dla PII
        from faker import Faker
        self._fake = Faker("pl_PL")
        if seed is not None:
            self._fake.seed_instance(seed)
        self._cache: dict[tuple[str, str], str] = {}

    def _fresh(self, label: str) -> str:
        """Nowy losowy zamiennik dla danego typu (bez cache)."""
        if label in EN_TO_POOL:
            pool = self._pools.get(EN_TO_POOL[label])
            if pool:
                return _pick_value(pool)
            if label == "PERSON":  # fallback bez puli CSV
                return self._fake.name()
            return f"[{label}]"
        if label == "ADDRESS":
            return f"{self._fake.street_address()}, {self._fake.postcode()} {self._fake.city()}"
        if label == "DATE":
            return self._fake.date(pattern="%d.%m.%Y")
        if label == "PESEL":
            return self._fake.pesel()
        if label == "PHONE":
            return self._fake.phone_number()
        return f"[{label}]"

    def value(self, label: str, original: str, consistent: bool) -> str:
        """Zamiennik dla encji. Przy consistent=True ten sam (label, original) -> ten sam wynik."""
        if not consistent:
            return self._fresh(label)
        key = (label, original.strip().lower())
        if key not in self._cache:
            self._cache[key] = self._fresh(label)
        return self._cache[key]

    def reset(self) -> None:
        self._cache.clear()
