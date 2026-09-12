"""
Wrapper BFV (via Pyfhel) : chiffrement, addition homomorphe, calcul de
moyenne. Implémente l'Option A pour la moyenne, comme pour Paillier
(cf. note technique, Partie I sections 2.2 et 2.3).
"""

import base64
import os
import sys
import numpy as np

from Pyfhel import Pyfhel, PyCtxt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BFV_POLY_MODULUS_DEGREE, BFV_PLAIN_MODULUS_BITS


class BFVScheme:
    def __init__(self, poly_modulus_degree=BFV_POLY_MODULUS_DEGREE,
                 plain_modulus_bits=BFV_PLAIN_MODULUS_BITS,
                 sec=128):
        self.he = Pyfhel()
        self.sec = sec
        self.poly_modulus_degree = poly_modulus_degree
        self.plain_modulus_bits = plain_modulus_bits
        # Génère automatiquement un plain_modulus premier valide respectant
        # t ≡ 1 mod 2n (cf. note technique, section 1.2).
        self.he.contextGen(scheme="BFV", n=poly_modulus_degree, t_bits=plain_modulus_bits, sec=sec)
        self.he.keyGen()

    def chiffrer(self, valeurs):
        """Chiffre une liste d'entiers. Retourne une liste de PyCtxt."""
        return [self.he.encryptInt(np.array([int(v)], dtype=np.int64)) for v in valeurs]

    def somme_homomorphe(self, chiffres):
        """Additionne des valeurs chiffrées (opération native BFV)."""
        resultat = chiffres[0].copy()
        for c in chiffres[1:]:
            resultat += c
        return resultat

    def dechiffrer(self, chiffre):
        """Déchiffre un PyCtxt (ou une liste)."""
        if isinstance(chiffre, list):
            return [int(self.he.decryptInt(c)[0]) for c in chiffre]
        return int(self.he.decryptInt(chiffre)[0])

    def moyenne(self, chiffres):
        """
        Option A (recommandée) : somme homomorphe, déchiffrement,
        division en clair par n. Logique identique à Paillier.
        """
        n = len(chiffres)
        somme_chiffree = self.somme_homomorphe(chiffres)
        somme_claire = self.dechiffrer(somme_chiffree)
        return somme_claire / n

    @staticmethod
    def serialiser_chiffre(chiffre):
        """Sérialise un PyCtxt en chaîne base64."""
        return base64.b64encode(chiffre.to_bytes()).decode("utf-8")

    def deserialiser_chiffre(self, b64_str):
        """Reconstruit un PyCtxt depuis base64."""
        ctxt = PyCtxt(pyfhel=self.he)
        ctxt.from_bytes(base64.b64decode(b64_str))
        return ctxt

    def serialiser_contexte(self):
        """Sérialise le contexte et la clé publique en base64 pour le serveur Cloud."""
        contexte_b64 = base64.b64encode(self.he.to_bytes_context()).decode("utf-8")
        pk_b64 = base64.b64encode(self.he.to_bytes_public_key()).decode("utf-8")
        return {"context": contexte_b64, "public_key": pk_b64}

    @staticmethod
    def deserialiser_contexte(data):
        """Crée un objet Pyfhel serveur reconstitué à partir du contexte et clé publique."""
        he_serv = Pyfhel()
        he_serv.from_bytes_context(base64.b64decode(data["context"]))
        he_serv.from_bytes_public_key(base64.b64decode(data["public_key"]))
        return he_serv



if __name__ == "__main__":
    # Test de justesse rapide. Si BFV_PLAIN_MODULUS_BITS est mal calibré
    # par rapport à la somme réelle, ce test échouera avec un résultat
    # incohérent (wrap-around silencieux, cf. note technique section 1.2)
    # plutôt qu'une erreur explicite — d'où l'intérêt de ce test.
    scheme = BFVScheme()
    valeurs = [100, 250, 75, 1000, 300]

    chiffres = scheme.chiffrer(valeurs)
    somme_dechiffree = scheme.dechiffrer(scheme.somme_homomorphe(chiffres))
    moyenne = scheme.moyenne(chiffres)

    assert somme_dechiffree == sum(valeurs), (
        f"Écart somme : {somme_dechiffree} vs {sum(valeurs)} "
        f"(vérifier BFV_PLAIN_MODULUS_BITS dans config.py)"
    )
    assert moyenne == sum(valeurs) / len(valeurs), f"Écart moyenne : {moyenne}"

    print(f"[OK] Somme chiffrée puis déchiffrée : {somme_dechiffree} (attendu {sum(valeurs)})")
    print(f"[OK] Moyenne : {moyenne}")