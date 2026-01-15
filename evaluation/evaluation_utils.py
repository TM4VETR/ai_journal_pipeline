import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple


# =========================
# Data structures
# =========================

@dataclass
class MicroPRF:
    tp: int
    fp: int
    fn: int

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return (2 * p * r / (p + r)) if (p + r) else 0.0


# =========================
# XML helpers
# =========================

def iter_token_elements(xml_path: Path) -> Iterable[ET.Element]:
    """
    Yields all <token> elements in the XML, regardless of nesting level.
    If the file cannot be parsed or tokens cannot be read, yields nothing.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        yield from root.findall(".//token")
    except Exception:
        return


def load_token_level_entities(
    xml_path: Path,
    *,
    gt_attr: str = "entity_gt",
    pred_attr: str = "entity_pred",
) -> Tuple[List[str], List[str]]:
    """
    Returns (gt_labels, pred_labels) in document order.
    Missing attributes are treated as "O".
    """
    gt_labels: List[str] = []
    pred_labels: List[str] = []

    for tok in iter_token_elements(xml_path):
        gt = tok.get(gt_attr)

        if not gt:
            # Ground truth filed might be named just "entity"
            gt = tok.get("entity")

        if not gt:
            gt = "O"

        gt = gt.strip()

        pred = tok.get(pred_attr, "O").strip()
        gt_labels.append(gt)
        pred_labels.append(pred)

    return gt_labels, pred_labels


# =========================
# Scoring (micro level)
# =========================

def score_token_micro(gt_labels: List[str], pred_labels: List[str]) -> MicroPRF:
    """
    Token-level micro P/R/F1.

    Definition:
      - TP: pred == gt != "O"
      - FP: pred != "O" and pred != gt
      - FN: gt != "O" and pred == "O"
    """
    if len(gt_labels) != len(pred_labels):
        raise ValueError(
            f"Length mismatch: GT={len(gt_labels)} PRED={len(pred_labels)}"
        )

    tp = fp = fn = 0

    for gt, pred in zip(gt_labels, pred_labels):
        if gt == pred and gt != "O":
            tp += 1
        elif pred != "O" and pred != gt:
            fp += 1
        elif gt != "O" and pred == "O":
            fn += 1

    return MicroPRF(tp=tp, fp=fp, fn=fn)
