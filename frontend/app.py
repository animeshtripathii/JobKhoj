# frontend/app.py
#
# Streamlit chat UI for the AI Job Search Copilot, plus a sidebar action
# for updating the stored resume. Runs as a completely separate process
# from the FastAPI backend -- knows nothing about LangGraph/MCP, only how
# to call the backend's HTTP endpoints (/chat, /update-resume, /health).

import os

import requests
import streamlit as st

# Configurable via environment variable — docker-compose sets this to
# http://backend:8000 so the frontend container can reach the backend container.
# Falls back to localhost for local development.
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="AI Job Search Copilot", page_icon="\U0001F4BC")
st.title("AI Job Search Copilot")

# --- Backend health check, shown before the chat UI ---
# The backend has a real, ~50-60s one-time startup cost (connecting to all
# 5 MCP servers). This check prevents the UI from looking "broken" if
# opened before the backend has finished starting.
try:
    health = requests.get(f"{BACKEND_URL}/health", timeout=3)
    backend_ready = health.ok and health.json().get("graph_ready", False)
except requests.exceptions.RequestException:
    backend_ready = False

if not backend_ready:
    st.warning(
        "Backend not ready yet. Make sure `uvicorn backend.main:app` is "
        "running in another terminal, and wait for its startup to finish "
        "(check that terminal for 'Startup complete')."
    )
    st.stop()

# --- Sidebar: Update Resume action ---
with st.sidebar:
    st.header("Resume")
    uploaded_file = st.file_uploader("Upload a new resume (PDF)", type=["pdf"])

    if uploaded_file is not None:
        if st.button("Update Resume"):
            with st.spinner("Processing new resume (extracting, chunking, embedding)..."):
                try:
                    # requests' multipart/form-data upload format -- matches
                    # what FastAPI's UploadFile expects on the other end.
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    response = requests.post(f"{BACKEND_URL}/update-resume", files=files, timeout=90)
                    response.raise_for_status()
                    st.success("Resume updated successfully!")
                except requests.exceptions.RequestException as e:
                    st.error(f"Failed to update resume: {e}. If this was a timeout, try again — it may just have been a slow moment.")

# --- Chat history, kept in Streamlit's session state ---
# Streamlit re-runs this whole script on every interaction -- session_state
# is what makes the conversation history survive across those re-runs.
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if user_input := st.chat_input("Ask about a job description, your applications, or interview prep..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(
                    f"{BACKEND_URL}/chat",
                    json={"message": user_input},
                    timeout=120,
                )
                response.raise_for_status()
                reply = response.json()["reply"]
            except requests.exceptions.RequestException as e:
                reply = f"Error reaching the backend: {e}"

        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})