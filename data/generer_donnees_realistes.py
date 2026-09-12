"""
Générateur de Données Bancaires et Financières Réalistes (1000+ Enregistrements)
Projet : HE_Proto — Chiffrement Homomorphe Appliqué à la Banque Cloud et Mobile Money.

Ce module produit 3 jeux de données conformes aux réalités de la zone UEMOA / CEMAC (FCFA) :
1. transactions_bancaires_1000.csv  : Relevé de flux bancaires et Mobile Money (P2P, Dépôts, Salaires, Achats)
2. profils_microcredit_1000.csv     : Données de scoring crédit pour micro-finance / Mobile Money
3. soldes_journaliers_1000.csv      : Relevés journaliers pour calculs d'intérêts et agios prorata temporis
"""

import csv
import os
import random
import datetime

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Graine aléatoire pour la reproductibilité
random.seed(42)

# Référentiel de noms et prénoms réalistes (Zone UEMOA / Afrique de l'Ouest & Centrale)
PRENOMS = [
    "Amadou", "Fatou", "Kouassi", "Awa", "Ibrahim", "Aminata", "Mamadou", "Oumar",
    "Mariam", "Cheikh", "Bakary", "Aïssatou", "Jean-Baptiste", "Nafi", "Seydou",
    "Bintou", "Yao", "Salif", "Koffi", "Khadija", "Adama", "Moussa", "Djeneba",
    "Sékou", "Hawa", "Boubacar", "Clarisse", "Tidiane", "Fanta", "Abdoulaye"
]

NOMS = [
    "Traoré", "Koné", "Diallo", "Coulibaly", "Diop", "Cissé", "Ndiaye", "Ouédraogo",
    "Kouadio", "Touré", "Sow", "Ba", "Sanogo", "Bamba", "Fofana", "Camara",
    "Soro", "Fall", "Koffi", "Barry", "Sylla", "Kane", "Gueye", "Sangaré"
]

VILLES = [
    "Abidjan", "Dakar", "Ouagadougou", "Bamako", "Lomé", "Cotonou", "Niamey",
    "Bouaké", "Saint-Louis", "Bobo-Dioulasso", "Yamoussoukro", "San-Pédro"
]

CANAUX = [
    "MOBILE_MONEY_WAVE", "MOBILE_MONEY_ORANGE", "MOBILE_MONEY_MTN",
    "VIREMENT_UEMOA", "GAB_DISTRIBUTEUR", "TPE_COMMERCE_QR", "AGENCE_GUICHET"
]

TYPES_OPS = [
    ("VIREMENT_SALAIRE", 150000, 1800000, "CREDIT", 0.12),
    ("DEPOT_ESPECES", 10000, 500000, "CREDIT", 0.18),
    ("PAIEMENT_MARCHAND", 2000, 75000, "DEBIT", 0.25),
    ("RETRAIT_GAB", 5000, 200000, "DEBIT", 0.15),
    ("TRANSFERT_P2P", 1000, 100000, "DEBIT", 0.18),
    ("PAIEMENT_FACTURE_EAU_ELEC", 5000, 60000, "DEBIT", 0.08),
    ("FRAIS_TENUE_COMPTE", 1000, 3500, "DEBIT", 0.04),
]


def generer_identite(client_id_num):
    p = random.choice(PRENOMS)
    n = random.choice(NOMS)
    return f"{p} {n}"


