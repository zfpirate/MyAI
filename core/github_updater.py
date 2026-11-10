"""GitHub release checks and safe Windows portable-app updates."""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath

import requests

from core.app_info import APP_VERSION, GITHUB_REPOSITORY, resource_path


GITHUB_API_URL = (
    f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
)
MAX_ARCHIVE_SIZE = 2 * 1024 * 1024 * 1024
MAX_DOWNLOAD_SIZE = 1024 * 1024 * 1024


def _version_key(version):
    match = re.fullmatch(r"v?(\d+(?:\.\d+){1,3})(?:[-+].*)?", version.strip())
    if not match:
        raise ValueError(f"Version CAPRI invalide : {version}")
    parts = tuple(int(part) for part in match.group(1).split("."))
    return parts + (0,) * (4 - len(parts))


def check_for_updates(current_version=APP_VERSION):
    response = requests.get(
        GITHUB_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "CAPRI-Updater",
        },
        timeout=15,
    )
    response.raise_for_status()
    release = response.json()

    tag_name = release.get("tag_name")
    release_url = release.get("html_url")
    if not isinstance(tag_name, str) or not isinstance(release_url, str):
        raise ValueError("La release GitHub ne contient pas de version valide.")

    latest_key = _version_key(tag_name)
    current_key = _version_key(current_version)
    if latest_key <= current_key:
        return {
            "status": "up_to_date",
            "current_version": current_version,
            "latest_version": tag_name,
            "release_url": release_url,
            "assets": {},
        }

    assets = {
        asset["name"]: asset["browser_download_url"]
        for asset in release.get("assets", [])
        if isinstance(asset, dict)
        and isinstance(asset.get("name"), str)
        and isinstance(asset.get("browser_download_url"), str)
    }
    return {
        "status": "update_available",
        "current_version": current_version,
        "latest_version": tag_name,
        "release_url": release_url,
        "assets": assets,
    }


def validate_update_archive(archive_path):
    """Reject zip-slip paths and unexpected package layouts before extraction."""
    total_size = 0
    has_executable = False

    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            name = member.filename.replace("\\", "/")
            path = PurePosixPath(name)
            if (
                path.is_absolute()
                or not path.parts
                or any(part in {"", ".", ".."} for part in path.parts)
                or any(
                    ":" in part
                    or part.endswith((".", " "))
                    or part.split(".", 1)[0].upper() in {
                        "CON", "PRN", "AUX", "NUL",
                        "COM1", "COM2", "COM3", "COM4", "COM5",
                        "COM6", "COM7", "COM8", "COM9",
                        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5",
                        "LPT6", "LPT7", "LPT8", "LPT9",
                    }
                    for part in path.parts
                )
                or path.parts[0] != "CAPRI"
            ):
                raise ValueError("L'archive de mise à jour contient un chemin interdit.")

            mode = member.external_attr >> 16
            if mode and (mode & 0o170000) == 0o120000:
                raise ValueError("L'archive de mise à jour contient un lien interdit.")

            total_size += member.file_size
            if total_size > MAX_ARCHIVE_SIZE:
                raise ValueError("L'archive de mise à jour est trop volumineuse.")

            if path.parts == ("CAPRI", "CAPRI.exe"):
                has_executable = True

    if not has_executable:
        raise ValueError("L'archive ne contient pas CAPRI.exe.")


def _download_asset(url, destination, progress_callback=None):
    size = 0
    response = requests.get(
        url,
        headers={"User-Agent": "CAPRI-Updater"},
        stream=True,
        timeout=(15, 60),
    )
    response.raise_for_status()
    with response, destination.open("wb") as downloaded:
        content_length = response.headers.get("Content-Length")
        try:
            total_size = int(content_length) if content_length else -1
        except ValueError:
            total_size = -1

        if progress_callback:
            progress_callback(0, total_size, destination.name)

        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            size += len(chunk)
            if size > MAX_DOWNLOAD_SIZE:
                raise ValueError("Le téléchargement dépasse la taille maximale.")
            downloaded.write(chunk)
            if progress_callback:
                progress_callback(size, total_size, destination.name)


