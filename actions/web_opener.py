"""Ouverture contrôlée de sites Internet."""

import subprocess
import webbrowser
from urllib.parse import urlsplit

from actions.app_catalog import get_catalog_app
from actions.catalog_launcher import verify_shortcut
from security.action_manager import (
    register_action,
    list_actions,
)


ALLOWED_BROWSERS = {
    "microsoft edge",
    "google chrome",
    "mozilla firefox",
    "opera",
    "opera gx",
    "brave",
}

MAX_URL_LENGTH = 2048


def validate_url(url):
    """Vérifie qu'une adresse HTTP ou HTTPS est valide."""

    if not isinstance(url, str):
        return False

    if not url or len(url) > MAX_URL_LENGTH:
        return False

    if url != url.strip():
        return False

    if any(ord(char) < 32 or ord(char) == 127 for char in url):
        return False

    if "\\" in url or any(char.isspace() for char in url):
        return False

    try:
        parts = urlsplit(url)

        if parts.scheme.lower() not in {"http", "https"}:
            return False

        if not parts.hostname:
            return False

        if parts.username is not None or parts.password is not None:
            return False

        # Vérifie également que le port est valide.
        if parts.port is not None:
            if not 1 <= parts.port <= 65535:
                return False

        return True

    except (ValueError, TypeError):
        return False


def validate_web_params(params):
    """Valide les paramètres de l'action."""

    if not isinstance(params, dict):
        return False

    if set(params.keys()) not in (
        {"url"},
        {"url", "browser_app_id"},
    ):
        return False

    if not validate_url(params.get("url")):
        return False

    browser_id = params.get("browser_app_id")

    if browser_id is not None:
        if not isinstance(browser_id, str):
            return False

        if not browser_id or len(browser_id) > 128:
            return False

    return True


def open_website(params):
    """Ouvre une adresse dans le navigateur demandé."""

    url = params["url"]
    browser_id = params.get("browser_app_id")

    if not validate_url(url):
        raise ValueError("Adresse Internet invalide ou non autorisée.")

    # Aucun navigateur précisé : navigateur par défaut.
    if browser_id is None:
        success = webbrowser.open(
            url,
            new=2,
            autoraise=True,
        )

        if not success:
            raise RuntimeError(
                "Impossible d'ouvrir le navigateur par défaut."
            )

        return {
            "status": "opened",
            "url": url,
            "browser": "Navigateur par défaut",
        }

    # Navigateur explicitement demandé.
    app = get_catalog_app(browser_id)

    if app is None:
        raise ValueError("Navigateur absent du catalogue CAPRI.")

    browser_name = app["name"].strip().casefold()

    if browser_name not in ALLOWED_BROWSERS:
        raise PermissionError(
            "Cette application n'est pas reconnue comme navigateur autorisé."
        )

    shortcut_path = app["shortcut_path"]

    inspected, signature = verify_shortcut(
        shortcut_path,
        app["name"],
    )

    process = subprocess.Popen(
        [
            str(inspected["target"]),
            *inspected["arguments"],
            url,
        ],
        shell=False,
        cwd=str(inspected["working_directory"]),
        close_fds=True,
    )

    return {
        "status": "opened",
        "url": url,
        "browser": app["name"],
        "process_id": process.pid,
        "publisher": signature["publisher"],
    }


def register_web_opener():
    """Enregistre l'action d'ouverture Internet."""

    existing = {
        action["id"]
        for action in list_actions()
    }

    if "web.open" in existing:
        return

    register_action(
        action_id="web.open",
        permission_id="web.open",
        handler=open_website,
        description="Ouvrir une adresse Internet validée.",
        validator=validate_web_params,
    )