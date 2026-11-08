
"""Lancement contrôlé des applications Windows découvertes."""

import ctypes
import os
import subprocess
import time
from pathlib import Path
from ctypes import wintypes

import win32com.client

from actions.app_catalog import get_catalog_app, START_MENU_LOCATIONS
from actions.applications import (
    open_application,
    get_visible_windows,
    is_trackable_application_window,
    get_process_path,
    is_catalog_process_path,
    verify_catalog_process,
    show_tracked_window,
    register_catalog_window,
    close_catalog_window,
)
from security.app_allowlist import ALLOWED_BUILTINS
from security.signature_verifier import verify_authenticode
from security.action_manager import register_action, list_actions


# Programmes pouvant exécuter des commandes, scripts ou opérations système.
BLOCKED_TARGET_NAMES = {
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "wscript.exe",
    "cscript.exe",
    "mshta.exe",
    "regedit.exe",
    "reg.exe",
    "rundll32.exe",
    "shutdown.exe",
    "format.com",
    "diskpart.exe",
    "taskkill.exe",
    "schtasks.exe",
    "regsvr32.exe",
    "control.exe",
    "python.exe",
    "pythonw.exe",
    "py.exe",
    "node.exe",
    "wsl.exe",
    "bash.exe",
    "sh.exe",
    "curl.exe",
    "ftp.exe",
}


def validate_catalog_params(params):
    return (
        isinstance(params, dict)
        and set(params.keys()) == {"app_id"}
        and isinstance(params.get("app_id"), str)
        and bool(params["app_id"])
        and len(params["app_id"]) <= 128
    )


def is_inside_start_menu(shortcut_path):
    """Vérifie que le raccourci se trouve dans le menu Démarrer."""

    try:
        shortcut = Path(shortcut_path).resolve(strict=True)

        if shortcut.suffix.lower() != ".lnk" or not shortcut.is_file():
            return False

        for root in START_MENU_LOCATIONS:
            try:
                resolved_root = Path(root).resolve(strict=True)
                shortcut.relative_to(resolved_root)
                return True
            except (ValueError, OSError, RuntimeError):
                continue

        return False

    except (OSError, RuntimeError):
        return False


def split_windows_arguments(arguments):
    """Transforme les arguments Windows en liste sans utiliser de shell."""

    if not arguments or not arguments.strip():
        return []

    if len(arguments) > 2048 or "\0" in arguments:
        raise ValueError("Arguments du raccourci invalides.")

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    shell32.CommandLineToArgvW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.c_int),
    ]
    shell32.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)

    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    count = ctypes.c_int()
    command_line = "capri-placeholder.exe " + arguments

    argv = shell32.CommandLineToArgvW(
        command_line,
        ctypes.byref(count),
    )

    if not argv:
        raise ValueError("Impossible de lire les arguments du raccourci.")

    try:
        return [
            os.path.expandvars(argv[index])
            for index in range(1, count.value)
        ]
    finally:
        kernel32.LocalFree(ctypes.cast(argv, ctypes.c_void_p))


def inspect_shortcut(shortcut_path):
    """Récupère et contrôle la cible réelle d'un raccourci."""

    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortcut(str(shortcut_path))

    target = os.path.expandvars(shortcut.TargetPath.strip())
    arguments = os.path.expandvars(shortcut.Arguments.strip())
    working_directory = os.path.expandvars(
        shortcut.WorkingDirectory.strip()
    )

    if not target:
        raise ValueError("Le raccourci ne possède aucune cible.")

    target_path = Path(target)

    if not target_path.is_absolute():
        raise ValueError("La cible n'est pas un chemin absolu.")

    target_path = target_path.resolve(strict=True)

    if not target_path.is_file():
        raise ValueError("La cible n'est pas un fichier.")

    if target_path.suffix.lower() != ".exe":
        raise PermissionError("Seuls les exécutables .exe sont autorisés.")

    if target_path.name.casefold() in BLOCKED_TARGET_NAMES:
        raise PermissionError(
            f"Exécutable bloqué par CAPRI : {target_path.name}"
        )

    if working_directory:
        working_path = Path(working_directory)

        if not working_path.is_absolute():
            raise ValueError("Dossier de travail invalide.")

        working_path = working_path.resolve(strict=True)

        if not working_path.is_dir():
            raise ValueError("Dossier de travail introuvable.")
    else:
        working_path = target_path.parent

    arguments_list = split_windows_arguments(arguments)

    return {
        "target": target_path,
        "arguments": arguments_list,
        "working_directory": working_path,
    }


