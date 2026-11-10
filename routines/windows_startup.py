"""Gestion du lancement optionnel de CAPRI à l'ouverture de session Windows."""

import os
import sys
from pathlib import Path


STARTUP_SHORTCUT_NAME = "CAPRI.lnk"


def get_startup_shortcut_path():
    app_data = os.environ.get("APPDATA")
    if not app_data:
        raise RuntimeError("Le dossier APPDATA de Windows est introuvable.")
    return (
        Path(app_data)
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / STARTUP_SHORTCUT_NAME
    )


def is_windows_startup_enabled():
    return get_startup_shortcut_path().is_file()


def set_windows_startup_enabled(enabled):
    if not isinstance(enabled, bool):
        raise ValueError("L'état du démarrage Windows doit être booléen.")

    shortcut_path = get_startup_shortcut_path()
    if not enabled:
        shortcut_path.unlink(missing_ok=True)
        return False

    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    pending_path = shortcut_path.with_name("CAPRI.pending.lnk")
    import pythoncom

    pythoncom.CoInitialize()
    shortcut = None
    try:
        from win32com.client import Dispatch

        shortcut = Dispatch("WScript.Shell").CreateShortCut(
            str(pending_path)
        )

        if getattr(sys, "frozen", False):
            shortcut.TargetPath = sys.executable
            shortcut.Arguments = "--background"
            shortcut.WorkingDirectory = str(Path(sys.executable).parent)
        else:
            interpreter = Path(sys.executable)
            windowless_interpreter = interpreter.with_name("pythonw.exe")
            if not windowless_interpreter.is_file():
                raise RuntimeError(
                    "pythonw.exe est introuvable ; CAPRI ne peut pas "
                    "démarrer en arrière-plan."
                )
            shortcut.TargetPath = str(windowless_interpreter)
            shortcut.Arguments = (
                f'"{Path(__file__).resolve().parents[1] / "main.py"}" '
                "--background"
            )
            shortcut.WorkingDirectory = str(Path(__file__).resolve().parents[1])

        shortcut.Description = "Démarrer CAPRI en arrière-plan"
        shortcut.save()
        pending_path.replace(shortcut_path)
    except Exception:
        pending_path.unlink(missing_ok=True)
        raise
    finally:
        shortcut = None
        pythoncom.CoUninitialize()

    return True
