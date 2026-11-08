
import core.brain as brain

# Remplace temporairement le routeur par un faux résultat.
# Aucun programme Windows ne sera lancé.
brain.route_command = lambda message: "ROUTEUR CONNECTÉ"

result = brain.ask_capri("ouvre Discord")

print("Réponse de CAPRI :", result)

assert result == "ROUTEUR CONNECTÉ"

print("TEST RÉUSSI")
