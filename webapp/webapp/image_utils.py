"""
Utility functions for cropping images based on PAGE XML bounding boxes.
"""
import os
import re
import xml.etree.ElementTree as ET
from typing import List, Tuple, Dict, Optional

from PIL import Image, ImageDraw


def generate_ner_cropped_images(doc_id: str, images: list, xmls: list) -> list:
    """
    Generate cropped images for all JOB_TITLE entities found in the XMLs.
    Returns list of paths to cropped images.
    """
    ner_images = []

    # Get the data root for the document
    data_root = os.environ.get("OCR4ALL_DATA_ROOT", "/var/ocr4all/data")
    processing_dir = os.path.join(data_root, doc_id, "processing")

    # Create directory for cropped NER images
    ner_crops_dir = os.path.join(data_root, doc_id, "ner_crops")
    os.makedirs(ner_crops_dir, exist_ok=True)

    # Process each XML file
    for xml_path in xmls:
        # Get the page name (e.g., "0001" from "/data/doc_id/processing/0001.xml" or "0001.ner.xml" or "0001.oc.xml")
        xml_basename = os.path.basename(xml_path)
        page_name = extract_page_name_from_xml(xml_basename)

        # Find corresponding image
        image_name = f"{page_name}.bin.png"
        image_path = os.path.join(processing_dir, image_name)

        if not os.path.exists(image_path):
            continue

        # Convert web path to filesystem path
        xml_fs_path = xml_path.replace("/data", data_root)

        # Extract JOB_TITLE entities with bounding boxes
        entities = extract_entities_with_bboxes(xml_fs_path, entity_type="JOB_TITLE")

        # Crop and save each entity
        for idx, entity in enumerate(entities):
            bbox = entity.get("bbox")
            if not bbox:
                continue

            # Generate output filename with sanitized entity text
            entity_text = sanitize_filename(entity.get("text", ""))
            output_name = f"{page_name}_ner_{idx:02d}_{entity_text}.png"
            output_path = os.path.join(ner_crops_dir, output_name)

            # Crop the image
            success = crop_image_with_bbox(
                image_path,
                bbox,
                output_path,
                margin=10,
                border_width=2,
                border_color="blue"
            )

            if success:
                # Store the web-accessible path
                web_path = os.path.join("/data", doc_id, "ner_crops", output_name)
                ner_images.append(web_path)

    return ner_images


def generate_occupation_cropped_images(doc_id: str, images: list, xmls: list) -> list:
    """
    Generate cropped images for all JOB_ID (occupation_id) entities found in the XMLs.
    Returns list of paths to cropped images.
    """
    occupation_images = []

    # Get the data root for the document
    data_root = os.environ.get("OCR4ALL_DATA_ROOT", "/var/ocr4all/data")
    processing_dir = os.path.join(data_root, doc_id, "processing")

    # Create directory for cropped occupation images
    occupation_crops_dir = os.path.join(data_root, doc_id, "occupation_crops")
    os.makedirs(occupation_crops_dir, exist_ok=True)

    # Process each XML file
    for xml_path in xmls:
        # Get the page name (e.g., "0001" from "/data/doc_id/processing/0001.xml" or "0001.ner.xml" or "0001.oc.xml")
        xml_basename = os.path.basename(xml_path)
        page_name = extract_page_name_from_xml(xml_basename)

        # Find corresponding image
        image_name = f"{page_name}.bin.png"
        image_path = os.path.join(processing_dir, image_name)

        if not os.path.exists(image_path):
            continue

        # Convert web path to filesystem path
        xml_fs_path = xml_path.replace("/data", data_root)

        # Extract occupation IDs with bounding boxes
        job_spans = extract_occupation_ids_with_bboxes(xml_fs_path)

        # Crop and save each span
        for idx, span in enumerate(job_spans):
            bbox = span.get("bbox")
            job_id = span.get("job_id", "unknown")

            if not bbox:
                continue

            # Generate output filename with sanitized entity text
            entity_text = sanitize_filename(span.get("text", ""))
            output_name = f"{page_name}_job_{job_id}_{idx:02d}_{entity_text}.png"
            output_path = os.path.join(occupation_crops_dir, output_name)

            # Crop the image
            success = crop_image_with_bbox(
                image_path,
                bbox,
                output_path,
                margin=10,
                border_width=2,
                border_color="green"
            )

            if success:
                # Store the web-accessible path
                web_path = os.path.join("/data", doc_id, "occupation_crops", output_name)
                occupation_images.append(web_path)

    return occupation_images


