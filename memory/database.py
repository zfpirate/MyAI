
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "capri.db"


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH, factory=_ClosingConnection)
    connection.row_factory = sqlite3.Row

    return connection


def init_db():
    with get_connection() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    print("CAPRI MEMORY : base de données opérationnelle.")


def add_memory(content, category="general"):
    with get_connection() as db:
        db.execute(
            "INSERT INTO memories (content, category) VALUES (?, ?)",
            (content, category)
        )


def list_memories():
    with get_connection() as db:
        return db.execute(
            "SELECT * FROM memories ORDER BY id DESC"
        ).fetchall()


def delete_memory(memory_id):
    with get_connection() as db:
        cursor = db.execute(
            "DELETE FROM memories WHERE id = ?",
            (memory_id,)
        )
        return cursor.rowcount > 0


def list_projects():
    with get_connection() as db:
        return db.execute(
            "SELECT * FROM projects ORDER BY id DESC"
        ).fetchall()


def get_memory_context():
    memories = list_memories()
    projects = list_projects()

    lines = []

    for memory in memories[:30]:
        lines.append(
            f"- [{memory['category']}] {memory['content']}"
        )

    for project in projects[:20]:
        lines.append(
            f"- Projet : {project['name']} | "
            f"{project['description']} | Statut : {project['status']}"
        )

    return "\n".join(lines)
