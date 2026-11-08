
"""Gestion sécurisée des applications Windows."""

import ctypes
import os
import subprocess
import time
from pathlib import Path
from ctypes import wintypes

from security.action_manager import register_action


# Applications que CAPRI a le droit de lancer et de suivre.
ALLOWED_APPLICATIONS = {
    "notepad": {
        "label": "Bloc-notes",
        "path": Path(os.environ["WINDIR"]) / "System32" / "notepad.exe",
        "process_names": {"notepad.exe"},
    },
    "calculator": {
        "label": "Calculatrice",
        "path": Path(os.environ["WINDIR"]) / "System32" / "calc.exe",
        "process_names": {"calculator.exe", "calculatorapp.exe"},
    },
}

# Fenêtres lancées et suivies par cette instance de CAPRI.
_RUNNING_WINDOWS = {}
# Fenêtres des applications découvertes et vérifiées du catalogue.
_RUNNING_CATALOG_WINDOWS = {}
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
WM_CLOSE = 0x0010


def validate_application_params(params):
    return (
        isinstance(params, dict)
        and set(params.keys()) == {"app_id"}
        and isinstance(params.get("app_id"), str)
        and params["app_id"] in ALLOWED_APPLICATIONS
    )


def get_window_process_id(hwnd):
    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(
        hwnd,
        ctypes.byref(process_id),
    )
    return process_id.value


def get_process_path(process_id):
    """Récupère le chemin de l'exécutable d'un processus."""
    handle = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION,
        False,
        process_id,
    )

    if not handle:
        return None

    try:
        buffer = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buffer))

        success = kernel32.QueryFullProcessImageNameW(
            handle,
            0,
            buffer,
            ctypes.byref(size),
        )

        if not success:
            return None

        return buffer.value

    finally:
        kernel32.CloseHandle(handle)



