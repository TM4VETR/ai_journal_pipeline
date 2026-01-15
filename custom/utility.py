"""
Utility functions for environment variable handling.
"""
import os
import re

import unicodedata

UMLAUT_MAP = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
    "ß": "ss",
})


def getenv_bool(name: str, default: bool = False) -> bool:
    """
    Get a boolean environment variable.
    :param name: Name of the environment variable.
    :param default: Default value.
    :return: Boolean value of the environment variable.
    """
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes", "on")


def replace_special_chars(text: str) -> str:
    """
    Normalize text:
    - replace German umlauts
    - remove all other non-ASCII characters
    - collapse whitespace

    Args:
        text (str): Input text.
    Returns:
        str: Normalized text.
    """

    if not text:
        return ""

    # 1. Replace umlauts explicitly
    text = text.translate(UMLAUT_MAP)

    # 2. Normalize unicode → decomposed form
    text = unicodedata.normalize("NFKD", text)

    # 3. Remove remaining non-ASCII characters
    text = text.encode("ascii", "ignore").decode("ascii")

    # 4. Remove special characters except word chars and spaces
    text = re.sub(r"[^\w\s\-]", " ", text)

    # 5. Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def extract_page_number(filepath: str) -> int:
    """
    Extract page number from filenames like '0016.oc.xml' → 16

    Args:
        filename (str): Filename to extract from.
    Returns:
        int: Extracted page number.
    """
    filename = os.path.basename(filepath)
    base = filename.split(".", 1)[0]
    return int(base) # int() removes leading zeros


def extract_doc_id(project_dir: str) -> str:
    """
    Given a project path ".../<doc_id>/processing", extract the document ID.
    Args:
        project_dir (str): Project directory path.
    Returns:
        str: Document ID.
    """
    project_dir = project_dir.replace("\\", "/")
    project_dir = project_dir.rstrip("/")

    if project_dir.endswith("/processing"):
        project_dir = os.path.dirname(project_dir)

    return os.path.basename(project_dir)
