
"""Compréhension intelligente des commandes d'applications."""

import re
import unicodedata
from difflib import SequenceMatcher

from actions.app_catalog import get_catalog_apps
from security.action_manager import request_action


ALIASES = {
    "note": "Bloc-notes",
    "notes": "Bloc-notes",
    "bloc note": "Bloc-notes",
    "bloc notes": "Bloc-notes",
    "notepad": "Bloc-notes",

    "calculatrice": "Calculatrice",
    "calculator": "Calculatrice",
    "calculette": "Calculatrice",

    "discorde": "Discord",
    "disc": "Discord",

    "chrome": "Google Chrome",
    "crom": "Google Chrome",
    "navigateur google": "Google Chrome",

    "musique": "Spotify",
    "spotfy": "Spotify",
    "spoti": "Spotify",

    "edge": "Microsoft Edge",
    "opera": "Opera GX",

    "code": "Visual Studio Code",
    "le code": "Visual Studio Code",
    "mon code": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "editeur de code": "Visual Studio Code",

    "py charm": "PyCharm",
    "py-charm": "PyCharm",
    "cursor": "Cursor",
    "windsurf": "Windsurf",

    "obs": "OBS Studio",
    "ollama": "Ollama",
    "cap cut": "CapCut",
    "riot": "Riot Client",
    "client riot": "Riot Client",
    "riot client": "Riot Client",
}

SITE_ALIASES = {
    "twitch": "https://www.twitch.tv",
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "reddit": "https://www.reddit.com",
    "github": "https://github.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
}

COMMAND_PATTERNS = [
    r"^(?:capri\s+)?ouvre(?:-moi)?\s+",
    r"^(?:capri\s+)?ouvrir\s+",
    r"^(?:capri\s+)?lance(?:-moi)?\s+",
    r"^(?:capri\s+)?lancer\s+",
    r"^(?:capri\s+)?demarre(?:-moi)?\s+",
    r"^(?:capri\s+)?demarrer\s+",
    r"^(?:capri\s+)?tu peux m ouvrir\s+",
    r"^(?:capri\s+)?tu peux ouvrir\s+",
    r"^(?:capri\s+)?peux tu ouvrir\s+",
    r"^(?:capri\s+)?peux tu m ouvrir\s+",
    r"^(?:capri\s+)?est ce que tu peux ouvrir\s+",
    r"^(?:capri\s+)?est ce que tu peux m ouvrir\s+",
]

CLOSE_COMMAND_PATTERNS = [
    r"^(?:capri\s+)?ferme(?:-moi)?\s+",
    r"^(?:capri\s+)?fermer\s+",
    r"^(?:capri\s+)?quitte(?:-moi)?\s+",
    r"^(?:capri\s+)?quitter\s+",
    r"^(?:capri\s+)?arrete(?:-moi)?\s+",
    r"^(?:capri\s+)?arreter\s+",
    r"^(?:capri\s+)?close\s+",
]

FILLER_WORDS = {
    "stp", "svp", "merci", "moi",
    "application", "app", "programme", "logiciel",
    "le", "la", "les", "l", "du", "de",
    "mon", "ma", "mes",
    "aussi", "egalement",
}

MULTI_ACTION_SEPARATOR = re.compile(
    r"\s+(?:et\s+apres|puis|ensuite|apres|et)\s+"
)


def normalize(text):
    """Normalise un texte pour faciliter sa compréhension."""

    text = unicodedata.normalize("NFD", str(text).casefold())

    text = "".join(
        char for char in text
        if unicodedata.category(char) != "Mn"
    )

    text = re.sub(r"[^a-z0-9 ]", " ", text)

    return " ".join(text.split())


def clean_query(text):
    """Supprime les mots inutiles d'une recherche d'application."""

    words = normalize(text).split()

    words = [
        word for word in words
        if word not in FILLER_WORDS
    ]

    return " ".join(words)


def remove_command_prefix(text):
    """Retire un verbe d'ouverture au début d'un texte."""

    for pattern in COMMAND_PATTERNS:
        updated = re.sub(pattern, "", text, count=1)

        if updated != text:
            return updated.strip()

    return text.strip()


