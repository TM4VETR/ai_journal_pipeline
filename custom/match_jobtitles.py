"""
Occupation coding for job titles in PAGE-XML files.
"""

import json
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional, Tuple

from logger import logger
from page_xml_utils import iter_pagexml_files, load_words_from_pagexml, upsert_custom_field
from utility import getenv_bool, replace_special_chars, extract_page_number

# occupation coding
sys.path.append("oc")
from oc.occupation_coding import code_occupations

NA_STRING = "NA"
NA_VALUES = {"NA", "N/A", "NONE", "UNKNOWN", "NA_CHARACTER_", ""}


def _get_custom_field_value(custom: str) -> Optional[str]:
    """
    Extracts value from a custom field like:
      '<... custom="ENTITY: B-JOB_TITLE"> ...'
    """
    if not custom:
        return None
    custom_one_line = custom.replace("\n", " ")
    return custom_one_line


def _extract_jobtitle_spans(
        words: List[str],
        word_elements,
        target_entity: str = "JOB_TITLE",
):
    """
    Returns (spans, labels) where spans is list of (start_idx, end_idx_exclusive, surface_text)
    and labels is the token-level BIO list aligned with `words`.
    Robust to occasional BIO inconsistencies (I-start treated as new span).
    """
    b_ent = f"ENTITY: B-{target_entity}"
    i_ent = f"ENTITY: I-{target_entity}"

    labels: List[str] = []
    for w_el in word_elements:
        lab = _get_custom_field_value(w_el.get("custom", ""))
        lab = (lab or "").strip()

        if b_ent in lab:
            labels.append(f"B-{target_entity}")
        elif i_ent in lab:
            labels.append(f"I-{target_entity}")
        else:
            labels.append("O")

    spans: List[Tuple[int, int, str]] = []
    i = 0
    n = len(words)
    while i < n:
        lab = labels[i].strip()

        # Start span on B- or (robustly) on I-
        if lab == f"B-{target_entity}" or lab == f"I-{target_entity}":
            start = i
            i += 1
            while i < n and labels[i] == f"I-{target_entity}":
                i += 1
            end = i
            surface = " ".join(words[start:end]).strip()
            if surface:
                spans.append((start, end, surface))
            continue

        i += 1

    return spans, labels


def _write_job_ids_to_spans(
        word_elements,
        spans: List[Tuple[int, int, str]],
        job_ids: List[str],
        field_name: str = "job_id",
):
    """
    Writes job_id {value:<job_id>;} to each token in each span.
    """
    if len(spans) != len(job_ids):
        raise ValueError(f"Mismatch: {len(spans)} spans vs {len(job_ids)} job_ids")

    for (start, end, _surface), job_id in zip(spans, job_ids):
        if job_id != NA_STRING:
            for idx in range(start, end):
                w_el = word_elements[idx]
                old_custom = w_el.get("custom", "")
                w_el.set("custom", upsert_custom_field(old_custom, field_name, str(job_id)))


def _sanitize_for_json(obj):
    """
    Recursively convert R NA types into JSON-safe values.
    """
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]

    if isinstance(obj, tuple):
        return [_sanitize_for_json(v) for v in obj]

    if isinstance(obj, set):
        return [_sanitize_for_json(v) for v in obj]

    # Leaf values: try JSON serialization
    try:
        json.dumps(obj)
        return obj
    except TypeError as e:
        logger.warning(f"Could not serialize value to JSON: {obj} ({e})")
        return None


def _write_job_ids_to_json(job_ids: List[str], project_dir: Path):
    """
    Writes all job IDs found in a document to a JSON file.
    The JSON file is created in the project folder with the same name as the XML file.
    """
    json_filename = "job_ids.json"
    json_path = project_dir / json_filename

    # Remove NA values
    job_ids = {job_id for job_id in job_ids if job_id != NA_STRING}

    data = {
        "job_ids": job_ids
    }

    with open(json_path, "w", encoding="utf-8") as f:
        data_sanitized = _sanitize_for_json(data)
        json.dump(data_sanitized, f, indent=2, ensure_ascii=False)

    logger.info(f"Job IDs written to JSON: {json_path}")


def _write_results_to_json(results: dict, project_dir: Path):
    """
    Writes dict with results to a JSON file.
    """
    json_filename = "results.json"
    json_path = project_dir / json_filename

    with open(json_path, "w", encoding="utf-8") as f:
        results_sanitized = _sanitize_for_json(results)
        json.dump(results_sanitized, f, indent=2, ensure_ascii=False)

    logger.info(f"Results written to JSON: {json_path}")


def _write_simple_xml(
        page_number: str,
        tokens: List[str],
        labels: List[str],
        token_job_ids: List[str],
        project_dir: Path,
        job_title_gt: List[str] | None = None,
        job_id_gt: List[str] | None = None,
):
    """
    Writes a simplified XML file for one page:

    <tokens>
        <token job_title_pred="Schuster"
              job_title_gt=""
              job_id_pred="1234"
              job_id_gt="">Schuster</token>
        ...
    </tokens>
    """

    n = len(tokens)
    assert len(labels) == n
    assert len(token_job_ids) == n

    if job_title_gt is None:
        job_title_gt = [""] * n
    if job_id_gt is None:
        job_id_gt = [""] * n

    root = ET.Element("tokens")

    for tok, lab, jid_pred, lab_gt, jid_gt in zip(
            tokens, labels, token_job_ids, job_title_gt, job_id_gt
    ):
        el = ET.SubElement(root, "token")
        el.set("job_title_pred", lab)
        el.set("job_title_gt", lab_gt)
        el.set("job_id_pred", str(jid_pred) if jid_pred else "")
        el.set("job_id_gt", str(jid_gt) if jid_gt else "")
        el.text = tok

    tree = ET.ElementTree(root)

    xml_path = project_dir / "processing" / f"{page_number}.simple.xml"
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)

    return xml_path


