import shutil
import re
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

import gradio as gr
from pypdf import PdfReader

from app.config import (
    UPLOAD_DIR,
    Config,
    app_state,
    log_event,
    safe_public_error,
)

def sanitize_filename(filename: str) -> str:
    filename = Path(filename).name
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)
    return filename[:200]

def extract_pdf_info(file_path: str) -> Dict[str, Any]:
    try:
        reader = PdfReader(file_path)
        total_pages = len(reader.pages)

        preview_parts = []
        max_preview_pages = min(Config.MAX_PREVIEW_PAGES, total_pages)

        for i in range(max_preview_pages):
            page_text = reader.pages[i].extract_text() or ""
            preview_parts.append(page_text[:1000])

        combined_preview = "\n".join(preview_parts).strip()
        if not combined_preview:
            combined_preview = "No extractable text preview available."

        return {
            "filename": Path(file_path).name,
            "filepath": str(file_path),
            "pages": total_pages,
            "preview": combined_preview[:Config.MAX_PREVIEW_CHARS],
            "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        log_event("pdf_info_error", {"filepath": str(file_path), "error": str(e)})
        return {
            "filename": Path(file_path).name,
            "filepath": str(file_path),
            "pages": "Unknown",
            "preview": "Could not read PDF preview.",
            "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

def extract_pdf_pages(file_path: str) -> List[Dict[str, Any]]:
    pages = []
    reader = PdfReader(file_path)

    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append({"page_number": i, "text": text})
    return pages

def get_file_summary() -> str:
    if not app_state["uploaded_files"]:
        return "No files uploaded yet."
    lines = ["Uploaded Files Summary:"]
    for f in app_state["uploaded_files"]:
        lines.append(f"- {f['filename']} ({f['pages']} pages) - Uploaded: {f['uploaded_at']}")
    return "\n".join(lines)

def get_uploaded_filenames() -> List[str]:
    return [f["filename"] for f in app_state["uploaded_files"]]

def save_uploaded_pdf(file_obj):
    try:
        if file_obj is None:
            return (
                "No file uploaded.",
                get_file_summary(),
                gr.update(choices=get_uploaded_filenames(), value=None),
            )

        source_path = file_obj if isinstance(file_obj, str) else file_obj.name
        original_name = sanitize_filename(Path(source_path).name)

        if not original_name.lower().endswith(".pdf"):
            return (
                "Only PDF files are allowed.",
                get_file_summary(),
                gr.update(choices=get_uploaded_filenames(), value=None),
            )

        save_path = UPLOAD_DIR / original_name
        shutil.copyfile(source_path, save_path)

        pdf_info = extract_pdf_info(str(save_path))
        existing = [f["filename"] for f in app_state["uploaded_files"]]
        if pdf_info["filename"] not in existing:
            app_state["uploaded_files"].append(pdf_info)

        app_state["knowledge_base_ready"] = False
        app_state["total_chunks"] = 0

        log_event("pdf_uploaded", {"filename": pdf_info["filename"], "pages": pdf_info["pages"]})

        msg = f"Uploaded successfully: {pdf_info['filename']} ({pdf_info['pages']} pages)"
        return msg, get_file_summary(), gr.update(choices=get_uploaded_filenames(), value=None)

    except Exception as e:
        message = safe_public_error(
            "Unable to upload the PDF right now.",
            "pdf_upload_error",
            e,
        )
        return message, get_file_summary(), gr.update(choices=get_uploaded_filenames(), value=None)

def show_file_preview(selected_name: str) -> str:
    if not selected_name:
        return "Select a file to view preview."

    for file in app_state["uploaded_files"]:
        if file["filename"] == selected_name:
            return (
                f"Filename: {file['filename']}\n"
                f"Pages: {file['pages']}\n"
                f"Uploaded At: {file['uploaded_at']}\n\n"
                f"Preview:\n{file['preview']}"
            )
    return "File not found."