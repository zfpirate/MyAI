
from internet.web_search import search_web

print("TEST DU MOTEUR INTERNET DE CAPRI")
print("=" * 50)

result = search_web("Python programming")

if result["status"] == "success":
    print(f"Recherche : {result['query']}")
    print(f"Résultats : {result['count']}")

    for index, item in enumerate(result["results"], 1):
        print(f"\n{index}. {item['title']}")
        print(f"   URL : {item['url']}")
        print(f"   Résumé : {item['snippet']}")

else:
    print("[ERREUR]")
    print(result["message"])

print("\nFin du test.")
