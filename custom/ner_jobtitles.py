"""
Named Entity Recognition (NER) for Job Titles in PAGE-XML files.
"""

import os
import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv

from logger import logger
from ner.ner import recognize_entities, load_model_and_tokenizer
from page_xml_utils import iter_pagexml_files, load_words_from_pagexml, write_labels_to_pagexml
from utility import getenv_bool

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"  # parent of this file
load_dotenv(ENV_PATH, override=True)

MODEL_DIR = os.getenv("MODEL_DIR", os.path.join(os.path.dirname(__file__), "models", "ner_model"))


def model_dir_is_valid(model_dir: Path) -> bool:
    """ Check whether model directory exists and is not empty. """
    if model_dir is None:
        logger.warning("""
            No NER model available. Skipping NER.
            If you want to apply NER, please download a pre-trained model and save it to MODEL_DIR.
            You can specify the path MODEL_DIR="..." in a .env file.
            """)
        return False

    if not model_dir.exists():
        logger.warning(f"NER model directory does not exist: {model_dir}")
        return False

    if not model_dir.is_dir():
        logger.warning(f"NER model path is not a directory: {model_dir}")
        return False

    if not any(model_dir.iterdir()):
        logger.warning(f"NER model directory is empty: {model_dir}")
        return False

    return True


def filter_and_normalize_bio(labels: List[str], target_entity: str = "JOB_TITLE", mode: str = "fix", ) -> List[str]:
    """
    - Keeps only BIO tags for `target_entity` (everything else becomes "O")
    - Repairs or discards invalid "I-" starts

    Args:
        labels: List of BIO labels
        target_entity: The entity type to keep (e.g. "JOB_TITLE")
        mode: "fix" to repair invalid I-starts, "discard" to drop invalid spans

    Returns:
        List of filtered and normalized BIO labels
    """
    assert mode in ("fix", "discard"), "mode must be 'fix' or 'discard'"

    B = f"B-{target_entity}"
    I = f"I-{target_entity}"

    # 1) Map non-target tags to O
    mapped = []
    for lab in labels:
        if lab == B or lab == I:
            mapped.append(lab)
        else:
            mapped.append("O")

    # 2) Normalize BIO consistency for the target
    out: List[str] = []
    prev = "O"
    discarding = False  # used for mode="discard"

    for lab in mapped:
        if mode == "discard":
            if discarding:
                # stop discarding once the predicted span ends
                if lab != I:
                    discarding = False
                else:
                    out.append("O")
                    prev = "O"
                    continue

        if lab == I and prev not in (B, I):
            # invalid I-start
            if mode == "fix":
                out.append(B)
                prev = B
            else:  # discard
                out.append("O")
                prev = "O"
                discarding = True
            continue

        out.append(lab)
        prev = lab

    return out


# ---------------------------------------------------------
# Main NER logic
# ---------------------------------------------------------
def main(project_dir: str) -> None:
    """
    Main function to run NER on PAGE-XML files in the specified project directory.
    :param project_dir: Project directory.
    """
    project_dir = Path(project_dir)

    logger.info(f"Starting job title NER for project: {project_dir}")

    if MODEL_DIR is None or not model_dir_is_valid(Path(MODEL_DIR)):
        os.environ["SKIPPED_NER"] = "true"
        logger.warning("NER skipped - model not available.")

    try:
        logger.info(f"Loading NER model from {MODEL_DIR}")
        model, tokenizer, params = load_model_and_tokenizer(str(MODEL_DIR))
    except Exception:
        os.environ["SKIPPED_NER"] = "true"
        logger.error("Failed to load NER model. Skipping NER.")

    pagexml_files = list(iter_pagexml_files(project_dir))
    if not pagexml_files:
        logger.warning("No PAGE-XML files found – skipping NER.")
        return

    skipped_ner = getenv_bool("SKIPPED_NER", False)

    for xml_path in pagexml_files:
        # Skip files that are already .ner.xml or .oc.xml to avoid double processing
        if xml_path.stem.endswith('.ner') or xml_path.stem.endswith('.oc'):
            continue

        ner_xml_path = xml_path.parent / f"{xml_path.stem}.ner.xml"

        try:
            tree, word_elements, words, ns = load_words_from_pagexml(xml_path)
            if not words:
                logger.info(f"No words in {xml_path}, skipping.")
                continue

            if skipped_ner:
                tree.write(ner_xml_path, encoding="utf-8", xml_declaration=True)
                continue

            labels = recognize_entities(model, tokenizer, params, words)

            labels = filter_and_normalize_bio(labels, target_entity="JOB_TITLE", mode="fix")
            for label in labels:
                assert label in ("O", "B-JOB_TITLE", "I-JOB_TITLE")

            write_labels_to_pagexml(word_elements, labels)

            # Save with .ner.xml suffix instead of overwriting original
            tree.write(ner_xml_path, encoding="utf-8", xml_declaration=True)
            logger.info(f"NER-annotated PAGE-XML written: {ner_xml_path}")

        except Exception:
            logger.exception(f"Failed processing PAGE-XML: {xml_path}")


if __name__ == "__main__":
    main(sys.argv[1])
