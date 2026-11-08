
"""Catalogue persistant et filtré des applications Windows."""

import os
import hashlib
import unicodedata
from pathlib import Path

from memory.database import get_connection


START_MENU_LOCATIONS = [
    Path(os.environ["PROGRAMDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
]

BLOCKED_NAMES = (
    "desinstaller", "uninstall", "command prompt",
    "powershell", "registry editor", "git cmd",
    "git bash", "terminal", "firmware", "recovery",
    "firewall", "task scheduler", "services",
    "administrative tools", "component services",
)

BLOCKED_FOLDERS = ("administrative tools", "system tools")


def normalize(text):
    text = unicodedata.normalize("NFD", text.casefold())
    return "".join(
        char for char in text
        if unicodedata.category(char) != "Mn"
    ).strip()


def init_app_catalog():
    with get_connection() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS app_catalog (
                app_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                shortcut_path TEXT NOT NULL UNIQUE,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def make_app_id(path):
    return hashlib.sha256(
        str(path).lower().encode("utf-8")
    ).hexdigest()[:16]


def is_safe_shortcut(name, path):
    normalized_name = normalize(name)
    normalized_path = normalize(path)

    if any(word in normalized_name for word in BLOCKED_NAMES):
        return False

    if any(folder in normalized_path for folder in BLOCKED_FOLDERS):
        return False

    return True


def scan_installed_apps():
    init_app_catalog()
    discovered = {}

    for folder in START_MENU_LOCATIONS:
        if not folder.is_dir():
            continue

        for shortcut in folder.rglob("*.lnk"):
            name = shortcut.stem.strip()
            path = str(shortcut.resolve())

            if not name or not is_safe_shortcut(name, path):
                continue

            app_id = make_app_id(path)

            discovered[app_id] = {
                "name": name,
                "path": path,
            }

    builtins = {
        "notepad": ("Bloc-notes", "builtin://notepad"),
        "calculator": ("Calculatrice", "builtin://calculator"),
    }

    for app_id, (name, path) in builtins.items():
        discovered[app_id] = {
            "name": name,
            "path": path,
        }

    with get_connection() as db:
        for app_id, app in discovered.items():
            db.execute("""
                INSERT INTO app_catalog
                    (app_id, name, shortcut_path, last_seen)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(app_id) DO UPDATE SET
                    name = excluded.name,
                    shortcut_path = excluded.shortcut_path,
                    last_seen = CURRENT_TIMESTAMP
            """, (
                app_id,
                app["name"],
                app["path"],
            ))

    return len(discovered)


def get_catalog_apps():
    init_app_catalog()

    with get_connection() as db:
        rows = db.execute("""
            SELECT app_id, name, shortcut_path
            FROM app_catalog
            ORDER BY name COLLATE NOCASE
        """).fetchall()

    unique = {}

    for row in rows:
        name = row["name"]
        path = row["shortcut_path"]

        if not is_safe_shortcut(name, path):
            continue

        key = normalize(name)

        candidate = {
            "app_id": row["app_id"],
            "name": name,
            "shortcut_path": path,
        }

        if (
            key not in unique
            or len(path) < len(unique[key]["shortcut_path"])
        ):
            unique[key] = candidate

    return sorted(
        unique.values(),
        key=lambda app: app["name"].casefold()
    )


def search_catalog_apps(query):
    query = normalize(query)

    if not query:
        return []

    return [
        app for app in get_catalog_apps()
        if query in normalize(app["name"])
    ]


def get_catalog_app(app_id):
    init_app_catalog()

    with get_connection() as db:
        row = db.execute("""
            SELECT app_id, name, shortcut_path
            FROM app_catalog
            WHERE app_id = ?
        """, (app_id,)).fetchone()

    if row is None:
        return None

    app = {
        "app_id": row["app_id"],
        "name": row["name"],
        "shortcut_path": row["shortcut_path"],
    }

    if not is_safe_shortcut(app["name"], app["shortcut_path"]):
        return None

    return app
