"""Testy części niezależnych od modelu: regex catch-net, strategie podmiany, provider.

Detekcja modelem (detect_model/anonymize) wymaga checkpointu na HF Hub — testowana
osobno po pushu modelu. Tu sprawdzamy logikę, którą da się odpalić bez GPU/modelu.

Uruchom: python -m app.test_anonymizer
"""

from app.anonymizer import Entity, apply, regex_catch_net, merge
from app.replacements import ReplacementProvider


def test_regex_catch_net():
    text = ("Pacjent zgłosił się 15.10.2023, PESEL 44051401359, "
            "tel. 601 234 567, kontrola 20 marca 2018 r.")
    ents = regex_catch_net(text)
    labels = {e.label for e in ents}
    assert "PESEL" in labels, "PESEL nie wykryty"
    assert "PHONE" in labels, "PHONE nie wykryty"
    assert "DATE" in labels, "DATE nie wykryty"
    # PESEL 44051401359 ma poprawną sumę kontrolną
    pesels = [e.text for e in ents if e.label == "PESEL"]
    assert "44051401359" in pesels
    # dwie daty
    dates = [e for e in ents if e.label == "DATE"]
    assert len(dates) == 2, f"oczekiwano 2 dat, jest {len(dates)}"
    print("OK regex_catch_net:", sorted(labels), "| daty:", [e.text for e in dates])


def test_invalid_pesel_rejected():
    # 11 cyfr z błędną sumą kontrolną — nie powinno być PESEL-em
    ents = regex_catch_net("numer 12345678901 w dokumencie")
    assert not [e for e in ents if e.label == "PESEL"], "zaakceptowano błędny PESEL"
    print("OK invalid_pesel_rejected")


def test_mask_preserves_no_leak():
    text = "Jan Kowalski, PESEL 44051401359"
    ents = [Entity("PERSON", 0, 12, "Jan Kowalski", 0.9),
            Entity("PESEL", 20, 31, "44051401359", 1.0)]
    out, _ = apply(text, ents, strategy="mask")
    assert "Jan Kowalski" not in out and "44051401359" not in out, "wyciek po maskowaniu!"
    assert "*" in out
    print("OK mask:", out)


def test_tag_numbering_consistent():
    text = "Jan Kowalski i Anna Nowak, potem znów Jan Kowalski"
    ents = [Entity("PERSON", 0, 12, "Jan Kowalski", 0.9),
            Entity("PERSON", 15, 25, "Anna Nowak", 0.9),
            Entity("PERSON", 38, 50, "Jan Kowalski", 0.9)]
    out, _ = apply(text, ents, strategy="tag", consistent=True)
    # ten sam Jan Kowalski -> ten sam numer
    assert out.count("[PERSON_1]") == 2, f"spójność numeracji zawiodła: {out}"
    assert "[PERSON_2]" in out
    print("OK tag consistent:", out)


def test_tag_numbering_inconsistent():
    text = "Jan Kowalski i znów Jan Kowalski"
    ents = [Entity("PERSON", 0, 12, "Jan Kowalski", 0.9),
            Entity("PERSON", 20, 32, "Jan Kowalski", 0.9)]
    out, _ = apply(text, ents, strategy="tag", consistent=False)
    assert "[PERSON_1]" in out and "[PERSON_2]" in out, f"brak numeracji per wystąpienie: {out}"
    print("OK tag inconsistent:", out)


def test_placeholder_realistic_and_consistent():
    prov = ReplacementProvider(seed=42)
    text = "Jan Kowalski, PESEL 44051401359, tel 601234567, data 15.10.2023, adres X"
    ents = [Entity("PERSON", 0, 12, "Jan Kowalski", 0.9),
            Entity("PESEL", 20, 31, "44051401359", 1.0),
            Entity("PHONE", 37, 46, "601234567", 1.0),
            Entity("DATE", 53, 63, "15.10.2023", 1.0),
            Entity("ADDRESS", 70, 71, "X", 0.9)]
    out, _ = apply(text, ents, strategy="placeholder", consistent=True, provider=prov)
    for leak in ["Jan Kowalski", "44051401359", "601234567", "15.10.2023"]:
        assert leak not in out, f"wyciek: {leak} w {out}"
    print("OK placeholder:", out)


def test_overlap_replacement_offsets():
    # podmiana od końca nie psuje offsetów przy wielu encjach różnej długości
    text = "A Jan Kowalski B Anna C"
    ents = [Entity("PERSON", 2, 14, "Jan Kowalski", 0.9),
            Entity("PERSON", 17, 21, "Anna", 0.9)]
    out, _ = apply(text, ents, strategy="mask")
    assert out == "A ************ B **** C", f"offsety rozjechane: {out}"
    print("OK offsets:", out)


def test_merge_prefers_model():
    model_ents = [Entity("DATE", 0, 10, "15.10.2023", 0.9, "model")]
    regex_ents = [Entity("DATE", 0, 10, "15.10.2023", 1.0, "regex"),  # nakłada się -> odrzuć
                  Entity("PHONE", 20, 29, "601234567", 1.0, "regex")]  # nowy -> dodaj
    merged = merge(model_ents, regex_ents)
    assert len(merged) == 2, f"merge źle: {len(merged)}"
    assert sum(1 for e in merged if e.source == "regex") == 1
    print("OK merge:", [(e.label, e.source) for e in merged])


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nWszystkie testy przeszły.")
