
import win32com.client

from pathlib import Path
from security.app_allowlist import ALLOWED_APPS
from actions.app_catalog import get_catalog_apps

shell = win32com.client.Dispatch("WScript.Shell")
catalog = get_catalog_apps()

print("INSPECTION DES APPLICATIONS AUTORISÉES")
print("=" * 55)

for app_id, config in ALLOWED_APPS.items():

    if config.get("builtin"):
        print(f"\n[{app_id}] Application intégrée à CAPRI")
        continue

    expected_name = config["catalog_name"].casefold()

    matches = [
        app for app in catalog
        if expected_name in app["name"].casefold()
    ]

    print(f"\n[{app_id}] {config['catalog_name']}")

    if not matches:
        print("  INTROUVABLE DANS LE CATALOGUE")
        continue

    for app in matches:
        shortcut_path = Path(app["shortcut_path"])

        print(f"  Nom : {app['name']}")
        print(f"  Raccourci : {shortcut_path}")

        if shortcut_path.suffix.lower() != ".lnk":
            print("  Pas un raccourci Windows classique.")
            continue

        try:
            shortcut = shell.CreateShortcut(str(shortcut_path))

            print(f"  Cible : {shortcut.TargetPath}")
            print(f"  Arguments : {shortcut.Arguments}")
            print(f"  Dossier : {shortcut.WorkingDirectory}")

        except Exception as error:
            print(f"  ERREUR : {error}")

print("\nInspection terminée. Aucune application lancée.")
