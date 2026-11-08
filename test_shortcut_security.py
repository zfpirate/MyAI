
from actions.app_catalog import get_catalog_apps
from actions.catalog_launcher import (
    is_inside_start_menu,
    inspect_shortcut,
)

apps = get_catalog_apps()

tested = 0

for app in apps:
    path = app["shortcut_path"]

    if path.startswith("builtin://"):
        continue

    if not is_inside_start_menu(path):
        print("[REFUSE] Emplacement :", app["name"])
        continue

    try:
        info = inspect_shortcut(path)

        print("[ACCEPTE]", app["name"])
        print("  Cible :", info["target"])

    except Exception as error:
        print("[REFUSE]", app["name"])
        print("  Motif :", error)

    tested += 1

print(f"\nInspection terminée : {tested} raccourcis.")
print("Aucune application n'a été lancée.")
