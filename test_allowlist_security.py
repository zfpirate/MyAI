import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from actions.catalog_launcher import (
    BLOCKED_TARGET_NAMES,
    inspect_shortcut,
)


class ShortcutAllowlistSecurityTests(unittest.TestCase):
    def test_command_interpreters_are_blocked(self):
        for name in (
            "cmd.exe",
            "powershell.exe",
            "python.exe",
            "wscript.exe",
            "rundll32.exe",
        ):
            with self.subTest(name=name):
                self.assertIn(name, BLOCKED_TARGET_NAMES)

    def test_shortcut_cannot_target_a_command_interpreter(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "python.exe"
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
                with self.assertRaisesRegex(PermissionError, "bloqué"):
                    inspect_shortcut(Path(directory) / "untrusted.lnk")


if __name__ == "__main__":
    unittest.main()
