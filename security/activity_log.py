
from memory.database import get_connection


def init_activity_log():
    """Crée la table du journal si elle n'existe pas."""

    with get_connection() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                permission_id TEXT NOT NULL,
                result TEXT NOT NULL,
                details TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def log_activity(permission_id, result, details=""):
    """Enregistre une décision de sécurité."""

    init_activity_log()

    with get_connection() as db:
        db.execute(
            """
            INSERT INTO activity_log
            (permission_id, result, details)
            VALUES (?, ?, ?)
            """,
            (permission_id, result, details[:1000]),
        )


def get_recent_activity(limit=50):
    """Récupère les dernières activités."""

    safe_limit = max(1, min(int(limit), 200))

    init_activity_log()

    with get_connection() as db:
        return db.execute(
            """
            SELECT id, permission_id, result, details, created_at
            FROM activity_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
