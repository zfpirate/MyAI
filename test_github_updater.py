import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from core.github_updater import (
    _version_key,
    check_for_updates,
    validate_update_archive,
)


class GitHubUpdaterTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
