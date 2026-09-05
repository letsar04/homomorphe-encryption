"""
Harnais de benchmark Cloud REST — Mesures avec transfert réseau HTTP effectif.

Orchestre les mesures de temps de chiffrement, temps de transfert réseau HTTP,
temps de calcul homomorphe sur le serveur Cloud distant, temps de déchiffrement,
et volume de données transmises sur le réseau.
Exporte les résultats dans results/benchmarks_cloud_bruts.csv.
"""

import csv
import os
import sys
import time
import tracemalloc

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from config import DATA_DIR, RESULTS_DIR, CLOUD_HOST, CLOUD_PORT
from schemes.paillier_ops import PaillierScheme
from schemes.bfv_ops import BFVScheme
from cloud_sim.cloud_api_client import CloudAPIClient
from benchmarks.baseline_clair import mesurer_baseline


def charger_transactions(chemin_csv):
    montants = []
    with open(chemin_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            montants.append(int(row["montant"]))
    return montants


def mesurer_scheme_cloud(nom_scheme, scheme, client, valeurs, nb_repetitions):
    resultats = []

    for rep in range(nb_repetitions):
        tracemalloc.start()

        # 1. Chiffrement côté client
        t0 = time.perf_counter()
        chiffres = scheme.chiffrer(valeurs)
        t_chiffrement = time.perf_counter() - t0

        # 2. Transmettre au serveur Cloud REST et calculer la somme
        if nom_scheme == "Paillier":
            res_cloud = client.sommer_paillier(scheme, chiffres)
        elif nom_scheme == "BFV":
            res_cloud = client.sommer_bfv(scheme, chiffres)
        else:
            raise ValueError(f"Schéma inconnu : {nom_scheme}")

        somme_chiffree = res_cloud["somme_chiffree"]

        # 3. Déchiffrement côté client
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
            "temps_reseau_total_sec": res_cloud["temps_reseau_total_sec"],
            "temps_calcul_cloud_sec": res_cloud["temps_calcul_cloud_sec"],
            "temps_latence_reseau_sec": res_cloud["temps_latence_reseau_sec"],
            "temps_dechiffrement_sec": t_dechiffrement,
            "octets_envoyes_reseau": res_cloud["octets_envoyes"],
            "octets_recus_reseau": res_cloud["octets_recus"],
            "memoire_pic_octets": memoire_pic,
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

    client = CloudAPIClient(host=CLOUD_HOST, port=CLOUD_PORT)
    if not client.verifier_connexion():
        print(f"[ERREUR] Serveur Cloud REST indisponible sur http://{CLOUD_HOST}:{CLOUD_PORT}.")
        print("Assurez-vous de démarrer `python cloud_sim/cloud_api_server.py` dans une autre console.")
        sys.exit(1)

    montants = charger_transactions(chemin_donnees)
    print(f"Chargé {len(montants)} montants depuis {chemin_donnees}")

    TAILLE_ECHANTILLON = 100
    NB_REPETITIONS_TEST = 5

    echantillon = montants[:TAILLE_ECHANTILLON]

    print("\n--- Baseline en clair ---")
    baseline = mesurer_baseline(echantillon)
    print(baseline)

    print(f"\n--- Paillier via Cloud REST API ({NB_REPETITIONS_TEST} répétitions) ---")
    paillier_scheme = PaillierScheme()
    resultats_paillier = mesurer_scheme_cloud(
        "Paillier", paillier_scheme, client, echantillon, NB_REPETITIONS_TEST
    )

    print(f"\n--- BFV via Cloud REST API ({NB_REPETITIONS_TEST} répétitions) ---")
    bfv_scheme = BFVScheme()
    resultats_bfv = mesurer_scheme_cloud(
        "BFV", bfv_scheme, client, echantillon, NB_REPETITIONS_TEST
    )

    tous_resultats = resultats_paillier + resultats_bfv
    sauvegarder_resultats(
        tous_resultats, os.path.join(ROOT_DIR, RESULTS_DIR, "benchmarks_cloud_bruts.csv")
    )
