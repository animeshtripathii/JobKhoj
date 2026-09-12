# mcp_servers/resume_matcher/server.py
#
# Real semantic matcher: loads the pre-built resume index at startup,
# embeds an incoming JD, retrieves the most similar resume chunks via
# FAISS, converts distance to a similarity score, and asks Groq to
# generate a short, grounded explanation using ONLY the retrieved chunks.
#
# NEW: reload_resume_index() lets an already-running server pick up a
# freshly rebuilt index (after "Update Resume") WITHOUT a full restart --
# see the Day 10.5 "Update Resume" discussion for why this is needed:
# resume_index/resume_chunks are loaded into memory ONCE at startup, and
# overwriting the files on disk alone does not affect an already-running
# process until it's told to re-read them.

import json
from typing import List

os_placeholder = None  # (kept intentionally absent -- see note below)
import os
os.environ["HF_HUB_OFFLINE"] = "1"

import faiss
import numpy as np
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

from config import groq_client, GROQ_MODEL

FAISS_INDEX_PATH = "data/faiss_index/resume.index"
CHUNKS_JSON_PATH = "data/faiss_index/resume_chunks.json"

mcp = FastMCP("ResumeMatcherServer")

# --- Loaded ONCE, when this server process starts ---
# Gracefully handles missing index (no resume uploaded yet at first deploy).
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
try:
    resume_index = faiss.read_index(FAISS_INDEX_PATH)
    with open(CHUNKS_JSON_PATH, "r", encoding="utf-8") as f:
        resume_chunks: List[str] = json.load(f)
    _resume_loaded = True
except Exception:
    resume_index = None
    resume_chunks = []
    _resume_loaded = False


class MatchResult(BaseModel):
    match_score: float = Field(
        ..., description="Overall resume-to-JD match score, from 0 to 100."
    )
    top_matching_chunks: List[str] = Field(
        ..., description="The resume bullet points most relevant to this JD."
    )
    explanation: str = Field(
        ..., description="A short, human-readable explanation of the match, grounded in the retrieved resume chunks."
    )


class ReloadResult(BaseModel):
    status: str = Field(..., description="Confirmation that the reload succeeded.")
    chunk_count: int = Field(..., description="Number of resume chunks loaded after reload.")


def _generate_explanation(jd_text: str, top_chunks: List[str], score: float) -> str:
    chunks_text = "\n".join(f"- {c}" for c in top_chunks)

    prompt = f"""You are helping explain a resume-to-job-match result.

Job description:
{jd_text}

Most relevant resume points (retrieved via semantic search):
{chunks_text}

Computed match score: {score:.1f}/100

In 2-3 sentences, explain why these resume points are relevant to this job.
Only reference what is written in the resume points above — do not invent
skills or experience not shown there."""

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


@mcp.tool()
def score_match(jd_text: str, top_k: int = 5) -> MatchResult:
    """
    Compares a job description against the candidate's stored resume using
    semantic similarity search, and returns a match score, the most relevant
    resume bullet points, and a short explanation of the match.
    """
    global _resume_loaded, resume_index, resume_chunks
    if not _resume_loaded or resume_index is None:
        raise ValueError(
            "No resume loaded yet. Please upload a resume PDF via the sidebar "
            "in the Streamlit UI, then try again."
        )

    jd_embedding = embedding_model.encode([jd_text], normalize_embeddings=True)

    distances, indices = resume_index.search(jd_embedding, top_k)

    top_chunks = [resume_chunks[i] for i in indices[0]]

    similarities = 1 - (distances[0] ** 2) / 2
    avg_similarity = float(np.mean(similarities))

    match_score = max(0.0, min(1.0, (avg_similarity + 1) / 2)) * 100

    explanation = _generate_explanation(jd_text, top_chunks, match_score)

    return MatchResult(
        match_score=round(match_score, 1),
        top_matching_chunks=top_chunks,
        explanation=explanation,
    )


@mcp.tool()
def reload_resume_index() -> ReloadResult:
    """
    Reloads the resume's FAISS index and chunk text from disk into this
    server's memory. Call this AFTER a new resume has been uploaded and
    re-ingested (i.e., after resume.index and resume_chunks.json have been
    freshly rebuilt on disk) — without this, the server keeps using the
    OLD resume data it loaded at startup, even though the files on disk
    have changed.
    """
    global resume_index, resume_chunks, _resume_loaded

    resume_index = faiss.read_index(FAISS_INDEX_PATH)
    with open(CHUNKS_JSON_PATH, "r", encoding="utf-8") as f:
        resume_chunks = json.load(f)
    _resume_loaded = True

    return ReloadResult(status="reloaded", chunk_count=len(resume_chunks))


if __name__ == "__main__":
    mcp.run()