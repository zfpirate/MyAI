
from actions.catalog_launcher import register_catalog_launcher
from security.action_manager import list_actions

print("Enregistrement du lanceur...")
register_catalog_launcher()

print("\nActions disponibles :")
for action in list_actions():
    print(
        action["id"],
        "->",
        action["permission_id"],
        "|",
        action["description"],
    )
