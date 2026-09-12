# Tableau Récapitulatif de l'Environnement de Test (Base Commune - Chapitre 3)

Ce tableau formalise l'alignement rigoureux des paramètres pour éliminer les biais d'évaluation entre chiffrement homomorphe partiel (Paillier) et complet (BFV).

| Paramètre de test | Configuration pour Paillier | Configuration pour BFV | Objectif de l'alignement |
| :--- | :--- | :--- | :--- |
| **Niveau de sécurité cible** | Clé de **3072 bits** (NIST SP 800-57) | Paramètres RLWE **128 bits** ($n=8192, \text{sec}=128$) | Équivalence face à la cryptanalyse (Standard 128-bit) |
| **Résistance Post-Quantique** | Non (Vulnérable à l'algorithme de Shor) | **Oui** (Cryptographie à base de réseaux euclidiens) | Anticipation des menaces quantiques à long terme |
| **Type de données** | Entiers codés (FCFA) | Entiers codés (FCFA) | Identité stricte des entrées financières |
| **Précision numérique** | Exacte (Arithmétique entière modulaire) | Exacte ($t > \text{Somme}_{\max}$, pas d'approximation) | Exactitude arithmétique 100% garantie |
| **Matériel / CPU** | Même machine virtuelle Cloud / Conteneur | Même machine virtuelle Cloud / Conteneur | Éliminer les biais matériels et d'architecture |

## Métriques Obtenues sur la Base Commune (128 bits de sécurité)

| Métrique | Paillier (3072 bits) | BFV ($n=8192, \text{sec}=128$) | Ratio / Avantage |
| :--- | :--- | :--- | :--- |
| **Temps KeyGen** | 11002.99 ms | 433.87 ms | BFV 25.4x plus rapide |
| **Chiffrement (1 tx)** | 453.11 ms | 10.57 ms | BFV 42.8x plus rapide |
| **Addition Homomorphe** | 2.624 ms | 3.502 ms | Paillier 1.3x plus rapide |
| **Déchiffrement** | 122.23 ms | 2.78 ms | BFV 44.0x plus rapide |
| **Taille Ciphertext** | 1,882 octets | 699,204 octets | Paillier 371.5x plus compact |
| **Facteur d'Expansion** | 235.2x | 87400.5x | Paillier moins gourmand en bande passante |
