import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from core.github_updater import (
    _download_asset,
    _version_key,
    check_for_updates,
    download_and_install_update,
    validate_update_archive,
)


class GitHubUpdaterTests(unittest.TestCase):
    def test_asset_download_reports_received_bytes(self):
        class DownloadResponse:
            headers = {"Content-Length": "5"}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def raise_for_status(self):
                pass

            def iter_content(self, chunk_size):
                self.assert_chunk_size = chunk_size
                yield b"abc"
                yield b"de"

        response = DownloadResponse()
        progress = []
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "download.zip"
            with patch(
                "core.github_updater.requests.get",
                return_value=response,
            ):
                _download_asset(
                    "https://example.com/download.zip",
                    destination,
                    lambda received, total, name: progress.append(
                        (received, total, name)
                    ),
                )

            self.assertEqual(destination.read_bytes(), b"abcde")

        self.assertEqual(
            progress,
            [
                (0, 5, "download.zip"),
                (3, 5, "download.zip"),
                (5, 5, "download.zip"),
            ],
        )

    def test_version_tags_are_compared_numerically(self):
        self.assertGreater(_version_key("v0.10.0"), _version_key("v0.9.9"))
        self.assertEqual(_version_key("v0.3"), _version_key("0.3.0"))

    def test_latest_release_reports_the_verified_package_assets(self):
        response = Mock()
        response.json.return_value = {
            "tag_name": "v0.4.0",
            "html_url": "https://github.com/zfpirate/MyAI/releases/tag/v0.4.0",
            "assets": [
                {
                    "name": "CAPRI-windows-x64.zip",
                    "browser_download_url": "https://example.com/capri.zip",
                },
                {
                    "name": "CAPRI-windows-x64.zip.sha256",
                    "browser_download_url": "https://example.com/capri.sha256",
                },
            ],
        }

        with patch(
            "core.github_updater.requests.get",
            return_value=response,
        ) as get:
            result = check_for_updates("0.3.0")

        response.raise_for_status.assert_called_once_with()
        self.assertEqual(result["status"], "update_available")
        self.assertEqual(result["latest_version"], "v0.4.0")
        self.assertIn("CAPRI-windows-x64.zip", result["assets"])
        get.assert_called_once()

    def test_latest_or_older_release_is_not_an_update(self):
        response = Mock()
        response.json.return_value = {
            "tag_name": "v0.3.0",
            "html_url": "https://github.com/zfpirate/MyAI/releases/tag/v0.3.0",
            "assets": [],
        }
        with patch("core.github_updater.requests.get", return_value=response):
            result = check_for_updates("0.3.0")
        self.assertEqual(result["status"], "up_to_date")

    def test_update_archive_requires_the_application_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "missing.exe.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("CAPRI/_internal/runtime.dll", b"runtime")
            with self.assertRaisesRegex(ValueError, "CAPRI.exe"):
                validate_update_archive(archive_path)

    def test_update_archive_rejects_parent_directory_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "unsafe.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("CAPRI/CAPRI.exe", b"application")
                archive.writestr("CAPRI/../../startup.bat", b"unsafe")
            with self.assertRaisesRegex(ValueError, "chemin interdit"):
                validate_update_archive(archive_path)

    def test_update_archive_accepts_the_release_package_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "release.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("CAPRI/CAPRI.exe", b"application")
                archive.writestr("CAPRI/_internal/runtime.dll", b"runtime")
            validate_update_archive(archive_path)

    def test_windows_update_helper_signals_start_and_cleans_staging(self):
        helper_script = (
            Path(__file__).parent / "scripts" / "update_windows.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn("[string]$StartedFile", helper_script)
        self.assertIn(
            'Set-Content -LiteralPath $StartedFile -Value "started"',
            helper_script,
        )
        self.assertIn(
            'Remove-Item -LiteralPath $StagingDirectory -Recurse -Force',
            helper_script,
        )
        self.assertIn(
            'Remove-Item -LiteralPath $StartedFile -Force',
            helper_script,
        )

    def test_update_does_not_finish_until_helper_starts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "Programs" / "CAPRI" / "CAPRI.exe"
            executable.parent.mkdir(parents=True)
            executable.touch()

            source_archive = root / "release.zip"
            with zipfile.ZipFile(source_archive, "w") as archive:
                archive.writestr("CAPRI/CAPRI.exe", b"application")
            digest = hashlib.sha256(source_archive.read_bytes()).hexdigest()

            def download_asset(url, destination, _progress_callback=None):
                if url.endswith(".sha256"):
                    destination.write_text(
                        f"{digest}  CAPRI-windows-x64.zip\n",
                        encoding="utf-8",
                    )
                else:
                    shutil.copyfile(source_archive, destination)

            helper_process = Mock()
            helper_process.poll.return_value = None

            def start_helper(command, **_kwargs):
                marker_index = command.index("-StartedFile") + 1
                Path(command[marker_index]).write_text(
                    "started",
                    encoding="ascii",
                )
                return helper_process

            with (
                patch("core.github_updater.os.name", "nt"),
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "executable", str(executable)),
                patch.dict(os.environ, {"LOCALAPPDATA": directory}),
                patch(
                    "core.github_updater._download_asset",
                    side_effect=download_asset,
                ),
                patch(
                    "core.github_updater.shutil.which",
                    return_value="powershell.exe",
                ),
                patch(
                    "core.github_updater.subprocess.Popen",
                    side_effect=start_helper,
                ) as popen,
                patch.object(
                    subprocess,
                    "CREATE_NO_WINDOW",
                    0x08000000,
                    create=True,
                ),
                patch.object(
                    subprocess,
                    "DETACHED_PROCESS",
                    0x00000008,
                    create=True,
                ),
            ):
                result = download_and_install_update({
                    "latest_version": "v0.4.0",
                    "assets": {
                        "CAPRI-windows-x64.zip": "https://example.com/release.zip",
                        "CAPRI-windows-x64.zip.sha256": (
                            "https://example.com/release.zip.sha256"
                        ),
                    },
                })

            self.assertEqual(result["status"], "installing")
            command = popen.call_args.args[0]
            self.assertIn("-StartedFile", command)
            self.assertEqual(
                popen.call_args.kwargs["creationflags"],
                subprocess.CREATE_NO_WINDOW,
            )


if __name__ == "__main__":
    unittest.main()
