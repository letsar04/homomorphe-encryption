"""
Génère un jeu de données synthétiques de transactions bancaires.
Correspond à la Phase 3 du protocole de recherche / points 1 à 4 de la
Partie II de la note technique (volume, format, plage, structure).
"""

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
                          seed=SEED):
    """
    Génère une liste de transactions synthétiques.
    Montants en entiers (FCFA) pour éviter les problèmes de précision
    en chiffrement homomorphe (cf. note technique, point 2 Partie II).

    Retourne une liste de dicts :
    {id_transaction, id_compte, montant, solde}
    """
    random.seed(seed)

    transactions = []
    soldes_comptes = {
        compte_id: random.randint(montant_min, montant_max)
        for compte_id in range(1, nb_comptes + 1)
    }

    for i in range(1, nb_transactions + 1):
        compte_id = random.randint(1, nb_comptes)
        montant = random.randint(montant_min, montant_max)
        soldes_comptes[compte_id] = montant  # simplification pour le prototype

        transactions.append({
            "id_transaction": i,
            "id_compte": compte_id,
            "montant": montant,
            "solde": soldes_comptes[compte_id],
        })

    return transactions


def sauvegarder_csv(transactions, chemin_sortie):
    """Sauvegarde les transactions dans un fichier CSV."""
    os.makedirs(os.path.dirname(chemin_sortie), exist_ok=True)

    with open(chemin_sortie, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["id_transaction", "id_compte", "montant", "solde"]
        )
        writer.writeheader()
        writer.writerows(transactions)

    print(f"[OK] {len(transactions)} transactions générées -> {chemin_sortie}")


if __name__ == "__main__":
    transactions = generer_transactions()
    chemin_sortie = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        DATA_DIR,
        "transactions_synthetiques.csv",
    )
    sauvegarder_csv(transactions, chemin_sortie)

    # Vérification rapide de la plage générée
    montants = [t["montant"] for t in transactions]
    print(f"Volume         : {len(transactions)} transactions")
    print(f"Plage montants : {min(montants):,} - {max(montants):,} FCFA")
    print(f"Somme totale   : {sum(montants):,} FCFA")