
from actions.command_router import (
    extract_app_name,
    find_application,
    is_open_command,
)

TESTS = [
    "Ouvre Discord",
    "Ouvre discorde",
    "Capri lance crom",
    "Ouvre py charm",
    "Tu peux m'ouvrir le code ?",
    "Démarre la musique",
    "Ouvre obs stp",
    "Lance la calculatrice",
    "Ouvre cap cut",
    "Démarre riot",
]

print("TEST DE COMPREHENSION DE CAPRI")
print("=" * 55)

for message in TESTS:
    query = extract_app_name(message)
    result = find_application(query)

    if result["status"] == "found":
        print(f"[OK] {message}")
        print(f"     -> {result['app']['name']}")

    elif result["status"] == "ambiguous":
        print(f"[PRECISION] {message}")
        for app in result["matches"]:
            print(f"     -> {app['name']}")

    else:
        print(f"[NON RECONNU] {message}")

print("=" * 55)

print("\nTEST DES INTENTIONS")
for message in [
    "Ouvre Discord",
    "Tu peux m'ouvrir Chrome ?",
    "Comment fonctionne Discord ?",
]:
    print(
        f"{message} -> "
        f"{is_open_command(message)}"
    )
