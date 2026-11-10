"""Application version and bundled resource lookup."""

import sys
from pathlib import Path


APP_VERSION = "0.3.0"
GITHUB_REPOSITORY = "zfpirate/MyAI"


def resource_path(relative_path):
    """Resolve a resource in development and in a PyInstaller bundle."""
    bundle_root = Path(
        getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])
    )
    return bundle_root / relative_path
