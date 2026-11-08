
"""Moteur de recherche Internet de CAPRI."""

from ddgs import DDGS

MAX_RESULTS = 5


def search_web(query, max_results=5):
    if not isinstance(query, str):
        return {"status": "error", "message": "Requête invalide.", "results": []}

    query = " ".join(query.strip().split())

    if len(query) < 2 or len(query) > 300:
        return {"status": "error", "message": "Longueur de recherche invalide.", "results": []}

    try:
        max_results = max(1, min(int(max_results), MAX_RESULTS))

        with DDGS(timeout=15) as ddgs:
            raw_results = list(
                ddgs.text(
                    query,
                    region="fr-fr",
                    safesearch="moderate",
                    max_results=max_results,
                )
            )

        results = []

        for item in raw_results:
            title = str(item.get("title") or "").strip()
            url = str(item.get("href") or "").strip()
            snippet = str(item.get("body") or "").strip()

            if not title or not url:
                continue

            if not url.startswith(("https://", "http://")):
                continue

            results.append({
                "title": title[:300],
                "url": url[:2000],
                "snippet": snippet[:1500],
            })

        return {
            "status": "success",
            "query": query,
            "count": len(results),
            "results": results,
        }

    except Exception as error:
        if "No results found" in str(error):
            return {
                "status": "success",
                "query": query,
                "count": 0,
                "results": [],
            }

        return {
            "status": "error",
            "message": f"Recherche Internet impossible : {error}",
            "results": [],
        }
