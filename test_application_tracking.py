import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from actions import applications, catalog_launcher, command_router
from security.action_manager import list_actions


class ApplicationTrackingTests(unittest.TestCase):
    def setUp(self):
        applications._RUNNING_WINDOWS.clear()
        applications._RUNNING_CATALOG_WINDOWS.clear()

    def test_application_actions_are_registered_idempotently(self):
        applications.register_application_actions()
        applications.register_application_actions()
        catalog_launcher.register_catalog_launcher()
        catalog_launcher.register_catalog_launcher()

        action_ids = {action["id"] for action in list_actions()}
        self.assertTrue({
            "applications.open",
            "applications.close",
            "applications.open_catalog",
            "applications.close_catalog",
        }.issubset(action_ids))

    def test_versioned_child_window_is_tracked_and_can_be_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "Discord.exe"
            child = root / "app-1.0" / "Discord Helper.exe"
            target.parent.mkdir(parents=True, exist_ok=True)
            child.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
            child.touch()

            window = {"hwnd": 101, "pid": 202, "title": "Discord"}
            process = Mock(pid=303)
            with (
                patch.object(
                    catalog_launcher,
                    "get_catalog_app",
                    return_value={
                        "app_id": "discord",
                        "name": "Discord",
                        "shortcut_path": "discord.lnk",
                    },
                ),
                patch.object(
                    catalog_launcher,
                    "verify_shortcut",
                    return_value=(
                        {
                            "target": target,
                            "arguments": [],
                            "working_directory": root,
                        },
                        {"publisher": "CN=Discord"},
                    ),
                ),
                patch.object(
                    catalog_launcher.subprocess,
                    "Popen",
                    return_value=process,
                ),
                patch.object(
                    catalog_launcher,
                    "get_visible_windows",
                    side_effect=[[window], [window]],
                ),
                patch.object(
                    applications,
                    "get_window_identity",
                    return_value={
                        "pid": 202,
                        "process_path": str(child),
                        "process_creation_time": 1234,
                    },
                ),
                patch.object(
                    applications,
                    "verify_catalog_process",
                    return_value={"publisher": "CN=Discord"},
                ) as verify_process,
                patch.object(
                    catalog_launcher,
                    "verify_catalog_process",
                    return_value={"publisher": "CN=Discord"},
                ),
                patch.object(
                    catalog_launcher,
                    "get_process_path",
                    return_value=str(child),
                ),
                patch.object(
                    catalog_launcher,
                    "is_catalog_process_path",
                    return_value=True,
                ),
                patch.object(applications, "user32") as user32,
                patch.object(catalog_launcher.time, "monotonic",
                             return_value=1),
                patch.object(catalog_launcher.time, "sleep"),
            ):
                user32.IsWindow.side_effect = [True, False]
                user32.PostMessageW.return_value = True

                result = catalog_launcher.launch_catalog_application({
                    "app_id": "discord",
                })

                self.assertEqual(result["status"], "reused_and_tracked")
                self.assertEqual(result["process_id"], 202)
                self.assertEqual(result["launch_process_id"], 303)
                self.assertEqual(
                    applications._RUNNING_CATALOG_WINDOWS["discord"][0]["pid"],
                    202,
                )

                close_result = applications.close_catalog_window({
                    "app_id": "discord",
                })
                self.assertEqual(close_result["status"], "closed")
                user32.PostMessageW.assert_called_once_with(
                    101,
                    applications.WM_CLOSE,
                    0,
                    0,
                )
                self.assertGreaterEqual(verify_process.call_count, 1)

    def test_untracked_catalog_window_is_never_closed(self):
        with patch.object(applications, "user32") as user32:
            with self.assertRaisesRegex(RuntimeError, "aucune fenêtre"):
                applications.close_catalog_window({"app_id": "discord"})

            user32.PostMessageW.assert_not_called()

    def test_hidden_primary_application_window_is_trackable(self):
        primary_window = {
            "hwnd": 101,
            "pid": 202,
            "visible": False,
            "owner": 0,
            "style": 0x24030000,
            "class_name": "Chrome_WidgetWin_1",
        }
        helper_window = {
            **primary_window,
            "hwnd": 102,
            "pid": 203,
        }

        with patch.object(applications.psutil, "Process") as process:
            process.return_value.cmdline.return_value = ["Discord.exe"]
            self.assertTrue(
                applications.is_trackable_application_window(primary_window)
            )

            process.return_value.cmdline.return_value = [
                "Discord.exe",
                "--type=renderer",
            ]
            self.assertFalse(
                applications.is_trackable_application_window(helper_window)
            )

            process.return_value.cmdline.return_value = ["Discord.exe"]
            self.assertFalse(applications.is_trackable_application_window({
                **primary_window,
                "owner": 999,
            }))

    def test_reused_hwnd_with_different_process_is_never_closed(self):
        applications._RUNNING_CATALOG_WINDOWS["discord"] = [{
            "hwnd": 101,
            "expected_path": "c:\\apps\\discord\\discord.exe",
            "process_path": "c:\\apps\\discord\\app-1.0\\discord.exe",
            "pid": 202,
            "process_creation_time": 1234,
            "expected_publisher": "CN=Discord",
            "label": "Discord",
        }]

        with (
            patch.object(applications, "user32") as user32,
            patch.object(applications, "get_window_identity", return_value={
                "pid": 999,
                "process_path": "c:\\apps\\discord\\app-1.0\\discord.exe",
                "process_creation_time": 5678,
            }),
        ):
            user32.IsWindow.return_value = True
            with self.assertRaisesRegex(RuntimeError, "aucune fenêtre"):
                applications.close_catalog_window({"app_id": "discord"})

            user32.PostMessageW.assert_not_called()

    def test_builtin_window_tracking_checks_process_identity(self):
        identity = {
            "pid": 202,
            "process_path": "c:\\windows\\system32\\notepad.exe",
            "process_creation_time": 1234,
        }
        window = {"hwnd": 101, "pid": 202, "title": "Sans titre"}

        with (
            patch.object(applications, "ALLOWED_APPLICATIONS", {
                "notepad": {
                    "label": "Bloc-notes",
                    "path": Path("C:/Windows/System32/notepad.exe"),
                    "process_names": {"notepad.exe"},
                },
            }),
            patch.object(applications, "get_visible_windows",
                         side_effect=[[window], [window]]),
            patch.object(applications, "get_window_identity",
                         return_value=identity),
            patch.object(applications.subprocess, "Popen"),
            patch.object(applications.time, "monotonic",
                         return_value=1),
            patch.object(applications.time, "sleep"),
            patch.object(applications, "user32") as user32,
        ):
            user32.PostMessageW.return_value = True
            user32.IsWindow.return_value = False
            result = applications.open_application({"app_id": "notepad"})

            self.assertEqual(result["status"], "reused_and_tracked")
            self.assertEqual(len(applications.get_running_applications()), 1)

            applications.close_application({"app_id": "notepad"})
            user32.PostMessageW.assert_called_once_with(
                101,
                applications.WM_CLOSE,
                0,
                0,
            )

    def test_notepad_package_identity_is_exact(self):
        identity = {
            "process_path": (
                "c:\\program files\\windowsapps\\"
                "microsoft.windowsnotepad_11.2607.14.0_x64__"
                "8wekyb3d8bbwe\\notepad\\notepad.exe"
            ),
            "package_family": "Microsoft.WindowsNotepad_8wekyb3d8bbwe",
        }

        self.assertTrue(
            applications.is_expected_process_identity(identity, "notepad")
        )
        self.assertFalse(applications.is_expected_process_identity(
            {
                **identity,
                "package_family": "Other.Publisher_1234567890",
            },
            "notepad",
        ))
        self.assertFalse(applications.is_expected_process_identity(
            {
                **identity,
                "process_path": "c:\\temp\\notepad.exe",
            },
            "notepad",
        ))

    def test_calculator_package_identity_is_exact(self):
        identity = {
            "process_path": (
                "c:\\program files\\windowsapps\\"
                "microsoft.windowscalculator_11.0_x64__"
                "8wekyb3d8bbwe\\calculatorapp.exe"
            ),
            "package_family": "Microsoft.WindowsCalculator_8wekyb3d8bbwe",
        }

        self.assertTrue(
            applications.is_expected_process_identity(identity, "calculator")
        )
        self.assertFalse(applications.is_expected_process_identity(
            {**identity, "package_family": None},
            "calculator",
        ))

    def test_catalog_accepts_signed_install_child_executable_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install = root / "install"
            target = install / "Launcher.exe"
            child = install / "versions" / "ApplicationUI.exe"
            outside = root / "other" / "ApplicationUI.exe"
            child.parent.mkdir(parents=True)
            outside.parent.mkdir()
            target.touch()
            child.touch()
            outside.touch()

            self.assertTrue(
                applications.is_catalog_process_path(child, target)
            )
            self.assertFalse(
                applications.is_catalog_process_path(outside, target)
            )

    def test_catalog_process_with_different_publisher_is_rejected(self):
        with patch(
            "security.signature_verifier.verify_authenticode",
            return_value={"publisher": "CN=Other Publisher"},
        ):
            self.assertFalse(applications.verify_catalog_process(
                "C:\\Apps\\Application\\Helper.exe",
                "CN=Trusted Publisher",
                "Application",
            ))

    def test_packaged_notepad_requires_microsoft_signature(self):
        identity = {
            "process_path": (
                "c:\\program files\\windowsapps\\"
                "microsoft.windowsnotepad_11.2607.14.0_x64__"
                "8wekyb3d8bbwe\\notepad\\notepad.exe"
            ),
            "package_family": "Microsoft.WindowsNotepad_8wekyb3d8bbwe",
        }
        microsoft_publisher = (
            "CN=Microsoft Corporation, O=Microsoft Corporation, "
            "L=Redmond, S=Washington, C=US"
        )

        with patch(
            "security.signature_verifier.verify_authenticode",
            return_value={"publisher": microsoft_publisher},
        ):
            self.assertTrue(
                applications.verify_expected_application_identity(
                    identity,
                    "notepad",
                )
            )

        with patch(
            "security.signature_verifier.verify_authenticode",
            return_value={"publisher": "CN=Untrusted Publisher"},
        ):
            with self.assertRaisesRegex(PermissionError, "éditeur"):
                applications.verify_expected_application_identity(
                    identity,
                    "notepad",
                )

    def test_packaged_notepad_close_rechecks_signature_and_posts_wm_close(self):
        identity = {
            "pid": 202,
            "process_path": (
                "c:\\program files\\windowsapps\\"
                "microsoft.windowsnotepad_11.2607.14.0_x64__"
                "8wekyb3d8bbwe\\notepad\\notepad.exe"
            ),
            "package_family": "Microsoft.WindowsNotepad_8wekyb3d8bbwe",
            "process_creation_time": 1234,
        }
        applications._RUNNING_WINDOWS["notepad"] = [{
            "hwnd": 101,
            **identity,
        }]
        publisher = (
            "CN=Microsoft Corporation, O=Microsoft Corporation, "
            "L=Redmond, S=Washington, C=US"
        )

        with (
            patch.object(applications, "get_window_identity",
                         return_value=identity),
            patch.object(applications, "user32") as user32,
            patch(
                "security.signature_verifier.verify_authenticode",
                return_value={"publisher": publisher},
            ) as verify_signature,
        ):
            user32.PostMessageW.return_value = True
            user32.IsWindow.return_value = False
            result = applications.close_application({"app_id": "notepad"})

        self.assertEqual(result["status"], "closed")
        verify_signature.assert_called_once_with(
            identity["process_path"],
            "Bloc-notes",
        )
        user32.PostMessageW.assert_called_once_with(
            101,
            applications.WM_CLOSE,
            0,
            0,
        )

    def test_close_status_distinguishes_closed_hidden_and_still_open(self):
        with patch.object(applications, "user32") as user32:
            user32.PostMessageW.return_value = True
            user32.IsWindow.return_value = False
            self.assertEqual(
                applications.request_window_close(101, process_id=202),
                "closed",
            )

            user32.IsWindow.return_value = True
            user32.IsWindowVisible.return_value = False
            self.assertEqual(
                applications.request_window_close(102),
                "hidden_in_background",
            )

            user32.IsWindowVisible.return_value = True
            with (
                patch.object(applications.time, "monotonic",
                             side_effect=[0, 2]),
                patch.object(applications.time, "sleep"),
            ):
                self.assertEqual(
                    applications.request_window_close(103, timeout=1),
                    "still_open",
                )

        with (
            patch.object(applications, "user32") as user32,
            patch.object(applications, "get_process_identity", return_value={
                "process_path": "c:\\apps\\spotify\\spotify.exe",
                "process_creation_time": 456,
            }),
            patch.object(applications.time, "monotonic",
                         side_effect=[0, 1.5]),
            patch.object(applications.time, "sleep"),
        ):
            user32.PostMessageW.return_value = True
            user32.IsWindow.return_value = False
            self.assertEqual(
                applications.request_window_close(
                    104,
                    process_id=202,
                    process_creation_time=456,
                    process_path="c:\\apps\\spotify\\spotify.exe",
                ),
                "closed_in_background",
            )

    def test_catalog_close_stops_verified_process_tree_when_window_hides(self):
        root_identity = {
            "pid": 202,
            "process_path": "c:\\apps\\discord\\discord.exe",
            "process_creation_time": 456,
        }
        child_identity = {
            "pid": 303,
            "process_path": "c:\\apps\\discord\\discord.exe",
            "process_creation_time": 789,
        }
        applications._RUNNING_CATALOG_WINDOWS["discord"] = [{
            "hwnd": 101,
            **root_identity,
            "expected_path": "c:\\apps\\discord\\discord.exe",
            "expected_publisher": "CN=Discord",
            "label": "Discord",
        }]
        root_process = Mock(pid=202)
        child_process = Mock(pid=303)
        root_process.children.return_value = [child_process]

        with (
            patch.object(
                applications,
                "get_window_identity",
                return_value=root_identity,
            ),
            patch.object(applications, "user32") as user32,
            patch.object(
                applications,
                "get_process_identity",
                side_effect=lambda pid: {
                    202: root_identity,
                    303: child_identity,
                }[pid],
            ),
            patch.object(
                applications,
                "is_catalog_process_path",
                return_value=True,
            ),
            patch.object(
                applications,
                "verify_catalog_process",
                return_value={"publisher": "CN=Discord"},
            ),
            patch.object(
                applications,
                "request_window_close",
                return_value="hidden_in_background",
            ),
            patch.object(
                applications.psutil,
                "Process",
                return_value=root_process,
            ),
            patch.object(
                applications.psutil,
                "wait_procs",
                return_value=([], []),
            ) as wait_procs,
        ):
            user32.IsWindow.return_value = True
            result = applications.close_catalog_window({"app_id": "discord"})

        self.assertEqual(result["status"], "closed")
        child_process.terminate.assert_called_once_with()
        root_process.terminate.assert_called_once_with()
        wait_procs.assert_called_once()

    def test_catalog_close_never_terminates_wrong_publisher(self):
        identity = {
            "pid": 202,
            "process_path": "c:\\apps\\discord\\discord.exe",
            "process_creation_time": 456,
        }
        applications._RUNNING_CATALOG_WINDOWS["discord"] = [{
            "hwnd": 101,
            **identity,
            "expected_path": "c:\\apps\\discord\\discord.exe",
            "expected_publisher": "CN=Discord",
            "label": "Discord",
        }]
        root_process = Mock(pid=202)

        with (
            patch.object(
                applications,
                "get_window_identity",
                return_value=identity,
            ),
            patch.object(applications, "user32") as user32,
            patch.object(
                applications,
                "get_process_identity",
                return_value=identity,
            ),
            patch.object(
                applications,
                "is_catalog_process_path",
                return_value=True,
            ),
            patch.object(
                applications,
                "verify_catalog_process",
                side_effect=[
                    {"publisher": "CN=Discord"},
                    False,
                ],
            ),
            patch.object(
                applications,
                "request_window_close",
                return_value="hidden_in_background",
            ),
            patch.object(
                applications.psutil,
                "Process",
                return_value=root_process,
            ),
        ):
            user32.IsWindow.return_value = True
            with self.assertRaisesRegex(PermissionError, "processus"):
                applications.close_catalog_window({"app_id": "discord"})

        root_process.terminate.assert_not_called()

    def test_tracked_window_is_restored_and_brought_forward(self):
        with patch.object(applications, "user32") as user32:
            applications.show_tracked_window(101)

        user32.ShowWindow.assert_called_once_with(101, applications.SW_RESTORE)
        user32.SetForegroundWindow.assert_called_once_with(101)

    def test_close_router_reports_apps_that_hide_to_tray(self):
        spotify = {
            "app_id": "spotify",
            "name": "Spotify",
        }
        with (
            patch.object(command_router, "find_application",
                         return_value={"status": "found", "app": spotify}),
            patch.object(command_router, "request_action", return_value={
                "status": "success",
                "result": {"status": "hidden_in_background"},
            }),
        ):
            result = command_router.close_one_application("spotify")

        self.assertIn("fenêtre fermée", result)
        self.assertIn("reste active en arrière-plan", result)

    def test_close_router_confirms_application_exit(self):
        discord = {
            "app_id": "discord",
            "name": "Discord",
        }
        with (
            patch.object(command_router, "find_application",
                         return_value={"status": "found", "app": discord}),
            patch.object(command_router, "request_action", return_value={
                "status": "success",
                "result": {"status": "closed"},
            }),
        ):
            result = command_router.close_one_application("discord")

        self.assertIn("Discord : application fermée", result)

    def test_multi_application_close_routes_each_target(self):
        with patch.object(
            command_router,
            "close_one_application",
            side_effect=lambda name: f"fermeture de {name}",
        ) as close_one:
            result = command_router.route_command("Ferme Discord et Edge")

        self.assertIn("fermeture de discord", result)
        self.assertIn("fermeture de edge", result)
        self.assertEqual(
            [call.args[0] for call in close_one.call_args_list],
            ["discord", "edge"],
        )


if __name__ == "__main__":
    unittest.main()
