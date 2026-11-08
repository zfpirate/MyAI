
from actions.app_catalog import get_catalog_apps
from actions.catalog_launcher import verify_shortcut
from security.app_allowlist import ALLOWED_BUILTINS

apps = get_catalog_apps()

print("TEST DE LA LISTE BLANCHE")
print("=" * 55)

success = 0
failed = 0

for app in apps:
    name = app["name"]
    shortcut = app["shortcut_path"]

    if name in ALLOWED_BUILTINS.values():
        print(f"[OK] {name} : application intégrée")
        success += 1
        continue

    try:
        config, target = verify_shortcut(shortcut, name)

        print(f"[OK] {name}")
        print(f"     Exécutable : {target}")
        success += 1

    except Exception as error:
        print(f"[REFUS] {name} : {error}")
        failed += 1

print("\n" + "=" * 55)
print(f"Applications vérifiées : {success}")
print(f"Applications refusées  : {failed}")
print("Aucune application n'a été lancée.")

