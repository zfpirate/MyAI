import unittest

from security.app_allowlist import ALLOWED_BUILTINS, ALLOWED_SHORTCUTS


class ApplicationAllowlistTests(unittest.TestCase):
    def test_builtin_allowlist_contains_only_supported_apps(self):
        self.assertEqual(
            ALLOWED_BUILTINS,
            {
                "notepad": "Bloc-notes",
                "calculator": "Calculatrice",
            },
        )

    def test_external_shortcuts_have_explicit_executable_targets(self):
        self.assertTrue(ALLOWED_SHORTCUTS)
        for shortcut_path, config in ALLOWED_SHORTCUTS.items():
            with self.subTest(shortcut=shortcut_path):
                self.assertTrue(shortcut_path.lower().endswith(".lnk"))
                self.assertTrue(config["name"])
                self.assertTrue(config["target"].lower().endswith(".exe"))
                self.assertIsInstance(config["arguments"], tuple)


if __name__ == "__main__":
    unittest.main()
