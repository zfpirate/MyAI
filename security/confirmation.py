
from uuid import uuid4
from datetime import datetime, timedelta, timezone

from security.permission_manager import check_permission
from security.activity_log import log_activity


# Durée de validité d'une demande : 2 minutes.
REQUEST_VALIDITY = timedelta(minutes=2)

# Demandes en attente.
_pending_requests = {}


def create_confirmation_request(permission_id, details=""):
    """Crée une demande de confirmation utilisateur."""

    decision = check_permission(permission_id)

    if decision != "needs_confirmation":
        return None

    request_id = str(uuid4())

    request = {
        "id": request_id,
        "permission_id": permission_id,
        "details": details,
        "created_at": datetime.now(timezone.utc),
    }

    _pending_requests[request_id] = request

    log_activity(
        permission_id,
        "confirmation_requested",
        details,
    )

    return {
        "id": request_id,
        "permission_id": permission_id,
        "details": details,
    }


def resolve_confirmation_request(request_id, approved):
    """Traite une décision utilisateur sur une demande précise."""

    request = _pending_requests.pop(request_id, None)

    if request is None:
        return False

    age = datetime.now(timezone.utc) - request["created_at"]

    if age > REQUEST_VALIDITY:
        log_activity(
            request["permission_id"],
            "confirmation_expired",
            request["details"],
        )
        return False

    if not isinstance(approved, bool):
        return False

    if not approved:
        log_activity(
            request["permission_id"],
            "confirmation_refused",
            request["details"],
        )
        return False

    # Vérifie à nouveau la permission au moment de la validation.
    if check_permission(request["permission_id"]) != "needs_confirmation":
        log_activity(
            request["permission_id"],
            "confirmation_invalidated",
            request["details"],
        )
        return False

    log_activity(
        request["permission_id"],
        "confirmation_approved",
        request["details"],
    )

    return True


def get_pending_requests():
    """Retourne les demandes encore valides."""

    now = datetime.now(timezone.utc)

    expired_ids = [
        request_id
        for request_id, request in _pending_requests.items()
        if now - request["created_at"] > REQUEST_VALIDITY
    ]

    for request_id in expired_ids:
        request = _pending_requests.pop(request_id)

        log_activity(
            request["permission_id"],
            "confirmation_expired",
            request["details"],
        )

    return [
        {
            "id": request["id"],
            "permission_id": request["permission_id"],
            "details": request["details"],
        }
        for request in _pending_requests.values()
    ]
