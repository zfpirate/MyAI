"""Catalogue des permissions de CAPRI."""

ALLOW = "allow"
CONFIRM = "confirm"
DENY = "deny"

VALID_MODES = {ALLOW, CONFIRM, DENY}

PERMISSIONS = {
    "system.read": {
        "label": "Lire les informations système",
        "description": "Consulter le CPU, la RAM et les informations système.",
        "default": ALLOW,
    },

    "apps.launch": {
        "label": "Lancer des applications",
        "description": "Lancer uniquement les applications autorisées.",
        "default": ALLOW,
    },

    "apps.close": {
    "label": "Fermer des applications",
    "description": "Fermer une application.",
    "default": ALLOW,
},

    "web.open": {
        "label": "Ouvrir des sites Internet",
        "description": "Ouvrir des adresses Web HTTP ou HTTPS validées.",
        "default": ALLOW,
    },

    "files.read": {
        "label": "Lire des fichiers",
        "description": "Lire uniquement les fichiers autorisés.",
        "default": DENY,
    },

    "files.write": {
        "label": "Créer ou modifier des fichiers",
        "description": "Modifier des fichiers après confirmation.",
        "default": CONFIRM,
    },

    "files.delete": {
        "label": "Supprimer des fichiers",
        "description": "Suppression bloquée par défaut.",
        "default": DENY,
    },

    "system.commands": {
        "label": "Exécuter des commandes système",
        "description": "Commandes Windows arbitraires bloquées.",
        "default": DENY,
    },
}