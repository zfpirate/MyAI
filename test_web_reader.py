
from internet.web_reader import read_webpage

print("TEST DU LECTEUR INTERNET DE CAPRI")
print("=" * 50)

result = read_webpage("https://www.python.org/")

if result["status"] == "success":
    print("Lecture réussie !")
    print(f"\nTitre : {result['title']}")
    print(f"URL : {result['url']}")
    print("\nContenu extrait :")
    print(result["content"][:2000])
else:
    print("[ERREUR]")
    print(result["message"])

print("\nFin du test.")
