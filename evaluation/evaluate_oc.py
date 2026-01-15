from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Dict, Tuple

from evaluation_utils import iter_token_elements


# =========================
# Data structures
# =========================


@dataclass
class AccuracyResult:
    correct: int
    total: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


@dataclass
class HierarchicalAccuracy:
    total: int
    correct_per_level: Dict[int, int]

    def accuracy_per_level(self) -> Dict[int, float]:
        return {
            lvl: (self.correct_per_level.get(lvl, 0) / self.total if self.total else 0.0)
            for lvl in range(1, 6)
        }


# =========================
# Helpers
# =========================


def _iter_job_id_pairs(xml_path: Path) -> Iterable[Tuple[str, str]]:
    """
    Yields (job_id_gt, job_id_pred) for each token where job_id_gt exists.
    If multiple predictions are present, only the first one is used.
    """
    for tok in iter_token_elements(xml_path):
        gt = tok.get("job_id_gt")
        if not gt:
            continue

        pred = tok.get("job_id_pred", "")

        # take first prediction if multiple are given
        pred_first = pred.split(",", 1)[0].strip() if pred else ""

        yield gt.strip(), pred_first


def _normalize_job_id(job_id: str) -> str:
    """
    Keeps digits only, truncates to max 5 digits.
    """
    digits = "".join(c for c in job_id if c.isdigit())
    return digits[:5]


# =========================
# Evaluation
# =========================

def evaluate_directory_oc(
    directory: Path,
    *,
    recursive: bool = True,
) -> Tuple[AccuracyResult, HierarchicalAccuracy]:
    """
    Token-level occupation coding evaluation.

    - Overall accuracy: exact 5-digit match
    - Hierarchical accuracy: prefix match for digits 1..5
    """
    files: Iterable[Path] = (
        directory.rglob("*.xml") if recursive else directory.glob("*.xml")
    )

    total = 0
    correct = 0
    correct_per_level: Dict[int, int] = {lvl: 0 for lvl in range(1, 6)}

    for xml_path in sorted(files):
        for gt_raw, pred_raw in _iter_job_id_pairs(xml_path):
            gt = _normalize_job_id(gt_raw)
            pred = _normalize_job_id(pred_raw)

            if not gt:
                continue

            total += 1

            if gt == pred:
                correct += 1

            for lvl in range(1, 6):
                if gt[:lvl] and pred[:lvl] and gt[:lvl] == pred[:lvl]:
                    correct_per_level[lvl] += 1

    acc = AccuracyResult(correct=correct, total=total)
    hier = HierarchicalAccuracy(total=total, correct_per_level=correct_per_level)

    return acc, hier


# =========================
# CLI
# =========================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python evaluate_oc.py <directory>")
        sys.exit(2)

    eval_dir = Path(sys.argv[1])

    acc, hier = evaluate_directory_oc(eval_dir)

    print(f"Overall accuracy: {acc.accuracy:.4f} ({acc.correct}/{acc.total})")
    print("Hierarchical accuracy:")
    for lvl, score in hier.accuracy_per_level().items():
        print(f"  Digit {lvl}: {score:.4f}")
