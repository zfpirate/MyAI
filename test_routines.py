import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from actions.command_router import create_startup_routine_command
from routines.manager import (
    list_routines,
    run_startup_routines,
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
