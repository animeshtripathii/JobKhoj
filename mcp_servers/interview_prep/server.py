# mcp_servers/interview_prep/server.py
#
# Generates interview prep questions grounded in the SPECIFIC resume chunks
# that matched a given JD (typically the output of resume_matcher's
# score_match tool) — not generic questions pulled from thin air. This is
# the same "retrieve first, generate second" principle as Day 5, just
# applied to question generation instead of match explanation.

import json
from typing import List

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from config import groq_client, GROQ_MODEL

mcp = FastMCP("InterviewPrepServer")


class InterviewQuestion(BaseModel):
    question: str = Field(..., description="The interview question itself.")
    tests_for: str = Field(..., description="One line on what this question is really probing for.")
    key_concepts: str = Field(..., description="2-3 core points a strong answer should cover.")
    resume_tie_in: str = Field(..., description="How to connect the answer to the candidate's specific resume/experience.")


class InterviewPrepResult(BaseModel):
    questions: List[InterviewQuestion]


@mcp.tool()
def generate_interview_prep(jd_text: str, matched_resume_chunks: List[str]) -> InterviewPrepResult:
    """
    Generates 6-8 interview prep questions for a given job description,
    grounded in the candidate's specific matched resume experience.
    Typically called after score_match, using its returned
    top_matching_chunks as the matched_resume_chunks input here.
    """
    chunks_text = "\n".join(f"- {c}" for c in matched_resume_chunks)

    # Note the STRUCTURED OUTPUT instruction: we ask Groq to return JSON
    # matching our exact schema. This is the same "structured generation"
    # idea from earlier, but this time we're relying on prompt instructions
    # rather than a tool-calling mechanism to get JSON back (Groq's chat
    # API doesn't enforce a schema the way our Pydantic return type does --
    # WE have to ask for it clearly, and validate/parse it ourselves).
    prompt = f"""You are an interview coach helping a candidate prepare for a job interview.

Job description:
{jd_text}

Candidate's relevant resume points (already matched to this JD):
{chunks_text}

Generate 6 to 8 realistic interview questions a candidate should expect for
this role, based on the job description. Mix technical/concept questions
with project-specific questions tied to the resume points above.

For EACH question, provide:
- "question": the interview question itself
- "tests_for": one line on what the interviewer is really probing for
- "key_concepts": 2-3 core points a strong answer should cover (brief, not an essay)
- "resume_tie_in": how the candidate should connect their answer to the
  SPECIFIC resume points above (reference them concretely, don't invent
  experience not shown there)

Respond with ONLY a JSON array of objects with exactly these 4 keys.
No other text, no markdown formatting, just the raw JSON array."""

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.choices[0].message.content

    # Groq sometimes wraps JSON in markdown code fences (```json ... ```)
    # even when asked not to -- stripping these defensively before parsing.
    cleaned = raw_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    # json.loads turns the raw JSON string Groq returned into actual Python
    # data (a list of dicts) -- this is the step that could fail if Groq
    # didn't follow instructions perfectly, which is why real systems often
    # add retry logic here (see interview angle notes below).
    questions_data = json.loads(cleaned)

    # Pydantic validates each dict against InterviewQuestion's schema --
    # if Groq's output is missing a field or has the wrong type, this
    # raises a clear error here rather than silently passing bad data on.
    questions = [InterviewQuestion(**q) for q in questions_data]

    return InterviewPrepResult(questions=questions)


if __name__ == "__main__":
    mcp.run()