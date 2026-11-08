
from security.app_allowlist import ALLOWED_APPS

print("LISTE BLANCHE CAPRI")
print("====================")

for app_id, config in ALLOWED_APPS.items():
    print(
        f"{app_id:15} -> "
        f"{config['catalog_name']}"
    )

print("\nNombre d'applications :", len(ALLOWED_APPS))