def download_and_install_update(update, progress_callback=None):
    """Download a release archive and hand off replacement to PowerShell."""
    if os.name != "nt" or not getattr(sys, "frozen", False):
        raise RuntimeError(
            "La mise à jour automatique nécessite la version Windows installée."
        )

    assets = update.get("assets", {})
    archive_url = assets.get("CAPRI-windows-x64.zip")
    checksum_url = assets.get("CAPRI-windows-x64.zip.sha256")
    if not archive_url or not checksum_url:
        raise ValueError(
            "Cette release ne contient pas encore le paquet Windows "
            "et son empreinte SHA-256."
        )

    if not Path(sys.executable).name.casefold() == "capri.exe":
        raise RuntimeError("CAPRI.exe doit être installé dans son dossier d'application.")

    update_directory = (
        Path(os.environ["LOCALAPPDATA"]) / "CAPRI" / "updates"
    )
    update_directory.mkdir(parents=True, exist_ok=True)
    install_directory = Path(sys.executable).resolve().parent
    staging_directory = Path(tempfile.mkdtemp(
        prefix=".capri-update-",
        dir=install_directory.parent,
    ))
    archive_path = update_directory / "CAPRI-windows-x64.zip"
    checksum_path = update_directory / "CAPRI-windows-x64.zip.sha256"
    helper_script = update_directory / "update_windows.ps1"
    started_file = update_directory / "update_started"
    helper_process = None
    helper_started = False

    try:
        _download_asset(archive_url, archive_path, progress_callback)
        _download_asset(checksum_url, checksum_path, progress_callback)

        checksum_text = checksum_path.read_text(encoding="utf-8")
        expected = re.match(r"^\s*([a-fA-F0-9]{64})(?:\s+[*]?.*)?\s*$",
                            checksum_text)
        if not expected:
            raise ValueError("L'empreinte SHA-256 de la release est invalide.")

        digest = hashlib.sha256()
        with archive_path.open("rb") as downloaded:
            for chunk in iter(lambda: downloaded.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest().casefold() != expected.group(1).casefold():
            raise ValueError(
                "La vérification SHA-256 a échoué ; CAPRI n'a pas été modifiée."
            )

        validate_update_archive(archive_path)

        script = resource_path(Path("scripts") / "update_windows.ps1")
        if not script.is_file():
            raise FileNotFoundError("Le script de mise à jour de Windows est absent.")

        shutil.copyfile(script, helper_script)
        started_file.unlink(missing_ok=True)

        powershell = shutil.which("powershell.exe")
        if not powershell:
            raise RuntimeError("Windows PowerShell est introuvable.")

        helper_process = subprocess.Popen(
            [
                powershell,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-File",
                str(helper_script),
                "-ProcessId",
                str(os.getpid()),
                "-ArchivePath",
                str(archive_path),
                "-ExpectedSha256",
                digest.hexdigest(),
                "-InstallDirectory",
                str(install_directory),
                "-StagingDirectory",
                str(staging_directory),
                "-ExecutableName",
                "CAPRI.exe",
                "-StartedFile",
                str(started_file),
            ],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            close_fds=True,
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if started_file.is_file():
                helper_started = True
                break
            if helper_process.poll() is not None:
                raise RuntimeError(
                    "Le programme de mise à jour s'est fermé avant de "
                    "démarrer. CAPRI reste ouverte."
                )
            time.sleep(0.1)
        else:
            raise RuntimeError(
                "Le programme de mise à jour n'a pas démarré. "
                "CAPRI reste ouverte."
            )
    except Exception:
        if not helper_started:
            if (
                helper_process is not None
                and helper_process.poll() is None
            ):
                helper_process.terminate()
                try:
                    helper_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    helper_process.kill()
                    helper_process.wait()
            shutil.rmtree(staging_directory, ignore_errors=True)
            archive_path.unlink(missing_ok=True)
            checksum_path.unlink(missing_ok=True)
            helper_script.unlink(missing_ok=True)
            started_file.unlink(missing_ok=True)
        raise

    return {"status": "installing", "version": update["latest_version"]}
