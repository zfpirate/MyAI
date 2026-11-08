from memory.database import get_connection


def init_chat_history():
    """Crée la table de conversations si elle n'existe pas."""
    with get_connection() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def save_chat_message(role, content):
    """Enregistre un message utilisateur ou assistant."""
    if role not in ("user", "assistant"):
        raise ValueError("Rôle de message invalide.")

    with get_connection() as db:
        db.execute(
            "INSERT INTO chat_messages (role, content) VALUES (?, ?)",
            (role, content)
        )


def get_chat_history(limit=100):
    """Retourne les derniers messages dans l'ordre chronologique."""
    with get_connection() as db:
        rows = db.execute(
            """
            SELECT role, content
            FROM (
                SELECT id, role, content
                FROM chat_messages
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
            """,
            (limit,)
        ).fetchall()

    return [(row["role"], row["content"]) for row in rows]
