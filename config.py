# config.py
#
# Single source of truth for project-wide configuration.
# Nothing else in this codebase should call os.getenv() for these values,
# or create its own Groq client — everything imports from here instead.
# Why this matters: when Groq deprecates a model (like it just did to us),
# we fix ONE line in .env and every file in the project picks it up
# automatically, with zero code changes.

import os
from dotenv import load_dotenv
from groq import Groq

# Loads .env into the process environment. Safe to call multiple times
# across files — it's a no-op if already loaded, so no harm if graph.py
# also calls it.
load_dotenv()

# --- Model configuration ---
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# --- Database configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Shared Groq client ---
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# --- LangSmith tracing config ---
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "ai-job-search-copilot")