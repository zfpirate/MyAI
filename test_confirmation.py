import unittest
from unittest.mock import patch

from security import confirmation


class ConfirmationRequestTests(unittest.TestCase):
    def setUp(self):
        confirmation._pending_requests.clear()

    def tearDown(self):
        confirmation._pending_requests.clear()

    def test_confirmation_requires_permission_and_can_be_approved_once(self):
        with (
            patch(
                "security.confirmation.check_permission",
                return_value="needs_confirmation",
            ),
            patch("security.confirmation.log_activity"),
        ):
            request = confirmation.create_confirmation_request(
                "apps.close",
                "Fermer Spotify",
            )
            self.assertIsNotNone(request)
            self.assertTrue(
                confirmation.resolve_confirmation_request(
                    request["id"],
                    True,
                )
            )
            self.assertFalse(
                confirmation.resolve_confirmation_request(
                    request["id"],
                    True,
                )
            )

    def test_confirmation_is_not_created_without_confirmation_permission(self):
        with patch(
            "security.confirmation.check_permission",
            return_value="denied",
        ):
            self.assertIsNone(
                confirmation.create_confirmation_request("apps.close")
            )


if __name__ == "__main__":
    unittest.main()
