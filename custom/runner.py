import json
import os
import shutil
import time
from pathlib import Path
from typing import Optional, Tuple
import subprocess
import traceback
from collections import deque


# -----------------------------
# Configuration (env override)
# -----------------------------
# Where the webapp drops files (PDF + meta + ready markers)
OCR4ALL_INPUT = Path(os.getenv("OCR4ALL_INPUT", "/var/ocr4all/data/default/input"))

# OCR4all data root (we create per-doc projects here)
OCR4ALL_DATA_ROOT = Path(os.getenv("OCR4ALL_DATA_ROOT", "/var/ocr4all/data"))

# Pipeline script inside the runner container
PIPELINE_SCRIPT = os.getenv("PIPELINE_SCRIPT", "/opt/custom/pipeline.py")

# Scan frequency
POLL_SECONDS = float(os.getenv("POLL_SECONDS", "1.0"))

# Marker suffixes
READY_SUFFIX = ".ready"
RUNNING_SUFFIX = ".running"
DONE_SUFFIX = ".done"
FAIL_SUFFIX = ".failed"

MAX_TAIL_CHARS = int(os.getenv("PIPELINE_LOG_TAIL_CHARS", "20000"))
MAX_TAIL_LINES = int(os.getenv("PIPELINE_LOG_TAIL_LINES", "2000"))

# -----------------------------
# Job discovery + preparation
# -----------------------------
def find_next_job() -> Optional[Tuple[str, Path, Path]]:
    """
    Expects in OCR4ALL_INPUT:
      - <doc_id>.ready
      - <doc_id>.meta.json
      - meta["filename"] -> PDF filename in OCR4ALL_INPUT

    Returns:
      (doc_id, meta_path, pdf_path)
    """
    if not OCR4ALL_INPUT.exists():
        return None

    for ready in sorted(OCR4ALL_INPUT.glob(f"*{READY_SUFFIX}")):
        doc_id = ready.stem  # "<doc_id>" from "<doc_id>.ready"
        meta_path = OCR4ALL_INPUT / f"{doc_id}.meta.json"
        if not meta_path.exists():
            continue

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        filename = meta.get("filename")
        if not filename:
            continue

        pdf_path = OCR4ALL_INPUT / filename
        if not pdf_path.exists():
            continue

        return doc_id, meta_path, pdf_path

    return None


def ensure_project_dir(doc_id: str) -> Path:
    """
    Create per-doc OCR4all project folder:
      /var/ocr4all/data/<doc_id>/
        input/
        work/
        .meta.json
        <pdf>
    """
    proj_dir = OCR4ALL_DATA_ROOT / doc_id
    (proj_dir / "input").mkdir(parents=True, exist_ok=True)
    (proj_dir / "work").mkdir(parents=True, exist_ok=True)
    return proj_dir


def stage_job_into_project(doc_id: str, meta_path: Path, pdf_path: Path) -> Path:
    proj_dir = ensure_project_dir(doc_id)

    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    # metadata for your custom scripts
    (proj_dir / ".meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # IMPORTANT: OCR4all expects the PDF in <project>/input/
    dest_pdf = (proj_dir / "input" / pdf_path.name)
    shutil.copy2(pdf_path, dest_pdf)

    return proj_dir


def write_marker(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def safe_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


# -----------------------------
# Main loop
# -----------------------------
def main() -> None:
    print(f"[runner] Watching: {OCR4ALL_INPUT}")
    print(f"[runner] Data root: {OCR4ALL_DATA_ROOT}")
    print(f"[runner] Pipeline:  {PIPELINE_SCRIPT}")

    OCR4ALL_INPUT.mkdir(parents=True, exist_ok=True)

    while True:
        job = find_next_job()
        if not job:
            time.sleep(POLL_SECONDS)
            continue

        doc_id, meta_path, pdf_path = job
        ready_path = OCR4ALL_INPUT / f"{doc_id}{READY_SUFFIX}"
        running_path = OCR4ALL_INPUT / f"{doc_id}{RUNNING_SUFFIX}"
        done_path = OCR4ALL_INPUT / f"{doc_id}{DONE_SUFFIX}"
        fail_path = OCR4ALL_INPUT / f"{doc_id}{FAIL_SUFFIX}"

        print(f"[runner] Picked job doc_id={doc_id}")

        # mark running
        write_marker(running_path, {"doc_id": doc_id, "status": "running", "ts": time.time()})

        try:
            proj_dir = stage_job_into_project(doc_id, meta_path, pdf_path)
            print(f"[runner] Staged into project: {proj_dir}")

            cmd = ["python3", "-u", PIPELINE_SCRIPT, str(proj_dir)]
            print(f"[runner] Running: {' '.join(cmd)}")

            # keep last lines (so .failed always contains something useful)
            tail_lines = deque(maxlen=MAX_TAIL_LINES)

            started = time.time()
            proc = subprocess.Popen(
                cmd,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=os.environ.copy(),
                bufsize=1,
                universal_newlines=True,
            )

            full_log_path = os.path.join(str(proj_dir), "pipeline.log")
            with open(full_log_path, "w", encoding="utf-8") as lf:
                assert proc.stdout is not None
                for line in proc.stdout:
                    print(line, end="")  # stream to docker logs
                    lf.write(line)  # persist full log
                    tail_lines.append(line)  # keep tail

            rc = proc.wait()
            runtime_s = round(time.time() - started, 3)

            if rc != 0:
                raise RuntimeError(f"pipeline exited with code {rc}")

            write_marker(done_path, {
                "doc_id": doc_id,
                "project_dir": str(proj_dir),
                "status": "done",
                "runtime_s": runtime_s,
                "log_file": full_log_path,
            })
            safe_unlink(ready_path)
            safe_unlink(running_path)
            print(f"[runner] Done doc_id={doc_id}")

        except Exception as e:
            tb = traceback.format_exc()

            # Build a tail string capped by chars (not just lines)
            tail_text = "".join(tail_lines)
            if len(tail_text) > MAX_TAIL_CHARS:
                tail_text = tail_text[-MAX_TAIL_CHARS:]

            payload = {
                "doc_id": doc_id,
                "error": str(e),
                "traceback": tb,
                "cmd": cmd if "cmd" in locals() else None,
                "project_dir": str(proj_dir) if "proj_dir" in locals() else None,
                "returncode": getattr(proc, "returncode", None) if "proc" in locals() else None,
                "pipeline_output_tail": tail_text,
                "log_file": os.path.join(str(proj_dir), "pipeline.log") if "proj_dir" in locals() else None,
                "ts": time.time(),
            }

            write_marker(fail_path, payload)
            safe_unlink(running_path)
            print(f"[runner] FAILED doc_id={doc_id}: {e}")
            print(tb)

        time.sleep(0.2)


if __name__ == "__main__":
    main()
