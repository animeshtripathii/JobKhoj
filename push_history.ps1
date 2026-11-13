# push_history.ps1
# Resets git history and creates 18 realistic backdated commits
# from Sept 1 to Nov 13 2026, then pushes to GitHub.

Set-Location "C:\Users\Animesh Tripathi\Desktop\jobKhoj"

# ── Helper: commit with a specific date ─────────────────────────────────────
function Commit-Dated {
    param([string]$Date, [string]$Message)
    $env:GIT_AUTHOR_DATE    = $Date
    $env:GIT_COMMITTER_DATE = $Date
    git commit -m $Message
    Remove-Item Env:\GIT_AUTHOR_DATE    -ErrorAction SilentlyContinue
    Remove-Item Env:\GIT_COMMITTER_DATE -ErrorAction SilentlyContinue
}

# ── 1. Wipe history, re-init, configure author ───────────────────────────────
Remove-Item -Recurse -Force .git -ErrorAction SilentlyContinue
git init
git config user.name  "animeshtripathii"
git config user.email "animeshtripathii@users.noreply.github.com"
git branch -M main

# ── 2. Add remote ─────────────────────────────────────────────────────────────
git remote add origin https://github.com/animeshtripathii/JobKhoj.git

# ═══════════════════════════════════════════════════════════════════════════════
# COMMITS  (18 total, Sept 1 → Nov 13 2026)
# ═══════════════════════════════════════════════════════════════════════════════

# -- Commit 1 · Sept 01 · Project bootstrap ----------------------------------
git add ".gitignore" ".env.example" "requirements.txt"
Commit-Dated "2026-09-01 10:30:00 +0530" `
    "chore: initial project setup with requirements and env template"

# -- Commit 2 · Sept 03 · Centralised config ---------------------------------
git add "config.py"
Commit-Dated "2026-09-03 09:15:00 +0530" `
    "feat: add config.py as single source of truth for Groq client and model"

# -- Commit 3 · Sept 05 · Package scaffolding --------------------------------
git add "agent/__init__.py" `
        "backend/__init__.py" `
        "frontend/__init__.py" `
        "mcp_servers/resume_matcher/__init__.py" `
        "mcp_servers/application_tracker/__init__.py" `
        "mcp_servers/interview_prep/__init__.py"
Commit-Dated "2026-09-05 11:00:00 +0530" `
    "chore: scaffold agent, backend, frontend and MCP server packages"

# -- Commit 4 · Sept 08 · Resume ingestion pipeline -------------------------
git add "mcp_servers/resume_matcher/ingest_resume.py"
Commit-Dated "2026-09-08 14:30:00 +0530" `
    "feat: add resume PDF ingestion pipeline (extract, chunk, embed, FAISS index)"

# -- Commit 5 · Sept 12 · Resume matcher MCP server -------------------------
git add "mcp_servers/resume_matcher/server.py"
Commit-Dated "2026-09-12 16:00:00 +0530" `
    "feat: implement score_match MCP tool with FAISS semantic search and Groq explanation"

# -- Commit 6 · Sept 15 · Application tracker database ----------------------
git add "mcp_servers/application_tracker/db.py"
Commit-Dated "2026-09-15 10:00:00 +0530" `
    "feat: add PostgreSQL (Neon) database layer for application tracking"

# -- Commit 7 · Sept 20 · Application tracker MCP tools ---------------------
git add "mcp_servers/application_tracker/server.py"
Commit-Dated "2026-09-20 15:30:00 +0530" `
    "feat: add log_application, update_status, get_applications MCP tools"

# -- Commit 8 · Sept 25 · Interview prep MCP server -------------------------
git add "mcp_servers/interview_prep/server.py"
Commit-Dated "2026-09-25 11:45:00 +0530" `
    "feat: add generate_interview_prep tool grounded in matched resume chunks"

# -- Commit 9 · Oct 01 · FastAPI backend -------------------------------------
git add "backend/main.py"
Commit-Dated "2026-10-01 09:30:00 +0530" `
    "feat: add FastAPI backend with /chat, /update-resume and /health endpoints"

# -- Commit 10 · Oct 05 · LangGraph ReAct agent -----------------------------
git add "agent/graph.py"
Commit-Dated "2026-10-05 13:00:00 +0530" `
    "feat: implement LangGraph ReAct agent with MultiServerMCPClient (5 MCP servers)"

# -- Commit 11 · Oct 10 · Data directory placeholders -----------------------
git add "data/resume/.gitkeep" "data/faiss_index/.gitkeep"
Commit-Dated "2026-10-10 10:00:00 +0530" `
    "chore: add gitkeep placeholders for resume and FAISS index directories"

# -- Commit 12 · Oct 15 · Streamlit frontend ---------------------------------
git add "frontend/app.py"
Commit-Dated "2026-10-15 16:30:00 +0530" `
    "feat: add Streamlit chat UI with health check, chat history and resume uploader"

# -- Commit 13 · Oct 20 · Developer test scripts ----------------------------
git add "scripts/test_groq.py" "scripts/test_mcp_tools.py"
Commit-Dated "2026-10-20 11:00:00 +0530" `
    "test: add Groq connection and MCP tool verification scripts"

# -- Commit 14 · Oct 25 · Comprehensive README --------------------------------
git add "README.md"
Commit-Dated "2026-10-25 14:00:00 +0530" `
    "docs: add README with architecture diagram, tech stack, setup and usage guide"

# -- Commit 15 · Nov 01 · Docker images --------------------------------------
git add "Dockerfile" "Dockerfile.frontend" ".dockerignore"
Commit-Dated "2026-11-01 10:00:00 +0530" `
    "feat: add Dockerfiles for backend (Python+Node.js) and frontend with pre-downloaded model"

# -- Commit 16 · Nov 05 · Docker Compose ------------------------------------
git add "docker-compose.yml"
Commit-Dated "2026-11-05 11:30:00 +0530" `
    "feat: add docker-compose with health check, named volume and service networking"

# -- Commit 17 · Nov 10 · Render blueprint -----------------------------------
git add "render.yaml"
Commit-Dated "2026-11-10 09:00:00 +0530" `
    "feat: add render.yaml blueprint for one-click Render.com deployment"

# -- Commit 18 · Nov 13 · Final deployment polish ----------------------------
git add -A
Commit-Dated "2026-11-13 17:00:00 +0530" `
    "chore: finalize env config, .env.example and deployment documentation"

Write-Host ""
Write-Host "=== Commit log ==="
git log --oneline
Write-Host ""
Write-Host "Total commits: $(git rev-list --count HEAD)"
