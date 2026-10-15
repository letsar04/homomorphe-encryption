"""
Harnais de benchmark principal — orchestration des mesures pour
Paillier, BFV (scalaire), BFV (SIMD batché), et baseline en clair.

Conforme à la méthodologie du Chapitre III du mémoire :
- Échelles de transactions : N ∈ [10, 100, 1 000, 10 000]
- Réduction des biais thermiques et de cache : Ordre d'exécution entrelacé (A/B testing)
- Métriques complètes : KeyGen, Chiffrement, Somme homomorphe, Déchiffrement,
  Taille de ciphertext, Empreinte RAM pic, Exactitude du résultat
- Export des résultats bruts en CSV pour analyse statistique (moyenne, écart-type, IC 95%)
"""

import argparse
import csv
import os
import random
import sys
import time
import tracemalloc

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from config import DATA_DIR, RESULTS_DIR, TIERS_BENCHMARK, NB_REPETITIONS, NB_REPETITIONS_RAPIDE
from schemes.paillier_ops import PaillierScheme
from schemes.bfv_ops import BFVScheme
from cloud_sim.local_server import CloudServerSimule
from benchmarks.baseline_clair import mesurer_baseline


def charger_transactions(chemin_csv):
    """Charge les transactions synthétiques (montants signés en FCFA)."""
    montants = []
    with open(chemin_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            montants.append(int(row["montant"]))
    return montants


def estimer_taille_octets(objet):
    """Estime la taille sérialisée d'un ciphertext ou d'un lot de ciphertexts."""
    try:
        if hasattr(objet, "to_bytes"):
            return len(objet.to_bytes())
        if hasattr(objet, "ciphertext"):
            # Paillier EncryptedNumber : taille du grand entier en octets
            return (int(objet.ciphertext()).bit_length() + 7) // 8
        if isinstance(objet, list) and len(objet) > 0:
            return sum(estimer_taille_octets(x) for x in objet)
        return sys.getsizeof(objet)
    except Exception:
        return sys.getsizeof(objet)


def mesurer_operation(scheme_name, scheme, valeurs, rep_index, mode_simd=False):
    """
    Exécute et mesure un cycle complet (Chiffrement -> Somme -> Déchiffrement)
    avec traçage précis de l'empreinte mémoire et des temps d'exécution.
    """
    tracemalloc.start()

    if mode_simd:
        # --- BFV SIMD Batching ---
        t0 = time.perf_counter()
        chiffres = scheme.chiffrer_simd(valeurs)
        t_chiffrement = time.perf_counter() - t0

        t0 = time.perf_counter()
        somme_chiffree = scheme.somme_homomorphe_simd(chiffres)
        t_calcul = time.perf_counter() - t0

        t0 = time.perf_counter()
        somme_dechiffree = scheme.dechiffrer_simd(somme_chiffree, extraire_somme=True)
        t_dechiffrement = time.perf_counter() - t0

        taille_unitaire = estimer_taille_octets(chiffres[0]) if chiffres else 0
        taille_totale = estimer_taille_octets(chiffres)
        nb_ciphertexts = len(chiffres)

    else:
        # --- Mode Scalaire (Paillier ou BFV) ---
        t0 = time.perf_counter()
        chiffres = scheme.chiffrer(valeurs)
        t_chiffrement = time.perf_counter() - t0

        serveur = CloudServerSimule(scheme)
        t0 = time.perf_counter()
        somme_chiffree = serveur.recevoir_et_sommer(chiffres)
        t_calcul = time.perf_counter() - t0

        t0 = time.perf_counter()
        somme_dechiffree = scheme.dechiffrer(somme_chiffree)
        t_dechiffrement = time.perf_counter() - t0

        taille_unitaire = estimer_taille_octets(chiffres[0]) if chiffres else 0
        taille_totale = taille_unitaire * len(chiffres)
        nb_ciphertexts = len(chiffres)

    _, memoire_pic = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    somme_attendue = sum(valeurs)
    assert somme_dechiffree == somme_attendue, (
        f"Incohérence mathématique sur {scheme_name} (N={len(valeurs)}): {somme_dechiffree} vs attendu {somme_attendue}"
    )

    return {
        "scheme": scheme_name,
        "repetition": rep_index,
        "nb_valeurs": len(valeurs),
        "nb_ciphertexts": nb_ciphertexts,
        "temps_chiffrement_sec": t_chiffrement,
        "temps_calcul_sec": t_calcul,
        "temps_dechiffrement_sec": t_dechiffrement,
        "temps_total_sec": t_chiffrement + t_calcul + t_dechiffrement,
        "memoire_pic_octets": memoire_pic,
        "taille_unitaire_octets": taille_unitaire,
        "taille_totale_ciphertexts_octets": taille_totale,
        "somme_resultat": somme_dechiffree,
        "somme_attendue": somme_attendue,
        "exactitude": (somme_dechiffree == somme_attendue)
    }


def executer_benchmarks(tiers, nb_repetitions, inclure_simd=True):
    """
    Exécute le protocole de benchmark en alternant l'ordre des schémas
    pour éliminer les biais thermiques et de cache (Méthodologie Chapitre III).
    """
    chemin_donnees = os.path.join(ROOT_DIR, DATA_DIR, "transactions_synthetiques.csv")
    if not os.path.exists(chemin_donnees):
        raise FileNotFoundError(f"{chemin_donnees} introuvable. Exécutez data/generate_synthetic.py")

    toutes_transactions = charger_transactions(chemin_donnees)
    print(f"\n[OK] {len(toutes_transactions):,} transactions chargées depuis {chemin_donnees}")
    print(f"Échelles évaluées : {tiers}")
    print(f"Répétitions par palier : {nb_repetitions}")

    # Mesure du temps d'initialisation des clés (KeyGen)
    print("\n--- Mesure du temps d'initialisation (KeyGen) ---")
    t0 = time.perf_counter()
    paillier_inst = PaillierScheme()
    t_keygen_paillier = time.perf_counter() - t0
    print(f"KeyGen Paillier (2048 bits) : {t_keygen_paillier:.4f} s")

    t0 = time.perf_counter()
    bfv_inst = BFVScheme()
    t_keygen_bfv = time.perf_counter() - t0
    print(f"KeyGen BFV (n=8192, 128-bit) : {t_keygen_bfv:.4f} s")

    if inclure_simd:
        t0 = time.perf_counter()
        bfv_inst.activer_simd()
        t_keygen_rot = time.perf_counter() - t0
        print(f"KeyGen BFV RotateKeys (SIMD) : {t_keygen_rot:.4f} s")

    resultats = []

    for N in tiers:
        if N > len(toutes_transactions):
            print(f"[ATTENTION] Palier N={N} supérieur au volume disponible ({len(toutes_transactions)}). Tronqué.")
            N = len(toutes_transactions)

        echantillon = toutes_transactions[:N]
        print(f"\n=======================================================")
        print(f"  BENCHMARK PALIER N = {N:,} TRANSACTIONS")
        print(f"=======================================================")

        # Baseline en clair
        baseline = mesurer_baseline(echantillon)
        print(f"Baseline en clair : {baseline['temps_somme_sec']*1000:.4f} ms | Somme: {baseline['somme']:,} FCFA")

        # Configurations à évaluer
        configs = [
            ("Paillier", paillier_inst, False),
            ("BFV-SIMD", bfv_inst, True),
        ]
        
        # Le mode BFV scalaire (1 ciphertext par tx) est évalué sur N <= 1000
        # Pour N=10000, 10 000 ciphers BFV satureraient la mémoire (~2.5 Go).
        if N <= 1000:
            configs.append(("BFV-Scalaire", bfv_inst, False))

        for rep in range(nb_repetitions):
            # Entrelacement d'ordre (A/B testing) : décale l'ordre à chaque répétition
            configs_ordonnees = configs[rep % len(configs):] + configs[:rep % len(configs)]

            for nom_scheme, inst, is_simd in configs_ordonnees:
                res = mesurer_operation(nom_scheme, inst, echantillon, rep + 1, mode_simd=is_simd)
                resultats.append(res)

            if (rep + 1) % max(1, nb_repetitions // 3) == 0 or (rep + 1) == nb_repetitions:
                print(f"  -> Répétition {rep + 1}/{nb_repetitions} terminée pour N={N}")

    return resultats


def sauvegarder_resultats(resultats, chemin_sortie):
    """Sauvegarde les résultats de benchmark au format CSV."""
    os.makedirs(os.path.dirname(chemin_sortie), exist_ok=True)
    if not resultats:
        print("[ATTENTION] Aucun résultat à sauvegarder.")
        return
    with open(chemin_sortie, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=resultats[0].keys())
        writer.writeheader()
        writer.writerows(resultats)
    print(f"\n[OK] Résultats complets sauvegardés -> {chemin_sortie}")


def main():
    parser = argparse.ArgumentParser(description="Harnais de benchmark HE_Proto conforme Chapitre III")
    parser.add_argument("--tiers", type=str, default=None, help="Liste des échelles séparées par virgules (ex: 10,100,1000,10000)")
    parser.add_argument("--repetitions", type=int, default=None, help="Nombre de répétitions par palier")
    parser.add_argument("--quick", action="store_true", help="Mode validation rapide (N=10, 100, 3 répétitions)")
    parser.add_argument("--sortie", type=str, default=None, help="Fichier de sortie CSV")

    args = parser.parse_args()

    if args.quick:
        tiers = [10, 100]
        nb_repetitions = 3
    else:
        if args.tiers:
            tiers = [int(x.strip()) for x in args.tiers.split(",")]
        else:
            tiers = TIERS_BENCHMARK
        nb_repetitions = args.repetitions or NB_REPETITIONS_RAPIDE

    chemin_sortie = args.sortie or os.path.join(ROOT_DIR, RESULTS_DIR, "benchmarks_bruts.csv")

    resultats = executer_benchmarks(tiers, nb_repetitions)
    sauvegarder_resultats(resultats, chemin_sortie)


if __name__ == "__main__":
    main()