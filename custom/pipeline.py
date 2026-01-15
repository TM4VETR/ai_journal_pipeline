import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List

import requests
from logger import logger

sys.path.append("ocr4all_ajax")
from ocr4all_ajax_client.ocr4all_ajax_utils import (
    ocr4all_open_project,
    ocr4all_get_page_ids,
    ocr4all_processflow_wait,
    ocr4all_threads,
    ocr4all_checkpdf,
    ocr4all_convert_project_files,
    ocr4all_processflow_current,
    ocr4all_processflow_execute_json
)

# Project directory (CLI arg)
PROJECT_DIR = sys.argv[1] if len(sys.argv) > 1 else "/var/ocr4all/data/default"

# OCR4all config (env override)
OCR4ALL_BASE_URL = os.getenv("OCR4ALL_BASE_URL", "http://localhost:8080/ocr4all")

# IMPORTANT: default to CLI arg
OCR4ALL_PROJECT_DIR = os.getenv("OCR4ALL_PROJECT_DIR", PROJECT_DIR)

# PDF conversion settings (blank-pages dialog replacement)
OCR4ALL_DELETE_BLANK = os.getenv("OCR4ALL_DELETE_BLANK", "true").lower() == "true"
OCR4ALL_PDF_DPI = int(os.getenv("OCR4ALL_PDF_DPI", "300"))
OCR4ALL_CONVERT_TIMEOUT_S = float(os.getenv("OCR4ALL_CONVERT_TIMEOUT_S", "1800"))  # 30 min

# Wait for pages after conversion/import
OCR4ALL_PAGE_WAIT_TIMEOUT_S = int(os.getenv("OCR4ALL_PAGE_WAIT_TIMEOUT_S", "1800"))  # 30 min
OCR4ALL_PAGE_WAIT_POLL_S = float(os.getenv("OCR4ALL_PAGE_WAIT_POLL_S", "2.0"))  # poll every 2s
OCR4ALL_PAGE_WAIT_LOG_S = float(os.getenv("OCR4ALL_PAGE_WAIT_LOG_S", "10.0"))  # log every 10s

# Centralized process-flow execute request timeout (HTTP request itself)
# IMPORTANT: This must be long enough for OCR on many pages. 5 min is often too short.
OCR4ALL_EXECUTE_TIMEOUT_S = float(os.getenv("OCR4ALL_EXECUTE_TIMEOUT_S", "3600"))  # 60 min

# Recognition checkpoint path MUST match OCR4all container filesystem
OCR4ALL_CHECKPOINT_PATH = os.getenv(
    "OCR4ALL_CHECKPOINT_PATH",
    "/var/ocr4all/models/default/default/deep3_antiqua-hist/0.ckpt.json",
)


# Fixed centralized workflow (no Kraken)
OCR4ALL_PROCESSFLOW = [
    "preprocessing",
    "despeckling",
    "segmentationDummy",
    "lineSegmentation",
    "recognition",
]



