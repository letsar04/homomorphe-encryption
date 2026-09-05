"""
Harnais de benchmark principal — orchestration des mesures pour
Paillier, BFV, et la baseline en clair.

Répète chaque opération plusieurs fois pour réduire le bruit de mesure
(cf. note technique, point 12 Partie II), et exporte les résultats en
CSV pour alimenter le Chapitre 4 du mémoire.
"""

import csv
import os
import sys
import time
import tracemalloc

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from config import DATA_DIR, RESULTS_DIR
from schemes.paillier_ops import PaillierScheme
from schemes.bfv_ops import BFVScheme
from cloud_sim.local_server import CloudServerSimule
from benchmarks.baseline_clair import mesurer_baseline


def charger_transactions(chemin_csv):
    montants = []
    with open(chemin_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            montants.append(int(row["montant"]))
    return montants


def taille_ciphertext(objet):
    """Taille approximative en mémoire d'un ciphertext (indicatif)."""
    try:
        return sys.getsizeof(objet)
    except TypeError:
        return -1


def mesurer_scheme(nom_scheme, scheme, valeurs, nb_repetitions):
    """
    Mesure temps de chiffrement / calcul homomorphe / déchiffrement,
    mémoire pic, et taille de ciphertext, répété nb_repetitions fois.
    """
    resultats = []

    for rep in range(nb_repetitions):
        tracemalloc.start()

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

        _, memoire_pic = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        resultats.append({
            "scheme": nom_scheme,
            "repetition": rep + 1,
            "nb_valeurs": len(valeurs),
            "temps_chiffrement_sec": t_chiffrement,
            "temps_calcul_sec": t_calcul,
            "temps_dechiffrement_sec": t_dechiffrement,
            "memoire_pic_octets": memoire_pic,
            "taille_ciphertext_octets": taille_ciphertext(chiffres[0]),
            "somme_resultat": somme_dechiffree,
            "somme_attendue": sum(valeurs),
        })

    return resultats


def sauvegarder_resultats(resultats, chemin_sortie):
    os.makedirs(os.path.dirname(chemin_sortie), exist_ok=True)
    if not resultats:
        print("[ATTENTION] Aucun résultat à sauvegarder.")
        return
    with open(chemin_sortie, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=resultats[0].keys())
        writer.writeheader()
        writer.writerows(resultats)
    print(f"[OK] Résultats sauvegardés -> {chemin_sortie}")


if __name__ == "__main__":
    chemin_donnees = os.path.join(ROOT_DIR, DATA_DIR, "transactions_synthetiques.csv")

    if not os.path.exists(chemin_donnees):
        print(f"[ERREUR] {chemin_donnees} introuvable. Lance d'abord data/generate_synthetic.py")
        sys.exit(1)

    montants = charger_transactions(chemin_donnees)
    print(f"Chargé {len(montants)} montants depuis {chemin_donnees}")

    # NOTE : Paillier et BFV chiffrent chaque valeur individuellement dans
    # cette version simple (pas de batching). Sur 5000 valeurs, le temps
    # de chiffrement séquentiel peut être long. Commence avec un petit
    # échantillon pour valider le pipeline, puis augmente progressivement.
    TAILLE_ECHANTILLON = 100
    NB_REPETITIONS_TEST = 5  # réduit pour un premier essai rapide ; monter à 30 en production

    echantillon = montants[:TAILLE_ECHANTILLON]

    print("\n--- Baseline en clair ---")
    baseline = mesurer_baseline(echantillon)
    print(baseline)

    print(f"\n--- Paillier ({NB_REPETITIONS_TEST} répétitions) ---")
    paillier_scheme = PaillierScheme()
    resultats_paillier = mesurer_scheme(
        "Paillier", paillier_scheme, echantillon, NB_REPETITIONS_TEST
    )

    print(f"\n--- BFV ({NB_REPETITIONS_TEST} répétitions) ---")
    bfv_scheme = BFVScheme()
    resultats_bfv = mesurer_scheme("BFV", bfv_scheme, echantillon, NB_REPETITIONS_TEST)

    tous_resultats = resultats_paillier + resultats_bfv
    sauvegarder_resultats(
        tous_resultats, os.path.join(ROOT_DIR, RESULTS_DIR, "benchmarks_bruts.csv")
    )