"""
Simulation du fournisseur Cloud — Option A (même processus), cf. note
technique Partie I section 3.1. Le "serveur" est un module Python appelé
directement en mémoire, sans passer par le réseau.

Structuré pour pouvoir migrer vers l'Option B (API FastAPI) plus tard
sans changer la logique métier (cf. note technique, section 3.3) : seule
la façon dont les chiffrés transitent entre client et serveur changerait,
pas les méthodes de calcul elles-mêmes.
"""

import os
import sys


class CloudServerSimule:
    """
    Représente le serveur Cloud. Ne connaît jamais les clés privées : il
    reçoit des chiffrés, effectue des opérations homomorphes, et renvoie
    des chiffrés — exactement comme un vrai serveur Cloud le ferait.
    """

    def __init__(self, scheme):
        """
        scheme : instance de PaillierScheme ou BFVScheme.
        Le serveur utilise uniquement les opérations homomorphes du
        scheme (somme_homomorphe), jamais dechiffrer().
        """
        self.scheme = scheme

    def recevoir_et_sommer(self, chiffres):
        """
        Simule la réception de ciphertexts par le serveur et le calcul
        de la somme homomorphe. Retourne un chiffré, jamais déchiffré
        côté serveur.
        """
        return self.scheme.somme_homomorphe(chiffres)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from schemes.paillier_ops import PaillierScheme

    # Démonstration : le client chiffre, le "serveur" calcule, le client déchiffre
    client_scheme = PaillierScheme()
    valeurs = [500, 1200, 300]

    chiffres = client_scheme.chiffrer(valeurs)              # côté client
    serveur = CloudServerSimule(client_scheme)
    somme_chiffree = serveur.recevoir_et_sommer(chiffres)   # côté "serveur"
    resultat = client_scheme.dechiffrer(somme_chiffree)     # côté client

    assert resultat == sum(valeurs), f"Écart : {resultat} vs {sum(valeurs)}"
    print(f"[OK] Résultat via simulation Cloud : {resultat} (attendu {sum(valeurs)})")