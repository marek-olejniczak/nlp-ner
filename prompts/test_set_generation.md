Jesteś doświadczonym polskim lekarzem z wieloletnim stażem, pracującym w różnych realiach (SOR, kardiologia, POZ, chirurgia, onkologia). Twoim zadaniem jest stworzenie niezwykle realistycznego zbioru testowego NLP do ekstrakcji encji medycznych (NER).

Wygeneruj 10 unikalnych, bardzo zróżnicowanych fragmentów polskiej dokumentacji medycznej.

ZASADY KRYTYCZNE (Zignorowanie ich zniszczy projekt):

1. REALIZM SKŁADNI: Pisz tak, jak piszą polscy lekarze pod presją czasu. Używaj potężnej ilości skrótów (np. b/z, p.o., s.o., rtg, tk, tętno miarowe, rr, hr, dtt, ndpl, op., r.), równoważników zdań, wtrąceń łacińskich i żargonu. Teksty mają być surowe.

2. RÓŻNORODNOŚĆ SYTUACJI: Każdy tekst musi reprezentować inny typ dokumentu: np. chaotyczna notatka z dyżuru SOR, zwięzła e-recepta z POZ, specjalistyczny fragment epikryzy z oddziału, krótki opis badania obrazowego, relacja z wywiadu środowiskowego.

3. NATURALNE DANE: W tekście używaj wymyślonych, ale naturalnie brzmiących danych (np. Jan Kowalski, Szpital Bielański, Ramipril, migotanie przedsionków, morfologia). Dane PII (PESEL, telefon, adres, data) także zmyślone, ale realistyczne formatowo.

4. ADNOTACJA INLINE: Encje oznaczaj BEZPOŚREDNIO w tekście znacznikami XML w formie `<TAG>treść</TAG>`. Zasady twarde:
   - Każdy otwarty znacznik MUSI być zamknięty tym samym tagiem. Bez zagnieżdżania.
   - Używaj WYŁĄCZNIE znaczników z listy poniżej, dokładnie w tej wielkości liter.
   - Oznaczaj TYLKO właściwą nazwę encji — bez słów kontekstowych (przyimków, nazw oddziałów, tytułów lekarskich). Przykłady:
     - DOBRZE: `na kardiologię <SZPITAL>Szpitala Bielańskiego</SZPITAL>`
     - ŹLE: `<SZPITAL>na kardiologię Szpitala Bielańskiego</SZPITAL>`
     - DOBRZE: `konsultował dr <PERSON>Jan Nowak</PERSON>`  (bez „dr")
   - Granica znacznika ma obejmować dokładnie nazwę encji — nie doklejaj sąsiednich znaków interpunkcyjnych ani jednostek (np. `<LEK>Acard</LEK> 75mg`, nie `<LEK>Acard 75mg</LEK>`).

5. FORMAT WYJŚCIOWY: Zwróć wynik WYŁĄCZNIE jako czysty, poprawny obiekt JSON (tablica obiektów). Żadnego tekstu przed i po. Każdy obiekt ma jedno pole `"text"` zawierające fragment z inline tagami.

Dozwolone znaczniki (WYŁĄCZNIE te):
- `<PERSON>`   — imię i nazwisko osoby (pacjent, lekarz) — bez tytułów
- `<CHOROBA>`  — jednostka chorobowa, rozpoznanie, objaw
- `<LEK>`      — nazwa leku lub substancji czynnej
- `<BADANIE>`  — badanie, zabieg, procedura (EKG, morfologia, rtg klatki, USG jamy brzusznej...)
- `<SZPITAL>`  — nazwa szpitala / placówki (sama nazwa, bez oddziału)
- `<ADRES>`    — adres (ulica/al. + numer, opcjonalnie kod pocztowy + miasto)
- `<DATA>`     — data w dowolnym formacie
- `<PESEL>`    — 11-cyfrowy numer PESEL
- `<TELEFON>`  — polski numer telefonu (9 cyfr)

Realizm danych PII:
- PESEL: dokładnie 11 cyfr.
- TELEFON: realistyczny 9-cyfrowy numer, mieszaj formaty zapisu (601234567, 601 234 567, +48 601 234 567).
- DATA: mieszaj formaty (15.10.2023, 20 marca 2018 r., 2023-10-15).
- ADRES: ul./al. + nazwa + numer, czasem kod pocztowy + miasto.

Struktura JSON ma wyglądać dokładnie tak (to jest tylko przykład formatowania, nie kopiuj tej treści):
[
  {
    "text": "Wypis z SOR, <DATA>14.03.2024</DATA>. Pacjent <PERSON>Jan Nowak</PERSON>, PESEL <PESEL>85031512345</PESEL>, zam. <ADRES>ul. Polna 7, 30-001 Kraków</ADRES>, tel. <TELEFON>601 234 567</TELEFON>. Zgłosił się z bólem w klatce, w <BADANIE>EKG</BADANIE> cechy <CHOROBA>STEMI</CHOROBA>. Podano <LEK>Acard</LEK>, przekazano na kardiologię <SZPITAL>Szpitala Wojewódzkiego</SZPITAL>. Zlecono <BADANIE>troponiny</BADANIE>."
  }
]
