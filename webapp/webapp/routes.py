import json
import os
import re
from datetime import datetime
from pathlib import Path

from PIL import Image
from flask import Blueprint, render_template, request, redirect, url_for, session, send_from_directory
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from webapp.results import get_results, get_results_json


# Create a Flask Blueprint for routes
bp = Blueprint("routes", __name__)

# OCR4All input path (must match the mounted volume path inside the container)
OCR4ALL_INPUT = os.environ.get("OCR4ALL_INPUT_DIR", "/var/ocr4all/data/default/input")
os.makedirs(OCR4ALL_INPUT, exist_ok=True)

# File upload constraints
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB in bytes
ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.bmp'}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp'}


@bp.route("/")
def index():
    return redirect(url_for("routes.upload"))


@bp.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        return render_template("upload.html")

    uploaded_file = request.files.get("file")
    if not uploaded_file:
        return "No file uploaded", 400

    # Validate file has a name
    original_name = secure_filename(uploaded_file.filename or "")
    if not original_name:
        return "Invalid filename", 400

    # Get file extension
    file_ext = os.path.splitext(original_name)[1].lower()

    # Validate file format
    if file_ext not in ALLOWED_EXTENSIONS:
        return f"Unsupported file format. Please upload PDF, PNG, JPG, or BMP files.", 400

    # Check file size
    uploaded_file.seek(0, os.SEEK_END)
    file_size = uploaded_file.tell()
    uploaded_file.seek(0)  # Reset file pointer

    if file_size > MAX_FILE_SIZE:
        return f"File size exceeds maximum allowed size of 100 MB", 400

    doc_id = upload_and_process(uploaded_file)

    # Redirect to results
    return redirect(url_for("routes.results", id=doc_id))


def convert_image_to_pdf(image_path: Path, pdf_path: Path) -> None:
    """Convert an image file (PNG, JPG, BMP) to PDF format."""
    try:
        # Open the image
        image = Image.open(image_path)

        # Convert to RGB if necessary (PDF requires RGB)
        if image.mode in ('RGBA', 'LA', 'P'):
            # Create a white background
            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
            # Convert palette mode to RGBA first
            if image.mode == 'P':
                image = image.convert('RGBA')
            # Paste image with transparency
            if image.mode in ('RGBA', 'LA'):
                rgb_image.paste(image, mask=image.split()[-1])  # Use alpha channel as mask
            else:
                rgb_image.paste(image)
            image = rgb_image
        elif image.mode != 'RGB':
            image = image.convert('RGB')

        # Save as PDF with higher resolution for better quality
        image.save(pdf_path, 'PDF', resolution=200.0)

    except Exception as e:
        raise RuntimeError(f"Failed to convert image to PDF: {str(e)}")


def upload_and_process(uploaded_file: FileStorage) -> str:
    title = (request.form.get("title") or "").strip()
    year_raw = (request.form.get("year") or "").strip()
    doc_type = (request.form.get("type") or "").strip()

    # Calculate doc_id
    original_name = secure_filename(uploaded_file.filename or "upload.pdf")
    base = os.path.splitext(original_name)[0]
    file_ext = os.path.splitext(original_name)[1].lower()
    doc_id = re.sub(r"[^a-zA-Z0-9_-]", "_", base.lower()).strip("_")
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    doc_id = f"{doc_id}_{timestamp}"

    input_dir = Path(OCR4ALL_INPUT)
    input_dir.mkdir(parents=True, exist_ok=True)

    # Determine if we need to convert image to PDF
    is_image = file_ext in IMAGE_EXTENSIONS

    if is_image:
        # Save the uploaded image temporarily
        temp_image_path = input_dir / f"{doc_id}_temp{file_ext}"
        uploaded_file.save(str(temp_image_path))

        # Convert to PDF
        stored_filename = f"{doc_id}_{base}.pdf"
        pdf_path = input_dir / stored_filename
        convert_image_to_pdf(temp_image_path, pdf_path)

        # Remove temporary image file
        temp_image_path.unlink()
    else:
        # Save PDF directly
        stored_filename = f"{doc_id}.pdf"
        pdf_path = input_dir / stored_filename
        uploaded_file.save(str(pdf_path))

    year = int(year_raw) if re.fullmatch(r"\d{4}", year_raw) else None

    # Save metadata JSON (write atomically)
    meta = {
        "id": doc_id,
        "title": title,
        "year": year,
        "type": doc_type,
        "uploaded_at": datetime.utcnow().isoformat(),
        "filename": stored_filename,
        "original_filename": uploaded_file.filename,
    }

    meta_path = input_dir / f"{doc_id}.meta.json"
    tmp_meta = input_dir / f"{doc_id}.meta.json.tmp"
    tmp_meta.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_meta, meta_path)

    # Save ready marker LAST (write atomically)
    ready_path = input_dir / f"{doc_id}.ready"
    tmp_ready = input_dir / f"{doc_id}.ready.tmp"
    tmp_ready.write_text("1", encoding="utf-8")
    os.replace(tmp_ready, ready_path)

    session["doc_id"] = doc_id
    return doc_id


def sanitize_filename(text: str, max_length: int = 30) -> str:
    """
    Sanitize text to be safe for use in filenames.
    Removes special characters and limits length.
    """
    # Replace spaces with underscores
    text = text.replace(" ", "_")
    # Keep only alphanumeric, underscores, and hyphens
    text = re.sub(r'[^a-zA-Z0-9_-]', '', text)
    # Limit length
    return text[:max_length]


def extract_page_name_from_xml(xml_basename: str) -> str:
    """
    Extract the base page name from an XML filename.
    Handles .xml, .ner.xml, and .oc.xml suffixes.
    
    Examples:
        "0001.xml" -> "0001"
        "0001.ner.xml" -> "0001"
        "0001.oc.xml" -> "0001"
    """
    page_name = xml_basename
    if page_name.endswith(".oc.xml"):
        return page_name[:-7]  # Remove .oc.xml
    elif page_name.endswith(".ner.xml"):
        return page_name[:-8]  # Remove .ner.xml
    elif page_name.endswith(".xml"):
        return page_name[:-4]  # Remove .xml
    return page_name




@bp.route("/results")
def results():
    doc_id = request.args.get("id", session.get("doc_id"))
    if not doc_id:
        return "Missing document id", 400

    # Get all results by doc_id
    images, xmls = get_results(doc_id)
    results_data = get_results_json(doc_id)

    return render_template(
        "results.html",
        doc_id=doc_id,
        pages=images,
        results_data=results_data,
    )


@bp.route("/data/<path:filename>")
def serve_data(filename):
    return send_from_directory("/var/ocr4all/data", filename)
