import fitz  # PyMuPDF
import docx2txt
import re
import tempfile
import os
import streamlit as st

@st.cache_data(show_spinner=False)
def extract_text(file_name: str, file_bytes: bytes) -> str:
    """Safely extracts text from document bytes with memory-safe caching."""
    if file_name.endswith(".pdf"):
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            pages = [page.get_text("text") for page in doc]
        text = "\n".join(pages)
        if not text.strip():
            st.warning(f"⚠️ {file_name} appears to be empty or scanned images. Text extraction returned 0 characters.")
        return text

    elif file_name.endswith(".docx"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            text = docx2txt.process(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        return text
    else:
        return file_bytes.decode("utf-8")

@st.cache_data(show_spinner=False)
def split_clauses(text: str) -> dict[str, str]:
    """Slices text into structured blocks using legal tags or standard numeric headings."""
    if not text.strip():
        return {}

    # Catches formal terms or standalone numeric hierarchies (e.g., 2.3, 4.1)
    pattern = r'(?=\b(?:Section|Clause|Article|Unit|Module)\s+\d+(?:\.\d+)*\b|\n\d+\.\d+\s+)'
    parts = re.split(pattern, text)

    clauses = {}
    block_counter = 1

    for p in parts:
        p = p.strip()
        if not p:
            continue

        match = re.match(r'^(Section|Clause|Article|Unit|Module)\s+\d+(?:\.\d+)*', p)
        num_match = re.match(r'^(\d+\.\d+)', p) if not match else None

        if match:
            key = match.group(0)
        elif num_match:
            key = f"Section {num_match.group(0)}"
        else:
            key = f"Structural Block {block_counter}"
            block_counter += 1

        if key in clauses:
            clauses[key] += "\n" + p
        else:
            clauses[key] = p

    return clauses