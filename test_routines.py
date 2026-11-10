import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from actions.command_router import create_startup_routine_command
from routines.manager import (
    get_application_launch_triggers,
    list_routines,
    run_application_launch_routines,
    run_startup_routines,
    save_application_launch_routine,
    save_startup_routine,
    set_routine_enabled,
)


class StartupRoutineCommandTests(unittest.TestCase):
    def test_creates_routine_from_startup_command(self):
        apps = {
            "spotify": {
                "status": "found",
                "app": {"app_id": "spotify-id", "name": "Spotify"},
            },
            "riot client": {
                "status": "found",
                "app": {"app_id": "riot-id", "name": "Riot Client"},
            },
        }

        with (
            patch(
                "actions.command_router.find_application",
                side_effect=lambda query: apps[query],
            ),
            patch("routines.manager.save_startup_routine") as save_routine,
        ):
            result = create_startup_routine_command(
                "Quand CAPRI démarre, ouvre Spotify et Riot Client"
            )

        self.assertIn("créée et activée", result)
        save_routine.assert_called_once_with(
            "Au démarrage : Spotify et Riot Client",
            ["spotify-id", "riot-id"],
        )

    def test_does_not_save_unknown_application(self):
        with (
            patch(
                "actions.command_router.find_application",
                return_value={"status": "not_found", "matches": []},
            ),
            patch("routines.manager.save_startup_routine") as save_routine,
        ):
            result = create_startup_routine_command(
                "Au démarrage ouvre une application inconnue"
            )

        self.assertIn("application non reconnue", result)
        save_routine.assert_not_called()

    def test_creates_startup_routine_for_windows_startup(self):
        apps = {
            "valorant": {
                "status": "found",
                "app": {"app_id": "valorant-id", "name": "Valorant"},
            },
            "spotify": {
                "status": "found",
                "app": {"app_id": "spotify-id", "name": "Spotify"},
            },
        }

        with (
            patch(
                "actions.command_router.find_application",
                side_effect=lambda query: apps[query],
            ),
            patch("routines.manager.save_startup_routine") as save_routine,
            patch(
                "routines.windows_startup.set_windows_startup_enabled"
            ) as set_startup,
        ):
            result = create_startup_routine_command(
                "Capri au démarrage du PC, lance Valorant et Spotify"
            )

        self.assertIn("créée et activée", result)
        save_routine.assert_called_once_with(
            "Au démarrage : Valorant et Spotify",
            ["valorant-id", "spotify-id"],
        )
        set_startup.assert_called_once_with(True)

    def test_chat_request_creates_a_windows_startup_routine(self):
        import core.brain as brain

        apps = {
            "valorant": {
                "status": "found",
                "app": {"app_id": "valorant-id", "name": "Valorant"},
            },
            "spotify": {
                "status": "found",
                "app": {"app_id": "spotify-id", "name": "Spotify"},
            },
        }
        with (
            patch(
                "actions.command_router.find_application",
                side_effect=lambda query: apps[query],
            ),
            patch("routines.manager.save_startup_routine") as save_routine,
            patch(
                "routines.windows_startup.set_windows_startup_enabled"
            ) as set_startup,
        ):
            answer = brain.ask_capri(
                "Capri, peux-tu créer une routine au démarrage du PC "
                "pour lancer Valorant et Spotify ?"
            )

        self.assertIn("créée et activée", answer)
        save_routine.assert_called_once_with(
            "Au démarrage : Valorant et Spotify",
            ["valorant-id", "spotify-id"],
        )
        set_startup.assert_called_once_with(True)

    def test_chat_request_creates_an_application_launch_routine(self):
        import core.brain as brain

        with (
            patch(
                "actions.command_router.find_application",
                return_value={
                    "status": "found",
                    "app": {"app_id": "osu-id", "name": "osu!"},
                },
            ),
            patch(
                "routines.manager.save_application_launch_routine"
            ) as save_routine,
        ):
            answer = brain.ask_capri(
                "Capri, peux-tu créer une routine : quand je lance osu, "
                "mets la résolution du PC en natif ?"
            )

        self.assertIn("créée et activée", answer)
        save_routine.assert_called_once_with(
            "Quand osu! démarre : résolution native",
            "osu-id",
            "native_resolution",
        )

    def test_creates_native_resolution_app_launch_routine(self):
        from actions.command_router import (
            create_application_launch_routine_command,
        )

        with (
            patch(
                "actions.command_router.find_application",
                return_value={
                    "status": "found",
                    "app": {"app_id": "osu-id", "name": "osu!"},
                },
            ),
            patch(
                "routines.manager.save_application_launch_routine"
            ) as save_routine,
        ):
            result = create_application_launch_routine_command(
                "Capri, quand je lance osu change les res du PC à natif"
            )

        self.assertIn("créée et activée", result)
        save_routine.assert_called_once_with(
            "Quand osu! démarre : résolution native",
            "osu-id",
            "native_resolution",
        )


class StartupRoutineStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "capri.db"
        self.db_path_patch = patch("memory.database.DB_PATH", self.db_path)
        self.db_path_patch.start()
        self.addCleanup(self.db_path_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def save_routine(self):
        app = {"app_id": "spotify-id"}
        with patch("actions.app_catalog.get_catalog_app", return_value=app):
            return save_startup_routine(
                "Au démarrage : Spotify",
                ["spotify-id"],
            )

    def test_routine_storage_and_disable(self):
        routine_id = self.save_routine()

        self.assertEqual(len(list_routines()), 1)
        self.assertTrue(list_routines()[0]["enabled"])

        set_routine_enabled(routine_id, False)

        self.assertFalse(list_routines()[0]["enabled"])

    def test_application_launch_routine_is_stored_and_resolved(self):
        with (
            patch(
                "actions.app_catalog.get_catalog_app",
                return_value={
                    "app_id": "osu-id",
                    "name": "osu!",
                    "shortcut_path": "osu.lnk",
                },
            ),
        ):
            save_application_launch_routine(
                "Quand osu! démarre : résolution native",
                "osu-id",
                "native_resolution",
            )

        self.assertEqual(list_routines()[0]["trigger_type"], "application_launch")
        self.assertEqual(list_routines()[0]["app_ids"], [])
        self.assertEqual(
            list_routines()[0]["action_type"],
            "native_resolution",
        )

        with (
            patch(
                "actions.app_catalog.get_catalog_app",
                return_value={
                    "app_id": "osu-id",
                    "name": "osu!",
                    "shortcut_path": "osu.lnk",
                },
            ),
            patch(
                "actions.catalog_launcher.verify_shortcut",
                return_value=(
                    {"target": Path("osu!.exe")},
                    {"publisher": "CN=osu!"},
                ),
            ),
        ):
            self.assertEqual(
                get_application_launch_triggers(),
                {"osu!.exe": {"osu-id"}},
            )

        with (
            patch("actions.display.register_display_actions"),
            patch(
                "security.action_manager.request_action",
                return_value={"status": "success", "result": {"status": "changed"}},
            ) as request_action,
        ):
            result = run_application_launch_routines({"osu-id"})

        request_action.assert_called_once_with(
            "display.set_native_resolution",
            {},
            details=(
                "Routine « Quand osu! démarre : résolution native » "
                "après le lancement de son application"
            ),
        )
        self.assertEqual(result[0]["status"], "success")

    def test_disabled_routine_is_not_executed(self):
        routine_id = self.save_routine()
        set_routine_enabled(routine_id, False)

        with (
            patch("actions.catalog_launcher.register_catalog_launcher"),
            patch("security.action_manager.request_action") as request_action,
        ):
            result = run_startup_routines()

        self.assertEqual(result, [])
        request_action.assert_not_called()

    def test_enabled_routine_preserves_permission_confirmation(self):
        self.save_routine()

        with (
            patch("actions.catalog_launcher.register_catalog_launcher"),
            patch(
                "security.action_manager.request_action",
                return_value={
                    "status": "confirmation_required",
                    "message": "Une confirmation est nécessaire.",
                },
            ) as request_action,
        ):
            result = run_startup_routines()

        request_action.assert_called_once()
        self.assertEqual(
            result[0]["applications"][0]["status"],
            "confirmation_required",
        )
        self.assertEqual(
            result[0]["applications"][0]["message"],
            "Une confirmation est nécessaire.",
        )


if __name__ == "__main__":
    unittest.main()
