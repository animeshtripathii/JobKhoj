# backend/main.py
#
# Wraps the LangGraph agent as an HTTP API. The agent's MCP connections
# are established ONCE at server startup (via FastAPI's lifespan
# mechanism) and reused for every request afterward -- avoiding the
# ~50-60s MCP reconnection cost (mainly resume_matcher's PyTorch import)
# on every single chat message.
#
# /update-resume handles the "Update Resume" flow:
#   1. Saves an uploaded PDF, overwriting the existing resume file.
#   2. Re-runs the ingestion pipeline (extract -> chunk -> embed -> save)
#      to rebuild resume.index and resume_chunks.json on disk.
#   3. Calls the resume_matcher server's reload_resume_index MCP tool
#      DIRECTLY (bypassing the LLM entirely) so the already-running
#      server picks up the fresh data immediately, without a full
#      backend restart.
#
# reload_resume_index is deliberately EXCLUDED from the tools bound to
# the LLM (see agent/graph.py) -- it should only ever fire as a
# deterministic consequence of a real upload, never as something the
# LLM decides to call based on conversational judgment.

from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from agent.graph import build_graph
from mcp_servers.resume_matcher.ingest_resume import build_index, RESUME_PDF_PATH

# Holds the compiled graph (for normal chat) and the full tools list
# (for direct invocation of tools not bound to the LLM, like reload_resume_index).
app_state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs once at server startup (before yield) and once at shutdown
    (after yield). build_graph() returns a TUPLE: (compiled_graph, all_tools) --
    both are unpacked and stored separately in app_state.
    """
    print("Starting up: connecting to MCP servers and building the agent graph...")
    graph, tools = await build_graph()
    app_state["graph"] = graph
    app_state["tools"] = tools
    print("Startup complete. Agent is ready to receive requests.")

    yield

    print("Shutting down.")


app = FastAPI(title="AI Job Search Copilot", lifespan=lifespan)


# --- Request/response schemas ---
class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


class UpdateResumeResponse(BaseModel):
    status: str


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Sends a user's message through the agent graph and returns its final
    text response. The graph was already built at startup -- this endpoint
    just invokes it against a real HTTP request.
    """
    graph = app_state["graph"]

    result = await graph.ainvoke({"messages": [HumanMessage(content=request.message)]})

    final_message = result["messages"][-1]

    return ChatResponse(reply=final_message.content)


@app.post("/update-resume", response_model=UpdateResumeResponse)
async def update_resume(file: UploadFile = File(...)) -> UpdateResumeResponse:
    """
    Handles a new resume upload: saves it, rebuilds the FAISS index on
    disk, then tells the already-running resume_matcher server to reload
    its in-memory copy. We only care that the reload call SUCCEEDS (no
    exception) -- if it fails, FastAPI correctly surfaces a 500 error,
    which is the honest signal that something went wrong.
    """
    contents = await file.read()
    with open(RESUME_PDF_PATH, "wb") as f:
        f.write(contents)

    build_index()

    tools = app_state["tools"]
    reload_tool = next(t for t in tools if t.name == "reload_resume_index")
    await reload_tool.ainvoke({})

    return UpdateResumeResponse(status="reloaded")


@app.get("/health")
async def health():
    """Confirms the server is running and the graph was built successfully."""
    return {"status": "ok", "graph_ready": "graph" in app_state}