def remove_close_command_prefix(text):
    """Retire un verbe de fermeture au début d'un texte."""

    for pattern in CLOSE_COMMAND_PATTERNS:
        updated = re.sub(pattern, "", text, count=1)

        if updated != text:
            return updated.strip()

    return text.strip()


def extract_app_name(message):
    """Extrait le nom d'une application depuis une commande."""

    text = normalize(message)
    text = remove_command_prefix(text)

    text = re.sub(
        r"\s+(stp|svp|merci|s il te plait|sil te plait)$",
        "",
        text,
    )

    return clean_query(text)


def extract_multiple_queries(message):
    """Sépare une commande contenant plusieurs applications à ouvrir."""

    text = str(message).strip().replace(",", " puis ")
    normalized = normalize(text)

    normalized = remove_command_prefix(normalized)

    parts = MULTI_ACTION_SEPARATOR.split(normalized)

    queries = []

    for part in parts:
        part = remove_command_prefix(part)
        query = clean_query(part)

        if query and query not in {"et", "puis", "ensuite"}:
            queries.append(query)

    return queries


def extract_multiple_queries_from_close(message):
    """Sépare plusieurs applications dans une commande de fermeture."""

    text = str(message).strip().replace(",", " puis ")
    normalized = normalize(text)

    normalized = remove_close_command_prefix(normalized)

    parts = MULTI_ACTION_SEPARATOR.split(normalized)

    queries = []

    for part in parts:
        part = remove_close_command_prefix(part)
        query = clean_query(part)

        if query and query not in {"et", "puis", "ensuite"}:
            queries.append(query)

    return queries


def is_open_command(message):
    """Détecte une commande d'ouverture."""

    text = normalize(message)

    return any(
        re.match(pattern, text)
        for pattern in COMMAND_PATTERNS
    )


def is_close_command(message):
    """Détecte une commande de fermeture."""

    text = normalize(message)

    return any(
        re.match(pattern, text)
        for pattern in CLOSE_COMMAND_PATTERNS
    )


def similarity(query, candidate):
    """Calcule une similarité entre deux noms."""

    query = normalize(query)
    candidate = normalize(candidate)

    if not query or not candidate:
        return 0.0

    sequence_score = SequenceMatcher(
        None, query, candidate
    ).ratio()

    query_words = set(query.split())
    candidate_words = set(candidate.split())

    if query_words and candidate_words:
        intersection = len(query_words & candidate_words)
        union = len(query_words | candidate_words)
        token_score = intersection / union
    else:
        token_score = 0.0

    if candidate.startswith(query + " "):
        sequence_score = max(sequence_score, 0.95)

    return max(sequence_score, token_score)


def get_available_apps():
    """Retourne les applications du catalogue."""

    return get_catalog_apps()


def find_application(query):
    """Recherche une application avec correspondance et tolérance aux fautes."""

    query = clean_query(query)

    if not query:
        return {"status": "not_found", "matches": []}

    apps = get_available_apps()

    if not apps:
        return {"status": "not_found", "matches": []}

    alias = ALIASES.get(query)

    if alias:
        target = normalize(alias)

        matches = [
            app for app in apps
            if normalize(app["name"]) == target
            or normalize(app["name"]).startswith(target + " ")
        ]

        if len(matches) == 1:
            return {
                "status": "found",
                "app": matches[0],
                "matches": matches,
                "score": 1.0,
            }

        if len(matches) > 1:
            return {
                "status": "ambiguous",
                "matches": matches[:3],
            }

    exact_matches = [
        app for app in apps
        if normalize(app["name"]) == query
    ]

    if len(exact_matches) == 1:
        return {
            "status": "found",
            "app": exact_matches[0],
            "matches": exact_matches,
            "score": 1.0,
        }

    scored_matches = []

    for app in apps:
        app_name = normalize(app["name"])
        score = similarity(query, app_name)

        for alias_name, target_name in ALIASES.items():
            if normalize(target_name) == app_name:
                score = max(
                    score,
                    similarity(query, alias_name),
                )

        scored_matches.append((score, app))

    scored_matches.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    best_score, best_app = scored_matches[0]

    second_score = (
        scored_matches[1][0]
        if len(scored_matches) > 1
        else 0.0
    )

    threshold = (
        0.78
        if len(query.replace(" ", "")) <= 4
        else 0.70
    )

    if best_score < threshold:
        return {
            "status": "not_found",
            "matches": [],
        }

    if second_score >= best_score - 0.08:
        return {
            "status": "ambiguous",
            "matches": [
                app
                for score, app in scored_matches[:3]
                if score >= best_score - 0.08
            ],
        }

    return {
        "status": "found",
        "app": best_app,
        "matches": [best_app],
        "score": best_score,
    }


