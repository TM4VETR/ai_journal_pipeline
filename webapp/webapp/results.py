import json
import os
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Any

# Base where runner creates per-doc OCR4all projects
DATA_ROOT = os.environ.get("OCR4ALL_DATA_ROOT", "/var/ocr4all/data")


def get_results(doc_id: str) -> List[Dict[str, str]]:
    """
    Return OCR results for a specific document project.

    Expected structure:
      /var/ocr4all/data/<doc_id>/processing/{page.png,page.txt,page.xml}
      After NER: {page.ner.xml}
      After OC: {page.oc.xml}
    """

    doc_id = (doc_id or "").strip()
    if not doc_id:
        return [], []

    # Basic safety: doc_id should be "slug-like"
    if not re.fullmatch(r"[a-z0-9_-]+", doc_id):
        return [], []

    output_root = os.path.join(DATA_ROOT, doc_id, "processing")
    if not os.path.exists(output_root):
        return [], []

    images = []
    xmls = []

    for root, dirs, files in os.walk(output_root):
        for f in files:
            filepath = os.path.join("/data", doc_id, "processing", f)
            if f.lower().endswith(".bin.png"):
                images.append(filepath)
            elif f.lower().endswith(".xml"):
                # Prefer .oc.xml > .ner.xml > .xml
                # Only add the most processed version of each base file
                if f.endswith(".oc.xml"):
                    xmls.append(filepath)
                elif f.endswith(".ner.xml"):
                    # Check if .oc.xml exists for this base
                    oc_version = f[:-8] + ".oc.xml"
                    if oc_version not in files:
                        xmls.append(filepath)
                else:
                    # Original .xml - only add if no .ner.xml or .oc.xml exists
                    ner_version = f[:-4] + ".ner.xml"
                    oc_version = f[:-4] + ".oc.xml"
                    if ner_version not in files and oc_version not in files:
                        xmls.append(filepath)

    return images, xmls


def get_results_json(doc_id: str) -> Dict[str, List[Dict[str, str]]]:
    """
    Load results.json:
    """
    doc_id = (doc_id or "").strip()
    if not doc_id or not re.fullmatch(r"[a-z0-9_-]+", doc_id):
        return {}

    results_path = os.path.join(DATA_ROOT, doc_id, "results.json")
    if not os.path.exists(results_path):
        return {}

    try:
        with open(results_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}




def extract_entities_from_pagexml(xml_path: str) -> List[Dict[str, str]]:
    """
    Extract job title entities from PAGE-XML 'custom' attributes.
    Returns list of entities with their text and label.
    """
    entities = []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Find all Word elements
        word_elements = root.findall(".//{*}Word")

        current_entity = []
        current_label = None

        for word_el in word_elements:
            # Get word text
            unicode_el = word_el.find(".//{*}TextEquiv/{*}Unicode")
            word_text = unicode_el.text.strip() if unicode_el is not None and unicode_el.text else ""

            if not word_text:
                continue

            # Check custom attribute for entity labels
            custom = word_el.get("custom", "")
            entity_label = None

            # Parse custom field for ENTITY label
            # Format: "ENTITY: B-JOB_TITLE" or "ENTITY: I-JOB_TITLE"
            match = re.search(r'ENTITY:\s*([BI]-\w+)', custom)
            if match:
                entity_label = match.group(1)

            # Handle entity spans
            if entity_label and entity_label.startswith("B-"):
                # Save previous entity if exists
                if current_entity:
                    entities.append({
                        "text": " ".join(current_entity),
                        "label": current_label
                    })
                # Start new entity
                current_entity = [word_text]
                current_label = entity_label[2:]  # Remove "B-" prefix
            elif entity_label and entity_label.startswith("I-"):
                # Continue current entity
                if current_entity:
                    current_entity.append(word_text)
            else:
                # No entity or "O" label - save previous entity if exists
                if current_entity:
                    entities.append({
                        "text": " ".join(current_entity),
                        "label": current_label
                    })
                    current_entity = []
                    current_label = None

        # Don't forget the last entity
        if current_entity:
            entities.append({
                "text": " ".join(current_entity),
                "label": current_label
            })

    except Exception:
        # Return empty list on error
        pass

    return entities