def _detect_page_ns(root: ET.Element) -> dict:
    """
    Detect PAGE namespace from root tag.
    Returns dict usable in ElementTree find/findall: {"pc": "<uri>"}.
    """
    if root.tag.startswith("{") and "}" in root.tag:
        uri = root.tag.split("}", 1)[0][1:]
        return {"pc": uri}
    return {"pc": ""}


def parse_coords(coords_str: str) -> List[Tuple[int, int]]:
    """
    Parse PAGE XML Coords points attribute.
    Format: "x1,y1 x2,y2 x3,y3 ..."
    Returns list of (x, y) tuples.
    """
    points = []
    if not coords_str:
        return points

    for point in coords_str.strip().split():
        if ',' in point:
            x, y = point.split(',')
            points.append((int(x), int(y)))

    return points


def get_bounding_box(points: List[Tuple[int, int]]) -> Tuple[int, int, int, int]:
    """
    Get bounding box (min_x, min_y, max_x, max_y) from list of points.
    """
    if not points:
        return (0, 0, 0, 0)

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    return (min(xs), min(ys), max(xs), max(ys))


def merge_bounding_boxes(boxes: List[Tuple[int, int, int, int]]) -> Tuple[int, int, int, int]:
    """
    Merge multiple bounding boxes into one encompassing box.
    Each box is (min_x, min_y, max_x, max_y).
    """
    if not boxes:
        return (0, 0, 0, 0)

    min_x = min(box[0] for box in boxes)
    min_y = min(box[1] for box in boxes)
    max_x = max(box[2] for box in boxes)
    max_y = max(box[3] for box in boxes)

    return (min_x, min_y, max_x, max_y)


def crop_image_with_bbox(
        image_path: str,
        bbox: Tuple[int, int, int, int],
        output_path: str,
        margin: int = 10,
        border_width: int = 2,
        border_color: str = "red"
) -> bool:
    """
    Crop an image based on bounding box with margin and border overlay.
    
    Args:
        image_path: Path to input image
        bbox: Bounding box as (min_x, min_y, max_x, max_y)
        output_path: Path to save cropped image
        margin: Pixels to add around the bounding box
        border_width: Width of the border overlay
        border_color: Color of the border overlay
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Load image
        img = Image.open(image_path)

        # Extract bbox coordinates
        min_x, min_y, max_x, max_y = bbox

        # Add margin (ensure within image bounds)
        crop_x1 = max(0, min_x - margin)
        crop_y1 = max(0, min_y - margin)
        crop_x2 = min(img.width, max_x + margin)
        crop_y2 = min(img.height, max_y + margin)

        # Crop the image
        cropped = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))

        # Draw border overlay around the actual bounding box (relative to cropped image)
        draw = ImageDraw.Draw(cropped)

        # Calculate border position in cropped image coordinates
        border_x1 = min_x - crop_x1
        border_y1 = min_y - crop_y1
        border_x2 = max_x - crop_x1
        border_y2 = max_y - crop_y1

        # Draw rectangle border
        for i in range(border_width):
            draw.rectangle(
                [border_x1 + i, border_y1 + i, border_x2 - i, border_y2 - i],
                outline=border_color
            )

        # Save cropped image
        cropped.save(output_path)

        return True

    except Exception as e:
        print(f"Error cropping image: {e}")
        return False


def extract_word_bboxes_from_xml(
        xml_path: str,
        word_indices: List[int]
) -> Optional[Tuple[int, int, int, int]]:
    """
    Extract and merge bounding boxes for specific word indices from PAGE XML.
    
    Args:
        xml_path: Path to PAGE XML file
        word_indices: List of word indices (0-based) to extract bounding boxes for
    
    Returns:
        Merged bounding box as (min_x, min_y, max_x, max_y) or None if not found
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = _detect_page_ns(root)

        # Find all Word elements
        word_elements = root.findall(".//pc:Word", ns) if ns["pc"] else root.findall(".//Word")

        boxes = []
        for idx in word_indices:
            if idx < len(word_elements):
                word_el = word_elements[idx]

                # Find Coords element
                coords_el = word_el.find("./pc:Coords", ns) if ns["pc"] else word_el.find("./Coords")

                if coords_el is not None:
                    points_str = coords_el.get("points", "")
                    points = parse_coords(points_str)

                    if points:
                        bbox = get_bounding_box(points)
                        boxes.append(bbox)

        if boxes:
            return merge_bounding_boxes(boxes)

        return None

    except Exception as e:
        print(f"Error extracting bounding boxes from XML: {e}")
        return None


