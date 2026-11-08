
from memory.database import get_connection


def add_project(name, description=""):
    try:
        with get_connection() as db:
            db.execute(
                """
                INSERT INTO projects (name, description)
                VALUES (?, ?)
                """,
                (name, description)
            )
        return True

    except Exception as error:
        print(f"Erreur projet : {error}")
        return False


def get_projects():
    with get_connection() as db:
        return db.execute(
            "SELECT * FROM projects ORDER BY id DESC"
        ).fetchall()
