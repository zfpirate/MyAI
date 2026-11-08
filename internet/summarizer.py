"""Extraction stricte de faits pour CAPRI."""

import json
import re
import unicodedata
from datetime import date, datetime

import ollama


MODEL = "qwen3:8b"

MAX_FACTS_PER_PAGE = 5
MAX_TOTAL_FACTS = 10
MIN_PAGE_LENGTH = 500
MIN_QUOTE_LENGTH = 35
MAX_QUOTE_LENGTH = 700


def normalize_quote(text):
    """Normalise le texte pour vérifier les citations."""

    text = unicodedata.normalize("NFKC", str(text)).casefold()
    return " ".join(text.split())


def extract_json(response):
    """Récupère le JSON produit par Ollama."""

    content = response["message"]["content"].strip()
    data = json.loads(content)

    if not isinstance(data, dict):
        raise ValueError("Objet JSON attendu.")

    return data


def is_recent_date(value, max_age_days=45):
    """Vérifie une date au format ISO."""

    if not value:
        return False

    try:
        publication_date = date.fromisoformat(str(value)[:10])
        age = (date.today() - publication_date).days

        return 0 <= age <= max_age_days

    except (ValueError, TypeError):
        return False


def extract_facts(page, question=""):
    """Extrait des faits dont les citations existent réellement."""

    source_id = page.get("source_id")
    content = page.get("content", "")

    if not source_id or len(content.strip()) < MIN_PAGE_LENGTH:
        return []

    prompt = f"""
Tu es un extracteur de faits extrêmement strict.

QUESTION :
{question}

SOURCE : {source_id}
TITRE : {page.get("title", "")}
DATE : {page.get("published_date") or "Inconnue"}

CONTENU :
{content}

Extrais au maximum {MAX_FACTS_PER_PAGE} faits utiles.

Pour chaque fait, retourne :
- claim : affirmation précise et courte.
- quote : citation copiée exactement depuis le contenu.
- importance : haute, moyenne ou faible.

RÈGLES :
- Ne crée aucun fait.
- Ne complète pas les informations manquantes.
- Ne déduis rien qui n'est pas explicitement écrit.
- Ne transforme jamais une hypothèse en certitude.
- Conserve les dates et les chiffres exactement.
- Une annonce doit rester une annonce.
- Une prévision doit rester une prévision.
- Ignore les publicités, menus et éléments sans rapport.
- Ignore les informations anciennes sans rapport avec la question.
- Si aucun fait pertinent n'existe, retourne une liste vide.

Réponds uniquement en JSON :
{{
  "facts": [
    {{
      "claim": "Affirmation",
      "quote": "Citation exacte",
      "importance": "haute"
    }}
  ]
}}
"""

    try:
        response = ollama.chat(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Tu extrais uniquement des informations "
                        "explicitement présentes dans le texte. "
                        "Tu n'inventes jamais de faits."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            format="json",
            think=False,
            options={"temperature": 0}
        )

        data = extract_json(response)
        facts = data.get("facts", [])

        if not isinstance(facts, list):
            return []

        original = normalize_quote(content)
        validated = []

        for fact in facts:
            if not isinstance(fact, dict):
                continue

            claim = str(fact.get("claim", "")).strip()
            quote = str(fact.get("quote", "")).strip()
            importance = str(
                fact.get("importance", "moyenne")
            ).lower()

            if not claim or not quote:
                continue

            if not MIN_QUOTE_LENGTH <= len(quote) <= MAX_QUOTE_LENGTH:
                continue

            normalized_quote = normalize_quote(quote)

            # La citation doit être réellement présente.
            if normalized_quote not in original:
                continue

            if importance not in ("haute", "moyenne", "faible"):
                importance = "moyenne"

            validated.append({
                "source_id": source_id,
                "claim": claim[:500],
                "quote": quote,
                "importance": importance,
                "published_date": page.get("published_date"),
                "url": page.get("url", ""),
                "title": page.get("title", ""),
            })

        return validated

    except Exception as error:
        print(
            f"[SUMMARIZER] {source_id} : "
            f"{type(error).__name__}: {error}"
        )
        return []


def summarize_research(question, research_result):
    """Construit une réponse à partir des faits extraits."""

    pages = research_result.get("pages", [])

    if not pages:
        return (
            "Je n'ai pas réussi à récupérer de pages exploitables. "
            "Je préfère ne pas inventer d'informations."
        )

    all_facts = []

    for page in pages:
        facts = extract_facts(page, question)
        all_facts.extend(facts)

    if not all_facts:
        return (
            "J'ai récupéré des pages Internet, mais aucun fait "
            "n'a passé mes vérifications. Je ne peux donc pas "
            "confirmer les actualités demandées."
        )

    # Une date inconnue ne doit pas être présentée comme récente.
    current_news = any(
        word in question.lower()
        for word in ("actualité", "actualités", "dernières", "récent", "récentes")
    )

    if current_news:
        all_facts = [
            fact for fact in all_facts
            if is_recent_date(fact.get("published_date"))
        ]

    if not all_facts:
        return (
            "J'ai trouvé des informations, mais aucune ne possède "
            "une date de publication suffisamment récente pour "
            "être présentée comme une actualité actuelle."
        )

    # Éviter les répétitions exactes.
    unique_facts = []
    seen = set()

    for fact in all_facts:
        key = normalize_quote(fact["claim"])

        if key in seen:
            continue

        seen.add(key)
        unique_facts.append(fact)

    importance_order = {
        "haute": 0,
        "moyenne": 1,
        "faible": 2,
    }

    unique_facts.sort(
        key=lambda fact: importance_order[fact["importance"]]
    )

    unique_facts = unique_facts[:MAX_TOTAL_FACTS]

    # Construction déterministe : aucune génération libre de faits.
    answer = "Voici les informations que j'ai pu extraire et vérifier :\n"

    used_sources = {}

    for fact in unique_facts:
        source_id = fact["source_id"]

        answer += (
            f"\n- **{fact['claim']}** [{source_id}]"
        )

        used_sources[source_id] = fact

    answer += "\n\n**Sources :**"

    for source_id, fact in used_sources.items():
        answer += (
            f"\n- [{source_id}] {fact['title']}"
            f"\n  {fact['url']}"
        )

        if fact.get("published_date"):
            answer += (
                f"\n  Publication : {fact['published_date']}"
            )
        else:
            answer += "\n  Date de publication inconnue"

    answer += (
        "\n\nNote : la présence d'une citation dans une page "
        "ne garantit pas à elle seule la véracité de son contenu."
    )

    return answer
