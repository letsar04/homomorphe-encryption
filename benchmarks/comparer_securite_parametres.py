"""
Module d'analyse et de comparaison des performances selon les paramètres de sécurité.

Ce module évalue l'impact de la variation des paramètres de sécurité cryptographique
sur les performances de Paillier (PHE) et BFV (FHE/RLWE), et fournit :
1. Une comparaison directe alignée au niveau de sécurité standard 128 bits (Recommandation NIST / Homomorphic Encryption Standard).
2. Une analyse de sensibilité aux paramètres (Key size Paillier : 1024, 2048, 3072, 4096 bits ; BFV : degré n=4096, 8192, 16384 et sec=128, 192, 256 bits).
3. L'export des métriques (Temps KeyGen, Chiffrement, Somme homomorphe, Déchiffrement, Tailles clés/ciphertexts, Mémoire RAM, Résistance Post-Quantique) en CSV et Markdown pour les Chapitres 3 et 4 du mémoire.
"""

import argparse
import base64
import csv
import json
import math
import os
import sys
import time
import tracemalloc
import numpy as np
from phe import paillier
from Pyfhel import Pyfhel, PyCtxt

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from config import DATA_DIR, RESULTS_DIR, BFV_PLAIN_MODULUS_BITS


# Force UTF-8 encoding for stdout/stderr on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def afficher_banniere():
    print("\n" + "=" * 80)
    print(" [SECU] HE_Proto -- COMPARAISON DES PERFORMANCES SELON LES PARAMETRES DE SECURITE")
    print("        Alignement 128 bits (NIST) & Etude de Sensibilite Multi-Parametres")
    print("=" * 80 + "\n")


