# ── Backend Dockerfile ──────────────────────────────────────────────────────
# Runs: FastAPI (uvicorn) + all 3 custom MCP servers (stdio, same container)
#       + official filesystem MCP server (via npx, needs Node.js)
# ────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# ── System packages: Node.js (for npx filesystem MCP) + build tools ─────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        gnupg \
        build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python dependencies (layer-cached unless requirements.txt changes) ───────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Pre-download the sentence-transformers model so the container works ──────
# offline at runtime (HF_HUB_OFFLINE=1 is set in resume_matcher/server.py).
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# ── Application code ─────────────────────────────────────────────────────────
COPY . .

# ── Persistent data directories (mounted as a Docker volume at runtime) ──────
RUN mkdir -p data/resume data/faiss_index

EXPOSE 8000

# Render injects $PORT at runtime — use shell form so the variable expands.
# Falls back to 8000 for local docker run / docker compose.
CMD sh -c "python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"
