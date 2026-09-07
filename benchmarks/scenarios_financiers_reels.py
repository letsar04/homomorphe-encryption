"""
Scénarios Financiers Réels — Calculs Homomorphes pour le Cloud Banking et Mobile Money.

Implémente et teste 2 cas d'usage réels adaptés au contexte africain/BCEAO (Burkina Faso) :
1. Calcul du Score de Micro-Crédit Mobile Money (Orange/Moov/Wave) :
   Score = (alpha * Volume_Tx) + (beta * Regularite) - (gamma * Retards)
2. Calcul d'Agios et d'Intérêts Bancaires (Méthode Hambourgeoise / Prorata Temporis) :
   Agios = (Somme(Soldes_Journaliers) * Taux_Annuel) / 360
"""

import csv
import json
import os
import random
import sys
import time
import tracemalloc
import numpy as np

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from config import DATA_DIR, RESULTS_DIR, PAILLIER_KEY_SIZE, BFV_POLY_MODULUS_DEGREE, BFV_PLAIN_MODULUS_BITS
from schemes.paillier_ops import PaillierScheme
from schemes.bfv_ops import BFVScheme


def generer_donnees_clients_financiers(nb_clients=50, seed=42):
    """
    Génère un jeu de données de profils financiers synthétiques :
    - Volume transactions mensuelles (FCFA)
    - Indice de régularité des dépôts (1 à 10)
    - Nombre de jours de retard de remboursement (0 à 60 jours)
    - Historique de soldes quotidiens sur 30 jours (FCFA)
    """
    random.seed(seed)
    clients = []

    for i in range(1, nb_clients + 1):
        vol_tx = random.randint(50_000, 2_500_000)  # Volume en FCFA
        regularite = random.randint(1, 10)            # Score de régularité
        retards = random.randint(0, 45)              # Jours de retard

        # 30 soldes quotidiens (entre 10 000 FCFA et 500 000 FCFA)
        soldes_30j = [random.randint(10_000, 500_000) for _ in range(30)]

        clients.append({
            "client_id": f"CLI-{i:04d}",
            "volume_tx": vol_tx,
            "regularite": regularite,
            "retards": retards,
            "soldes_30j": soldes_30j
        })

    return clients


def scenario_1_microcredit_mobile_money(clients, paillier_scheme, bfv_scheme):
    """
    Scénario 1 : Octroi de Micro-Crédit Mobile Money.
    Algorithme de scoring : Score = (0.005 * Volume) + (50 * Régularité) - (20 * Retards)
    Pour rester en entiers sous HE, on multiplie les coefficients par 1000 :
    Score_Scaled = (5 * Volume) + (50 000 * Régularité) - (20 000 * Retards)
    """
    print("\n" + "=" * 70)
    print(" SCÉNARIO 1 : Calcul du Score de Micro-Crédit Mobile Money (HE)")
    print("=" * 70)

    ALPHA = 5       # Poids du volume
    BETA = 50_000   # Poids de la régularité
    GAMMA = 20_000  # Pénalité de retard
    SEUIL_ACCORD = 500_000  # Seuil minimal pour accorder le prêt

    res_paillier = []
    res_bfv = []

    for c in clients[:10]:  # Test sur les 10 premiers clients pour la démonstration
        vol = c["volume_tx"]
        reg = c["regularite"]
        ret = c["retards"]

        # Calcul de référence en clair
        score_attendu = (ALPHA * vol) + (BETA * reg) - (GAMMA * ret)
        decision_attendue = "ACCORDÉ" if score_attendu >= SEUIL_ACCORD else "REFUSÉ"

        # --- A. EXECUTION PAILLIER ---
        c_vol = paillier_scheme.public_key.encrypt(vol)
        c_reg = paillier_scheme.public_key.encrypt(reg)
        c_ret = paillier_scheme.public_key.encrypt(ret)

        t0 = time.perf_counter()
        # Somme pondérée homomorphe : (c_vol * ALPHA) + (c_reg * BETA) - (c_ret * GAMMA)
        score_chiffre_p = (c_vol * ALPHA) + (c_reg * BETA) - (c_ret * GAMMA)
        t_calcul_p = time.perf_counter() - t0

        score_p = paillier_scheme.private_key.decrypt(score_chiffre_p)
        decision_p = "ACCORDÉ" if score_p >= SEUIL_ACCORD else "REFUSÉ"

        res_paillier.append(score_p == score_attendu)

        # --- B. EXECUTION BFV ---
        # BFV chiffrement vectoriel ou scalaire
        c_vol_b = bfv_scheme.he.encryptInt(np.array([vol], dtype=np.int64))
        c_reg_b = bfv_scheme.he.encryptInt(np.array([reg], dtype=np.int64))
        c_ret_b = bfv_scheme.he.encryptInt(np.array([ret], dtype=np.int64))

        t0 = time.perf_counter()
        # Opérations homomorphes BFV
        term1 = c_vol_b * ALPHA
        term2 = c_reg_b * BETA
        term3 = c_ret_b * GAMMA
        score_chiffre_b = term1 + term2 - term3
        t_calcul_b = time.perf_counter() - t0

        score_b = int(bfv_scheme.he.decryptInt(score_chiffre_b)[0])
        decision_b = "ACCORDÉ" if score_b >= SEUIL_ACCORD else "REFUSÉ"

        res_bfv.append(score_b == score_attendu)

        print(f"Client {c['client_id']} | Vol: {vol:>9,} FCFA | Rég: {reg:>2}/10 | Ret: {ret:>2}j | "
              f"Score Paillier: {score_p:>10,} ({decision_p}) | Exact: {'[OK]' if score_p == score_attendu else '[ERREUR]'}")

    print("-" * 70)
    print(f"Précision globale Paillier : {sum(res_paillier)}/{len(res_paillier)} exacts")
    print(f"Précision globale BFV      : {sum(res_bfv)}/{len(res_bfv)} exacts")