def generer_transactions_bancaires(nb_lignes=1000):
    """
    Génère un flux de transactions bancaires et Mobile Money réalistes.
    """
    fichier_csv = os.path.join(DATA_DIR, "transactions_bancaires_1000.csv")
    transactions = []

    # 150 clients actifs
    nb_clients = 150
    clients = {}
    for cid in range(1, nb_clients + 1):
        nom = generer_identite(cid)
        solde_initial = random.randint(50000, 1500000)
        clients[cid] = {
            "nom": nom,
            "solde": solde_initial,
            "ville": random.choice(VILLES)
        }

    date_debut = datetime.datetime(2026, 1, 1, 8, 0, 0)

    for tid in range(1, nb_lignes + 1):
        cid = random.randint(1, nb_clients)
        client = clients[cid]

        # Choix du type d'opération selon les probabilités
        type_op_tuple = random.choices(
            TYPES_OPS,
            weights=[t[4] for t in TYPES_OPS],
            k=1
        )[0]

        type_nom, m_min, m_max, sens, _ = type_op_tuple

        # Distribution de montants réaliste (favorisant les montants ronds et arrondis à 100 ou 500 FCFA)
        montant_brut = random.randint(m_min, m_max)
        if montant_brut > 10000:
            montant = (montant_brut // 500) * 500
        else:
            montant = (montant_brut // 100) * 100
        if montant == 0:
            montant = m_min

        solde_avant = client["solde"]
        if sens == "CREDIT":
            solde_apres = solde_avant + montant
        else:
            # Si le solde est insuffisant, on ajuste un petit découvert ou on réduit le montant
            if solde_avant < montant:
                montant = max(1000, solde_avant // 2)
            solde_apres = solde_avant - montant

        client["solde"] = solde_apres

        # Incrément de date réaliste (entre 5 min et 4 heures)
        date_debut += datetime.timedelta(minutes=random.randint(5, 240))
        date_str = date_debut.strftime("%Y-%m-%d %H:%M:%S")

        transactions.append({
            "Transaction_ID": f"TX-{100000 + tid}",
            "Date_Heure": date_str,
            "Client_ID": f"CLI-{1000 + cid}",
            "Nom_Client": client["nom"],
            "Ville": client["ville"],
            "Type_Operation": type_nom,
            "Sens": sens,
            "Montant_FCFA": montant,
            "Solde_Avant_FCFA": solde_avant,
            "Solde_Apres_FCFA": solde_apres,
            "Canal": random.choice(CANAUX),
            "Statut": "VALIDE"
        })

    with open(fichier_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(transactions[0].keys()))
        writer.writeheader()
        writer.writerows(transactions)

    print(f"[OK] 1. Transactions Bancaires générées : {fichier_csv} ({len(transactions)} lignes)")
    return transactions


def generer_profils_microcredit(nb_lignes=1000):
    """
    Génère 1000 profils d'emprunteurs pour évaluation du score de solvabilité par chiffrement homomorphe.
    Formule : Score = (5 * Volume_Mensuel) + (50 000 * Regularite) - (20 000 * Retards)
    Seuil d'éligibilité : Score >= 2 500 000 FCFA
    """
    fichier_csv = os.path.join(DATA_DIR, "profils_microcredit_1000.csv")
    profils = []

    SECTEURS = [
        "Commerce Général", "Agriculture / Vivrier", "Artisanat", "Transport / Moto-Taxi",
        "Restauration / Maquis", "BTP / Électricité", "Services Numériques", "Salarié PME"
    ]

    for cid in range(1, nb_lignes + 1):
        nom = generer_identite(cid)
        secteur = random.choice(SECTEURS)
        ville = random.choice(VILLES)

        # Profils variés : excellents, moyens, à risque
        categorie = random.choices(["EXCELLENT", "STANDARD", "A_RISQUE"], weights=[0.45, 0.35, 0.20], k=1)[0]

        if categorie == "EXCELLENT":
            vol_mensuel = random.randint(500000, 3500000)
            regularite = random.randint(7, 10)
            retards = random.randint(0, 3)
        elif categorie == "STANDARD":
            vol_mensuel = random.randint(250000, 800000)
            regularite = random.randint(4, 7)
            retards = random.randint(2, 10)
        else: # A_RISQUE
            vol_mensuel = random.randint(50000, 350000)
            regularite = random.randint(1, 4)
            retards = random.randint(8, 30)

        # Arrondi du volume
        vol_mensuel = (vol_mensuel // 1000) * 1000

        # Calcul mathématique exact de référence
        score = (5 * vol_mensuel) + (50000 * regularite) - (20000 * retards)
        decision = "ACCORDÉ" if score >= 2500000 else "REFUSÉ"

        profils.append({
            "Client_ID": f"CLI-{20000 + cid}",
            "Nom_Client": nom,
            "Ville": ville,
            "Secteur_Activite": secteur,
            "Volume_Transactions_FCFA": vol_mensuel,
            "Note_Regularite_10": regularite,
            "Jours_Retard_Moyen": retards,
            "Score_Calcul_Clair": score,
            "Decision_Eligibilite": decision
        })

    with open(fichier_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(profils[0].keys()))
        writer.writeheader()
        writer.writerows(profils)

    nb_accordes = sum(1 for p in profils if p["Decision_Eligibilite"] == "ACCORDÉ")
    print(f"[OK] 2. Profils Micro-Crédit générés : {fichier_csv} ({len(profils)} profils — {nb_accordes} accordés, {len(profils)-nb_accordes} refusés)")
    return profils


def generer_soldes_journaliers_agios(nb_lignes=1000):
    """
    Génère 1000 relevés de soldes bancaires journaliers pour le calcul homomorphe des intérêts / agios.
    Formule : Agios = (Solde_Moyen_30J * 30 jours * Taux_Annuel) / 360 jours
    """
    fichier_csv = os.path.join(DATA_DIR, "soldes_journaliers_agios_1000.csv")
    releves = []

    TYPES_COMPTES = ["COMPTE_COURANT_ENTREPRISE", "COMPTE_PARTICULIER_PREMIUM", "COMPTE_COMMERCANT_PRO", "COMPTE_EPARGNE_DEPOT"]

    for cid in range(1, nb_lignes + 1):
        nom = generer_identite(cid)
        type_cpt = random.choice(TYPES_COMPTES)

        # Soldes moyens typiques en FCFA (entre 200 000 et 15 000 000 FCFA)
        if "ENTREPRISE" in type_cpt:
            solde = random.randint(2000000, 25000000)
            taux = 6.50
        elif "PRO" in type_cpt:
            solde = random.randint(500000, 8000000)
            taux = 5.50
        else:
            solde = random.randint(150000, 3500000)
            taux = 5.00

        solde = (solde // 1000) * 1000
        nb_jours = 30
        
        # Formule bancaire prorata temporis standard UEMOA (base 360)
        agios_theoriques = round((solde * nb_jours * (taux / 100.0)) / 360.0, 2)

        releves.append({
            "Compte_ID": f"CPT-{50000 + cid}",
            "Titulaire": nom,
            "Type_Compte": type_cpt,
            "Solde_Moyen_30J_FCFA": solde,
            "Duree_Jours": nb_jours,
            "Taux_Annuel_Pct": taux,
            "Agios_Calcules_FCFA": agios_theoriques
        })

    with open(fichier_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(releves[0].keys()))
        writer.writeheader()
        writer.writerows(releves)

    print(f"[OK] 3. Soldes & Agios générés : {fichier_csv} ({len(releves)} comptes)")
    return releves


if __name__ == "__main__":
    print("=" * 70)
    print("GÉNÉRATION DES JEUX DE DONNÉES BANCAIRES RÉALISTES POUR HE_PROTO")
    print("=" * 70)
    generer_transactions_bancaires(1000)
    generer_profils_microcredit(1000)
    generer_soldes_journaliers_agios(1000)
    print("=" * 70)
    print("Tous les fichiers CSV (1000 lignes chacun) ont été créés avec succès dans 'data/' !")
