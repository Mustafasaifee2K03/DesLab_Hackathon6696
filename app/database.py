import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "recommendation.db"


def _dict_factory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = _dict_factory
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS content_items (
                id TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                tags TEXT NOT NULL,
                language TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                source TEXT NOT NULL,
                url TEXT NOT NULL,
                creator TEXT NOT NULL,
                published_at TEXT NOT NULL,
                popularity REAL NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                interests TEXT NOT NULL,
                languages TEXT NOT NULL,
                moods TEXT NOT NULL,
                demand_text TEXT NOT NULL DEFAULT '',
                domain_weights TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                content_id TEXT NOT NULL,
                action TEXT NOT NULL,
                ts TEXT NOT NULL,
                FOREIGN KEY(content_id) REFERENCES content_items(id)
            )
            """
        )

        # Lightweight migration for databases created before demand_text existed.
        columns = {
            row["name"]
            for row in cursor.execute("PRAGMA table_info(user_profiles)").fetchall()
        }
        if "demand_text" not in columns:
            cursor.execute(
                "ALTER TABLE user_profiles ADD COLUMN demand_text TEXT NOT NULL DEFAULT ''"
            )


def content_count() -> int:
    with get_connection() as conn:
        result = conn.execute("SELECT COUNT(*) AS count FROM content_items").fetchone()
        return int(result["count"])


def insert_content_items(items: list[dict[str, Any]]) -> None:
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO content_items (
                id, domain, title, description, tags, language,
                duration_minutes, source, url, creator, published_at, popularity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["id"],
                    item["domain"],
                    item["title"],
                    item["description"],
                    json.dumps(item["tags"]),
                    item["language"],
                    item["duration_minutes"],
                    item["source"],
                    item["url"],
                    item["creator"],
                    item["published_at"],
                    item["popularity"],
                )
                for item in items
            ],
        )


def get_all_content() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM content_items ORDER BY published_at DESC"
        ).fetchall()
    for row in rows:
        row["tags"] = json.loads(row["tags"])
    return rows


def upsert_user_profile(profile: dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_profiles (
                user_id, name, interests, languages, moods, demand_text, domain_weights, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name = excluded.name,
                interests = excluded.interests,
                languages = excluded.languages,
                moods = excluded.moods,
                demand_text = excluded.demand_text,
                domain_weights = excluded.domain_weights,
                updated_at = excluded.updated_at
            """,
            (
                profile["user_id"],
                profile["name"],
                json.dumps(profile["interests"]),
                json.dumps(profile["languages"]),
                json.dumps(profile["moods"]),
                profile.get("demand_text", ""),
                json.dumps(profile["domain_weights"]),
                profile["updated_at"],
            ),
        )


def get_user_profile(user_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
    if not row:
        return None
    row["interests"] = json.loads(row["interests"])
    row["languages"] = json.loads(row["languages"])
    row["moods"] = json.loads(row["moods"])
    row["demand_text"] = row.get("demand_text", "") or ""
    row["domain_weights"] = json.loads(row["domain_weights"])
    return row


def insert_feedback(user_id: str, content_id: str, action: str, ts: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO user_feedback (user_id, content_id, action, ts) VALUES (?, ?, ?, ?)",
            (user_id, content_id, action, ts),
        )


def get_feedback(user_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM user_feedback WHERE user_id = ? ORDER BY ts DESC", (user_id,)
        ).fetchall()


def get_feedback_with_content(user_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT f.action, f.ts, c.id AS content_id, c.domain, c.tags
            FROM user_feedback f
            JOIN content_items c ON c.id = f.content_id
            WHERE f.user_id = ?
            ORDER BY f.ts DESC
            """,
            (user_id,),
        ).fetchall()
    for row in rows:
        row["tags"] = json.loads(row["tags"])
    return rows


def get_hidden_or_disliked_ids(user_id: str) -> set[str]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT content_id
            FROM user_feedback
            WHERE user_id = ? AND action IN ('hide', 'dislike')
            """,
            (user_id,),
        ).fetchall()
    return {row["content_id"] for row in rows}


def get_saved_ids(user_id: str) -> set[str]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT content_id
            FROM user_feedback
            WHERE user_id = ? AND action = 'save'
            """,
            (user_id,),
        ).fetchall()
    return {row["content_id"] for row in rows}


def count_content_for_filters(languages: list[str], domain: str | None = None) -> int:
    query = "SELECT COUNT(*) AS count FROM content_items"
    conditions: list[str] = []
    params: list[Any] = []

    if domain:
        conditions.append("domain = ?")
        params.append(domain)

    if languages:
        placeholders = ", ".join(["?"] * len(languages))
        conditions.append(f"language IN ({placeholders})")
        params.extend(languages)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    with get_connection() as conn:
        row = conn.execute(query, tuple(params)).fetchone()
    return int(row["count"])


def content_language_breakdown(domain: str | None = None) -> dict[str, int]:
    if domain:
        query = (
            "SELECT language, COUNT(*) AS count FROM content_items "
            "WHERE domain = ? GROUP BY language"
        )
        params: tuple[Any, ...] = (domain,)
    else:
        query = "SELECT language, COUNT(*) AS count FROM content_items GROUP BY language"
        params = ()

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    return {row["language"]: int(row["count"]) for row in rows}


def purge_seed_content() -> int:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM content_items WHERE id NOT LIKE 'live_%'")
        return int(cursor.rowcount or 0)
