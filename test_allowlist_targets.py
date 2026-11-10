import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from actions.catalog_launcher import (
    is_inside_start_menu,
    validate_catalog_params,
)


class AllowlistedTargetTests(unittest.TestCase):
    def test_catalog_action_accepts_only_an_application_id(self):
        self.assertTrue(validate_catalog_params({"app_id": "spotify-id"}))
        self.assertFalse(validate_catalog_params({
            "app_id": "spotify-id",
            "target": "C:\\Windows\\System32\\cmd.exe",
        }))
        self.assertFalse(validate_catalog_params({"app_id": ""}))
        self.assertFalse(validate_catalog_params([]))

    def test_shortcut_must_be_inside_an_allowed_start_menu(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            allowed = root / "Programs"
            allowed.mkdir()
            shortcut = allowed / "Spotify.lnk"
            shortcut.touch()
            outside = root / "Spotify.lnk"
            outside.touch()

            with patch(
                "actions.catalog_launcher.START_MENU_LOCATIONS",
                [allowed],
            ):
                self.assertTrue(is_inside_start_menu(shortcut))
                self.assertFalse(is_inside_start_menu(outside))

    def test_non_shortcut_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "spotify.exe"
            executable.touch()
            with patch(
                "actions.catalog_launcher.START_MENU_LOCATIONS",
                [root],
            ):
                self.assertFalse(is_inside_start_menu(executable))


if __name__ == "__main__":
    unittest.main()