def get_entity_from_custom_field(custom: str, key: str) -> Optional[str]:
    """
    Extract entity label from PAGE XML custom field.
    Example: "ENTITY: B-JOB_TITLE" or "occupation_id {value:1234;}"
    """
    if not custom:
        return None

    custom_one_line = custom.replace("\n", " ")

    # Try ENTITY format first (for NER labels)
    m = re.search(r'ENTITY:\s*([BI]-\w+)', custom_one_line)
    if m:
        return m.group(1)

    # Try key-value format (for occupation IDs)
    m = re.search(rf"\b{re.escape(key)}\b\s*\{{([^}}]*)\}}", custom_one_line)
    if m:
        inner = m.group(1)
        m2 = re.search(r"\bvalue\s*:\s*([^;]+)\s*;", inner)
        if m2:
            return m2.group(1).strip()

    return None


def extract_entities_with_bboxes(
        xml_path: str,
        entity_type: str = "JOB_TITLE",
        custom_key: str = "ENTITY"
) -> List[Dict]:
    """
    Extract entities with their bounding boxes from PAGE XML.
    Merges multi-word entities (B-entity followed by I-entity tokens).
    
    Args:
        xml_path: Path to PAGE XML file
        entity_type: Type of entity to extract (e.g., "JOB_TITLE")
        custom_key: Key to look for in custom attribute
    
    Returns:
        List of dicts with keys: text, label, word_indices, bbox
    """
    entities = []

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = _detect_page_ns(root)

        # Find all Word elements
        word_elements = root.findall(".//pc:Word", ns) if ns["pc"] else root.findall(".//Word")

        current_entity_words = []
        current_entity_indices = []
        current_label = None

        for idx, word_el in enumerate(word_elements):
            # Get word text
            unicode_el = word_el.find("./pc:TextEquiv/pc:Unicode", ns) if ns["pc"] else word_el.find(".//Unicode")
            word_text = unicode_el.text.strip() if unicode_el is not None and unicode_el.text else ""

            # Get entity label from custom attribute
            custom = word_el.get("custom", "")
            entity_label = get_entity_from_custom_field(custom, custom_key)

            # Process entity labels
            if entity_label and entity_label.startswith("B-"):
                # Save previous entity if exists
                if current_entity_words:
                    bbox = extract_word_bboxes_from_xml(xml_path, current_entity_indices)
                    if bbox:
                        entities.append({
                            "text": " ".join(current_entity_words),
                            "label": current_label,
                            "word_indices": current_entity_indices[:],
                            "bbox": bbox
                        })

                # Start new entity
                entity_name = entity_label[2:]  # Remove "B-" prefix
                if entity_name == entity_type:
                    current_entity_words = [word_text] if word_text else []
                    current_entity_indices = [idx]
                    current_label = entity_name
                else:
                    current_entity_words = []
                    current_entity_indices = []
                    current_label = None

            elif entity_label and entity_label.startswith("I-"):
                # Continue current entity
                entity_name = entity_label[2:]  # Remove "I-" prefix
                if entity_name == entity_type and current_entity_words:
                    if word_text:
                        current_entity_words.append(word_text)
                    current_entity_indices.append(idx)
            else:
                # No entity or different entity - save previous if exists
                if current_entity_words:
                    bbox = extract_word_bboxes_from_xml(xml_path, current_entity_indices)
                    if bbox:
                        entities.append({
                            "text": " ".join(current_entity_words),
                            "label": current_label,
                            "word_indices": current_entity_indices[:],
                            "bbox": bbox
                        })
                current_entity_words = []
                current_entity_indices = []
                current_label = None

        # Don't forget the last entity
        if current_entity_words:
            bbox = extract_word_bboxes_from_xml(xml_path, current_entity_indices)
            if bbox:
                entities.append({
                    "text": " ".join(current_entity_words),
                    "label": current_label,
                    "word_indices": current_entity_indices[:],
                    "bbox": bbox
                })

    except Exception as e:
        print(f"Error extracting entities from XML: {e}")

    return entities