def launch_one_application(query):
    """Recherche et demande l'ouverture d'une application."""

    result = find_application(query)

    if result["status"] == "not_found":
        return f"❌ {query} : application non reconnue."

    if result["status"] == "ambiguous":
        names = ", ".join(
            app["name"]
            for app in result["matches"]
        )

        return f"❓ {query} : plusieurs possibilités ({names})."

    app = result["app"]

    from actions.catalog_launcher import register_catalog_launcher
    register_catalog_launcher()

    launch_result = request_action(
        "applications.open_catalog",
        {"app_id": app["app_id"]},
        details=f"Ouverture de {app['name']} demandée par l'utilisateur",
    )

    if launch_result["status"] == "success":
        return f"✅ {app['name']} : ouverture demandée."

    if launch_result["status"] == "confirmation_required":
        return f"🔐 {app['name']} : confirmation nécessaire."

    if launch_result["status"] == "denied":
        return f"⛔ {app['name']} : permission refusée."

    return (
        f"❌ {app['name']} : "
        f"{launch_result.get('message', launch_result['status'])}"
    )


def close_one_application(query):
    """Recherche une application et demande sa fermeture."""

    result = find_application(query)

    if result["status"] == "not_found":
        return f"❌ {query} : application non reconnue."

    if result["status"] == "ambiguous":
        names = ", ".join(
            app["name"]
            for app in result["matches"]
        )

        return f"❓ {query} : plusieurs possibilités ({names})."

    app = result["app"]

    from actions.catalog_launcher import register_catalog_launcher
    register_catalog_launcher()

    from security.app_allowlist import ALLOWED_BUILTINS
    from actions.applications import register_application_actions

    if app["app_id"] in ALLOWED_BUILTINS:
        register_application_actions()
        action_id = "applications.close"
    else:
        action_id = "applications.close_catalog"

    close_result = request_action(
        action_id,
        {"app_id": app["app_id"]},
        details=f"Fermeture de {app['name']} demandée par l'utilisateur",
    )

    if close_result["status"] == "success":
        return f"✅ {app['name']} : fermeture demandée."

    if close_result["status"] == "confirmation_required":
        return f"🔐 {app['name']} : confirmation nécessaire."

    if close_result["status"] == "denied":
        return f"⛔ {app['name']} : permission refusée."

    return (
        f"❌ {app['name']} : "
        f"{close_result.get('message', close_result['status'])}"
    )


def resolve_website(target):
    """Convertit un nom de site ou un domaine en URL validée."""

    from actions.web_opener import validate_url

    target = target.strip().rstrip(".,!?")
    normalized = normalize(target)

    if normalized in SITE_ALIASES:
        return SITE_ALIASES[normalized]

    if validate_url(target):
        return target

    if re.fullmatch(
        r"[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?::[0-9]{1,5})?(?:/[^\s]*)?",
        target,
    ):
        url = "https://" + target

        if validate_url(url):
            return url

    return None


