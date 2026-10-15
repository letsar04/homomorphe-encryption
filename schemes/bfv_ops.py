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
        """Chiffre une liste d'entiers en mode scalaire (1 ciphertext par valeur). Retourne une liste de PyCtxt."""
        return [self.he.encryptInt(np.array([int(v)], dtype=np.int64)) for v in valeurs]

    def activer_simd(self):
        """Génère les clés de rotation Galois pour les opérations de batching SIMD."""
        if not hasattr(self, "_rotate_key_ready") or not self._rotate_key_ready:
            self.he.rotateKeyGen()
            self._rotate_key_ready = True

    def chiffrer_simd(self, valeurs):
        """
        Chiffrement vectorisé SIMD (Batching) conforme à QR4 du Chapitre III.
        Regroupe jusqu'à n=8192 entiers par ciphertext.
        Pour N > n (ex: 10 000), produit math.ceil(N / n) ciphertexts.
        """
        n_slots = self.poly_modulus_degree
        valeurs_list = list(valeurs)
        ciphers = []
        for i in range(0, len(valeurs_list), n_slots):
            chunk = valeurs_list[i:i + n_slots]
            arr = np.zeros(n_slots, dtype=np.int64)
            arr[:len(chunk)] = chunk
            ciphers.append(self.he.encryptInt(arr))
        return ciphers

    def somme_homomorphe(self, chiffres):
        """Additionne des valeurs chiffrées en mode scalaire (opération native BFV)."""
        resultat = chiffres[0].copy()
        for c in chiffres[1:]:
            resultat += c
        return resultat

    def somme_homomorphe_simd(self, chiffres_batch):
        """
        Somme totale intra- et inter-vecteurs SIMD (réduction par cumul_add).
        Retourne le ciphertext contenant la somme totale dans son premier créneau (slot 0).
        """
        self.activer_simd()
        if not chiffres_batch:
            raise ValueError("Liste de ciphertexts SIMD vide")

        sommes_partielles = []
        for ct in chiffres_batch:
            ct_copy = ct.copy()
            self.he.cumul_add(ct_copy)
            sommes_partielles.append(ct_copy)

        res = sommes_partielles[0]
        for sp in sommes_partielles[1:]:
            res += sp
        return res

    def dechiffrer(self, chiffre):
        """Déchiffre un PyCtxt scalaire (ou une liste)."""
        if isinstance(chiffre, list):
            return [int(self.he.decryptInt(c)[0]) for c in chiffre]
        return int(self.he.decryptInt(chiffre)[0])

    def dechiffrer_simd(self, chiffre_batch, extraire_somme=True):
        """
        Déchiffre un ou plusieurs ciphertexts SIMD.
        Si extraire_somme=True, extrait la somme totale (slot 0).
        Sinon retourne le tableau complet des créneaux décodés.
        """
        if isinstance(chiffre_batch, list):
            res_list = [self.he.decryptInt(c) for c in chiffre_batch]
            if extraire_somme:
                return sum(int(r[0]) for r in res_list)
            return np.concatenate(res_list)

        res = self.he.decryptInt(chiffre_batch)
        if extraire_somme:
            return int(res[0])
        return res

    def moyenne(self, chiffres):
        """
        Option A (recommandée) : somme homomorphe, déchiffrement,
        division en clair par n. Logique identique à Paillier.
        """
        n = len(chiffres)
        somme_chiffree = self.somme_homomorphe(chiffres)
        somme_claire = self.dechiffrer(somme_chiffree)
        return somme_claire / n

    def moyenne_simd(self, chiffres_batch, nb_valeurs):
        """Calcule la moyenne en mode SIMD : somme homomorphe vectorielle, déchiffrement, division par n."""
        somme_chiffree = self.somme_homomorphe_simd(chiffres_batch)
        somme_claire = self.dechiffrer_simd(somme_chiffree, extraire_somme=True)
        return somme_claire / nb_valeurs

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
    # Test de justesse rapide (Scalaire & SIMD) avec valeurs signées (débits/crédits)
    scheme = BFVScheme()
    valeurs = [100, -250, 75, 1000, -300]

    # 1. Test Scalaire
    chiffres = scheme.chiffrer(valeurs)
    somme_dechiffree = scheme.dechiffrer(scheme.somme_homomorphe(chiffres))
    moyenne = scheme.moyenne(chiffres)

    assert somme_dechiffree == sum(valeurs), (
        f"Écart somme scalaire : {somme_dechiffree} vs {sum(valeurs)}"
    )
    assert moyenne == sum(valeurs) / len(valeurs), f"Écart moyenne scalaire : {moyenne}"
    print(f"[OK] Scalaire - Somme : {somme_dechiffree} (attendu {sum(valeurs)}) | Moyenne : {moyenne}")

    # 2. Test SIMD Vectorisé (Batching)
    chiffres_simd = scheme.chiffrer_simd(valeurs)
    somme_simd_ct = scheme.somme_homomorphe_simd(chiffres_simd)
    somme_simd_res = scheme.dechiffrer_simd(somme_simd_ct, extraire_somme=True)
    moyenne_simd_res = scheme.moyenne_simd(chiffres_simd, len(valeurs))

    assert somme_simd_res == sum(valeurs), (
        f"Écart somme SIMD : {somme_simd_res} vs {sum(valeurs)}"
    )
    assert moyenne_simd_res == sum(valeurs) / len(valeurs), f"Écart moyenne SIMD : {moyenne_simd_res}"
    print(f"[OK] SIMD     - Somme : {somme_simd_res} (attendu {sum(valeurs)}) | Moyenne : {moyenne_simd_res}")