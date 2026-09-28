import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB_PATH = DATA / "jansetu.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS districts (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    state TEXT NOT NULL,
    lang TEXT NOT NULL,
    pop INTEGER NOT NULL,
    rural REAL NOT NULL,
    literacy REAL NOT NULL,
    deprivation REAL NOT NULL,
    voice REAL NOT NULL,
    infra_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS investments (
    id INTEGER PRIMARY KEY,
    district_id INTEGER NOT NULL,
    sector TEXT NOT NULL,
    scheme TEXT NOT NULL,
    allocated_cr REAL NOT NULL,
    spent_cr REAL NOT NULL,
    fy TEXT NOT NULL,
    UNIQUE(district_id, sector)
);

CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY,
    ref TEXT UNIQUE NOT NULL,
    district_id INTEGER NOT NULL,
    channel TEXT NOT NULL,
    language TEXT NOT NULL,
    sector TEXT NOT NULL,
    severity INTEGER NOT NULL,
    confidence REAL NOT NULL,
    body TEXT NOT NULL,
    gloss TEXT NOT NULL,
    signals TEXT NOT NULL,
    status TEXT NOT NULL,
    phone_last4 TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_requests_district ON requests(district_id, sector);
CREATE INDEX IF NOT EXISTS idx_requests_created ON requests(created_at);
"""


def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute("SELECT COUNT(*) AS n FROM districts").fetchone()["n"]
        if count == 0:
            from jansetu.seed import seed

            seed(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)
