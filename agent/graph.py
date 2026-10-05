# agent/graph.py
#
# The full agentic loop: connects to our 5 MCP servers, binds their
# tools to a Groq-backed LLM via LangChain, and builds a LangGraph that
# lets the LLM autonomously decide whether to call a tool or respond
# directly -- looping back after each tool call until it's ready to answer.
#
# UPDATED: build_graph() now returns both the compiled graph AND the raw
# tools list, since backend/main.py's /update-resume endpoint needs to
# call reload_resume_index DIRECTLY (deterministically, every upload) --
# not via LLM reasoning, which is what invoking the compiled graph would do.

import asyncio
import os
import sys

from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, MessagesState, END
from langgraph.prebuilt import ToolNode

from config import GROQ_MODEL


async def build_graph():
    """
    Async because connecting to MCP servers requires awaiting their startup
    and handshake. Returns (compiled_graph, tools) -- the graph for normal
    conversational use, and the raw tools list for direct, deterministic
    tool invocation when needed (e.g., resume reload after an upload).
    """
    client = MultiServerMCPClient({
        "resume_matcher": {
            "command": sys.executable,
            "args": ["-m", "mcp_servers.resume_matcher.server"],
            "transport": "stdio",
        },
        "application_tracker": {
            "command": sys.executable,
            "args": ["-m", "mcp_servers.application_tracker.server"],
            "transport": "stdio",
        },
        "interview_prep": {
            "command": sys.executable,
            "args": ["-m", "mcp_servers.interview_prep.server"],
            "transport": "stdio",
        },
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", os.path.abspath("data")],
            "transport": "stdio",
        },
        "fetch": {
            "command": sys.executable,
            "args": ["-m", "mcp_server_fetch"],
            "transport": "stdio",
        },
    })

    all_tools = await client.get_tools()

    # Trim Filesystem's large tool set down to just what's genuinely useful
    # here, to avoid the token-bloat/413 issue from Day 8 Part 4. Note:
    # reload_resume_index is a resume_matcher tool, so it's NOT filtered
    # out here -- but we deliberately do NOT bind it to the LLM below,
    # since it should only ever be triggered deterministically by the
    # /update-resume endpoint, never by LLM judgment.
    FILESYSTEM_TOOLS_TO_KEEP = {"read_text_file", "list_directory"}
    filesystem_tool_names = {
        "read_file", "read_text_file", "read_media_file", "read_multiple_files",
        "write_file", "edit_file", "create_directory", "list_directory",
        "list_directory_with_sizes", "directory_tree", "move_file",
        "search_files", "get_file_info", "list_allowed_directories",
    }

    def should_keep(tool):
        if tool.name in filesystem_tool_names:
            return tool.name in FILESYSTEM_TOOLS_TO_KEEP
        return True

    all_tools = [t for t in all_tools if should_keep(t)]

    # The LLM should never autonomously decide to reload the resume index --
    # that's a deterministic action tied to a specific upload event, not a
    # conversational judgment call. Exclude it from what's bound to the LLM,
    # but keep it in the returned tools list so /update-resume can call it
    # directly.
    llm_facing_tools = [t for t in all_tools if t.name != "reload_resume_index"]

    print(f"Connected. {len(llm_facing_tools)} tools bound to the LLM: {[t.name for t in llm_facing_tools]}")

    llm = ChatGroq(model=GROQ_MODEL, api_key=os.getenv("GROQ_API_KEY"))
    llm_with_tools = llm.bind_tools(llm_facing_tools)

    async def call_model(state: MessagesState) -> dict:
        response = await llm_with_tools.ainvoke(state["messages"])
        return {"messages": [response]}

    def should_continue(state: MessagesState) -> str:
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tools"
        return END

    tool_node = ToolNode(llm_facing_tools)

    graph_builder = StateGraph(MessagesState)
    graph_builder.add_node("agent", call_model)
    graph_builder.add_node("tools", tool_node)
    graph_builder.set_entry_point("agent")

    graph_builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph_builder.add_edge("tools", "agent")

    compiled_graph = graph_builder.compile()

    # Return BOTH: the compiled graph for normal chat, and the full tools
    # list (including reload_resume_index) for direct invocation elsewhere.
    return compiled_graph, all_tools


async def main():
    graph, _tools = await build_graph()

    user_message = (
        "Here's a job description: 'Looking for an AI Engineer with "
        "experience in LLMs, RAG, LangChain, and AWS cloud deployment.' "
        "How well does my resume match this role?"
    )

    result = await graph.ainvoke({"messages": [HumanMessage(content=user_message)]})

    print("\n--- FULL CONVERSATION ---")
    for msg in result["messages"]:
        print(f"\n[{msg.type}]: {msg.content}")
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            print(f"  -> Tool calls requested: {[tc['name'] for tc in msg.tool_calls]}")


if __name__ == "__main__":
    asyncio.run(main())