
"""Gestion sécurisée des applications Windows."""

import ctypes
import os
import subprocess
import time
from pathlib import Path
from ctypes import wintypes

import psutil

from security.action_manager import register_action, list_actions


# Applications que CAPRI a le droit de lancer et de suivre.
ALLOWED_APPLICATIONS = {
    "notepad": {
        "label": "Bloc-notes",
        "path": Path(os.environ["WINDIR"]) / "System32" / "notepad.exe",
        "process_names": {"notepad.exe"},
        "package_family": "Microsoft.WindowsNotepad_8wekyb3d8bbwe",
        "package_publisher": (
            "CN=Microsoft Corporation, O=Microsoft Corporation, "
            "L=Redmond, S=Washington, C=US"
        ),
    },
    "calculator": {
        "label": "Calculatrice",
        "path": Path(os.environ["WINDIR"]) / "System32" / "calc.exe",
        "process_names": {"calculator.exe", "calculatorapp.exe"},
        "package_family": "Microsoft.WindowsCalculator_8wekyb3d8bbwe",
        "package_publisher": (
            "CN=Microsoft Corporation, O=Microsoft Corporation, "
            "L=Redmond, S=Washington, C=US"
        ),
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

user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.DWORD),
]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowTextW.argtypes = [
    wintypes.HWND,
    wintypes.LPWSTR,
    ctypes.c_int,
]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [
    wintypes.HWND,
    wintypes.LPWSTR,
    ctypes.c_int,
]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindow.restype = wintypes.HWND
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = wintypes.LONG
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.PostMessageW.restype = wintypes.BOOL

kernel32.OpenProcess.argtypes = [
    wintypes.DWORD,
    wintypes.BOOL,
    wintypes.DWORD,
]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.GetProcessTimes.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(wintypes.FILETIME),
    ctypes.POINTER(wintypes.FILETIME),
    ctypes.POINTER(wintypes.FILETIME),
    ctypes.POINTER(wintypes.FILETIME),
]
kernel32.GetProcessTimes.restype = wintypes.BOOL
kernel32.GetPackageFamilyName.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.LPWSTR,
]
kernel32.GetPackageFamilyName.restype = wintypes.LONG
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

ERROR_INSUFFICIENT_BUFFER = 122
APPMODEL_ERROR_NO_PACKAGE = 15700
GW_OWNER = 4
GWL_STYLE = -16
WS_CHILD = 0x40000000
SW_RESTORE = 9


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


def get_process_identity(process_id):
    """Lit le chemin et l'heure de création depuis le même handle de processus."""
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
        creation_time = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel_time = wintypes.FILETIME()
        user_time = wintypes.FILETIME()

        path_success = kernel32.QueryFullProcessImageNameW(
            handle,
            0,
            buffer,
            ctypes.byref(size),
        )
        time_success = kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation_time),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        )
        package_family = get_package_family_name(handle)

        if not path_success or not time_success or package_family is False:
            return None

        return {
            "process_path": normalize_process_path(buffer.value),
            "package_family": package_family,
            "process_creation_time": (
                creation_time.dwHighDateTime << 32
            ) | creation_time.dwLowDateTime,
        }

    finally:
        kernel32.CloseHandle(handle)


def get_package_family_name(process_handle):
    """Retourne l'identité de package Windows, ou None pour un processus classique."""
    length = wintypes.DWORD(0)
    status = kernel32.GetPackageFamilyName(
        process_handle,
        ctypes.byref(length),
        None,
    )

    if status == APPMODEL_ERROR_NO_PACKAGE:
        return None

    if status != ERROR_INSUFFICIENT_BUFFER or length.value == 0:
        return False

    package_family = ctypes.create_unicode_buffer(length.value)
    status = kernel32.GetPackageFamilyName(
        process_handle,
        ctypes.byref(length),
        package_family,
    )

    if status != 0:
        return False

    return package_family.value


def normalize_process_path(path):
    return os.path.normcase(os.path.abspath(os.path.realpath(path)))


def is_catalog_process_path(actual_path, expected_path):
    """Autorise un exécutable de l'installation vérifiée de l'application."""
    try:
        actual = Path(actual_path).resolve(strict=True)
        expected = Path(expected_path).resolve(strict=True)

        if actual.suffix.casefold() != ".exe" or not actual.is_file():
            return False

        actual.relative_to(expected.parent)
        return True

    except (OSError, ValueError, RuntimeError):
        return False


