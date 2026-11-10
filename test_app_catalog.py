import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from actions.app_catalog import (
    get_catalog_apps,
    is_safe_shortcut,
    make_app_id,
    scan_installed_apps,
)


class ApplicationCatalogTests(unittest.TestCase):
    def test_filters_administrative_and_command_shortcuts(self):
        self.assertFalse(
            is_safe_shortcut(
                "PowerShell",
                "C:\\Start Menu\\Programs\\PowerShell.lnk",
            )
        )
        self.assertFalse(
            is_safe_shortcut(
                "Device Manager",
                "C:\\Start Menu\\Programs\\System Tools\\Device Manager.lnk",
            )
        )
        self.assertTrue(
            is_safe_shortcut(
                "Spotify",
                "C:\\Start Menu\\Programs\\Spotify.lnk",
            )
        )

    def test_application_id_is_stable_for_the_same_shortcut(self):
        self.assertEqual(
            make_app_id("C:\\Programs\\Spotify.lnk"),
            make_app_id("C:\\Programs\\Spotify.lnk"),
        )
        self.assertNotEqual(
            make_app_id("C:\\Programs\\Spotify.lnk"),
            make_app_id("C:\\Programs\\Discord.lnk"),
        )

    def test_scan_indexes_start_menu_apps_and_builtin_apps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            programs = root / "Programs"
            programs.mkdir()
            (programs / "Spotify.lnk").touch()
            (programs / "PowerShell.lnk").touch()
            db_path = root / "capri.db"

            with (
                patch("memory.database.DB_PATH", db_path),
                patch(
                    "actions.app_catalog.START_MENU_LOCATIONS",
                    [programs],
                ),
            ):
                self.assertEqual(scan_installed_apps(), 3)
                apps = get_catalog_apps()
                gc.collect()

            names = {app["name"] for app in apps}
            self.assertEqual(
                names,
                {"Spotify", "Bloc-notes", "Calculatrice"},
            )


if __name__ == "__main__":
    unittest.main()
