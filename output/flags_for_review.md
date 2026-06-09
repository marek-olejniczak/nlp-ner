# Usunięte próbki (57 flag, 55 próbek) — NIE ma ich w czystej puli

Te próbki USUNIĘTO z `ner_dataset_generated_clean.jsonl` (dogenerujemy, zamiast poprawiać ręcznie).
Lista służy jako rejestr błędów do uniknięcia przy regeneracji — zaostrzyć prompt: polski only (bez
angielskich leków), ADDRESS tylko adres pocztowy (nie anatomia), span = sama nazwa bez wartości/jednostek.
Numer = indeks w output/generated_review.md.

- [0001] **wartosc-wewnatrz-spanu** DISEASE: «Zwężenie 50% w RCA,»
- [0001] **wartosc-wewnatrz-spanu** DISEASE: «zwężenie 70% w LAD,»
- [0001] **wartosc-wewnatrz-spanu** DISEASE: «zwężenie 85% w CX.»
- [0002] **ADDRESS-bez-markera** ADDRESS: «lewego przedramienia»
- [0008] **wartosc-wewnatrz-spanu** TEST: «Glikemia 356 mg/dl, ketonemia»
- [0024] **wartosc-wewnatrz-spanu** DISEASE: «kaszel trwający 3 tygodnie z odkrztuszaniem krwi.»
- [0063] **wartosc-wewnatrz-spanu** TEST: «Amylase 520 j/l, lipase 780 j/l.»
- [0137] **ADDRESS-bez-markera** ADDRESS: «Poznań, Nowe Miasto 15/7.»
- [0146] **wartosc-wewnatrz-spanu** TEST: «Wymaga miary TSH, wolnego T4, testosteronu.»
- [0155] **wartosc-wewnatrz-spanu** TEST: «USG kontrolne za 2 miesiące.»
- [0160] **angielski-lek** «Vitamin»
- [0171] **ADDRESS-bez-markera** ADDRESS: «Marszałkowska 42/5, Warszawa,»
- [0185] **wartosc-wewnatrz-spanu** TEST: «(glikoza na czczo 118 mg/dl).»
- [0211] **wartosc-wewnatrz-spanu** TEST: «Lipaza 1200 j.m.»
- [0235] **wartosc-wewnatrz-spanu** DISEASE: «otyłość klasa II (BMI 37), prediabetes.»
- [0271] **wartosc-wewnatrz-spanu** DISEASE: «melanoma invasive, Breslow 2.8mm, Clark V, bez przerzutów do węzłów.»
- [0279] **wartosc-wewnatrz-spanu** TEST: «HbA1c:»
- [0284] **wartosc-wewnatrz-spanu** DISEASE: «przebyta grypa H1N1 z powikłaniami oddechowymi.»
- [0291] **wartosc-wewnatrz-spanu** DISEASE: «przekroczony termin porodu o 10 dni.»
- [0292] **wartosc-wewnatrz-spanu** DISEASE: «Rak piersi T2N1M0 lewej piersi.»
- [0302] **angielski-lek** «Vitamin»
- [0329] **wartosc-wewnatrz-spanu** DISEASE: «DM2 z CKD»
- [0337] **wartosc-wewnatrz-spanu** TEST: «HbA1c»
- [0352] **wartosc-wewnatrz-spanu** TEST: «Glikemia o godz. 3 rano:»
- [0371] **angielski-lek** «Sunscreen»
- [0378] **wartosc-wewnatrz-spanu** TEST: «SpO2»
- [0430] **wartosc-wewnatrz-spanu** TEST: «HbA1c»
- [0454] **angielski-lek** «Retinol»
- [0463] **wartosc-wewnatrz-spanu** TEST: «USG 3D macicy»
- [0501] **wartosc-wewnatrz-spanu** DISEASE: «nagłym upadkiem cukru we krwi (30 mg/dl),»
- [0518] **angielski-lek** «Vitamin»
- [0519] **wartosc-wewnatrz-spanu** DISEASE: «HbA1c»
- [0537] **wartosc-wewnatrz-spanu** TEST: «MRI za 3 m-ce, pomiar stężenia prolaktyny.»
- [0551] **wartosc-wewnatrz-spanu** TEST: «wymianę zastawki aorty BioCor 25mm + plastykę zastawki mitralnej.»
- [0582] **ADDRESS-bez-markera** ADDRESS: «Warszawa, Wierzbno 50/3.»
- [0583] **angielski-lek** «Vitamin»
- [0593] **wartosc-wewnatrz-spanu** DISEASE: «DM2 z powikłaniami, hiperlipidemia.»
- [0618] **wartosc-wewnatrz-spanu** TEST: «USG co 1 tydzień.»
- [0638] **wartosc-wewnatrz-spanu** DISEASE: «cukrzyca tip 2, hypertensja samoistna, hiperlipidemia.»
- [0649] **wartosc-wewnatrz-spanu** TEST: «EEG kontrolne po 3 m-cach.»
- [0665] **wartosc-wewnatrz-spanu** TEST: «Zamrażanie ciekłym azotem — 15 brodzików.»
- [0718] **wartosc-wewnatrz-spanu** TEST: «SpO2»
- [0731] **wartosc-wewnatrz-spanu** TEST: «HbA1c»
- [0744] **wartosc-wewnatrz-spanu** TEST: «Cortisol w słinie 18:00: 8.2 nmol/l,»
- [0785] **wartosc-wewnatrz-spanu** TEST: «HbA1c»
- [0789] **wartosc-wewnatrz-spanu** TEST: «Rentgen kolana 2 rzuty.»
- [0790] **wartosc-wewnatrz-spanu** DISEASE: «kontrola za 6 m-cy,»
- [0792] **wartosc-wewnatrz-spanu** DISEASE: «COVID-19,»
- [0811] **wartosc-wewnatrz-spanu** TEST: «RTG zapęści 3 rzuty»
- [0824] **wartosc-wewnatrz-spanu** DISEASE: «cukrzyca 2 typu,»
- [0829] **wartosc-wewnatrz-spanu** TEST: «RTG 3 rzuty.»
- [0840] **wartosc-wewnatrz-spanu** DISEASE: «Cukrzyca typ 2, kardiopatie zwójkowa rozpoznana.»
- [0865] **wartosc-wewnatrz-spanu** TEST: «RTG kontrola za 10 dni.»
- [0866] **wartosc-wewnatrz-spanu** TEST: «laser CO2 na wiele znamion»
- [0874] **wartosc-wewnatrz-spanu** DISEASE: «Cukrzyca tip 2 wyrównana, hipertensja samoistna.»
- [0893] **wartosc-wewnatrz-spanu** DISEASE: «COVID-19.»
- [0901] **angielski-lek** «cream»