def _replace_na_codes(code) -> str:
    """
    Replace various N/A codes with a standard NA_STRING.
    """
    try:
        if code is None:
            return NA_STRING

        if isinstance(code, str):
            if code.upper().strip() in NA_VALUES:
                return NA_STRING

        if isinstance(code, float) or isinstance(code, int):
            if code < 0:
                return NA_STRING

        if str(code).upper().strip() in NA_VALUES:
            return NA_STRING

        return code
    except Exception as e:
        logger.error(f"Error replacing NA codes for code '{code}': {e}")
        return code


def _expand_job_ids_to_tokens(
        num_tokens: int,
        spans,
        job_ids,
        na_string: str = "",
):
    """
    Returns a list of length num_tokens with job_id per token (or NA).
    """
    token_job_ids = [na_string] * num_tokens

    for (start, end, _), job_id in zip(spans, job_ids):
        for i in range(start, end):
            token_job_ids[i] = job_id

    return token_job_ids


def main(project_dir: str) -> None:
    """
    Main function to perform occupation coding on PAGE-XML files in the given project directory.
    :param project_dir: Project directory.
    """
    project_dir = Path(project_dir)
    logger.info(f"Starting occupation coding for project: {project_dir}")

    pagexml_files = list(iter_pagexml_files(project_dir))
    if not pagexml_files:
        logger.warning("No PAGE-XML files found – skipping occupation coding.")
        return

    results = {}
    all_job_ids = set()

    for xml_path in pagexml_files:
        # Skip files that are already .ner.xml or .oc.xml to avoid double processing
        if xml_path.stem.endswith('.ner') or xml_path.stem.endswith('.oc'):
            continue

        page_number = str(extract_page_number(str(xml_path)))
        results[page_number] = []

        # Look for .ner.xml file first (output from NER step)
        ner_xml_path = xml_path.parent / f"{xml_path.stem}.ner.xml"
        if ner_xml_path.exists():
            input_xml_path = ner_xml_path
        else:
            # Fall back to original XML if .ner.xml doesn't exist
            input_xml_path = xml_path

        try:
            tree, word_elements, words, ns = load_words_from_pagexml(input_xml_path)
            if not words:
                logger.info(f"No words in {input_xml_path}, skipping.")
                continue

            skipped_ner = getenv_bool("SKIPPED_NER", False)
            if skipped_ner:
                # Run occupation coding on all words
                spans = [(i, i + 1, words[i]) for i in range(len(words))]
                labels = ["O"] * len(words)
            else:
                spans, labels = _extract_jobtitle_spans(
                    words,
                    word_elements,
                    target_entity="JOB_TITLE",
                )

                if not spans:
                    #logger.info(f"No JOB_TITLE spans found in {input_xml_path}, skipping.")
                    continue

            occupations = [replace_special_chars(s[2]) for s in spans]

            try:
                logger.info("Calling code_occupations() with %d occupations", len(occupations))
                df_results = code_occupations(occupations)
                logger.info("Occupation coding finished")

                # Replace N/A codes with NA_STRING
                df_results["pred.code"] = df_results["pred.code"].apply(_replace_na_codes)

                job_ids = df_results["pred.code"].fillna(NA_STRING).tolist()

                token_job_ids = _expand_job_ids_to_tokens(
                    num_tokens=len(words),
                    spans=spans,
                    job_ids=job_ids,
                    na_string="",
                )

                # Write simplified XML
                _write_simple_xml(
                    page_number=page_number,
                    tokens=words,
                    labels=labels,
                    token_job_ids=token_job_ids,
                    project_dir=project_dir,
                )

                # Store results for this page
                for i, occupation in enumerate(occupations):
                    results[page_number].append({
                        "job_title": occupation,
                        "job_id": job_ids[i],
                    })
            except Exception as e:
                logger.error(f"Occupation coding failed for {input_xml_path}: {e}")
                job_ids = [NA_STRING] * len(spans)

            # If multiple job_ids found: Take first one
            for i in range(len(job_ids)):
                job_id = job_ids[i]
                if "," in str(job_id):
                    job_ids[i] = str(job_id).split(",")[0].strip()

            _write_job_ids_to_spans(
                word_elements,
                spans,
                job_ids,
                field_name="job_id",
            )

            # Save with .oc.xml suffix instead of overwriting
            oc_xml_path = xml_path.parent / f"{xml_path.stem}.oc.xml"
            tree.write(oc_xml_path, encoding="utf-8", xml_declaration=True)
            logger.info(f"Occupation-coded PAGE-XML written: {oc_xml_path}")

            all_job_ids.update(job_ids)

        except Exception as e:
            logger.error(f"Failed processing PAGE-XML: {input_xml_path}\n{e}")
            traceback.print_exc()

    # Write job IDs to JSON file
    try:
        results = dict(
            sorted(results.items(), key=lambda x: int(x[0]))
        )

        _write_results_to_json(results, project_dir)
        _write_job_ids_to_json(all_job_ids, project_dir)
    except (IOError, OSError, PermissionError) as e:
        logger.error(f"Failed to write JSON file with all job titles: {e}")


if __name__ == "__main__":
    main(sys.argv[1])
