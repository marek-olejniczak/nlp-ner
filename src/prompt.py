PLACEHOLDERS = [
    "<PERSON>",
    "<HOSPITAL>",
    "<DISEASE>",
    "<DRUG>",
    "<TEST>",
]

DOCUMENT_TYPES = [
    "wypis ze szpitala",
    "notatka z wizyty POZ",
    "opis badania RTG",
    "konsultacja specjalistyczna",
    "krotki wywiad lekarski",
]

TONES = [
    "skrajnie skrotowy, pelny skrotow i laciny",
    "opisowy, rzeczowy",
    "pisany w pospiechu, urywany",
    "techniczny, raportowy",
]

PROMPT_TEMPLATE = """Jestes asystentem tworzacym dane treningowe NER dla polskiej dokumentacji medycznej.
Wygeneruj realistyczny, krotki {doc_type}.
Ton wypowiedzi: {tone}.

ZASADY:
1. Uzywaj medycznego zargonu i typowych skrotow (np. nt, rtg, usg, b/z, s.o., p.o.).
2. Tekst ma symulowac wynik z OCR, wplesc 2-3 drobne bledy literowe (np. "pacjet" zamiast "pacjent", zloczone slowa "wklatce", brak spacji po kropce).
3. ZAMIEN wszystkie dane wrazliwe na placeholdery. Uzywaj DOKLADNIE tych tagow:
   <PERSON>, <HOSPITAL>, <DISEASE>, <DRUG>, <TEST>
4. W tekscie MUSZA pojawic sie wszystkie powyzsze placeholdery co najmniej raz.
5. Zwracaj WYLUZNIE surowy tekst z placeholderami. Bez JSON, bez cudzyslowow, bez Markdown.

Przyklad uzycia placeholderow (nie kopiuj doslownie):
"<PERSON> przyjety do <HOSPITAL> z powodu <DISEASE>. Zalecono <DRUG> i zlecono <TEST>."
"""
