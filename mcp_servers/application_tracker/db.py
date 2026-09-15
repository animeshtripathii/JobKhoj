# mcp_servers/application_tracker/db.py
#
# PostgreSQL (Neon) version — replaces the original SQLite implementation.
# Uses psycopg2 with the DATABASE_URL from environment. All SQL placeholder
# syntax changed from SQLite's ? to psycopg2's %s. The table schema is
# otherwise identical; AUTOINCREMENT becomes SERIAL in Postgres.

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection() -> psycopg2.extensions.connection:
    """
    Opens a connection to the PostgreSQL database via DATABASE_URL.
    psycopg2 parses the full connection string including sslmode and
    channel_binding parameters required by Neon.
    """
    return psycopg2.connect(DATABASE_URL)


def initialize_db():
    """
    Creates the applications table if it doesn't already exist.
    Safe to call every time the server starts — IF NOT EXISTS means
    this won't error out or wipe existing data on repeated runs.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id SERIAL PRIMARY KEY,
            company TEXT NOT NULL,
            role TEXT NOT NULL,
            jd_text TEXT DEFAULT '',
            match_score REAL,
            matched_chunks TEXT DEFAULT '[]',
            status TEXT NOT NULL,
            date_applied TEXT NOT NULL,
            date_updated TEXT NOT NULL
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()


if __name__ == "__main__":
    initialize_db()
    print("PostgreSQL (Neon) database initialized.")