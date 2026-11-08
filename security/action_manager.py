
"""
Gestionnaire central des actions de CAPRI.

L'IA peut demander une action, mais ne peut pas
enregistrer elle-même de nouvelles fonctions.
"""

from copy import deepcopy

from security.permissions import PERMISSIONS
from security.permission_manager import check_permission
from security.confirmation import (
    create_confirmation_request,
    resolve_confirmation_request,
)
from security.activity_log import log_activity


# Registre interne des actions autorisées.
_ACTIONS = {}

# Actions en attente de confirmation.
_PENDING_ACTIONS = {}


def register_action(
    action_id,
    permission_id,
    handler,
    description="",
    validator=None,
):
    """
    Enregistre une action dans le programme.

    Cette fonction doit être appelée uniquement par
    les modules Python de confiance de CAPRI.
    """

    if not isinstance(action_id, str) or not action_id:
        raise ValueError("Identifiant d'action invalide.")

    if action_id in _ACTIONS:
        raise ValueError("Cette action existe déjà.")

    if permission_id not in PERMISSIONS:
        raise ValueError("Permission inconnue.")

    if not callable(handler):
        raise ValueError("Handler invalide.")

    if validator is not None and not callable(validator):
        raise ValueError("Validateur invalide.")

    _ACTIONS[action_id] = {
        "permission_id": permission_id,
        "handler": handler,
        "description": description,
        "validator": validator,
    }


def list_actions():
    """Retourne la liste des actions disponibles."""

    return [
        {
            "id": action_id,
            "permission_id": config["permission_id"],
            "description": config["description"],
        }
        for action_id, config in _ACTIONS.items()
    ]


def _execute_action(action_id, params, details):
    """Exécute une action déjà autorisée."""

    config = _ACTIONS[action_id]

    try:
        result = config["handler"](deepcopy(params))

        log_activity(
            config["permission_id"],
            "action_executed",
            details,
        )

        return {
            "status": "success",
            "result": result,
        }

    except Exception as error:
        log_activity(
            config["permission_id"],
            "action_failed",
            f"{details} | Erreur : {error}",
        )

        return {
            "status": "error",
            "message": str(error),
        }


def request_action(action_id, params=None, details=""):
    """
    Demande l'exécution d'une action.

    Résultats possibles :
    - success
    - confirmation_required
    - denied
    - error
    """

    if action_id not in _ACTIONS:
        log_activity(
            "unknown_action",
            "denied",
            str(action_id),
        )

        return {"status": "denied", "message": "Action inconnue."}

    if params is None:
        params = {}

    if not isinstance(params, dict):
        return {"status": "error", "message": "Paramètres invalides."}

    if not isinstance(details, str):
        return {"status": "error", "message": "Description invalide."}

    if len(details) > 500:
        return {"status": "error", "message": "Description trop longue."}

    config = _ACTIONS[action_id]
    permission_id = config["permission_id"]

    # Validation des paramètres avant toute action.
    validator = config["validator"]

    if validator is not None:
        try:
            if validator(deepcopy(params)) is not True:
                return {
                    "status": "denied",
                    "message": "Paramètres refusés.",
                }
        except Exception:
            return {
                "status": "error",
                "message": "Erreur de validation.",
            }

    decision = check_permission(permission_id)

    if decision == "denied":
        log_activity(permission_id, "denied", details)
        return {"status": "denied"}

    if decision == "allowed":
        return _execute_action(action_id, params, details)

    # Une confirmation est nécessaire.
    request = create_confirmation_request(
        permission_id,
        details,
    )

    if request is None:
        return {"status": "denied"}

    _PENDING_ACTIONS[request["id"]] = {
        "action_id": action_id,
        "params": deepcopy(params),
        "details": details,
    }

    return {
        "status": "confirmation_required",
        "request": request,
    }


def confirm_action(request_id, approved):
    """
    Traite la réponse de l'utilisateur et exécute
    l'action uniquement si la demande est valide.
    """

    if not isinstance(approved, bool):
        return {"status": "error", "message": "Décision invalide."}

    pending = _PENDING_ACTIONS.get(request_id)

    if pending is None:
        return {"status": "invalid_request"}

    # La demande devient inutilisable après cette tentative.
    _PENDING_ACTIONS.pop(request_id, None)

    success = resolve_confirmation_request(
        request_id,
        approved,
    )

    if not success:
        return {
            "status": "refused" if not approved else "invalid_request"
        }

    return _execute_action(
        pending["action_id"],
        pending["params"],
        pending["details"],
    )
