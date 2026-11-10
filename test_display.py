import sys
import types
import unittest
from unittest.mock import Mock, patch

from actions.display import (
    set_native_resolution,
    set_resolution,
    validate_display_params,
    validate_resolution_params,
)


class DisplayRoutineTests(unittest.TestCase):
    def test_only_empty_parameters_are_allowed(self):
        self.assertTrue(validate_display_params({}))
        self.assertFalse(validate_display_params({"width": 1920}))
        self.assertFalse(validate_display_params([]))

    def test_resolution_parameters_are_bounded_integers(self):
        self.assertTrue(validate_resolution_params({
            "width": 1200,
            "height": 1080,
        }))
        self.assertFalse(validate_resolution_params({
            "width": True,
            "height": 1080,
        }))
        self.assertFalse(validate_resolution_params({
            "width": 1920,
            "height": 1080,
            "extra": 1,
        }))
        self.assertFalse(validate_resolution_params({
            "width": 100,
            "height": 1080,
        }))

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
            win32api.ChangeDisplaySettingsEx.call_args_list[0].args[2],
            win32con.CDS_TEST,
        )
        self.assertEqual(
            len(win32api.ChangeDisplaySettingsEx.call_args_list[0].args),
            3,
        )
        self.assertIs(
            win32api.ChangeDisplaySettingsEx.call_args_list[1].args[1],
            modes[1],
        )

    def test_applies_requested_supported_resolution(self):
        class DisplayMode:
            def __init__(self, width, height):
                self.PelsWidth = width
                self.PelsHeight = height
                self.DisplayFrequency = 60

        current = DisplayMode(1920, 1080)
        requested = DisplayMode(1200, 1080)
        win32api = types.SimpleNamespace(
            ChangeDisplaySettingsEx=Mock(return_value=0),
            EnumDisplaySettings=Mock(return_value=current),
        )
        win32con = types.SimpleNamespace(
            CDS_TEST=2,
            DISP_CHANGE_SUCCESSFUL=0,
        )
        with (
            patch(
                "actions.display.get_display_modes",
                return_value=(win32api, "DISPLAY1", [requested]),
            ),
            patch.dict(sys.modules, {"win32con": win32con}),
        ):
            result = set_resolution({"width": 1200, "height": 1080})

        self.assertEqual(
            result,
            {"status": "changed", "width": 1200, "height": 1080},
        )
        self.assertEqual(
            win32api.ChangeDisplaySettingsEx.call_args_list[1].args[:2],
            ("DISPLAY1", requested),
        )
        self.assertEqual(
            len(win32api.ChangeDisplaySettingsEx.call_args_list[1].args),
            3,
        )

    def test_rejects_resolution_not_supported_by_display(self):
        supported = types.SimpleNamespace(
            PelsWidth=1920,
            PelsHeight=1080,
            DisplayFrequency=60,
        )
        with patch(
            "actions.display.get_display_modes",
            return_value=(Mock(), "DISPLAY1", [supported]),
        ):
            with self.assertRaisesRegex(ValueError, "pas prise en charge"):
                set_resolution({"width": 1200, "height": 1080})


class DisplayCommandRoutingTests(unittest.TestCase):
    def test_resolution_request_is_handled_as_a_local_command(self):
        from actions import command_router

        success = {
            "status": "success",
            "result": {
                "status": "changed",
                "width": 1200,
                "height": 1080,
            },
        }
        with patch.object(
            command_router,
            "request_action",
            return_value=success,
        ) as request_action:
            result = command_router.route_command(
                "met la res en 1200 par 1080"
            )

        self.assertIn("1200x1080", result)
        request_action.assert_called_once_with(
            "display.set_resolution",
            {"width": 1200, "height": 1080},
            details=(
                "Changement de résolution demandé par l'utilisateur : "
                "1200x1080"
            ),
        )

    def test_resolution_x_notation_is_recognized(self):
        from actions import command_router

        with patch.object(
            command_router,
            "request_action",
            return_value={
                "status": "success",
                "result": {
                    "status": "already_set",
                    "width": 1920,
                    "height": 1080,
                },
            },
        ):
            result = command_router.route_command(
                "Capri, mets la résolution en 1920x1080"
            )

        self.assertIn("déjà réglée", result)


if __name__ == "__main__":
    unittest.main()
