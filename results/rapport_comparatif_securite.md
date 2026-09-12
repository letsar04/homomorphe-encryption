# Rapport d'Analyse des Performances Cryptographiques selon les Paramètres de Sécurité

## 1. Introduction et Problématique de l'Alignement

Dans le cadre de l'évaluation comparative des schémas homomorphes pour les architectures bancaires Cloud (BCEAO / UEMOA), la comparaison brute entre schémas peut introduire des biais méthodologiques majeurs si les niveaux de sécurité théorique ne sont pas strictement alignés.

- **Le piège classique** : Comparer une clé Paillier de 2048 bits (offrant environ 112 bits de sécurité classique) avec un schéma BFV standard (offrant 128 bits de sécurité post-quantique).
- **La solution adoptée** : Aligner le protocole de test sur le standard minimal de **128 bits de sécurité** recommandé par le NIST et la *Homomorphic Encryption Standard* (clé Paillier de 3072 bits vs BFV avec $n=8192, \text{sec}=128$).

## 2. Synthèse Complète des Mesures Multi-Paramètres

| Schéma | Configuration | Sécurité Cible | Post-Quantique | KeyGen (ms) | Chiffrement unitaire (ms) | Somme Homomorphe (ms) | Déchiffrement (ms) | Taille Ciphertext (octets) | Expansion |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Paillier (PHE) | `N = 1024 bits` | 80 bits (Legacy) | Non (Vulnérable Shor) | 506.9 | 23.36 | 0.516 | 9.42 | 649 | 81.1x |
| Paillier (PHE) | `N = 2048 bits` | 112 bits (Standard) | Non (Vulnérable Shor) | 3033.1 | 143.44 | 1.293 | 43.50 | 1,266 | 158.2x |
| Paillier (PHE) | `N = 3072 bits` | 128 bits (Recommandé NIST) | Non (Vulnérable Shor) | 11003.0 | 453.11 | 2.624 | 122.23 | 1,882 | 235.2x |
| Paillier (PHE) | `N = 4096 bits` | 140 bits (Haute Sécurité) | Non (Vulnérable Shor) | 4026.4 | 978.26 | 4.822 | 334.30 | 2,499 | 312.4x |
| BFV (Pyfhel / SEAL) | `n = 4096, sec = 128b` | 128 bits (Standard RLWE 128) | Oui (RLWE / Réseaux) | 86.9 | 3.71 | 12.515 | 2.57 | 174,916 | 21864.5x |
| BFV (Pyfhel / SEAL) | `n = 8192, sec = 128b` | 128 bits (Standard RLWE 128) | Oui (RLWE / Réseaux) | 433.9 | 10.57 | 3.502 | 2.78 | 699,204 | 87400.5x |
| BFV (Pyfhel / SEAL) | `n = 16384, sec = 128b` | 128 bits (Standard RLWE 128) | Oui (RLWE / Réseaux) | 2807.8 | 37.13 | 19.306 | 13.36 | 2,796,356 | 349544.5x |
| BFV (Pyfhel / SEAL) | `n = 16384, sec = 256b` | 256 bits (Très Haute Sécurité) | Oui (RLWE / Réseaux) | 940.5 | 22.89 | 7.482 | 6.72 | 1,398,252 | 174781.5x |

## 3. Analyse des Tendances et Compromis Sécurité / Performance

### A. Impact sur Paillier (PHE)
- Le coût de génération des clés croît de façon cubique $\mathcal{O}(k^3)$ avec la taille de la clé $k$.
- Le passage de 2048 bits (112b) à 3072 bits (128b) augmente le temps de chiffrement d'environ un facteur $3\times$, et la taille des ciphertexts de 50%.
- L'addition homomorphe reste extrêmement rapide (simple multiplication modulaire $c_1 \cdot c_2 \pmod{N^2}$).

### B. Impact sur BFV (FHE)
- Le niveau de sécurité (`sec=128, 192, 256`) et le degré polynomial ($n=4096, 8192, 16384$) déterminent la capacité de multiplication et la résistance aux attaques LWE.
- BFV offre des temps de chiffrement et déchiffrement significativement plus rapides que Paillier grâce aux opérations polynomiales optimisées (NTT / SIMD).
- En contrepartie, la taille unitaire d'un ciphertext BFV non packagé est nettement plus volumineuse que Paillier, justifiant l'usage du batching SIMD en production bancaire.

## 4. Recommandations Décisionnelles pour le Secteur Bancaire

1. **Pour les calculs financiers purement additifs (Agrégation de soldes, calcul d'agios, scoring linéaire)** : Paillier 3072 bits offre la meilleure efficacité réseau et mémoire avec un overhead minimal sur les serveurs Cloud.
2. **Pour les architectures pérennes et post-quantiques ou calculs polynomiaux** : BFV ($n=8192, \text{sec}=128$) est le choix d'excellence, éliminant tout risque lié aux futurs calculateurs quantiques.
