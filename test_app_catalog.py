
from actions.app_catalog import (
    scan_installed_apps,
    get_catalog_apps,
)

print("Analyse des applications Windows...")

count = scan_installed_apps()

print(f"\n{count} raccourcis recensés.\n")

for app in get_catalog_apps():
    print(f"{app['name']} -> {app['shortcut_path']}")
