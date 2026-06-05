SPECIALIZATIONS = [
    "Kardiologia i Hipertensjologia",
    "Chirurgia Ogólna / Urazowa (SOR)",
    "Pediatria",
    "Onkologia",
    "Medycyna Pracy / POZ",
    "Ginekologia i Położnictwo",
]

SCENARIOS = [
    {
        "doc_type": "wypis ze szpitala / epikryza",
        "required_tags": ["<PERSON>", "<PESEL>", "<ADRES>", "<HOSPITAL>", "<DISEASE>", "<DRUG>"],
    },
    {
        "doc_type": "skierowanie na cito do szpitala",
        "required_tags": ["<PERSON>", "<PESEL>", "<TELEFON>", "<DISEASE>", "<TEST>", "<HOSPITAL>"],
    },
    {
        "doc_type": "opis badania obrazowego (RTG/USG/MRI)",
        "required_tags": ["<PERSON>", "<DATA>", "<TEST>", "<DISEASE>"],
    },
    {
        "doc_type": "zalecenia po ambulatoryjne / e-recepta",
        "required_tags": ["<PERSON>", "<PESEL>", "<DISEASE>", "<DRUG>"],
    },
    {
        "doc_type": "notatka z wizyty POZ",
        "required_tags": ["<PERSON>", "<TELEFON>", "<DISEASE>", "<DRUG>"],
    },
    {
        "doc_type": "konsultacja specjalistyczna",
        "required_tags": ["<PERSON>", "<DATA>", "<ADRES>", "<DISEASE>", "<TEST>"],
    },
    {
        "doc_type": "krótki wywiad lekarski / badanie przedmiotowe",
        "required_tags": ["<PERSON>", "<PESEL>", "<DISEASE>"],
    },
]

TONES = [
    "skrajnie skrótowy, pełen skrótów i łaciny, forma równoważników zdań",
    "opisowy, rzeczowy, ciągły blok tekstu",
    "pisany w pośpiechu, urywany, zapis punktowy",
    "techniczny, raportowy, struktura SOAP",
    "zwięzły, formalny, ciągły blok tekstu",
    "skrótowa notatka, luźne wyliczanie",
]

PROMPT_TEMPLATE = """Jesteś lekarzem pracującym na oddziale/w poradni: {specialization}.
Wygeneruj realistyczny fragment polskiej dokumentacji medycznej.
Rodzaj dokumentu: {doc_type}.
Styl i format zapisu: {tone}.

ZASADY KRYTYCZNE:
1. Skup się na specyfice swojej specjalizacji. Używaj poprawnego żargonu i odpowiednich skrótów lekarskich.
2. Twoim jedynym zadaniem jest stworzenie SZABLONU, w którym dane pacjenta, nazwy leków, chorób itp. są zastąpione ścisłymi tagami.
3. MASZ OBOWIĄZEK użyć w tekście TYCH I TYLKO TYCH tagów, dokładnie w tej formie:
   {required_tags}
4. Każdy z podanych tagów musi wystąpić w tekście co najmniej raz.
5. NIE używaj żadnych innych tagów. NIE zmyślaj własnych imion, nazw leków czy szpitali – wszędzie tam używaj podanych tagów.
6. Zwróć wyłącznie surowy tekst dokumentu. Żadnych wstępów, podsumowań, formatowania Markdown ani JSON."""
