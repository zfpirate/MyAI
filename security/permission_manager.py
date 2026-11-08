
from memory.database import get_connection
from security.permissions import (
    PERMISSIONS,
    VALID_MODES,
    ALLOW,
    CONFIRM,
    DENY,
)


def init_permissions():
    """Crée la table et initialise les permissions manquantes."""

    with get_connection() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS permissions (
                permission_id TEXT PRIMARY KEY,
                mode TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        for permission_id, config in PERMISSIONS.items():
            db.execute(
                """
                INSERT OR IGNORE INTO permissions
                (permission_id, mode)
                VALUES (?, ?)
                """,
                (permission_id, config["default"]),
            )


def get_permission_mode(permission_id):
    """Récupère le mode actuel d'une permission."""

    if permission_id not in PERMISSIONS:
        return DENY

    init_permissions()

    with get_connection() as db:
        row = db.execute(
            "SELECT mode FROM permissions WHERE permission_id = ?",
            (permission_id,),
        ).fetchone()

    if row is None or row["mode"] not in VALID_MODES:
        return DENY

    return row["mode"]


def set_permission_mode(permission_id, mode):
    """Modifie une permission connue."""

    if permission_id not in PERMISSIONS:
        return False

    if mode not in VALID_MODES:
        return False

    init_permissions()

    with get_connection() as db:
        db.execute(
            """
            UPDATE permissions
            SET mode = ?, updated_at = CURRENT_TIMESTAMP
            WHERE permission_id = ?
            """,
            (mode, permission_id),
        )

    return True


def get_all_permissions():
    """Récupère toutes les permissions."""

    init_permissions()

    with get_connection() as db:
        rows = db.execute(
            "SELECT permission_id, mode FROM permissions"
        ).fetchall()

    modes = {
        row["permission_id"]: row["mode"]
        for row in rows
    }

    result = []

    for permission_id, config in PERMISSIONS.items():
        mode = modes.get(permission_id, DENY)

        if mode not in VALID_MODES:
            mode = DENY

        result.append({
            "id": permission_id,
            "label": config["label"],
            "description": config["description"],
            "mode": mode,
        })

    return result


def check_permission(permission_id):
    """Vérifie si une action est autorisée ou nécessite une confirmation."""

    if permission_id not in PERMISSIONS:
        return "denied"

    mode = get_permission_mode(permission_id)

    if mode == ALLOW:
        return "allowed"

    if mode == CONFIRM:
        return "needs_confirmation"

    return "denied"


def authorize_action(permission_id, details=""):
    """
    Autorise uniquement les actions en mode ALLOW.
    Une confirmation utilisateur sera gérée séparément par l'interface.
    """

    from security.activity_log import log_activity

    decision = check_permission(permission_id)

    if decision == "allowed":
        log_activity(permission_id, "allowed", details)
        return True

    if decision == "needs_confirmation":
        log_activity(
            permission_id,
            "needs_confirmation",
            details,
        )
        return False

    log_activity(permission_id, "denied", details)
    return False
