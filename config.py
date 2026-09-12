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
NB_TRANSACTIONS = 5000          # volume du jeu de données
MONTANT_MIN = 0                 # FCFA, entiers pour éviter les problèmes
MONTANT_MAX = 10_000_000        # FCFA  de précision en HE (point 2)
NB_COMPTES = 200                # comptes/clients simulés (point 4)

# --- Paillier (point 5, Partie II) ---
PAILLIER_KEY_SIZE = 2048             # bits, standard historique de transition (112 bits de sécurité)
PAILLIER_KEY_SIZE_128BIT = 3072      # bits, standard recommandé NIST (128 bits de sécurité classique)

# --- BFV (point 6, Partie II) ---
BFV_POLY_MODULUS_DEGREE = 8192
BFV_SECURITY_LEVEL = 128             # bits, niveau de sécurité Homomorphic Encryption Standard (RLWE)

# plain_modulus calibré selon l'exemple de la note technique :
# t doit être > somme maximale théorique (NB_TRANSACTIONS * MONTANT_MAX).
# Pyfhel génère un nombre premier valide respectant t ≡ 1 mod 2n à partir
# du nombre de bits demandé — on calcule ce nombre de bits directement
# depuis la plage de valeurs retenue, avec une marge de sécurité de 2 bits.
_SOMME_MAX_THEORIQUE = NB_TRANSACTIONS * MONTANT_MAX
BFV_PLAIN_MODULUS_BITS = math.ceil(math.log2(_SOMME_MAX_THEORIQUE)) + 2

# --- Benchmarks (point 12, Partie II) ---
NB_REPETITIONS = 30             # répétitions par mesure pour lisser le bruit

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