def open_website_command(url, browser=None):
    """Demande l'ouverture d'un site dans un navigateur."""

    from actions.web_opener import register_web_opener

    register_web_opener()

    params = {"url": url}

    if browser is not None:
        params["browser_app_id"] = browser["app_id"]

    result = request_action(
        "web.open",
        params,
        details=f"Ouverture du site {url}",
    )

    if result["status"] == "success":
        browser_name = (
            browser["name"]
            if browser
            else "navigateur par défaut"
        )

        return f"✅ Ouverture de {url} dans {browser_name} demandée."

    if result["status"] == "confirmation_required":
        return f"🔐 Confirmation nécessaire pour ouvrir {url}."

    if result["status"] == "denied":
        return f"⛔ Permission refusée pour ouvrir {url}."

    return (
        f"❌ Impossible d'ouvrir {url} : "
        f"{result.get('message', result['status'])}"
    )


def extract_browser_and_website(message):
    """Détecte une commande navigateur + site web."""

    text = normalize(message)
    text = remove_command_prefix(text)

    pattern = (
        r"\s+(?:et|puis|ensuite)\s+"
        r"(?:ouvre|ouvrir|lance|lancer)\s+(.+)$"
    )

    match = re.search(pattern, text)

    if not match:
        return None

    browser_query = text[:match.start()].strip()
    website_query = match.group(1).strip()

    browser_result = find_application(browser_query)

    if browser_result["status"] != "found":
        return None

    url = resolve_website(website_query)

    if url is None:
        return None

    return browser_result["app"], url


def extract_browser_and_research(message):
    """Détecte une commande navigateur + recherche Internet."""

    normalized_text = normalize(message)
    normalized_text = remove_command_prefix(normalized_text)

    pattern = (
        r"\s+(?:et|puis|ensuite)\s+"
        r"(?:cherche|recherche|trouve)\s+(.+)$"
    )

    match = re.search(pattern, normalized_text)

    if not match:
        return None

    browser_query = normalized_text[:match.start()].strip()

    original_text = remove_command_prefix(message)

    original_match = re.search(
        pattern,
        normalize(original_text),
    )

    if not original_match:
        return None

    research_query = original_text[
        original_match.start(1):
    ].strip()

    if not browser_query or len(research_query) < 2:
        return None

    browser_result = find_application(browser_query)

    if browser_result["status"] != "found":
        return None

    return browser_result["app"], research_query


def route_command(message):
    """Dirige les commandes d'ouverture et de fermeture."""

    # Fermeture d'applications.
    if is_close_command(message):

        target = remove_close_command_prefix(
            normalize(message)
        )

        if target in {
            "tout",
            "toutes les applications",
            "toutes les apps",
            "tous les programmes",
            "tout les programmes",
        }:
            return (
                "🔐 La fermeture globale des applications "
                "n'est pas disponible."
            )

        queries = extract_multiple_queries_from_close(message)

        if not queries:
            return "Quelle application veux-tu fermer ?"

        results = [
            close_one_application(query)
            for query in queries
        ]

        if len(results) == 1:
            return results[0]

        return "Résultat des fermetures :\n" + "\n".join(results)

    # Si ce n'est pas une commande d'ouverture, laisser
    # le reste de CAPRI traiter le message.
    if not is_open_command(message):
        return None

    # Navigateur + site web.
    browser_website = extract_browser_and_website(message)

    if browser_website is not None:
        browser, url = browser_website
        return open_website_command(url, browser)

    # Navigateur + recherche Internet.
    browser_research = extract_browser_and_research(message)

    if browser_research is not None:
        browser, query = browser_research

        from internet.web_research import research_web
        from internet.summarizer import summarize_research

        open_result = open_website_command(
            "https://www.google.com/search?q=" + query.replace(" ", "+"),
            browser,
        )

        research_result = research_web(query)
        summary = summarize_research(research_result)

        return (
            f"{open_result}\n\n"
            f"{summary}"
        )

    # Site web seul.
    target = remove_command_prefix(normalize(message))
    url = resolve_website(target)

    if url is not None:
        return open_website_command(url)

    # Application seule ou plusieurs applications.
    queries = extract_multiple_queries(message)

    if not queries:
        return "Quelle application veux-tu ouvrir ?"

    results = [
        launch_one_application(query)
        for query in queries
    ]

    if len(results) == 1:
        return results[0]

    return "Résultat des ouvertures :\n" + "\n".join(results)
