import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from interface.window import CapriWindow


class SystemRefreshTests(unittest.TestCase):
    def test_nvidia_smi_runs_without_opening_a_console(self):
        window = SimpleNamespace(
            cpu_label=Mock(),
            cpu_bar=Mock(),
            ram_label=Mock(),
            ram_bar=Mock(),
            gpu_label=Mock(),
            gpu_temp=Mock(),
        )
        result = SimpleNamespace(returncode=1)

        with (
            patch("interface.window.psutil.cpu_percent", return_value=10),
            patch(
                "interface.window.psutil.virtual_memory",
                return_value=SimpleNamespace(percent=20),
            ),
            patch(
                "interface.window.subprocess.run",
                return_value=result,
            ) as run,
            patch.object(subprocess, "CREATE_NO_WINDOW", 0x08000000,
                         create=True),
        ):
            CapriWindow.refresh_system(window)

        self.assertEqual(
            run.call_args.kwargs["creationflags"],
            0x08000000,
        )


if __name__ == "__main__":
    unittest.main()
