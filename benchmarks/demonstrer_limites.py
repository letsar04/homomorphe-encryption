"""
Démonstration pratique des limites des schémas Paillier et BFV.

Ce script exécute 4 expérimentations concrètes :
1. Tentative de multiplication chiffré * chiffré sous Paillier (Erreur d'homomorphisme partiel).
2. Débordement modulaire sous BFV (Wrap-around modulo t quand plain_modulus est sous-dimensionné).
3. Surcharge mémoire et réseau (Comparaison de la taille sérialisée des ciphertexts).
4. Profondeur multiplicative et accumulation de bruit sous BFV.
"""

import base64
import json
import os
import sys
import numpy as np
from phe import paillier

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from config import PAILLIER_KEY_SIZE, BFV_POLY_MODULUS_DEGREE, BFV_PLAIN_MODULUS_BITS
from schemes.paillier_ops import PaillierScheme
from schemes.bfv_ops import BFVScheme


def afficher_titre(titre):
    print("\n" + "=" * 70)
    print(f" {titre}")
    print("=" * 70)


def cas_1_paillier_multiplication_chiffree():
    afficher_titre("CAS 1 : Limite de la Multiplication Chiffrée sous Paillier")
    print("Paillier est un schéma à homomorphisme PARTIEL (additif).")
    print("Tentative d'effectuer c1 * c2 (où c1 et c2 sont deux nombres chiffrés)...")

    pub, priv = paillier.generate_paillier_keypair(n_length=PAILLIER_KEY_SIZE)
    val1, val2 = 500, 10

    c1 = pub.encrypt(val1)
    c2 = pub.encrypt(val2)

    try:
        # Tentative de multiplication chiffré * chiffré
        _ = c1 * c2
        print("[ANOMALIE] La multiplication a réussi (inattendu).")
    except (TypeError, NotImplementedError) as e:
        print(f"\n[ÉCHEC OBTENU COMME ATTENDU]")
        print(f"Type d'erreur : {type(e).__name__}")
        print(f"Message       : {e}")
        print("-> Conclusion  : Paillier ne supporte PAS la multiplication de deux ciphertexts.")
        print("   Seule la multiplication par une constante claire (ex: c1 * 10) est autorisée.")


def cas_2_bfv_debordement_modulaire():
    afficher_titre("CAS 2 : Débordement Modulaire sous BFV (Wrap-Around Modulo t)")
    print("BFV effectue les calculs dans un anneau modulo t (plain_modulus).")
    print("Si la somme dépasse t, le résultat déborde silencieusement sans erreur.\n")

    from Pyfhel import Pyfhel

    # 1. Configuration avec un plain_modulus volontairement réduit (t_bits = 17 -> t ≈ 131,072)
    he_petit = Pyfhel()
    he_petit.contextGen(scheme="BFV", n=8192, t_bits=17)
    he_petit.keyGen()

    val1, val2 = 100000, 50000  # Somme réelle = 150 000 FCFA (> 131 072)
    c1 = he_petit.encryptInt(np.array([val1], dtype=np.int64))
    c2 = he_petit.encryptInt(np.array([val2], dtype=np.int64))

    c_somme = c1 + c2
    resultat_faux = int(he_petit.decryptInt(c_somme)[0])

    print(f"Valeurs en clair         : {val1:,} FCFA + {val2:,} FCFA")
    print(f"Somme réelle attendue    : {val1 + val2:,} FCFA")
    print(f"Taille plain_modulus (t) : ~131 072 (t_bits = 17)")
    print(f"Résultat déchiffré BFV   : {resultat_faux:,} FCFA [ERREUR SILENCIEUSE]")
    print(f"Écart / Perte de donnée  : -{val1 + val2 - resultat_faux:,} FCFA")

    # 2. Configuration correcte avec notre calibrage dans config.py
    bfv_correct = BFVScheme()
    chiffres = bfv_correct.chiffrer([val1, val2])
    somme_correcte = bfv_correct.dechiffrer(bfv_correct.somme_homomorphe(chiffres))

    print(f"\nAvec le calibrage correct du projet (t_bits={BFV_PLAIN_MODULUS_BITS}) :")
    print(f"Résultat déchiffré BFV   : {somme_correcte:,} FCFA [EXACT]")


