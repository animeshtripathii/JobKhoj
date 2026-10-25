# AI Job Search Copilot

An agentic AI system that helps automate and streamline the job search process — matching your resume against job descriptions, tracking applications, and generating tailored interview preparation — built using **LangGraph**, the **Model Context Protocol (MCP)**, and a fully local, free-tier tech stack.

This project was built incrementally, day by day, as a hands-on learning exercise in agentic AI system design — not generated in one pass. Every architectural decision below was made deliberately, and several were revised mid-build after hitting and resolving real engineering problems (documented in [Challenges & Learnings](#challenges--learnings)).

---

## What It Does

Given a job description (pasted text or a URL) and a stored resume, the system can:

- **Score the match** between your resume and the JD using semantic similarity search (not keyword matching), with a grounded, LLM-generated explanation
- **Track applications** — log new applications, update their status (Applied → Screening → Interview → Offer/Rejected), and query your history
- **Generate interview prep** — realistic, role-specific questions grounded in your *actual* matched resume experience, each with what it's testing for, key concepts to cover, and how to tie your answer back to your resume
- **Fetch job postings from a URL** instead of requiring pasted text
- **Update your resume** live, without restarting the system, whenever it changes

All of this is driven by a single conversational interface — the underlying agent autonomously decides which capability (or combination of capabilities) a given message requires, rather than following a fixed script.

---

## Architecture

```text
┌─────────────┐       HTTP        ┌──────────────┐
│  Streamlit  │ ────────────────▶ │   FastAPI    │
│  Frontend   │ ◀──────────────── │   Backend    │
└─────────────┘                   └──────┬───────┘
                                        │
                                        ▼
                         ┌──────────────────────────┐
                         │     LangGraph Agent      │
                         │   ReAct reasoning loop   │
                         │                          │
                         │ Reason → Act → Observe   │
                         │          → Repeat        │
                         └────────────┬─────────────┘
                                      │
                                      │ ChatGroq
                                      │ openai/gpt-oss-120b
                                      │
                                      │ Bound MCP tool schemas
                                      ▼
                    ┌───────────────────────────────────┐
                    │      MultiServerMCPClient         │
                    │              (stdio)              │
                    └───┬────────┬────────┬────────┬────┘
                        │        │        │        │
             ┌──────────┘        │        │        └──────────┐
             ▼                   ▼        ▼                   ▼
      ┌─────────────┐    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
      │   Resume    │    │ Application │  │  Interview  │  │ Filesystem  │
      │   Matcher   │    │   Tracker   │  │    Prep     │  │  Official   │
      │   Custom    │    │   Custom    │  │   Custom    │  │ MCP Server  │
      └──────┬──────┘    └──────┬──────┘  └─────────────┘  └─────────────┘
             │                  │                                  │
             ▼                  ▼                                  │
      ┌─────────────┐    ┌─────────────┐                           │
      │    FAISS    │    │   SQLite    │                           │
      │    Index    │    │app_tracker.db│                          │
      │      +      │    └─────────────┘                           │
      │ Sentence-   │                                              │
      │Transformers │                              ┌─────────────┐ │
      └─────────────┘                              │    Fetch    │◀┘
                                                   │  Official   │
                                                   │ MCP Server  │
                                                   └─────────────┘

```

**Design principle:** the agent (LLM) never touches a database, vector index, or filesystem directly. It only sees a set of well-described *tools* exposed through MCP and decides, at runtime, which tools to call and in what order. The same ReAct cycle — **Reason → Act → Observe → Repeat** — continues until the agent has enough information to respond.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| LLM inference | **Groq** (`openai/gpt-oss-120b`) | Free-tier, fast inference on open models |
| Agent orchestration | **LangGraph** | Explicit state machine for tool-calling loops, not a black-box agent executor |
| Tool protocol | **MCP** (Model Context Protocol) | Standardized, framework-agnostic tool interface — 3 custom servers + 2 official reference servers |
| Vector search | **FAISS** (`IndexFlatL2`) | Local, in-memory semantic similarity search |
| Embeddings | **sentence-transformers** (`all-MiniLM-L6-v2`) | Free, local, CPU-only embedding model |
| Structured storage | **SQLite** | Relational data for application tracking (status, dates, scores) |
| Backend | **FastAPI** | Wraps the agent as an HTTP API; async, auto-documented |
| Frontend | **Streamlit** | Chat UI, run as a fully separate process from the backend |
| Observability | **LangSmith** | Automatic tracing of every LLM/tool call — zero extra code, environment-variable-driven |
| Validation | **Pydantic** | Every MCP tool's input/output is a validated schema, not a loose dict |

**No paid APIs. Everything runs locally except the LLM inference call itself (Groq's free tier) and LangSmith's tracing dashboard.**

---

## The 5 MCP Servers

| Server | Type | Tools |
|---|---|---|
| `resume_matcher` | Custom | `score_match`, `reload_resume_index` (internal-only, see below) |
| `application_tracker` | Custom | `log_application`, `update_status`, `get_applications` |
| `interview_prep` | Custom | `generate_interview_prep` |
| `filesystem` | Official (Anthropic reference server) | `read_text_file`, `list_directory` (of 14 available, deliberately trimmed — see below) |
| `fetch` | Official (Anthropic reference server) | `fetch` (retrieves and converts a URL to markdown, respects `robots.txt`) |

**A deliberate design detail:** `reload_resume_index` exists as a real, callable MCP tool, but is *excluded* from what's bound to the LLM. It's only ever invoked directly by the backend's `/update-resume` endpoint — a resume reload should be a deterministic consequence of a file upload, never something the LLM decides to do based on conversational judgment. Similarly, only 2 of Filesystem's 14 tools are bound to the LLM; binding all of them caused a real `413` token-limit error (documented below), since every bound tool's schema is resent to the model on every single call.

---

## Project Structure

```text
ai-job-search-copilot/
│
├── agent/
│   ├── __init__.py
│   └── graph.py
│       └── LangGraph agent, MCP connections, and ReAct tool-calling loop
│
├── backend/
│   ├── __init__.py
│   └── main.py
│       └── FastAPI endpoints: /chat, /update-resume, /health
│
├── frontend/
│   ├── __init__.py
│   └── app.py
│       └── Streamlit conversational UI and resume uploader
│
├── mcp_servers/
│   │
│   ├── resume_matcher/
│   │   ├── __init__.py
│   │   ├── ingest_resume.py
│   │   └── server.py
│   │       └── FAISS + embeddings-based semantic resume/JD matching
│   │
│   ├── application_tracker/
│   │   ├── __init__.py
│   │   ├── db.py
│   │   └── server.py
│   │       └── SQLite-backed job application tracking
│   │
│   └── interview_prep/
│       ├── __init__.py
│       └── server.py
│           └── Grounded, role-specific interview preparation
│
├── data/
│   ├── resume/
│   │   └── .gitkeep
│   │       └── Resume PDF stored here locally (gitignored)
│   │
│   └── faiss_index/
│       └── .gitkeep
│           └── Generated FAISS index stored here locally (gitignored)
│
├── scripts/
│   ├── test_groq.py
│   └── test_mcp_tools.py
│       └── Development and verification scripts
│
├── config.py
│   └── Shared configuration and LLM/model setup
│
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Setup

### Prerequisites
- Python 3.10+
- Node.js (for the Filesystem MCP server, launched via `npx`)
- A free [Groq](https://console.groq.com) API key
- A free [LangSmith](https://smith.langchain.com) API key (optional — only needed for tracing)

### Installation

```bash
git clone https://github.com/Abhi002Ram/ai-job-search-copilot.git
cd ai-job-search-copilot

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

python -m pip install -r requirements.txt
```

### Configuration

Copy the template and fill in your own keys:
```bash
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux
```

### Add your resume

Place a PDF resume at `data/resume/resume.pdf`, then build the initial embeddings index:
```bash
python -m mcp_servers.resume_matcher.ingest_resume
```

### Run it

Two separate terminals, in this order:

```bash
# Terminal 1 — backend (wait for "Startup complete" — first run takes ~50-60s)
python -m uvicorn backend.main:app

# Terminal 2 — frontend
python -m streamlit run frontend/app.py
```

Streamlit will open automatically at `http://localhost:8501`.

---

## Usage Examples

- *"Here's a JD: [paste text]. How well does my resume match?"* → semantic match score + grounded explanation
- *"What's the status of my applications?"* → queries the tracker
- *"I got an interview with [Company]"* → looks up the application and updates its status
- *"Give me interview prep for this role"* → generates grounded, resume-tied questions
- *"Here's a job posting URL: [link]"* → fetches the page content, then matches it

---

## Challenges & Learnings

This section exists because the debugging process taught as much as the building did.

- **A Groq model deprecation mid-build.** `llama-3.3-70b-versatile` was deprecated by Groq during development; resolved by isolating the model name into a single `config.py` source of truth, so the fix was a one-line change instead of a multi-file hunt.
- **A three-way dependency conflict** between `fastmcp`, `mcp`, and `langchain-mcp-adapters` — each expecting incompatible versions of a shared transitive dependency. Diagnosed by progressively isolating layers (bypassing higher-level libraries to capture raw subprocess stderr) down to the exact incompatible internal import, then resolved by switching to `mcp`'s own bundled `FastMCP` implementation instead of the standalone package.
- **A silent, unexpected network dependency.** MCP tool calls were mysteriously timing out; traced through several false leads (interpreter resolution, buffering, newline encoding) before discovering `sentence-transformers` was making live Hugging Face API calls on every server startup to check for model updates — even with a fully cached model. Fixed with `HF_HUB_OFFLINE=1`.
- **A tool-schema token-bloat issue.** Binding all 20 available tools (5 custom + 14 Filesystem + Fetch) caused a Groq `413` error — every bound tool's schema is resent on every call. Resolved by curating which tools are actually LLM-facing, a deliberate architectural choice rather than binding everything available.
- **A stale in-memory cache after file updates.** Overwriting the resume file on disk didn't affect an already-running server, since it had loaded the old data into memory at startup. Solved with a dedicated `reload_resume_index` tool, invoked deterministically by the upload endpoint — not exposed to the LLM.

---

## What This Project Demonstrates

- Designing and implementing **custom MCP servers** from scratch (not just consuming pre-built ones), alongside integrating official reference servers appropriately
- Building a genuine **agentic system** (LangGraph, ReAct pattern) where an LLM autonomously selects and chains tools, rather than a fixed pipeline
- **RAG fundamentals** (embeddings, FAISS, chunking strategy, grounding) applied as one component within a larger agentic architecture, not as the whole system
- **Full-stack integration**: MCP servers → LangGraph agent → FastAPI → Streamlit, as properly separated, independently-deployable services
- **Real production judgment**: caching expensive resources (model loading, MCP connections), curating LLM tool exposure, separating deterministic system actions from LLM-judgment actions, and methodical, evidence-based debugging of multi-layered failures

---

## Roadmap

- [ ] Automated tests (pytest) for MCP tool logic
- [ ] Additional error-handling and input validation polish
- [ ] Docker containerization
- [ ] Optional: GitHub MCP server integration for resume-grounded interview prep using real repo activity

---

## License

This project is for portfolio/demonstration purposes.