
from actions.applications import (
    register_application_actions,
    get_running_applications,
)

from security.action_manager import (
    request_action,
    confirm_action,
)

register_application_actions()

print("1. Ouverture du Bloc-notes")

opened = request_action(
    "applications.open",
    {"app_id": "notepad"},
    "Ouverture du Bloc-notes",
)

print(opened)

print("\nApplications suivies :")
print(get_running_applications())

print("\n2. Demande de fermeture")

close_request = request_action(
    "applications.close",
    {"app_id": "notepad"},
    "Fermeture du Bloc-notes",
)

print(close_request)

if close_request["status"] == "confirmation_required":
    answer = input(
        "\nConfirmer la fermeture ? Tape OUI pour accepter : "
    )

    approved = answer.strip().upper() == "OUI"

    result = confirm_action(
        close_request["request"]["id"],
        approved,
    )

    print("\nRésultat :", result)
