import os
import threading
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from interface import window as chat_window


class ChatQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_can_send_while_answer_is_running_and_messages_stay_serial(self):
        first_started = threading.Event()
        release_first = threading.Event()
        calls = []

        def answer(message):
            calls.append(message)
            if message == "premier":
                first_started.set()
                if not release_first.wait(5):
                    raise TimeoutError("Le test n'a pas libéré la première réponse.")
            return f"Réponse {message}"

        window = chat_window.CapriWindow()
        window.timer.stop()

        try:
            with patch.object(chat_window, "ask_capri", side_effect=answer):
                window.message_input.setText("premier")
                window.send_message()
                self.assertTrue(first_started.wait(5))

                self.assertTrue(window.message_input.isEnabled())
                self.assertTrue(window.send_button.isEnabled())

                window.message_input.setText("deuxième")
                window.send_message()
                self.assertEqual(list(window.pending_messages), ["deuxième"])
                self.assertTrue(window.message_input.isEnabled())

                release_first.set()
                deadline = time.monotonic() + 10
                while (
                    (window.worker is not None or window.pending_messages)
                    and time.monotonic() < deadline
                ):
                    self.application.processEvents()
                    time.sleep(0.01)
                self.application.processEvents()

            self.assertIsNone(window.worker)
            self.assertEqual(list(window.pending_messages), [])
            self.assertEqual(calls, ["premier", "deuxième"])
            transcript = window.chat.toPlainText()
            self.assertIn("CAPRI : Réponse premier", transcript)
            self.assertIn("CAPRI : Réponse deuxième", transcript)
        finally:
            release_first.set()
            window.close()


if __name__ == "__main__":
    unittest.main()
