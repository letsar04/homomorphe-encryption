"""
Harnais de benchmark Cloud REST — Mesures avec transfert réseau HTTP effectif.
Conforme à la méthodologie du Chapitre III du mémoire (échelles N ∈ [10, 100, 1000, 10000],
ordre d'exécution entrelacé, télémesures réseau et serveur Hetzner / Cloud public).

Exporte les résultats détaillés dans results/benchmarks_cloud_bruts.csv.
"""

import argparse
import csv
import os
import sys
import time
import tracemalloc

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from config import DATA_DIR, RESULTS_DIR, CLOUD_HOST, CLOUD_PORT, TIERS_BENCHMARK, NB_REPETITIONS_RAPIDE
from schemes.paillier_ops import PaillierScheme
from schemes.bfv_ops import BFVScheme
from cloud_sim.cloud_api_client import CloudAPIClient
from benchmarks.baseline_clair import mesurer_baseline


def charger_transactions(chemin_csv):
    """Charge les transactions synthétiques (montants signés en FCFA)."""
    montants = []
    with open(chemin_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            montants.append(int(row["montant"]))
    return montants


def mesurer_iteration_cloud(nom_scheme, scheme, client, valeurs, rep_index):
    """
    Mesure une itération complète avec transfert réseau HTTP réel :
    1. Chiffrement local client
    2. Envoi HTTP au serveur Cloud + calcul homomorphe distant
    3. Réception de la réponse chiffrée
    4. Déchiffrement local client
    """
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

    somme_attendue = sum(valeurs)
    assert somme_dechiffree == somme_attendue, (
        f"Incohérence mathématique sur {nom_scheme} (N={len(valeurs)}): {somme_dechiffree} vs attendu {somme_attendue}"
    )

    return {
        "scheme": nom_scheme,
        "repetition": rep_index,
        "nb_valeurs": len(valeurs),
        "temps_chiffrement_sec": t_chiffrement,
        "temps_reseau_total_sec": res_cloud["temps_reseau_total_sec"],
        "temps_calcul_cloud_sec": res_cloud["temps_calcul_cloud_sec"],
        "temps_latence_reseau_sec": res_cloud["temps_latence_reseau_sec"],
        "temps_dechiffrement_sec": t_dechiffrement,
        "temps_total_cycle_sec": t_chiffrement + res_cloud["temps_reseau_total_sec"] + t_dechiffrement,
        "octets_envoyes_reseau": res_cloud["octets_envoyes"],
        "octets_recus_reseau": res_cloud["octets_recus"],
        "memoire_pic_client_octets": memoire_pic,
        "somme_resultat": somme_dechiffree,
        "somme_attendue": somme_attendue,
        "exactitude": (somme_dechiffree == somme_attendue)
    }


def executer_benchmarks_cloud(client, tiers, nb_repetitions):
    """
    Exécute le benchmark Cloud avec entrelacement d'ordre (A/B testing)
    pour éliminer les biais thermiques et de cache réseau.
    """
    chemin_donnees = os.path.join(ROOT_DIR, DATA_DIR, "transactions_synthetiques.csv")
    if not os.path.exists(chemin_donnees):
        raise FileNotFoundError(f"{chemin_donnees} introuvable. Exécutez data/generate_synthetic.py")

    toutes_transactions = charger_transactions(chemin_donnees)
    print(f"\n[OK] {len(toutes_transactions):,} transactions chargées depuis {chemin_donnees}")
    print(f"Échelles évaluées : {tiers}")
    print(f"Répétitions par palier : {nb_repetitions}")

    print("\n--- Initialisation des instances de clés ---")
    paillier_inst = PaillierScheme()
    bfv_inst = BFVScheme()

    resultats = []

    for N in tiers:
        if N > len(toutes_transactions):
            print(f"[ATTENTION] Palier N={N} supérieur au volume disponible ({len(toutes_transactions)}). Tronqué.")
            N = len(toutes_transactions)

        echantillon = toutes_transactions[:N]
        print(f"\n=======================================================")
        print(f"  BENCHMARK CLOUD REST — PALIER N = {N:,} TRANSACTIONS")
        print(f"=======================================================")

        # Baseline en clair
        baseline = mesurer_baseline(echantillon)
        print(f"Baseline en clair : {baseline['temps_somme_sec']*1000:.4f} ms | Somme: {baseline['somme']:,} FCFA")

        configs = [
            ("Paillier", paillier_inst),
            ("BFV", bfv_inst),
        ]

        for rep in range(nb_repetitions):
            # Entrelacement d'ordre (A/B testing)
            configs_ordonnees = configs[rep % len(configs):] + configs[:rep % len(configs)]

            for nom_scheme, inst in configs_ordonnees:
                res = mesurer_iteration_cloud(nom_scheme, inst, client, echantillon, rep + 1)
                resultats.append(res)

            if (rep + 1) % max(1, nb_repetitions // 2) == 0 or (rep + 1) == nb_repetitions:
                print(f"  -> Répétition {rep + 1}/{nb_repetitions} terminée pour N={N}")

    return resultats


def sauvegarder_resultats(resultats, chemin_sortie):
    """Sauvegarde les résultats Cloud au format CSV."""
    os.makedirs(os.path.dirname(chemin_sortie), exist_ok=True)
    if not resultats:
        print("[ATTENTION] Aucun résultat à sauvegarder.")
        return
    with open(chemin_sortie, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=resultats[0].keys())
        writer.writeheader()
        writer.writerows(resultats)
    print(f"\n[OK] Résultats Cloud sauvegardés -> {chemin_sortie}")


def main():
    parser = argparse.ArgumentParser(description="Harnais de benchmark Cloud REST HE_Proto conforme Chapitre III")
    parser.add_argument("--host", type=str, default=CLOUD_HOST, help="Hôte de l'API Cloud (ex: 127.0.0.1 ou IP Hetzner)")
    parser.add_argument("--port", type=int, default=CLOUD_PORT, help="Port de l'API Cloud (défaut: 8000)")
    parser.add_argument("--tiers", type=str, default=None, help="Liste des échelles (ex: 10,100,1000)")
    parser.add_argument("--repetitions", type=int, default=None, help="Nombre de répétitions par palier")
    parser.add_argument("--quick", action="store_true", help="Mode rapide (N=10, 100 avec 3 répétitions)")
    parser.add_argument("--sortie", type=str, default=None, help="Chemin du CSV de sortie")

    args = parser.parse_args()

    client = CloudAPIClient(host=args.host, port=args.port)
    if not client.verifier_connexion():
        print(f"[ERREUR] Serveur Cloud REST indisponible sur http://{args.host}:{args.port}.")
        print("Assurez-vous que le conteneur Docker ou `python cloud_sim/cloud_api_server.py` est démarré.")
        sys.exit(1)

    if args.quick:
        tiers = [10, 100]
        nb_repetitions = 3
    else:
        if args.tiers:
            tiers = [int(x.strip()) for x in args.tiers.split(",")]
        else:
            tiers = [10, 100, 1_000] # Par défaut sur Cloud réseau HTTP
        nb_repetitions = args.repetitions or NB_REPETITIONS_RAPIDE

    chemin_sortie = args.sortie or os.path.join(ROOT_DIR, RESULTS_DIR, "benchmarks_cloud_bruts.csv")

    resultats = executer_benchmarks_cloud(client, tiers, nb_repetitions)
    sauvegarder_resultats(resultats, chemin_sortie)


if __name__ == "__main__":
    main()
