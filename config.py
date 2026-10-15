"""
Configuration centrale du prototype.
Toutes les valeurs ici doivent rester cohérentes entre data/, schemes/,
benchmarks/ — c'est le seul endroit où on les modifie (cf. Partie II
de la note technique).
"""

import math

# --- Reproductibilité (point 15, Partie II) ---
SEED = 42

# --- Données synthétiques (points 1, 2, 3, 4 — Partie II) ---
NB_TRANSACTIONS = 10_000        # volume complet du jeu de données (échelles 10, 100, 1000, 10000)
MONTANT_MIN = 1_000             # FCFA, montant unitaire minimum
MONTANT_MAX = 10_000_000        # FCFA, montant unitaire maximum
NB_COMPTES = 200                # comptes/clients bancaires simulés

# --- Échelles de benchmark (Chapitre III du mémoire) ---
TIERS_BENCHMARK = [10, 100, 1_000, 10_000]

# --- Paillier (point 5, Partie II) ---
PAILLIER_KEY_SIZE = 2048             # bits, standard historique de transition (112 bits de sécurité)
PAILLIER_KEY_SIZE_128BIT = 3072      # bits, standard recommandé NIST (128 bits de sécurité classique)

# --- BFV (point 6, Partie II) ---
BFV_POLY_MODULUS_DEGREE = 8192
BFV_SECURITY_LEVEL = 128             # bits, niveau de sécurité Homomorphic Encryption Standard (RLWE)
BFV_SLOTS = BFV_POLY_MODULUS_DEGREE  # 8192 créneaux (slots) pour le batching SIMD

# plain_modulus calibré pour supporter les transactions signées (débits/crédits)
# sur l'échelle maximale N = 10 000 avec montants jusqu'à 10 000 000 FCFA.
# Plage théorique [-S_max, +S_max] => t doit être > 2 * S_max.
# On applique une marge de sécurité de 3 bits pour garantir l'absence de wrap-around modulaire.
_SOMME_MAX_THEORIQUE = NB_TRANSACTIONS * MONTANT_MAX
_PLAGE_THEORIQUE = 2 * _SOMME_MAX_THEORIQUE
BFV_PLAIN_MODULUS_BITS = max(math.ceil(math.log2(_PLAGE_THEORIQUE)) + 3, 41)

# --- Benchmarks (point 12, Partie II) ---
NB_REPETITIONS = 30             # répétitions par mesure pour lisser le bruit
NB_REPETITIONS_RAPIDE = 5       # mode rapide pour validation fonctionnelle

# --- Chemins ---
DATA_DIR = "data"
RESULTS_DIR = "results"

# --- Interconnexion Cloud REST API ---
import os
CLOUD_HOST = os.environ.get("CLOUD_HOST", "127.0.0.1")
CLOUD_PORT = int(os.environ.get("CLOUD_PORT", 8000))


if __name__ == "__main__":
    print(f"Somme max théorique      : {_SOMME_MAX_THEORIQUE:,} FCFA")
    print(f"BFV plain_modulus (bits) : {BFV_PLAIN_MODULUS_BITS}")