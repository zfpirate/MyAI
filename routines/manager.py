"""Stockage et exécution des routines de démarrage de CAPRI."""

import json
from contextlib import closing, contextmanager

from memory.database import get_connection


@contextmanager
def _connection():
    with closing(get_connection()) as db:
        with db:
            yield db


def init_routines():
    with _connection() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS routines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                trigger_type TEXT NOT NULL,
                app_ids TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def list_routines():
    init_routines()

    with _connection() as db:
        rows = db.execute("""
            SELECT id, name, trigger_type, app_ids, enabled, created_at
            FROM routines
            ORDER BY id DESC
        """).fetchall()

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "trigger_type": row["trigger_type"],
            "app_ids": json.loads(row["app_ids"]),
            "enabled": bool(row["enabled"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def save_startup_routine(name, app_ids):
    """Crée ou met à jour une routine de démarrage avec des apps du catalogue."""
    from actions.app_catalog import get_catalog_app

    if not isinstance(name, str) or not name.strip() or len(name) > 160:
        raise ValueError("Nom de routine invalide.")

    if (
        not isinstance(app_ids, (list, tuple))
        or not app_ids
        or len(app_ids) > 20
        or any(not isinstance(app_id, str) for app_id in app_ids)
    ):
        raise ValueError("La routine doit contenir de 1 à 20 applications.")

    unique_app_ids = list(dict.fromkeys(app_ids))
    for app_id in unique_app_ids:
        if get_catalog_app(app_id) is None:
            raise ValueError("Une application de cette routine est inconnue.")

    init_routines()
    with _connection() as db:
        db.execute("""
            INSERT INTO routines (name, trigger_type, app_ids, enabled)
            VALUES (?, 'startup', ?, 1)
            ON CONFLICT(name) DO UPDATE SET
                trigger_type = 'startup',
                app_ids = excluded.app_ids,
                enabled = 1
        """, (name.strip(), json.dumps(unique_app_ids)))

        row = db.execute(
            "SELECT id FROM routines WHERE name = ?",
            (name.strip(),),
        ).fetchone()

    return row["id"]


def delete_routine(routine_id):
    if not isinstance(routine_id, int) or isinstance(routine_id, bool):
        raise ValueError("Identifiant de routine invalide.")

    init_routines()
    with _connection() as db:
        cursor = db.execute(
            "DELETE FROM routines WHERE id = ?",
            (routine_id,),
        )
        return cursor.rowcount > 0


def set_routine_enabled(routine_id, enabled):
    if (
        not isinstance(routine_id, int)
        or isinstance(routine_id, bool)
        or not isinstance(enabled, bool)
    ):
        raise ValueError("Paramètres de routine invalides.")

    init_routines()
    with _connection() as db:
        cursor = db.execute(
            "UPDATE routines SET enabled = ? WHERE id = ?",
            (int(enabled), routine_id),
        )
        return cursor.rowcount > 0


def run_startup_routines():
    """Exécute séquentiellement les applications des routines activées."""
    from actions.catalog_launcher import register_catalog_launcher
    from security.action_manager import request_action

    register_catalog_launcher()
    results = []

    for routine in list_routines():
        if not routine["enabled"] or routine["trigger_type"] != "startup":
            continue

        routine_result = {
            "name": routine["name"],
            "applications": [],
        }

        for app_id in routine["app_ids"]:
            action_result = request_action(
                "applications.open_catalog",
                {"app_id": app_id},
                details=(
                    f"Routine « {routine['name']} » au démarrage de CAPRI"
                ),
            )

            if action_result["status"] == "success":
                launch_result = action_result["result"]
                routine_result["applications"].append({
                    "app_id": app_id,
                    "status": launch_result.get("status", "opened"),
                    "message": "",
                })
            else:
                routine_result["applications"].append({
                    "app_id": app_id,
                    "status": action_result["status"],
                    "message": action_result.get(
                        "message",
                        "L'action n'a pas été autorisée automatiquement.",
                    ),
                })

        results.append(routine_result)

    return results
