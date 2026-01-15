from pathlib import Path
from typing import Iterable

from evaluation_utils import (
    MicroPRF,
    load_token_level_entities,
    score_token_micro,
)


def evaluate_directory_ner_micro(directory: Path, *, recursive: bool = True) -> MicroPRF:
    """
    Evaluates all XML files in a directory (token-level micro P/R/F1).
    """
    tp = fp = fn = 0

    files: Iterable[Path] = (
        directory.rglob("*.xml") if recursive else directory.glob("*.xml")
    )

    for xml_path in sorted(files):
        gt, pred = load_token_level_entities(xml_path)
        scores = score_token_micro(gt, pred)

        tp += scores.tp
        fp += scores.fp
        fn += scores.fn

    return MicroPRF(tp=tp, fp=fp, fn=fn)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python evaluate_ner.py <directory>")
        sys.exit(2)

    eval_dir = Path(sys.argv[1])

    scores = evaluate_directory_ner_micro(eval_dir)

    print(f"TP={scores.tp} FP={scores.fp} FN={scores.fn}")
    print(f"Precision={scores.precision:.4f}")
    print(f"Recall={scores.recall:.4f}")
    print(f"F1={scores.f1:.4f}")
