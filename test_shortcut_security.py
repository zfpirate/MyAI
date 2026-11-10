import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from actions.catalog_launcher import inspect_shortcut, verify_shortcut


class ShortcutSecurityTests(unittest.TestCase):
    def test_relative_shortcut_target_is_rejected(self):
        shortcut = SimpleNamespace(
            TargetPath="Spotify.exe",
            Arguments="",
            WorkingDirectory="",
        )
        shell = SimpleNamespace(
            CreateShortcut=lambda _path: shortcut,
        )
        with patch(
            "actions.catalog_launcher.win32com.client.Dispatch",
            return_value=shell,
        ):
            with self.assertRaisesRegex(ValueError, "absolu"):
                inspect_shortcut("Spotify.lnk")

    def test_shortcut_outside_start_menu_is_rejected_before_inspection(self):
        with (
            patch(
                "actions.catalog_launcher.is_inside_start_menu",
                return_value=False,
            ),
            patch(
                "actions.catalog_launcher.inspect_shortcut"
            ) as inspect,
        ):
            with self.assertRaisesRegex(PermissionError, "menu Démarrer"):
                verify_shortcut("untrusted.lnk", "Spotify")
        inspect.assert_not_called()

    def test_shortcut_must_be_an_existing_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "Spotify.txt"
            target.touch()
            shortcut = SimpleNamespace(
                TargetPath=str(target),
                Arguments="",
                WorkingDirectory=directory,
            )
            shell = SimpleNamespace(
                CreateShortcut=lambda _path: shortcut,
            )
            with patch(
                "actions.catalog_launcher.win32com.client.Dispatch",
                return_value=shell,
            ):
                with self.assertRaisesRegex(PermissionError, r"\.exe"):
                    inspect_shortcut("Spotify.lnk")


if __name__ == "__main__":
    unittest.main()
