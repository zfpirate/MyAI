
from unittest.mock import patch

from actions.catalog_launcher import verify_shortcut

DISCORD_SHORTCUT = (
    r"C:\Users\maxence\AppData\Roaming\Microsoft\Windows"
    r"\Start Menu\Programs\Discord.lnk"
)

FAKE_SHORTCUT_DATA = {
    "target": r"C:\Windows\System32\notepad.exe",
    "arguments": "",
    "working_directory": None,
}

print("TEST DE DETECTION DE FALSIFICATION")
print("=" * 50)

try:
    with patch(
        "actions.catalog_launcher.inspect_shortcut",
        return_value=FAKE_SHORTCUT_DATA
    ):
        verify_shortcut(DISCORD_SHORTCUT, "Discord")

    print("[ERREUR] La cible falsifiée a été acceptée.")

except PermissionError as error:
    print("[OK] Falsification détectée.")
    print(f"Motif : {error}")

except Exception as error:
    print(f"[ERREUR INATTENDUE] {type(error).__name__}: {error}")

print("=" * 50)
print("Aucune application n'a été lancée.")