# Pipeline modules (downstream)
def run_module(script: str, *args: str) -> None:
    path = f"/opt/custom/{script}"
    cmd = ["python3", path, *args]
    logger.debug(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def load_metadata(project_dir: str) -> Dict[str, Any]:
    meta_path = os.path.join(project_dir, ".meta.json")
    if not os.path.exists(meta_path):
        logger.warning("No .meta.json found – proceeding without metadata.")
        return {"year": None, "title": None, "type": None}

    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    logger.info(f"Document metadata: {meta}")
    return meta


def build_process_settings(threads: int) -> Dict[str, Any]:
    """
    Builds the processSettings object to match the UI's payload.
    """
    settings: Dict[str, Any] = {}

    # preprocessing
    settings["preprocessing"] = {
        "cmdArgs": ["--nocheck", "--maxskew", "0", "--parallel", str(threads)]
    }

    # despeckling
    settings["despeckling"] = {
        "maxContourRemovalSize": "100"
    }

    # segmentationDummy
    # IMPORTANT: UI uses Binary here. This assumes preprocessing produces Binary images.
    settings["segmentationDummy"] = {
        "imageType": "Binary",
    }

    # lineSegmentation
    settings["lineSegmentation"] = {
        "cmdArgs": ["--max-whiteseps", "-1", "--parallel", str(threads)]
    }

    # recognition
    settings["recognition"] = {
        "cmdArgs": [
#            "--verbose True",
            "--estimate_skew",
            "--data.output_confidences",
            "--data.output_glyphs",
            "--pipeline.batch_size", "5",
            "--data.max_glyph_alternatives", "1",
            "--checkpoint", OCR4ALL_CHECKPOINT_PATH,
        ]
    }

    return settings


def sanitize_processes(processes: List[str]) -> List[str]:
    return [p.strip() for p in processes if p and p.strip()]


def wait_for_pages(session: requests.Session) -> List[str]:
    """
    Poll pagelist until we get at least one page id (or timeout).
    Includes periodic logging and shows OCR4all 'current' status string.
    """
    t0 = time.time()
    last_log = 0.0
    last_cur = None

    while True:
        now = time.time()
        if now - last_log >= OCR4ALL_PAGE_WAIT_LOG_S:
            try:
                cur = ocr4all_processflow_current(session, OCR4ALL_BASE_URL)
            except Exception:
                cur = None

            if cur is not None and cur != last_cur:
                logger.info(f"OCR4all current while waiting for pages: {cur!r}")
                last_cur = cur

            elapsed = int(now - t0)
            logger.info(
                f"Waiting for OCR4all pages... elapsed={elapsed}s "
                f"(project={OCR4ALL_PROJECT_DIR})"
            )
            last_log = now

        try:
            page_ids = ocr4all_get_page_ids(session, OCR4ALL_BASE_URL, image_type="Original")
            if page_ids:
                logger.info(f"Pages ready: {len(page_ids)}")
                return page_ids
        except Exception as e:
            logger.warning(f"pagelist failed (transient): {e}")

        if time.time() - t0 > OCR4ALL_PAGE_WAIT_TIMEOUT_S:
            raise TimeoutError(
                f"Timed out waiting for OCR4all pages (pagelist empty) for project {OCR4ALL_PROJECT_DIR} "
                f"after {OCR4ALL_PAGE_WAIT_TIMEOUT_S}s."
            )

        time.sleep(OCR4ALL_PAGE_WAIT_POLL_S)


# Main
if __name__ == "__main__":
    logger.info("Running OCR4all + custom extraction pipeline...")

    _meta = load_metadata(PROJECT_DIR)

    session = requests.Session()

    # 1) Select project in OCR4all session (MUST be the per-doc project)
    logger.info(f"Opening OCR4all project: {OCR4ALL_PROJECT_DIR}")
    ocr4all_open_project(
        session,
        OCR4ALL_BASE_URL,
        OCR4ALL_PROJECT_DIR,
        image_type = "Binary",
        reset_session=True,
    )

    session.get(f"{OCR4ALL_BASE_URL}/ProcessFlow", timeout=30).raise_for_status()

    # 2) If project contains only PDFs, OCR4all requires convertProjectFiles (blank pages dialog)
    if ocr4all_checkpdf(session, OCR4ALL_BASE_URL):
        logger.info(
            f"checkpdf=true -> converting PDFs (deleteBlank={OCR4ALL_DELETE_BLANK}, dpi={OCR4ALL_PDF_DPI})"
        )
        ocr4all_convert_project_files(
            session,
            OCR4ALL_BASE_URL,
            delete_blank=OCR4ALL_DELETE_BLANK,
            dpi=OCR4ALL_PDF_DPI,
            timeout_s=OCR4ALL_CONVERT_TIMEOUT_S,
        )

    # 3) Wait for page IDs in THIS project
    page_ids = wait_for_pages(session)

    # 4) Centralized Process Flow (single execute call)
    threads = ocr4all_threads(session, OCR4ALL_BASE_URL)
    processes = sanitize_processes(OCR4ALL_PROCESSFLOW)

    process_settings = build_process_settings(threads)
    process_settings = {k: v for k, v in process_settings.items() if k in processes}

    logger.info(f"OCR4all threads={threads} | centralized processes={processes}")

    # Debug: show payload preview
    preview = {
        "processesToExecute": processes,
        "pageIds": page_ids[:1],
        "processSettings": process_settings,
    }
    logger.info("Payload preview (first 1 page):\n%s", json.dumps(preview, indent=2, ensure_ascii=False))

    session.get(f"{OCR4ALL_BASE_URL}/ProcessFlow", timeout=30).raise_for_status()

    # Execute whole flow
    ocr4all_processflow_execute_json(
        session=session,
        base_url=OCR4ALL_BASE_URL,
        page_ids=page_ids,
        processes=processes,
        process_settings=process_settings,
        timeout_s=OCR4ALL_EXECUTE_TIMEOUT_S,
    )

    # Wait until OCR4all is idle again
    ocr4all_processflow_wait(session, OCR4ALL_BASE_URL)
    logger.info("OCR4all centralized process flow finished.")

    # 5) Downstream extraction tasks (operate on the per-doc project staged by runner)
    run_module("ner_jobtitles.py", PROJECT_DIR)
    run_module("match_jobtitles.py", PROJECT_DIR)
    run_module("neo4j_insert.py", PROJECT_DIR)

    logger.info("Pipeline finished successfully.")
