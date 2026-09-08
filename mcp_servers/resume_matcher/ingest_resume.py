# mcp_servers/resume_matcher/ingest_resume.py
#
# This is the "Update Resume" pipeline: run this ONCE (or whenever you
# revise your resume), and it will:
#   1. Extract raw text from your resume PDF
#   2. Split it into small chunks (roughly one idea/bullet per chunk)
#   3. Embed each chunk into a vector using all-MiniLM-L6-v2
#   4. Save those vectors into a FAISS index on disk
#   5. Save the original chunk TEXT alongside it (FAISS only stores numbers,
#      not the text itself — we need our own way to map "vector #7" back
#      to "what did vector #7 actually say")
#
# The real-time JD matching (Day 5) will LOAD this saved index instead of
# re-running this whole pipeline on every request — exactly the caching
# design decision from the original project spec.

import os
import json
import faiss
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

# --- Paths: keeping all resume-related data together, matching our folder design ---
RESUME_PDF_PATH = "data/resume/resume.pdf"          # adjust filename to match yours
FAISS_INDEX_PATH = "data/faiss_index/resume.index"
CHUNKS_JSON_PATH = "data/faiss_index/resume_chunks.json"

# Loaded once, reused for both ingestion (today) and matching (Day 5).
# This line downloads the model the FIRST time you run this (a few hundred MB
# cached locally afterward) — expect a short delay only on first run.
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def extract_text_from_pdf(pdf_path: str) -> str:
    """Reads a PDF file and returns all its text as one big string."""
    reader = PdfReader(pdf_path)
    full_text = ""
    for page in reader.pages:
        # extract_text() can occasionally return None for weird/scanned PDFs —
        # guarding against that so we don't crash on a blank page.
        page_text = page.extract_text()
        if page_text:
            full_text += page_text + "\n"
    return full_text


def chunk_text(text: str) -> list[str]:
    """
    Splits resume text into meaningful chunks — roughly one bullet point,
    header, or paragraph per chunk — instead of one chunk per raw PDF line.

    PROBLEM this solves: PDF text extraction preserves visual line wrapping,
    not semantic sentence boundaries. A single bullet point that wraps across
    two lines in the PDF gets extracted as two separate lines of text, which
    would otherwise become two disconnected, half-meaning chunks.

    APPROACH: treat lines starting with a bullet character, or short
    Title-Case lines (likely section headers), as the START of a new chunk.
    Any other line is treated as a CONTINUATION of the previous chunk and
    merged back onto it.
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    chunks = []
    current_chunk = ""

    for line in lines:
        is_bullet = line.startswith("•") or line.startswith("-")
        # Heuristic for section headers: short, no ending punctuation,
        # e.g. "Technical Skills", "Professional Experience"
        is_likely_header = (
            len(line.split()) <= 4
            and not line.endswith((".", ":", ","))
            and not is_bullet
        )

        if is_bullet or is_likely_header:
            # Starting a new chunk — save whatever we were building before.
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = line
        else:
            # Continuation of the previous line — merge with a space instead
            # of a newline, since it's really one flowing sentence.
            current_chunk += " " + line

    # Don't forget the last chunk being built when the loop ends.
    if current_chunk:
        chunks.append(current_chunk.strip())

    # Filter out very short/low-value chunks (bare headers, stray fragments).
    chunks = [c for c in chunks if len(c) > 15]

    return chunks


def build_index():
    print(f"Reading resume from: {RESUME_PDF_PATH}")
    raw_text = extract_text_from_pdf(RESUME_PDF_PATH)

    chunks = chunk_text(raw_text)
    print(f"Split resume into {len(chunks)} chunks.")

    # .encode() turns a list of strings into a list of vectors (a 2D array):
    # one 384-dimensional vector per chunk. This is the actual "embedding" step.
    # normalize_embeddings=True rescales every vector to unit length (magnitude 1),
    # so later we can convert FAISS's L2 distance directly into cosine similarity
    # using a simple formula — see score_match() in server.py.
    print("Embedding chunks... (first run downloads the model, be patient)")
    embeddings = embedding_model.encode(chunks, normalize_embeddings=True)

    # --- Building the FAISS index ---
    # IndexFlatL2 is the simplest possible FAISS index: it does an exact,
    # brute-force distance comparison against every stored vector. For a
    # resume with maybe 20-50 chunks, "brute force" is instant — the fancier
    # FAISS index types (which trade a little accuracy for huge speed at
    # millions of vectors) aren't needed here, but it's worth knowing they
    # exist for when data is much bigger (see rabbit holes below).
    dimension = embeddings.shape[1]  # 384 for this model
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    print(f"FAISS index built with {index.ntotal} vectors.")

    # --- Saving everything to disk ---
    # FAISS's own save function writes just the vectors + index structure.
    faiss.write_index(index, FAISS_INDEX_PATH)

    # Separately, we save the ORIGINAL TEXT of each chunk, in the same order
    # they were added to the index. This is critical: FAISS will later tell
    # us "vector at position 7 is your best match" — but only as a number.
    # This JSON file is how we translate "position 7" back into the actual
    # resume sentence, so we can show a human-readable result.
    with open(CHUNKS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2)

    print(f"Saved index to {FAISS_INDEX_PATH}")
    print(f"Saved chunk text to {CHUNKS_JSON_PATH}")


if __name__ == "__main__":
    build_index()