def get_window_identity(hwnd):
    """Récupère l'identité vérifiable du processus propriétaire d'une fenêtre."""
    if not user32.IsWindow(hwnd):
        return None

    process_id = get_window_process_id(hwnd)

    if not process_id:
        return None

    process = get_process_identity(process_id)

    if process is None:
        return None

    return {
        "pid": process_id,
        **process,
    }


def verify_catalog_process(process_path, expected_publisher, label):
    """Vérifie la signature de l'exécutable et son éditeur attendu."""
    from security.signature_verifier import verify_authenticode

    signature = verify_authenticode(process_path, label)

    if signature["publisher"].casefold() != expected_publisher.casefold():
        return False

    return signature



def get_visible_windows(include_hidden=False):
    """Retourne les fenêtres visibles, et optionnellement les masquées."""

    windows = []

    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM,
    )

    def callback(hwnd, lparam):
        visible = bool(user32.IsWindowVisible(hwnd))
        if visible or include_hidden:
            process_id = get_window_process_id(hwnd)
            title_buffer = ctypes.create_unicode_buffer(512)
            class_buffer = ctypes.create_unicode_buffer(256)

            user32.GetWindowTextW(
                hwnd,
                title_buffer,
                len(title_buffer),
            )
            user32.GetClassNameW(
                hwnd,
                class_buffer,
                len(class_buffer),
            )

            windows.append({
                "hwnd": int(hwnd),
                "pid": process_id,
                "title": title_buffer.value,
                "visible": visible,
                "class_name": class_buffer.value,
                "owner": int(user32.GetWindow(hwnd, GW_OWNER) or 0),
                "style": user32.GetWindowLongW(hwnd, GWL_STYLE),
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


def is_trackable_application_window(window):
    """Accepte les fenêtres visibles ou un HWND principal actuellement masqué."""
    if window.get("visible", True):
        return True

    if window.get("owner", 0) or window.get("style", 0) & WS_CHILD:
        return False

    window_class = window.get("class_name", "").casefold()
    if window_class in {
        "ime",
        "msctfime ui",
        "ole dde server window",
        "electron_notifyiconhostwindow",
        "discorddesktopoverlayinputtrap",
    } or "crashpad" in window_class:
        return False

    try:
        command_line = psutil.Process(window["pid"]).cmdline()
    except (
        psutil.NoSuchProcess,
        psutil.AccessDenied,
        psutil.ZombieProcess,
    ):
        return False

    return bool(command_line) and not any(
        argument.casefold().startswith("--type=")
        for argument in command_line
    )


def show_tracked_window(hwnd):
    """Restaure au premier plan une fenêtre dont le processus est vérifié."""
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)


def request_window_close(
    hwnd,
    process_id=None,
    process_creation_time=None,
    process_path=None,
    timeout=1.5,
):
    """Envoie WM_CLOSE et distingue la fermeture de la mise en arrière-plan."""
    success = user32.PostMessageW(
        hwnd,
        WM_CLOSE,
        0,
        0,
    )

    if not success:
        raise ctypes.WinError(ctypes.get_last_error())

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not user32.IsWindow(hwnd):
            if process_id is not None:
                identity = get_process_identity(process_id)
                if identity is not None and (
                    identity["process_creation_time"] != process_creation_time
                    or identity["process_path"] != process_path
                ):
                    return "closed"
                if identity is not None:
                    time.sleep(0.05)
                    continue
            return "closed"
        if not user32.IsWindowVisible(hwnd):
            return "hidden_in_background"
        time.sleep(0.05)

    if not user32.IsWindow(hwnd):
        identity = (
            get_process_identity(process_id)
            if process_id is not None
            else None
        )
        if (
            identity is not None
            and identity["process_creation_time"] == process_creation_time
            and identity["process_path"] == process_path
        ):
            return "closed_in_background"
        return "closed"

    if not user32.IsWindowVisible(hwnd):
        return "hidden_in_background"

    return "still_open"


def register_catalog_window(
    app_id,
    hwnd,
    expected_path,
    label,
    expected_publisher,
):
    """Enregistre une fenêtre dont l'exécutable a été vérifié."""

    identity = get_window_identity(hwnd)

    if identity is None:
        raise RuntimeError("La fenêtre n'existe plus.")

    if not is_catalog_process_path(
        identity["process_path"],
        expected_path,
    ):
        raise PermissionError(
            "L'exécutable propriétaire de la fenêtre ne correspond "
            "pas à l'application autorisée."
        )

    if not verify_catalog_process(
        identity["process_path"],
        expected_publisher,
        label,
    ):
        raise PermissionError(
            "L'éditeur de l'exécutable ne correspond pas "
            "à celui de l'application autorisée."
        )

    entries = _RUNNING_CATALOG_WINDOWS.setdefault(app_id, [])

    existing = next(
        (entry for entry in entries if entry["hwnd"] == int(hwnd)),
        None,
    )

    if existing is None:
        entries.append({
            "hwnd": int(hwnd),
            "expected_path": normalize_process_path(expected_path),
            "process_path": identity["process_path"],
            "pid": identity["pid"],
            "process_creation_time": identity["process_creation_time"],
            "expected_publisher": expected_publisher,
            "label": label,
        })
    else:
        existing.update({
            "expected_path": normalize_process_path(expected_path),
            "process_path": identity["process_path"],
            "pid": identity["pid"],
            "process_creation_time": identity["process_creation_time"],
            "expected_publisher": expected_publisher,
            "label": label,
        })

    return existing or entries[-1]


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

        identity = get_window_identity(hwnd)

        if identity is None:
            entries.pop()
            continue

        if (
            identity["pid"] != entry["pid"]
            or identity["process_creation_time"]
            != entry["process_creation_time"]
            or identity["process_path"] != entry["process_path"]
            or not is_catalog_process_path(
                identity["process_path"],
                entry["expected_path"],
            )
        ):
            entries.pop()
            continue

        if not verify_catalog_process(
            identity["process_path"],
            entry["expected_publisher"],
            entry["label"],
        ):
            entries.pop()
            continue

        close_status = request_window_close(
            hwnd,
            entry["pid"],
            entry["process_creation_time"],
            entry["process_path"],
        )

        return {
            "application": entry["label"],
            "window_id": hwnd,
            "status": close_status,
        }

    raise RuntimeError(
        "CAPRI ne possède aucune fenêtre active et vérifiée "
        "pour cette application."
    )


def is_expected_process_identity(identity, app_id):
    """Vérifie le chemin et le nom du processus propriétaire."""
    if identity is None:
        return False

    process_name = Path(identity["process_path"]).name.lower()

    allowed_names = ALLOWED_APPLICATIONS[app_id]["process_names"]

    expected_path = normalize_process_path(
        ALLOWED_APPLICATIONS[app_id]["path"]
    )

    if process_name not in allowed_names:
        return False

    if identity["process_path"] == expected_path:
        return True

    package_family = ALLOWED_APPLICATIONS[app_id].get("package_family")
    package_process_names = ALLOWED_APPLICATIONS[app_id].get(
        "package_process_names",
        allowed_names,
    )
    if (
        not package_family
        or (identity.get("package_family") or "").casefold()
        != package_family.casefold()
        or process_name not in package_process_names
    ):
        return False

    package_name, publisher_id = package_family.rsplit("_", 1)
    process_path = Path(identity["process_path"])
    path_parts = [part.casefold() for part in process_path.parts]
    package_directory = any(
        part.startswith(package_name.casefold() + "_")
        and part.endswith("_" + publisher_id.casefold())
        for part in path_parts
    )

    return "windowsapps" in path_parts and package_directory


def verify_expected_application_identity(identity, app_id):
    """Vérifie l'éditeur du processus empaqueté avant de le suivre ou fermer."""
    if not is_expected_process_identity(identity, app_id):
        return False

    application = ALLOWED_APPLICATIONS[app_id]
    if identity["process_path"] == normalize_process_path(application["path"]):
        return True

    from security.signature_verifier import verify_authenticode

    publisher = application.get("package_publisher")
    if not publisher:
        return False

    signature = verify_authenticode(
        identity["process_path"],
        application["label"],
    )
    if (
        signature["publisher"].casefold()
        != publisher.casefold()
    ):
        raise PermissionError(
            f"L'éditeur du processus empaqueté {application['label']} "
            "ne correspond pas à celui qui a été autorisé."
        )

    return True


def is_expected_application(hwnd, app_id):
    """Vérifie que la fenêtre appartient à l'application attendue."""
    return verify_expected_application_identity(
        get_window_identity(hwnd),
        app_id,
    )


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
        window["hwnd"]: window["pid"]
        for window in get_visible_windows(include_hidden=True)
    }

    subprocess.Popen(
        [str(executable)],
        shell=False,
        cwd=str(executable.parent),
        close_fds=True,
    )

    # Une application peut réutiliser sa fenêtre déjà ouverte.
    deadline = time.monotonic() + 10

    while time.monotonic() < deadline:
        candidates = []
        for window in get_visible_windows(include_hidden=True):
            hwnd = window["hwnd"]

            if not is_trackable_application_window(window):
                continue

            identity = get_window_identity(hwnd)
            if not verify_expected_application_identity(identity, app_id):
                continue

            candidates.append((window, identity))

        candidates.sort(
            key=lambda item: (
                not item[0].get("visible", True),
                previous_windows.get(item[0]["hwnd"])
                == item[1]["pid"]
            )
        )

        for window, identity in candidates:
            hwnd = window["hwnd"]
            entries = _RUNNING_WINDOWS.setdefault(app_id, [])
            tracked_entry = next(
                (entry for entry in entries if entry["hwnd"] == int(hwnd)),
                None,
            )
            window_identity = {
                "hwnd": int(hwnd),
                "pid": identity["pid"],
                "process_path": identity["process_path"],
                "package_family": identity.get("package_family"),
                "process_creation_time": identity["process_creation_time"],
            }

            if tracked_entry is None:
                entries.append(window_identity)
            else:
                tracked_entry.update(window_identity)

            show_tracked_window(hwnd)

            reused = previous_windows.get(hwnd) == identity["pid"]
            return {
                "application": application["label"],
                "window_id": hwnd,
                "process_id": identity["pid"],
                "window_title": window["title"],
                "status": (
                    "reused_and_tracked"
                    if reused
                    else "launched_and_tracked"
                ),
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

    for app_id, entries in _RUNNING_WINDOWS.items():
        for entry in entries:
            hwnd = entry["hwnd"]
            identity = get_window_identity(hwnd)

            if (
                identity is not None
                and identity["pid"] == entry["pid"]
                and identity["process_path"] == entry["process_path"]
                and identity.get("package_family")
                == entry.get("package_family")
                and identity["process_creation_time"]
                == entry["process_creation_time"]
                and verify_expected_application_identity(identity, app_id)
            ):
                result.append({
                    "app_id": app_id,
                    "window_id": hwnd,
                    "label": ALLOWED_APPLICATIONS[app_id]["label"],
                })

    for app_id, entries in _RUNNING_CATALOG_WINDOWS.items():
        for entry in entries:
            identity = get_window_identity(entry["hwnd"])
            if (
                identity is not None
                and identity["pid"] == entry["pid"]
                and identity["process_path"] == entry["process_path"]
                and identity["process_creation_time"]
                == entry["process_creation_time"]
                and is_catalog_process_path(
                    identity["process_path"],
                    entry["expected_path"],
                )
                and verify_catalog_process(
                    identity["process_path"],
                    entry["expected_publisher"],
                    entry["label"],
                )
            ):
                result.append({
                    "app_id": app_id,
                    "window_id": entry["hwnd"],
                    "label": entry["label"],
                })

    return result


def close_application(params):
    app_id = params["app_id"]
    entries = _RUNNING_WINDOWS.get(app_id, [])

    # On ne ferme que la dernière fenêtre suivie par CAPRI.
    while entries:
        entry = entries[-1]
        hwnd = entry["hwnd"]

        identity = get_window_identity(hwnd)
        if identity is None:
            entries.pop()
            continue

        if (
            identity["pid"] != entry["pid"]
            or identity["process_path"] != entry["process_path"]
            or identity.get("package_family")
            != entry.get("package_family")
            or identity["process_creation_time"]
            != entry["process_creation_time"]
            or not verify_expected_application_identity(identity, app_id)
        ):
            entries.pop()
            continue

        # Demande une fermeture normale à CETTE fenêtre.
        close_status = request_window_close(
            hwnd,
            entry["pid"],
            entry["process_creation_time"],
            entry["process_path"],
        )

        return {
            "application": ALLOWED_APPLICATIONS[app_id]["label"],
            "window_id": hwnd,
            "status": close_status,
        }

    raise RuntimeError(
        "CAPRI ne possède aucune fenêtre active et vérifiée "
        "pour cette application."
    )


def register_application_actions():
    existing = {
        action["id"]
        for action in list_actions()
    }

    if "applications.open" not in existing:
        register_action(
            action_id="applications.open",
            permission_id="apps.launch",
            handler=open_application,
            description="Ouvrir une application autorisée.",
            validator=validate_application_params,
        )

    if "applications.close" not in existing:
        register_action(
            action_id="applications.close",
            permission_id="apps.close",
            handler=close_application,
            description="Demander la fermeture normale d'une fenêtre "
                        "lancée par CAPRI.",
            validator=validate_application_params,
        )