def extract_occupation_ids_with_bboxes(xml_path: str) -> List[Dict]:
    """
    Extract occupation IDs with their bounding boxes from PAGE XML.
    Looks for "occupation_id" or "job_id" in custom fields.
    
    Returns:
        List of dicts with keys: text, job_id, word_indices, bbox
    """
    job_spans = []

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = _detect_page_ns(root)

        # Find all Word elements
        word_elements = root.findall(".//pc:Word", ns) if ns["pc"] else root.findall(".//Word")

        current_job_id = None
        current_words = []
        current_indices = []

        for idx, word_el in enumerate(word_elements):
            # Get word text
            unicode_el = word_el.find("./pc:TextEquiv/pc:Unicode", ns) if ns["pc"] else word_el.find(".//Unicode")
            word_text = unicode_el.text.strip() if unicode_el is not None and unicode_el.text else ""

            # Get occupation_id from custom attribute
            custom = word_el.get("custom", "")
            job_id = get_entity_from_custom_field(custom, "occupation_id")
            if not job_id:
                job_id = get_entity_from_custom_field(custom, "job_id")

            if job_id:
                if job_id == current_job_id:
                    # Continue current span
                    if word_text:
                        current_words.append(word_text)
                    current_indices.append(idx)
                else:
                    # Save previous span if exists
                    if current_words and current_job_id:
                        bbox = extract_word_bboxes_from_xml(xml_path, current_indices)
                        if bbox:
                            job_spans.append({
                                "text": " ".join(current_words),
                                "job_id": current_job_id,
                                "word_indices": current_indices[:],
                                "bbox": bbox
                            })

                    # Start new span
                    current_job_id = job_id
                    current_words = [word_text] if word_text else []
                    current_indices = [idx]
            else:
                # No job_id - save previous span if exists
                if current_words and current_job_id:
                    bbox = extract_word_bboxes_from_xml(xml_path, current_indices)
                    if bbox:
                        job_spans.append({
                            "text": " ".join(current_words),
                            "job_id": current_job_id,
                            "word_indices": current_indices[:],
                            "bbox": bbox
                        })
                current_job_id = None
                current_words = []
                current_indices = []

        # Don't forget the last span
        if current_words and current_job_id:
            bbox = extract_word_bboxes_from_xml(xml_path, current_indices)
            if bbox:
                job_spans.append({
                    "text": " ".join(current_words),
                    "job_id": current_job_id,
                    "word_indices": current_indices[:],
                    "bbox": bbox
                })

    except Exception as e:
        print(f"Error extracting occupation IDs from XML: {e}")

    return job_spans