def get_visible_windows():
    """Retourne les fenêtres visibles et leurs identifiants."""

    windows = []

    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM,
    )

    def callback(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            process_id = get_window_process_id(hwnd)
            title_buffer = ctypes.create_unicode_buffer(512)

            user32.GetWindowTextW(
                hwnd,
                title_buffer,
                len(title_buffer),
            )

            windows.append({
                "hwnd": int(hwnd),
                "pid": process_id,
                "title": title_buffer.value,
            })

        return True

    callback = callback_type(callback)

    user32.EnumWindows.argtypes = [
        callback_type,
        wintypes.LPARAM,
    ]
    user32.EnumWindows.restype = wintypes.BOOL

    success = user32.EnumWindows(callback, 0)

    if not success:
        raise ctypes.WinError(ctypes.get_last_error())

    return windows


def register_catalog_window(app_id, hwnd, expected_path, label):
    """Enregistre une fenêtre dont l'exécutable a été vérifié."""

    if not user32.IsWindow(hwnd):
        raise RuntimeError("La fenêtre n'existe plus.")

    process_id = get_window_process_id(hwnd)
    actual_path = get_process_path(process_id)

    if not actual_path:
        raise PermissionError(
            "Impossible de vérifier l'exécutable de la fenêtre."
        )

    expected = os.path.normcase(os.path.abspath(expected_path))
    actual = os.path.normcase(os.path.abspath(actual_path))

    if expected != actual:
        raise PermissionError(
            "L'exécutable de la fenêtre ne correspond pas "
            "à celui qui a été autorisé."
        )

    entries = _RUNNING_CATALOG_WINDOWS.setdefault(app_id, [])

    if not any(entry["hwnd"] == int(hwnd) for entry in entries):
        entries.append({
            "hwnd": int(hwnd),
            "expected_path": expected,
            "label": label,
        })


def close_catalog_window(params):
    """Demande la fermeture normale d'une fenêtre suivie du catalogue."""

    app_id = params["app_id"]
    entries = _RUNNING_CATALOG_WINDOWS.get(app_id, [])

    while entries:
        entry = entries[-1]
        hwnd = entry["hwnd"]

        if not user32.IsWindow(hwnd):
            entries.pop()
            continue

        process_id = get_window_process_id(hwnd)
        actual_path = get_process_path(process_id)

        if not actual_path:
            entries.pop()
            continue

        actual = os.path.normcase(os.path.abspath(actual_path))

        if actual != entry["expected_path"]:
            entries.pop()
            continue

        success = user32.PostMessageW(
            hwnd,
            WM_CLOSE,
            0,
            0,
        )

        if not success:
            raise ctypes.WinError(ctypes.get_last_error())

        return {
            "application": entry["label"],
            "window_id": hwnd,
            "status": "close_requested",
        }

    raise RuntimeError(
        "CAPRI ne possède aucune fenêtre active et vérifiée "
        "pour cette application."
    )


def is_expected_application(hwnd, app_id):
    """Vérifie que la fenêtre appartient à l'application attendue."""
    if not user32.IsWindow(hwnd):
        return False

    process_id = get_window_process_id(hwnd)

    if not process_id:
        return False

    process_path = get_process_path(process_id)

    if not process_path:
        return False

    process_name = Path(process_path).name.lower()

    allowed_names = ALLOWED_APPLICATIONS[app_id]["process_names"]

    return process_name in allowed_names


def open_application(params):
    app_id = params["app_id"]
    application = ALLOWED_APPLICATIONS[app_id]
    executable = application["path"]

    if not executable.is_file():
        raise FileNotFoundError(
            f"Exécutable introuvable : {executable}"
        )

    # On mémorise les fenêtres existantes AVANT le lancement.
    previous_windows = {
        window["hwnd"]
        for window in get_visible_windows()
    }

    subprocess.Popen(
        [str(executable)],
        shell=False,
        cwd=str(executable.parent),
        close_fds=True,
    )

    # On cherche une nouvelle fenêtre appartenant à l'application.
    deadline = time.monotonic() + 10

    while time.monotonic() < deadline:
        for window in get_visible_windows():
            hwnd = window["hwnd"]

            if hwnd in previous_windows:
                continue

            if is_expected_application(hwnd, app_id):
                _RUNNING_WINDOWS.setdefault(app_id, []).append(hwnd)

                return {
                    "application": application["label"],
                    "window_id": hwnd,
                    "process_id": window["pid"],
                    "window_title": window["title"],
                    "status": "launched_and_tracked",
                }

        time.sleep(0.2)

    raise RuntimeError(
        "L'application a été lancée, mais CAPRI n'a pas réussi "
        "à identifier une nouvelle fenêtre. "
        "Aucune fermeture ne sera tentée."
    )


def get_running_applications():
    """Liste les fenêtres encore suivies et valides."""
    result = []

    for app_id, handles in _RUNNING_WINDOWS.items():
        for hwnd in handles:
            if is_expected_application(hwnd, app_id):
                result.append({
                    "app_id": app_id,
                    "window_id": hwnd,
                    "label": ALLOWED_APPLICATIONS[app_id]["label"],
                })

    return result


def close_application(params):
    app_id = params["app_id"]
    handles = _RUNNING_WINDOWS.get(app_id, [])

    # On ne ferme que la dernière fenêtre suivie par CAPRI.
    while handles:
        hwnd = handles[-1]

        if not user32.IsWindow(hwnd):
            handles.pop()
            continue

        if not is_expected_application(hwnd, app_id):
            handles.pop()
            continue

        # Demande une fermeture normale à CETTE fenêtre.
        success = user32.PostMessageW(
            hwnd,
            WM_CLOSE,
            0,
            0,
        )

        if not success:
            raise ctypes.WinError(ctypes.get_last_error())

        return {
            "application": ALLOWED_APPLICATIONS[app_id]["label"],
            "window_id": hwnd,
            "status": "close_requested",
        }

    raise RuntimeError(
        "CAPRI ne possède aucune fenêtre active et vérifiée "
        "pour cette application."
    )


def register_application_actions():
    register_action(
        action_id="applications.open",
        permission_id="apps.launch",
        handler=open_application,
        description="Ouvrir une application autorisée.",
        validator=validate_application_params,
    )

    register_action(
        action_id="applications.close",
        permission_id="apps.close",
        handler=close_application,
        description="Demander la fermeture normale d'une fenêtre "
                    "lancée par CAPRI.",
        validator=validate_application_params,
    )

