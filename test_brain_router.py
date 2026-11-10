import unittest
from unittest.mock import patch

import core.brain as brain


class BrainCommandRouterTests(unittest.TestCase):
    def test_local_command_result_is_returned_without_calling_ollama(self):
        with patch.object(
            brain,
            "route_command",
            return_value="ROUTEUR CONNECTÉ",
        ) as route_command:
            result = brain.ask_capri("ouvre Discord")

        self.assertEqual(result, "ROUTEUR CONNECTÉ")
        route_command.assert_called_once_with("ouvre Discord")


if __name__ == "__main__":
    unittest.main()
