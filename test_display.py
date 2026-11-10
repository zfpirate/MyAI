import sys
import types
import unittest
from unittest.mock import Mock, patch

from actions.display import set_native_resolution, validate_display_params


class DisplayRoutineTests(unittest.TestCase):
    def test_only_empty_parameters_are_allowed(self):
        self.assertTrue(validate_display_params({}))
        self.assertFalse(validate_display_params({"width": 1920}))
        self.assertFalse(validate_display_params([]))

    def test_applies_highest_supported_resolution(self):
        class DisplayMode:
            def __init__(self, width, height, frequency=60):
                self.PelsWidth = width
                self.PelsHeight = height
                self.DisplayFrequency = frequency

        current = DisplayMode(1280, 720)
        modes = [
            DisplayMode(1920, 1080),
            DisplayMode(2560, 1440),
        ]

        def enum_display_settings(_device, index):
            if index == -1:
                return current
            if index < len(modes):
                return modes[index]
            raise RuntimeError("Enumeration terminée")

        win32api = types.SimpleNamespace(
            error=RuntimeError,
            EnumDisplaySettings=enum_display_settings,
            ChangeDisplaySettingsEx=Mock(return_value=0),
        )
        win32con = types.SimpleNamespace(
            CDS_TEST=2,
            DISP_CHANGE_SUCCESSFUL=0,
        )
        with (
            patch("actions.display.os.name", "nt"),
            patch.dict(
                sys.modules,
                {"win32api": win32api, "win32con": win32con},
            ),
        ):
            result = set_native_resolution({})

        self.assertEqual(
            result,
            {"status": "changed", "width": 2560, "height": 1440},
        )
        self.assertEqual(
            win32api.ChangeDisplaySettingsEx.call_count,
            2,
        )
        self.assertEqual(
            win32api.ChangeDisplaySettingsEx.call_args_list[0].args[3],
            win32con.CDS_TEST,
        )
        self.assertIs(
            win32api.ChangeDisplaySettingsEx.call_args_list[1].args[1],
            modes[1],
        )


if __name__ == "__main__":
    unittest.main()
