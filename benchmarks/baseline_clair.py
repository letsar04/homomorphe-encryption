"""
Baseline en clair (non chiffré) — indispensable pour quantifier le
surcoût du chiffrement homomorphe et valider l'hypothèse H2
(cf. note technique, point 13 de la Partie II).
"""

import time


def somme_claire(valeurs):
    return sum(valeurs)


def moyenne_claire(valeurs):
    return sum(valeurs) / len(valeurs)


def mesurer_baseline(valeurs):
    """Mesure le temps de calcul en clair (somme et moyenne)."""
    t0 = time.perf_counter()
    s = somme_claire(valeurs)
    t_somme = time.perf_counter() - t0

    t0 = time.perf_counter()
    m = moyenne_claire(valeurs)
    t_moyenne = time.perf_counter() - t0

    return {
        "somme": s,
        "moyenne": m,
        "temps_somme_sec": t_somme,
        "temps_moyenne_sec": t_moyenne,
    }


if __name__ == "__main__":
    valeurs = [100, 250, 75, 1000, 300]
    resultat = mesurer_baseline(valeurs)
    print(resultat)