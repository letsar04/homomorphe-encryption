"""
Wrapper Paillier : chiffrement, addition homomorphe, calcul de moyenne.
Implémente l'Option A pour la moyenne (déchiffrement de la somme puis
division en clair) — cf. note technique, Partie I sections 2.1 et 2.3.
"""

import os
import sys

from phe import paillier

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PAILLIER_KEY_SIZE


class PaillierScheme:
    def __init__(self, key_size=PAILLIER_KEY_SIZE):
        self.key_size = key_size
        self.public_key, self.private_key = paillier.generate_paillier_keypair(
            n_length=key_size
        )

    def chiffrer(self, valeurs):
        """Chiffre une liste d'entiers. Retourne une liste de EncryptedNumber."""
        return [self.public_key.encrypt(int(v)) for v in valeurs]

    def somme_homomorphe(self, chiffres):
        """
        Additionne des valeurs chiffrées (opération native Paillier,
        illimitée). Ne nécessite AUCUN déchiffrement intermédiaire.
        """
        resultat = chiffres[0]
        for c in chiffres[1:]:
            resultat += c
        return resultat

    def dechiffrer(self, chiffre):
        """Déchiffre un EncryptedNumber (ou une liste)."""
        if isinstance(chiffre, list):
            return [self.private_key.decrypt(c) for c in chiffre]
        return self.private_key.decrypt(chiffre)

    def moyenne(self, chiffres):
        """
        Option A (recommandée, cf. note technique 2.1 et 2.3) :
        1. Somme homomorphe (chiffrée)
        2. Déchiffrement de la somme
        3. Division en clair par n (nombre de transactions, donnée publique)
        """
        n = len(chiffres)
        somme_chiffree = self.somme_homomorphe(chiffres)
        somme_claire = self.dechiffrer(somme_chiffree)
        return somme_claire / n

    @staticmethod
    def serialiser_chiffre(chiffre):
        """Sérialise un EncryptedNumber en dict JSON-compatible."""
        return {
            "ciphertext": str(chiffre.ciphertext()),
            "exponent": chiffre.exponent
        }

    @staticmethod
    def deserialiser_chiffre(data, public_key):
        """Reconstruit un EncryptedNumber depuis un dict."""
        return paillier.EncryptedNumber(
            public_key, int(data["ciphertext"]), int(data["exponent"])
        )

    def serialiser_cle_publique(self):
        """Sérialise la clé publique Paillier en dict."""
        return {"n": str(self.public_key.n)}

    @staticmethod
    def deserialiser_cle_publique(data):
        """Reconstruit PaillierPublicKey depuis un dict."""
        return paillier.PaillierPublicKey(n=int(data["n"]))



if __name__ == "__main__":
    # Test de justesse rapide : le résultat chiffré doit correspondre
    # exactement au calcul en clair.
    scheme = PaillierScheme()
    valeurs = [100, 250, 75, 1000, 300]

    chiffres = scheme.chiffrer(valeurs)
    somme_dechiffree = scheme.dechiffrer(scheme.somme_homomorphe(chiffres))
    moyenne = scheme.moyenne(chiffres)

    assert somme_dechiffree == sum(valeurs), (
        f"Écart somme : {somme_dechiffree} vs {sum(valeurs)}"
    )
    assert moyenne == sum(valeurs) / len(valeurs), f"Écart moyenne : {moyenne}"

    print(f"[OK] Somme chiffrée puis déchiffrée : {somme_dechiffree} (attendu {sum(valeurs)})")
    print(f"[OK] Moyenne : {moyenne}")