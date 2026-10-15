"""
Génère un jeu de données synthétiques de transactions bancaires.
Correspond à la méthodologie du Chapitre III du mémoire (volume N jusqu'à 10 000,
opérations signées crédits/débits, multi-comptes, montants en FCFA).
"""

import argparse
import csv
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SEED, NB_TRANSACTIONS, MONTANT_MIN, MONTANT_MAX, NB_COMPTES, DATA_DIR


def generer_transactions(nb_transactions=NB_TRANSACTIONS,
                          montant_min=MONTANT_MIN,
                          montant_max=MONTANT_MAX,
                          nb_comptes=NB_COMPTES,
                          ratio_credit=0.55,
                          seed=SEED):
    """
    Génère une liste de transactions bancaires synthétiques conformes au Chapitre III.
    
    Chaque transaction comporte :
    - id_transaction : identifiant séquentiel unique
    - id_compte : identifiant du compte bancaire (1 à nb_comptes)
    - type_operation : 'CREDIT' (+ flux entrant) ou 'DEBIT' (- flux sortant)
    - montant : entier signé en FCFA (+montant si CREDIT, -montant si DEBIT)
    - montant_brut : montant positif brut
    - solde : solde résultant du compte
    """
    random.seed(seed)

    transactions = []
    # Solde initial réaliste pour chaque compte (ex: entre 500 000 et 50 000 000 FCFA)
    soldes_comptes = {
        compte_id: random.randint(500_000, 50_000_000)
        for compte_id in range(1, nb_comptes + 1)
    }

    for i in range(1, nb_transactions + 1):
        compte_id = random.randint(1, nb_comptes)
        montant_brut = random.randint(montant_min, montant_max)
        
        # Détermination du type d'opération (Crédit vs Débit)
        is_credit = (random.random() < ratio_credit)
        type_op = "CREDIT" if is_credit else "DEBIT"
        montant_signe = montant_brut if is_credit else -montant_brut
        
        # Mise à jour du solde du compte
        soldes_comptes[compte_id] += montant_signe

        transactions.append({
            "id_transaction": i,
            "id_compte": compte_id,
            "type_operation": type_op,
            "montant": montant_signe,          # Valeur signée exploitée par les opérateurs homomorphes
            "montant_brut": montant_brut,      # Valeur absolue indicative
            "solde": soldes_comptes[compte_id] # Solde après opération
        })

    return transactions


def sauvegarder_csv(transactions, chemin_sortie):
    """Sauvegarde les transactions dans un fichier CSV."""
    os.makedirs(os.path.dirname(chemin_sortie), exist_ok=True)

    champs = ["id_transaction", "id_compte", "type_operation", "montant", "montant_brut", "solde"]
    with open(chemin_sortie, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=champs)
        writer.writeheader()
        writer.writerows(transactions)

    print(f"[OK] {len(transactions)} transactions générées -> {chemin_sortie}")


def main():
    parser = argparse.ArgumentParser(description="Générateur de transactions bancaires synthétiques pour HE_Proto")
    parser.add_argument("--nb_transactions", type=int, default=NB_TRANSACTIONS, help="Nombre de transactions (défaut: 10000)")
    parser.add_argument("--seed", type=int, default=SEED, help="Graine aléatoire pour reproductibilité")
    parser.add_argument("--sortie", type=str, default=None, help="Chemin du fichier CSV de sortie")
    args = parser.parse_args()

    chemin_sortie = args.sortie or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        DATA_DIR,
        "transactions_synthetiques.csv",
    )

    transactions = generer_transactions(nb_transactions=args.nb_transactions, seed=args.seed)
    sauvegarder_csv(transactions, chemin_sortie)

    # Statistiques descriptives
    montants = [t["montant"] for t in transactions]
    credits = [m for m in montants if m > 0]
    debits = [abs(m) for m in montants if m < 0]

    print("\n--- Synthèse du jeu de données (Chapitre III) ---")
    print(f"Volume total      : {len(transactions):,} transactions")
    print(f"Crédits           : {len(credits):,} opérations (total: {sum(credits):,} FCFA)")
    print(f"Débits            : {len(debits):,} opérations (total: {sum(debits):,} FCFA)")
    print(f"Solde net agrégé  : {sum(montants):,} FCFA")
    print(f"Plage des flux    : {min(montants):,} FCFA à {max(montants):,} FCFA\n")


if __name__ == "__main__":
    main()