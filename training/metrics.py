"""Metryki NER: entity-level F1 (seqeval), nie token accuracy.

Token accuracy jest mylące — ~78% tagów to "O", więc model przewidujący
wszędzie "O" miałby 78% accuracy. seqeval liczy encję jako trafioną tylko
przy idealnym dopasowaniu typu ORAZ pełnego spanu (tryb strict, schemat IOB2).
"""

import numpy as np
from seqeval.metrics import (
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)
from seqeval.scheme import IOB2

from .dataset import ID2LABEL


def decode_predictions(
    predictions: np.ndarray, label_ids: np.ndarray
) -> tuple[list[list[str]], list[list[str]]]:
    """Logity + gold labels -> listy sekwencji tagów (pomijając pozycje -100)."""
    pred_ids = np.argmax(predictions, axis=-1)

    true_seqs, pred_seqs = [], []
    for pred_row, label_row in zip(pred_ids, label_ids):
        true_seq, pred_seq = [], []
        for p, l in zip(pred_row, label_row):
            if l == -100:  # subword kontynuacji / token specjalny — nie oceniamy
                continue
            true_seq.append(ID2LABEL[int(l)])
            pred_seq.append(ID2LABEL[int(p)])
        true_seqs.append(true_seq)
        pred_seqs.append(pred_seq)
    return true_seqs, pred_seqs


def compute_metrics(eval_pred) -> dict:
    """Hook dla HF Trainer — micro P/R/F1 na poziomie encji."""
    predictions, label_ids = eval_pred
    true_seqs, pred_seqs = decode_predictions(predictions, label_ids)
    return {
        "precision": precision_score(true_seqs, pred_seqs, mode="strict", scheme=IOB2),
        "recall": recall_score(true_seqs, pred_seqs, mode="strict", scheme=IOB2),
        "f1": f1_score(true_seqs, pred_seqs, mode="strict", scheme=IOB2),
    }


def full_report(true_seqs: list[list[str]], pred_seqs: list[list[str]]) -> tuple[str, dict]:
    """Raport per typ encji: tekstowy (do konsoli) + dict (do JSON-a)."""
    text = classification_report(true_seqs, pred_seqs, mode="strict", scheme=IOB2, digits=4)
    as_dict = classification_report(
        true_seqs, pred_seqs, mode="strict", scheme=IOB2, output_dict=True
    )
    return text, as_dict