def cas_3_expansion_donnees_et_reseau():
    afficher_titre("CAS 3 : Expansion de la Taille des Données (Ciphertext Blowup)")
    print("Mesure de la taille sérialisée pour 100 transactions bancaires.\n")

    valeurs = list(range(100, 100 + 100))  # 100 entiers

    # 1. Clair (JSON)
    json_clair = json.dumps(valeurs)
    taille_clair = len(json_clair.encode("utf-8"))

    # 2. Paillier (JSON des ciphertexts)
    paillier_scheme = PaillierScheme()
    chiffres_p = paillier_scheme.chiffrer(valeurs)
    json_paillier = json.dumps([PaillierScheme.serialiser_chiffre(c) for c in chiffres_p])
    taille_paillier = len(json_paillier.encode("utf-8"))

    # 3. BFV (Liste de ciphertexts sérialisés)
    bfv_scheme = BFVScheme()
    chiffres_b = bfv_scheme.chiffrer(valeurs)
    str_bfv = json.dumps([BFVScheme.serialiser_chiffre(c) for c in chiffres_b])
    taille_bfv = len(str_bfv.encode("utf-8"))

    print(f"Format Données (100 tx)  | Taille Sérialisée | Facteur d'Expansion")
    print("-" * 65)
    print(f"Clair (JSON)             | {taille_clair:>10,} octets | 1.0x (Référence)")
    print(f"Paillier (2048 bits)     | {taille_paillier:>10,} octets | {taille_paillier / taille_clair:.1f}x")
    print(f"BFV (Sans batching SIMD) | {taille_bfv:>10,} octets | {taille_bfv / taille_clair:.1f}x")
    print("-" * 65)
    print("-> Conclusion : Le chiffrement homomorphe augmente fortement la bande passante.")


def cas_4_accumulation_bruit_bfv():
    afficher_titre("CAS 4 : Accumulation de Bruit et Profondeur Multiplicative sous BFV")
    print("Test du nombre maximal de multiplications homomorphes c = c * c")
    print("avant la dégradation du texte clair par le bruit cryptographique.\n")

    from Pyfhel import Pyfhel

    he = Pyfhel()
    he.contextGen(scheme="BFV", n=BFV_POLY_MODULUS_DEGREE, t_bits=BFV_PLAIN_MODULUS_BITS)
    he.keyGen()
    he.relinKeyGen()  # clés de rélinéarisation pour limiter le bruit de multiplication

    valeur_initiale = 2
    c = he.encryptInt(np.array([valeur_initiale], dtype=np.int64))
    valeur_attendue = valeur_initiale

    profondeur_max = 5
    for i in range(1, profondeur_max + 1):
        try:
            c = c * c  # Multiplication homomorphe chiffré * chiffré
            valeur_attendue = valeur_attendue * valeur_attendue
            valeur_dechiffree = int(he.decryptInt(c)[0])

            status = "OK" if valeur_dechiffree == valeur_attendue else "CORROMPU"
            print(f"Multiplication {i:>2} | Attendu: {valeur_attendue:<10} | Obtenu: {valeur_dechiffree:<10} | Statut: {status}")

            if status == "CORROMPU":
                print(f"\n[LIMITE ATTEINTE] Le bruit a corrompu la donnée à la multiplication n°{i}.")
                break
        except Exception as e:
            print(f"\n[ÉCHEC MULTIPLICATION n°{i}] Erreur : {e}")
            break


if __name__ == "__main__":
    print("\n" + "#" * 70)
    print(" BENCHMARK & EXPERIMENTATION DES LIMITES DES SCHÉMAS HE (HE_Proto)")
    print("#" * 70)

    cas_1_paillier_multiplication_chiffree()
    cas_2_bfv_debordement_modulaire()
    cas_3_expansion_donnees_et_reseau()
    cas_4_accumulation_bruit_bfv()

    print("\n" + "#" * 70)
    print(" EXPÉRIMENTATIONS TERMINÉES AVEC SUCCÈS")
    print("#" * 70 + "\n")