def verify_shortcut(shortcut_path, app_name):
    """Vérifie le raccourci et la signature de son exécutable."""

    if not is_inside_start_menu(shortcut_path):
        raise PermissionError(
            "Raccourci absent des emplacements autorisés du menu Démarrer."
        )

    inspected = inspect_shortcut(shortcut_path)

    signature = verify_authenticode(
        inspected["target"],
        app_name,
    )

    return inspected, signature


def launch_catalog_application(params):
    """Lance une application découverte et vérifiée."""

    app_id = params["app_id"]
    app = get_catalog_app(app_id)

    if app is None:
        raise ValueError("Application absente du catalogue.")

    name = app["name"]
    shortcut_path = app["shortcut_path"]

    # Les applications intégrées conservent leur contrôle strict.
    if app_id in ALLOWED_BUILTINS:
        expected_name = ALLOWED_BUILTINS[app_id]
        expected_shortcut = f"builtin://{app_id}"

        if (
            name.casefold() != expected_name.casefold()
            or shortcut_path != expected_shortcut
        ):
            raise PermissionError(
                "Application intégrée non conforme à la liste blanche."
            )

        return open_application({"app_id": app_id})

    inspected, signature = verify_shortcut(shortcut_path, name)

    # Photographier les fenêtres avant le lancement.
    previous_windows = {
        window["hwnd"]: window["pid"]
        for window in get_visible_windows(include_hidden=True)
    }

    process = subprocess.Popen(
        [
            str(inspected["target"]),
            *inspected["arguments"],
        ],
        shell=False,
        cwd=str(inspected["working_directory"]),
        close_fds=True,
    )

    expected_path = os.path.normcase(
        os.path.abspath(str(inspected["target"]))
    )

    # Une application peut démarrer une version dans un sous-dossier
    # ou réutiliser une fenêtre déjà ouverte.
    deadline = time.monotonic() + 10

    while time.monotonic() < deadline:
        candidates = []
        for window in get_visible_windows(include_hidden=True):
            hwnd = window["hwnd"]

            if not is_trackable_application_window(window):
                continue

            actual_path = get_process_path(window["pid"])

            if not actual_path:
                continue

            if not is_catalog_process_path(
                actual_path,
                expected_path,
            ):
                continue

            signature_result = verify_catalog_process(
                actual_path,
                signature["publisher"],
                name,
            )
            if not signature_result:
                continue

            candidates.append(window)

        candidates.sort(
            key=lambda window: (
                not window.get("visible", True),
                previous_windows.get(window["hwnd"]) == window["pid"]
            )
        )

        for window in candidates:
            hwnd = window["hwnd"]
            entry = register_catalog_window(
                app_id,
                hwnd,
                expected_path,
                name,
                signature["publisher"],
            )

            show_tracked_window(hwnd)

            reused = previous_windows.get(hwnd) == entry["pid"]
            return {
                "application": name,
                "process_id": entry["pid"],
                "launch_process_id": process.pid,
                "window_id": hwnd,
                "publisher": signature["publisher"],
                "status": (
                    "reused_and_tracked"
                    if reused
                    else "launched_and_tracked"
                ),
            }

        time.sleep(0.2)

    return {
        "application": name,
        "process_id": process.pid,
        "publisher": signature["publisher"],
        "status": "launched_not_tracked",
    }


def register_catalog_launcher():
    """Enregistre les actions d'ouverture et de fermeture du catalogue."""

    existing = {
        action["id"]
        for action in list_actions()
    }

    if "applications.open_catalog" not in existing:
        register_action(
            action_id="applications.open_catalog",
            permission_id="apps.launch",
            handler=launch_catalog_application,
            description="Ouvrir une application découverte et vérifiée.",
            validator=validate_catalog_params,
        )

    if "applications.close_catalog" not in existing:
        register_action(
            action_id="applications.close_catalog",
            permission_id="apps.close",
            handler=close_catalog_window,
            description="Demander la fermeture normale d'une fenêtre "
                        "vérifiée du catalogue.",
            validator=validate_catalog_params,
        )
