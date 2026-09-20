# mcp_servers/application_tracker/server.py
#
# Exposes the applications table as 3 MCP tools: log a new application,
# update an existing one's status, and query/list applications.
# All database access goes through parameterized queries to avoid SQL
# injection, even though our only "attacker" here is unpredictable
# LLM-generated text rather than a malicious human.

import json
from datetime import date
from typing import List, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from mcp_servers.application_tracker.db import get_connection, initialize_db

mcp = FastMCP("ApplicationTrackerServer")

# Ensure the table exists every time this server starts — safe to call
# repeatedly thanks to IF NOT EXISTS in the CREATE TABLE statement.
initialize_db()

VALID_STATUSES = ["Applied", "Screening", "Interview", "Offer", "Rejected"]


# --- Structured input/output schemas ---
class ApplicationRecord(BaseModel):
    id: int
    company: str
    role: str
    match_score: Optional[float] = None
    status: str
    date_applied: str
    date_updated: str


# A SEPARATE class, defined AFTER ApplicationRecord (since it references
# it) — this wraps a list of ApplicationRecord objects, ensuring
# get_applications always returns exactly ONE valid JSON object, even
# when the list itself is empty. This was the actual fix from before;
# it just needed to be its own class, not a field bolted onto
# ApplicationRecord.
class ApplicationListResult(BaseModel):
    applications: List[ApplicationRecord]


@mcp.tool()
def log_application(
    company: str,
    role: str,
    jd_text: str = "",
    match_score: Optional[float] = None,
    matched_chunks: Optional[List[str]] = None,
) -> ApplicationRecord:
    """
    Logs a new job application. Call this after analyzing a job description,
    typically right after score_match has produced a match score and
    matching resume chunks for this JD.
    """
    today = date.today().isoformat()

    chunks_json = json.dumps(matched_chunks or [])

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO applications
            (company, role, jd_text, match_score, matched_chunks, status, date_applied, date_updated)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (company, role, jd_text, match_score, chunks_json, "Applied", today, today),
    )
    new_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()

    return ApplicationRecord(
        id=new_id,
        company=company,
        role=role,
        match_score=match_score,
        status="Applied",
        date_applied=today,
        date_updated=today,
    )


@mcp.tool()
def update_status(application_id: int, new_status: str) -> ApplicationRecord:
    """
    Updates the status of an existing application (e.g., when the user
    mentions they got an interview or were rejected). Automatically
    records today's date as the update timestamp.
    """
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{new_status}'. Must be one of: {VALID_STATUSES}")

    today = date.today().isoformat()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE applications SET status = %s, date_updated = %s WHERE id = %s",
        (new_status, today, application_id),
    )
    conn.commit()

    cursor.execute(
        "SELECT id, company, role, match_score, status, date_applied, date_updated FROM applications WHERE id = %s",
        (application_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row is None:
        raise ValueError(f"No application found with id {application_id}")

    return ApplicationRecord(
        id=row[0], company=row[1], role=row[2], match_score=row[3],
        status=row[4], date_applied=row[5], date_updated=row[6],
    )


@mcp.tool()
def get_applications(status_filter: Optional[str] = None) -> ApplicationListResult:
    """
    Lists tracked applications, optionally filtered by status
    (e.g., only 'Interview' stage applications).
    """
    conn = get_connection()
    cursor = conn.cursor()

    if status_filter:
        cursor.execute(
            "SELECT id, company, role, match_score, status, date_applied, date_updated FROM applications WHERE status = %s",
            (status_filter,),
        )
    else:
        cursor.execute(
            "SELECT id, company, role, match_score, status, date_applied, date_updated FROM applications"
        )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    applications = [
        ApplicationRecord(
            id=r[0], company=r[1], role=r[2], match_score=r[3],
            status=r[4], date_applied=r[5], date_updated=r[6],
        )
        for r in rows
    ]

    return ApplicationListResult(applications=applications)


if __name__ == "__main__":
    mcp.run()