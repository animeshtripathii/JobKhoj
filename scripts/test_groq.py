# test_groq.py
# Purpose: one-time sanity check that our Groq API key works
# and we can get a chat completion back. Nothing agentic yet —
# just confirming the wire is connected before we build on top of it.

import os
from dotenv import load_dotenv
from groq import Groq

# Loads variables from .env into the environment so os.getenv() can find them
load_dotenv()

# Groq's Python client reads the key either from the argument below
# or automatically from the GROQ_API_KEY env var. Being explicit here
# for clarity while we're learning.
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# chat.completions.create() is the same shape you'd see with OpenAI's API —
# Groq deliberately mirrors that interface so it's a near drop-in swap.
response = client.chat.completions.create(
    model="openai/gpt-oss-120b",  # the open model Groq is hosting for us
    messages=[
        {"role": "user", "content": "In one sentence, what is Groq known for?"}
    ],
)

# .choices[0].message.content is where the actual reply text lives
print(response.choices[0].message.content)