def scenario_2_agios_intérets_bancaires(clients, paillier_scheme, bfv_scheme):
    """
    Scénario 2 : Calcul des Agios et Intérêts sur 30 jours (Système Bancaire).
    Formule : Somme des soldes journaliers * Taux Annuel / 360
    Taux annuel = 5% (0.05). Pour le HE en entiers, on multiplie par 100 puis on divise par 36 000 en clair.
    """
    print("\n" + "=" * 70)
    print(" SCÉNARIO 2 : Calcul des Agios & Intérêts sur Soldes Journaliers (HE)")
    print("=" * 70)

    TAUX_NUMERATEUR = 5  # 5%
    DIVISEUR = 36000     # 360 * 100

    res_paillier = []
    res_bfv = []

    for c in clients[:10]:
        soldes = c["soldes_30j"]
        somme_soldes_attendue = sum(soldes)
        agios_attendus = (somme_soldes_attendue * TAUX_NUMERATEUR) / DIVISEUR

        # --- A. EXECUTION PAILLIER ---
        soldes_chiffres_p = paillier_scheme.chiffrer(soldes)

        t0 = time.perf_counter()
        somme_c_p = paillier_scheme.somme_homomorphe(soldes_chiffres_p)
        produit_c_p = somme_c_p * TAUX_NUMERATEUR
        t_calcul_p = time.perf_counter() - t0

        somme_dechiffree_p = paillier_scheme.dechiffrer(produit_c_p)
        agios_p = somme_dechiffree_p / DIVISEUR

        res_paillier.append(abs(agios_p - agios_attendus) < 1e-4)

        # --- B. EXECUTION BFV ---
        soldes_chiffres_b = bfv_scheme.chiffrer(soldes)

        t0 = time.perf_counter()
        somme_c_b = bfv_scheme.somme_homomorphe(soldes_chiffres_b)
        produit_c_b = somme_c_b * TAUX_NUMERATEUR
        t_calcul_b = time.perf_counter() - t0

        somme_dechiffree_b = bfv_scheme.dechiffrer(produit_c_b)
        agios_b = somme_dechiffree_b / DIVISEUR

        res_bfv.append(abs(agios_b - agios_attendus) < 1e-4)

        print(f"Client {c['client_id']} | Somme 30j: {somme_soldes_attendue:>10,} FCFA | "
              f"Agios Paillier: {agios_p:>8.2f} FCFA | Agios BFV: {agios_b:>8.2f} FCFA | "
              f"Exact: {'[OK]' if abs(agios_p - agios_attendus) < 1e-4 else '[ERREUR]'}")

    print("-" * 70)
    print(f"Précision calcul Agios Paillier : {sum(res_paillier)}/{len(res_paillier)} exacts")
    print(f"Précision calcul Agios BFV      : {sum(res_bfv)}/{len(res_bfv)} exacts")


if __name__ == "__main__":
    print("\n" + "#" * 70)
    print(" BENCHMARK FINANCIER RÉEL — SCORE MICRO-CRÉDIT & AGIOS BANCAIRES")
    print("#" * 70)

    print("\nInitialisation des clés cryptographiques...")
    p_scheme = PaillierScheme()
    b_scheme = BFVScheme()

    print("Génération des profils clients synthétiques (Mobile Money & Banque)...")
    clients = generer_donnees_clients_financiers(nb_clients=50)

    scenario_1_microcredit_mobile_money(clients, p_scheme, b_scheme)
    scenario_2_agios_intérets_bancaires(clients, p_scheme, b_scheme)

    print("\n" + "#" * 70)
    print(" EXPÉRIMENTATIONS FINANCIÈRES RÉELLES TERMINÉES AVEC SUCCÈS")
    print("#" * 70 + "\n")