def charger_ou_generer_donnees(nb_transactions=100):
    """Charge un échantillon de transactions financières ou génère des valeurs représentatives en FCFA."""
    chemin_csv = os.path.join(ROOT_DIR, DATA_DIR, "transactions_synthetiques.csv")
    valeurs = []
    if os.path.exists(chemin_csv):
        with open(chemin_csv, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                valeurs.append(int(row["montant"]))
                if len(valeurs) >= nb_transactions:
                    break

    if not valeurs:
        # Fallback si le CSV n'est pas encore généré
        np.random.seed(42)
        valeurs = [int(v) for v in np.random.randint(1_000, 500_000, size=nb_transactions)]

    return valeurs[:nb_transactions]


def evaluer_paillier(key_size, valeurs, nb_repetitions=3):
    """Mesure les métriques complètes de Paillier pour une taille de clé donnée."""
    # 1. Équivalence de sécurité NIST SP 800-57
    sec_equiv = {
        1024: 80,
        2048: 112,
        3072: 128,
        4096: 140
    }.get(key_size, int(key_size / 24))

    temps_keygen_list = []
    temps_enc_list = []
    temps_add_list = []
    temps_dec_list = []
    mem_pic_list = []

    pub_key, priv_key = None, None
    sample_ciphertext_size = 0
    pub_key_size = 0
    priv_key_size = 0

    for _ in range(nb_repetitions):
        tracemalloc.start()

        # KeyGen
        t0 = time.perf_counter()
        pub_key, priv_key = paillier.generate_paillier_keypair(n_length=key_size)
        t_keygen = time.perf_counter() - t0

        # Encryption
        t0 = time.perf_counter()
        chiffres = [pub_key.encrypt(int(v)) for v in valeurs]
        t_enc = time.perf_counter() - t0

        # Homomorphic Addition
        t0 = time.perf_counter()
        somme_c = chiffres[0]
        for c in chiffres[1:]:
            somme_c += c
        t_add = time.perf_counter() - t0

        # Decryption
        t0 = time.perf_counter()
        somme_dechiffree = priv_key.decrypt(somme_c)
        t_dec = time.perf_counter() - t0

        _, mem_pic = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Validation mathématique
        assert somme_dechiffree == sum(valeurs), f"Erreur calcul Paillier {key_size}b"

        temps_keygen_list.append(t_keygen)
        temps_enc_list.append(t_enc)
        temps_add_list.append(t_add)
        temps_dec_list.append(t_dec)
        mem_pic_list.append(mem_pic)

    # Calcul des tailles sérialisées
    sample_c = chiffres[0]
    c_dict = {"ciphertext": str(sample_c.ciphertext()), "exponent": sample_c.exponent}
    sample_ciphertext_size = len(json.dumps(c_dict).encode("utf-8"))

    pk_dict = {"n": str(pub_key.n)}
    pub_key_size = len(json.dumps(pk_dict).encode("utf-8"))

    sk_dict = {"p": str(priv_key.p), "q": str(priv_key.q)}
    priv_key_size = len(json.dumps(sk_dict).encode("utf-8"))

    taille_clair_moyenne = 8  # 64-bit integer en moyenne (8 octets)

    return {
        "scheme": "Paillier (PHE)",
        "parametre_cle": f"N = {key_size} bits",
        "securite_bits": sec_equiv,
        "niveau_label": f"{sec_equiv} bits ({'Recommandé NIST' if sec_equiv==128 else 'Legacy' if sec_equiv==80 else 'Standard' if sec_equiv==112 else 'Haute Sécurité'})",
        "post_quantique": "Non (Vulnérable Shor)",
        "base_mathematique": "Résiduosité Composite / Factorisation",
        "temps_keygen_ms": float(np.mean(temps_keygen_list)) * 1000,
        "temps_enc_total_ms": float(np.mean(temps_enc_list)) * 1000,
        "temps_enc_unitaire_ms": (float(np.mean(temps_enc_list)) / len(valeurs)) * 1000,
        "temps_somme_homomorphe_ms": float(np.mean(temps_add_list)) * 1000,
        "temps_dec_total_ms": float(np.mean(temps_dec_list)) * 1000,
        "debit_chiffrement_ops_sec": len(valeurs) / float(np.mean(temps_enc_list)),
        "taille_cle_publique_octets": pub_key_size,
        "taille_cle_privee_octets": priv_key_size,
        "taille_ciphertext_octets": sample_ciphertext_size,
        "facteur_expansion": sample_ciphertext_size / taille_clair_moyenne,
        "memoire_pic_ko": float(np.mean(mem_pic_list)) / 1024,
        "nb_valeurs_testees": len(valeurs),
        "exactitude": "Exacte (100%)"
    }


def evaluer_bfv(poly_degree, sec_level, plain_modulus_bits, valeurs, nb_repetitions=3):
    """Mesure les métriques complètes de BFV pour un degré n et niveau de sécurité sec."""
    he_test = Pyfhel()
    status = he_test.contextGen(scheme="BFV", n=poly_degree, t_bits=plain_modulus_bits, sec=sec_level)
    if "success: valid" not in status:
        return None

    temps_keygen_list = []
    temps_enc_list = []
    temps_add_list = []
    temps_dec_list = []
    mem_pic_list = []

    he = None
    sample_ciphertext_size = 0
    pub_key_size = 0
    priv_key_size = 0

    for _ in range(nb_repetitions):
        tracemalloc.start()

        # Context & KeyGen
        t0 = time.perf_counter()
        he = Pyfhel()
        he.contextGen(scheme="BFV", n=poly_degree, t_bits=plain_modulus_bits, sec=sec_level)
        he.keyGen()
        t_keygen = time.perf_counter() - t0

        # Encryption
        t0 = time.perf_counter()
        chiffres = [he.encryptInt(np.array([int(v)], dtype=np.int64)) for v in valeurs]
        t_enc = time.perf_counter() - t0

        # Homomorphic Addition
        t0 = time.perf_counter()
        somme_c = chiffres[0].copy()
        for c in chiffres[1:]:
            somme_c += c
        t_add = time.perf_counter() - t0

        # Decryption
        t0 = time.perf_counter()
        somme_dechiffree = int(he.decryptInt(somme_c)[0])
        t_dec = time.perf_counter() - t0

        _, mem_pic = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Validation mathématique
        assert somme_dechiffree == sum(valeurs), f"Erreur calcul BFV n={poly_degree}, sec={sec_level}"

        temps_keygen_list.append(t_keygen)
        temps_enc_list.append(t_enc)
        temps_add_list.append(t_add)
        temps_dec_list.append(t_dec)
        mem_pic_list.append(mem_pic)

    # Tailles sérialisées
    sample_c = chiffres[0]
    c_b64 = base64.b64encode(sample_c.to_bytes()).decode("utf-8")
    sample_ciphertext_size = len(c_b64.encode("utf-8"))

    pk_bytes = he.to_bytes_public_key()
    pub_key_size = len(base64.b64encode(pk_bytes).decode("utf-8"))

    sk_bytes = he.to_bytes_secret_key()
    priv_key_size = len(base64.b64encode(sk_bytes).decode("utf-8"))

    taille_clair_moyenne = 8  # 64-bit integer en moyenne (8 octets)

    return {
        "scheme": "BFV (Pyfhel / SEAL)",
        "parametre_cle": f"n = {poly_degree}, sec = {sec_level}b",
        "securite_bits": sec_level,
        "niveau_label": f"{sec_level} bits ({'Standard RLWE 128' if sec_level==128 else 'Haute Sécurité' if sec_level==192 else 'Très Haute Sécurité'})",
        "post_quantique": "Oui (RLWE / Réseaux)",
        "base_mathematique": "Ring Learning With Errors (RLWE)",
        "temps_keygen_ms": float(np.mean(temps_keygen_list)) * 1000,
        "temps_enc_total_ms": float(np.mean(temps_enc_list)) * 1000,
        "temps_enc_unitaire_ms": (float(np.mean(temps_enc_list)) / len(valeurs)) * 1000,
        "temps_somme_homomorphe_ms": float(np.mean(temps_add_list)) * 1000,
        "temps_dec_total_ms": float(np.mean(temps_dec_list)) * 1000,
        "debit_chiffrement_ops_sec": len(valeurs) / float(np.mean(temps_enc_list)),
        "taille_cle_publique_octets": pub_key_size,
        "taille_cle_privee_octets": priv_key_size,
        "taille_ciphertext_octets": sample_ciphertext_size,
        "facteur_expansion": sample_ciphertext_size / taille_clair_moyenne,
        "memoire_pic_ko": float(np.mean(mem_pic_list)) / 1024,
        "nb_valeurs_testees": len(valeurs),
        "exactitude": "Exacte (100%)"
    }


def executer_comparatif_securite(nb_valeurs=50, nb_repetitions=2):
    """Exécute la batterie de tests complète sur plusieurs configurations de sécurité."""
    valeurs = charger_ou_generer_donnees(nb_valeurs)
    print(f"[+] Données de test chargées : {len(valeurs)} transactions financières")
    print(f"[+] Répétitions par configuration : {nb_repetitions}")

    resultats = []

    # 1. Configurations Paillier (1024, 2048, 3072, 4096 bits)
    paillier_configs = [1024, 2048, 3072, 4096]
    print("\n--- [PAILLIER] Evaluation Paillier (Variation de la taille de cle N) ---")
    for ks in paillier_configs:
        print(f" -> Test Paillier N={ks} bits...")
        res = evaluer_paillier(ks, valeurs, nb_repetitions=nb_repetitions)
        resultats.append(res)
        print(f"    KeyGen: {res['temps_keygen_ms']:.1f}ms | Enc (1tx): {res['temps_enc_unitaire_ms']:.2f}ms | Ciphertext: {res['taille_ciphertext_octets']} o")

    # 2. Configurations BFV (Combinaisons de degré polynomial n et sec)
    bfv_configs = [
        (4096, 128),
        (8192, 128),   # Alignement standard 128 bits
        (8192, 192),
        (16384, 128),
        (16384, 256)
    ]
    print("\n--- [BFV] Evaluation BFV (Variation du degre n et du niveau sec RLWE) ---")
    for deg, sec in bfv_configs:
        print(f" -> Test BFV n={deg}, sec={sec} bits...")
        res = evaluer_bfv(deg, sec, BFV_PLAIN_MODULUS_BITS, valeurs, nb_repetitions=nb_repetitions)
        if res:
            resultats.append(res)
            print(f"    KeyGen: {res['temps_keygen_ms']:.1f}ms | Enc (1tx): {res['temps_enc_unitaire_ms']:.2f}ms | Ciphertext: {res['taille_ciphertext_octets']} o")
        else:
            print(f"    [SKIP] Parametres BFV incompatibles (budget de bruit insuffisant pour n={deg}, sec={sec})")

    return resultats


def afficher_tableau_alignement_128bits(resultats):
    """Affiche le tableau spécifique d'alignement équitable à 128 bits (Pilier 1 du mémoire)."""
    p_128 = next((r for r in resultats if r["scheme"].startswith("Paillier") and "3072" in r["parametre_cle"]), None)
    b_128 = next((r for r in resultats if r["scheme"].startswith("BFV") and "8192" in r["parametre_cle"] and "128" in r["parametre_cle"]), None)

    if not p_128 or not b_128:
        return

    print("\n" + "#" * 85)
    print(" [ALIGNEMENT] TABLEAU D'ALIGNEMENT DU NIVEAU DE SECURITE (STANDARD 128 BITS NIST / RLWE)")
    print("              Base commune equitable pour le Chapitre 3 & 4 du memoire")
    print("#" * 85)

    format_row = "{:<32} | {:<24} | {:<24}"
    print(format_row.format("METRIQUE / CARACTERISTIQUE", "PAILLIER (PHE)", "BFV (Pyfhel / SEAL)"))
    print("-" * 85)
    print(format_row.format("Niveau de securite theorique", "128 bits (NIST SP 800-57)", "128 bits (Homomorphic Std)"))
    print(format_row.format("Parametres cryptographiques", p_128["parametre_cle"], b_128["parametre_cle"]))
    print(format_row.format("Resistance Post-Quantique", p_128["post_quantique"], b_128["post_quantique"]))
    print(format_row.format("Fondement mathematique", "Factorisation (DCR)", "Reseaux Euclidiens (RLWE)"))
    print("-" * 85)
    print(format_row.format("Temps Generation Cles (KeyGen)", f"{p_128['temps_keygen_ms']:.2f} ms", f"{b_128['temps_keygen_ms']:.2f} ms"))
    print(format_row.format("Chiffrement (1 transaction)", f"{p_128['temps_enc_unitaire_ms']:.2f} ms", f"{b_128['temps_enc_unitaire_ms']:.2f} ms"))
    print(format_row.format("Chiffrement (Lot)", f"{p_128['temps_enc_total_ms']:.2f} ms", f"{b_128['temps_enc_total_ms']:.2f} ms"))
    print(format_row.format("Addition Homomorphe (Total)", f"{p_128['temps_somme_homomorphe_ms']:.3f} ms", f"{b_128['temps_somme_homomorphe_ms']:.3f} ms"))
    print(format_row.format("Temps Dechiffrement", f"{p_128['temps_dec_total_ms']:.2f} ms", f"{b_128['temps_dec_total_ms']:.2f} ms"))
    print(format_row.format("Debit Chiffrement (ops/sec)", f"{p_128['debit_chiffrement_ops_sec']:.1f} ops/s", f"{b_128['debit_chiffrement_ops_sec']:.1f} ops/s"))
    print("-" * 85)
    print(format_row.format("Taille Cle Publique", f"{p_128['taille_cle_publique_octets']:,} octets", f"{b_128['taille_cle_publique_octets']:,} octets"))
    print(format_row.format("Taille Cle Privee", f"{p_128['taille_cle_privee_octets']:,} octets", f"{b_128['taille_cle_privee_octets']:,} octets"))
    print(format_row.format("Taille Ciphertext unitaire", f"{p_128['taille_ciphertext_octets']:,} octets", f"{b_128['taille_ciphertext_octets']:,} octets"))
    print(format_row.format("Facteur d'expansion vs clair", f"{p_128['facteur_expansion']:.1f}x", f"{b_128['facteur_expansion']:.1f}x"))
    print(format_row.format("Memoire Vive PIC (RAM)", f"{p_128['memoire_pic_ko']:.1f} Ko", f"{b_128['memoire_pic_ko']:.1f} Ko"))
    print("#" * 85 + "\n")


def sauvegarder_donnees(resultats):
    """Exporte les résultats en CSV et génère les rapports Markdown pour le mémoire."""
    os.makedirs(os.path.join(ROOT_DIR, RESULTS_DIR), exist_ok=True)

    # 1. Export CSV
    chemin_csv = os.path.join(ROOT_DIR, RESULTS_DIR, "comparatif_securite_parametres.csv")
    if resultats:
        with open(chemin_csv, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=resultats[0].keys())
            writer.writeheader()
            writer.writerows(resultats)
        print(f"[OK] Fichier CSV exporté -> {chemin_csv}")

    # 2. Export Tableau Alignement Chapitre 3
    chemin_alignement = os.path.join(ROOT_DIR, RESULTS_DIR, "tableau_alignement_chapitre3.md")
    p_128 = next((r for r in resultats if r["scheme"].startswith("Paillier") and "3072" in r["parametre_cle"]), None)
    b_128 = next((r for r in resultats if r["scheme"].startswith("BFV") and "8192" in r["parametre_cle"] and "128" in r["parametre_cle"]), None)

    with open(chemin_alignement, mode="w", encoding="utf-8") as f:
        f.write("# Tableau Récapitulatif de l'Environnement de Test (Base Commune - Chapitre 3)\n\n")
        f.write("Ce tableau formalise l'alignement rigoureux des paramètres pour éliminer les biais d'évaluation entre chiffrement homomorphe partiel (Paillier) et complet (BFV).\n\n")
        f.write("| Paramètre de test | Configuration pour Paillier | Configuration pour BFV | Objectif de l'alignement |\n")
        f.write("| :--- | :--- | :--- | :--- |\n")
        f.write("| **Niveau de sécurité cible** | Clé de **3072 bits** (NIST SP 800-57) | Paramètres RLWE **128 bits** ($n=8192, \\text{sec}=128$) | Équivalence face à la cryptanalyse (Standard 128-bit) |\n")
        f.write("| **Résistance Post-Quantique** | Non (Vulnérable à l'algorithme de Shor) | **Oui** (Cryptographie à base de réseaux euclidiens) | Anticipation des menaces quantiques à long terme |\n")
        f.write("| **Type de données** | Entiers codés (FCFA) | Entiers codés (FCFA) | Identité stricte des entrées financières |\n")
        f.write("| **Précision numérique** | Exacte (Arithmétique entière modulaire) | Exacte ($t > \\text{Somme}_{\\max}$, pas d'approximation) | Exactitude arithmétique 100% garantie |\n")
        f.write("| **Matériel / CPU** | Même machine virtuelle Cloud / Conteneur | Même machine virtuelle Cloud / Conteneur | Éliminer les biais matériels et d'architecture |\n\n")

        if p_128 and b_128:
            f.write("## Métriques Obtenues sur la Base Commune (128 bits de sécurité)\n\n")
            f.write("| Métrique | Paillier (3072 bits) | BFV ($n=8192, \\text{sec}=128$) | Ratio / Avantage |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
            f.write(f"| **Temps KeyGen** | {p_128['temps_keygen_ms']:.2f} ms | {b_128['temps_keygen_ms']:.2f} ms | BFV {p_128['temps_keygen_ms']/b_128['temps_keygen_ms']:.1f}x plus rapide |\n")
            f.write(f"| **Chiffrement (1 tx)** | {p_128['temps_enc_unitaire_ms']:.2f} ms | {b_128['temps_enc_unitaire_ms']:.2f} ms | BFV {p_128['temps_enc_unitaire_ms']/b_128['temps_enc_unitaire_ms']:.1f}x plus rapide |\n")
            f.write(f"| **Addition Homomorphe** | {p_128['temps_somme_homomorphe_ms']:.3f} ms | {b_128['temps_somme_homomorphe_ms']:.3f} ms | Paillier {b_128['temps_somme_homomorphe_ms']/p_128['temps_somme_homomorphe_ms']:.1f}x plus rapide |\n")
            f.write(f"| **Déchiffrement** | {p_128['temps_dec_total_ms']:.2f} ms | {b_128['temps_dec_total_ms']:.2f} ms | BFV {p_128['temps_dec_total_ms']/b_128['temps_dec_total_ms']:.1f}x plus rapide |\n")
            f.write(f"| **Taille Ciphertext** | {p_128['taille_ciphertext_octets']:,} octets | {b_128['taille_ciphertext_octets']:,} octets | Paillier {b_128['taille_ciphertext_octets']/p_128['taille_ciphertext_octets']:.1f}x plus compact |\n")
            f.write(f"| **Facteur d'Expansion** | {p_128['facteur_expansion']:.1f}x | {b_128['facteur_expansion']:.1f}x | Paillier moins gourmand en bande passante |\n")

    print(f"[OK] Tableau d'alignement Chapitre 3 généré -> {chemin_alignement}")

    # 3. Export Rapport Global de Sécurité
    chemin_rapport = os.path.join(ROOT_DIR, RESULTS_DIR, "rapport_comparatif_securite.md")
    with open(chemin_rapport, mode="w", encoding="utf-8") as f:
        f.write("# Rapport d'Analyse des Performances Cryptographiques selon les Paramètres de Sécurité\n\n")
        f.write("## 1. Introduction et Problématique de l'Alignement\n\n")
        f.write("Dans le cadre de l'évaluation comparative des schémas homomorphes pour les architectures bancaires Cloud (BCEAO / UEMOA), la comparaison brute entre schémas peut introduire des biais méthodologiques majeurs si les niveaux de sécurité théorique ne sont pas strictement alignés.\n\n")
        f.write("- **Le piège classique** : Comparer une clé Paillier de 2048 bits (offrant environ 112 bits de sécurité classique) avec un schéma BFV standard (offrant 128 bits de sécurité post-quantique).\n")
        f.write("- **La solution adoptée** : Aligner le protocole de test sur le standard minimal de **128 bits de sécurité** recommandé par le NIST et la *Homomorphic Encryption Standard* (clé Paillier de 3072 bits vs BFV avec $n=8192, \\text{sec}=128$).\n\n")

        f.write("## 2. Synthèse Complète des Mesures Multi-Paramètres\n\n")
        f.write("| Schéma | Configuration | Sécurité Cible | Post-Quantique | KeyGen (ms) | Chiffrement unitaire (ms) | Somme Homomorphe (ms) | Déchiffrement (ms) | Taille Ciphertext (octets) | Expansion |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for r in resultats:
            f.write(f"| {r['scheme']} | `{r['parametre_cle']}` | {r['niveau_label']} | {r['post_quantique']} | {r['temps_keygen_ms']:.1f} | {r['temps_enc_unitaire_ms']:.2f} | {r['temps_somme_homomorphe_ms']:.3f} | {r['temps_dec_total_ms']:.2f} | {r['taille_ciphertext_octets']:,} | {r['facteur_expansion']:.1f}x |\n")

        f.write("\n## 3. Analyse des Tendances et Compromis Sécurité / Performance\n\n")
        f.write("### A. Impact sur Paillier (PHE)\n")
        f.write("- Le coût de génération des clés croît de façon cubique $\\mathcal{O}(k^3)$ avec la taille de la clé $k$.\n")
        f.write("- Le passage de 2048 bits (112b) à 3072 bits (128b) augmente le temps de chiffrement d'environ un facteur $3\\times$, et la taille des ciphertexts de 50%.\n")
        f.write("- L'addition homomorphe reste extrêmement rapide (simple multiplication modulaire $c_1 \\cdot c_2 \\pmod{N^2}$).\n\n")

        f.write("### B. Impact sur BFV (FHE)\n")
        f.write("- Le niveau de sécurité (`sec=128, 192, 256`) et le degré polynomial ($n=4096, 8192, 16384$) déterminent la capacité de multiplication et la résistance aux attaques LWE.\n")
        f.write("- BFV offre des temps de chiffrement et déchiffrement significativement plus rapides que Paillier grâce aux opérations polynomiales optimisées (NTT / SIMD).\n")
        f.write("- En contrepartie, la taille unitaire d'un ciphertext BFV non packagé est nettement plus volumineuse que Paillier, justifiant l'usage du batching SIMD en production bancaire.\n\n")

        f.write("## 4. Recommandations Décisionnelles pour le Secteur Bancaire\n\n")
        f.write("1. **Pour les calculs financiers purement additifs (Agrégation de soldes, calcul d'agios, scoring linéaire)** : Paillier 3072 bits offre la meilleure efficacité réseau et mémoire avec un overhead minimal sur les serveurs Cloud.\n")
        f.write("2. **Pour les architectures pérennes et post-quantiques ou calculs polynomiaux** : BFV ($n=8192, \\text{sec}=128$) est le choix d'excellence, éliminant tout risque lié aux futurs calculateurs quantiques.\n")

    print(f"[OK] Rapport d'analyse complet généré -> {chemin_rapport}")


def main():
    parser = argparse.ArgumentParser(description="Comparaison des performances selon les paramètres de sécurité (Paillier vs BFV)")
    parser.add_argument("--transactions", type=int, default=50, help="Nombre de transactions testées par lot (défaut: 50)")
    parser.add_argument("--repetitions", type=int, default=3, help="Nombre de répétitions par configuration (défaut: 3)")
    parser.add_argument("--quick", action="store_true", help="Mode rapide (20 transactions, 1 répétition)")

    args = parser.parse_args()

    afficher_banniere()

    nb_tx = 20 if args.quick else args.transactions
    nb_rep = 1 if args.quick else args.repetitions

    resultats = executer_comparatif_securite(nb_valeurs=nb_tx, nb_repetitions=nb_rep)
    afficher_tableau_alignement_128bits(resultats)
    sauvegarder_donnees(resultats)

    print("\n" + "=" * 80)
    print(" [SUCCES] ETUDE COMPARATIVE DE SECURITE TERMINEE AVEC SUCCES")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
