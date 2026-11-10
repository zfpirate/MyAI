import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from routines.windows_startup import (
    get_startup_shortcut_path,
    is_windows_startup_enabled,
    set_windows_startup_enabled,
)


class WindowsStartupTests(unittest.TestCase):
    def test_creates_and_removes_background_startup_shortcut(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app_data = root / "AppData"
            python_directory = root / "venv" / "Scripts"
            python_directory.mkdir(parents=True)
            (python_directory / "pythonw.exe").touch()
            shortcut_data = {}

            class Shortcut:
                def save(self):
                    Path(shortcut_data["path"]).write_text(
                        "shortcut",
                        encoding="utf-8",
                    )

            def create_shortcut(path):
                shortcut_data["path"] = path
                shortcut_data["shortcut"] = Shortcut()
                return shortcut_data["shortcut"]

            pythoncom = types.SimpleNamespace(
                CoInitialize=Mock(),
                CoUninitialize=Mock(),
            )
            client = types.ModuleType("win32com.client")
            client.Dispatch = Mock(
                return_value=types.SimpleNamespace(
                    CreateShortCut=create_shortcut,
                )
            )
            win32com = types.ModuleType("win32com")
            win32com.client = client

            with (
                patch.dict(os.environ, {"APPDATA": str(app_data)}),
                patch("routines.windows_startup.sys.executable",
                      str(python_directory / "python.exe")),
                patch.dict(
                    sys.modules,
                    {
                        "pythoncom": pythoncom,
                        "win32com": win32com,
                        "win32com.client": client,
                    },
                ),
            ):
                set_windows_startup_enabled(True)

                shortcut_path = get_startup_shortcut_path()
                self.assertTrue(shortcut_path.is_file())
                self.assertTrue(is_windows_startup_enabled())
                self.assertEqual(
                    shortcut_data["shortcut"].TargetPath,
                    str(python_directory / "pythonw.exe"),
                )
                self.assertIn("--background", shortcut_data["shortcut"].Arguments)
                pythoncom.CoInitialize.assert_called_once()
                pythoncom.CoUninitialize.assert_called_once()

                set_windows_startup_enabled(False)

            self.assertFalse(shortcut_path.exists())


if __name__ == "__main__":
    unittest.main()
