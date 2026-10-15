# 🐳 Procédure de Déploiement Docker sur VM Ubuntu (HE_Proto)

Ce document fournit la procédure pas-à-pas pour déployer et exécuter le projet **HE_Proto** sur une machine virtuelle Ubuntu en utilisant **Docker**.

Cette méthode évite toute installation complexe sur l'hôte (pas besoin d'installer manuellement Python 3.11, CMake, GCC, ou de compiler les extensions C++ Pyfhel/SEAL).

---

## 📋 Sommaire

1. [Prérequis](#1-prérequis)
2. [Installation de Docker & Docker Compose](#2-installation-de-docker--docker-compose)
3. [Lancement du Projet avec Docker Compose](#3-lancement-du-projet-avec-docker-compose)
4. [Vérification du Fonctionnement](#4-vérification-du-fonctionnement)
5. [Accès au Tableau de Bord Web](#5-accès-au-tableau-de-bord-web)
6. [Exécution des Benchmarks dans le Conteneur](#6-exécution-des-benchmarks-dans-le-conteneur)
7. [Commandes d'Exploitation Courantes](#7-commandes-dexploitation-courantes)
8. [Résolution des Problèmes Fréquents](#8-résolution-des-problèmes-fréquents)

---

## 1. Prérequis & Dimensionnement VM (Hetzner Cloud Recommandé)

Pour reproduire fidèlement les résultats expérimentaux du **Chapitre III du mémoire** sans subir de throttling CPU ni de saturation mémoire :

* **Fournisseur Cloud retenu** : **Hetzner Cloud** (ou VM locale Ubuntu 22.04 / 24.04 LTS).
* **Type d'instance recommandé** : **`CPX31`** (4 vCPU AMD EPYC dédiés, 8 Go RAM, 160 Go NVMe, ~14 € / mois ou ~0,02 € / heure).
* **Système d'exploitation** : Ubuntu 24.04 LTS (x86_64).
* **Réseau / Pare-feu (Firewall Hetzner)** :
  * Autoriser le port **22/TCP** (SSH).
  * Autoriser le port **8000/TCP** (API REST Chiffrement Homomorphe).
* Accès administrateur (`sudo`).

---

## 2. Installation de Docker & Docker Compose

Si Docker n'est pas encore installé sur votre VM Ubuntu, exécutez les commandes suivantes dans votre terminal :

```bash
# 1. Mise à jour des paquets et installation de Docker et Docker Compose
sudo apt update
sudo apt install -y docker.io docker-compose-v2 git

# 2. Permettre à votre utilisateur d'exécuter Docker sans sudo
sudo usermod -aG docker $USER

# 3. Appliquer immédiatement les permissions du groupe docker (sans redémarrer la session)
newgrp docker
```

---

## 3. Lancement du Projet avec Docker Compose

Placez-vous dans le répertoire cloné du projet et lancez la construction :

```bash
# Aller dans le répertoire du projet
cd HE_Proto   # (ou le nom exact du dossier où le dépôt est cloné)

# Construire l'image et démarrer le conteneur en arrière-plan
docker compose up --build -d
```

> ⏳ **Note sur le premier démarrage :**  
> La première construction télécharge l'image de base Python 3.11-slim et compile les bibliothèques C++ de chiffrement homomorphe (`Pyfhel` / Microsoft SEAL). Cette étape prend généralement entre **1 et 3 minutes**.  
> Les lancements ultérieurs seront quasi instantanés.

---

## 4. Vérification du Fonctionnement

### A. Consulter l'état du conteneur
```bash
docker compose ps
```
Le conteneur `cloud_he_server` doit avoir le statut **Up**.

### B. Suivre les logs en direct
```bash
docker compose logs -f
```
*(Appuyez sur `Ctrl + C` pour quitter l'affichage des logs)*

### C. Tester l'API avec un appel Health Check
```bash
curl http://localhost:8000/health
```
**Réponse attendue :**
```json
{"status": "ok", "service": "Cloud HE REST Server"}
```

---

## 5. Accès au Tableau de Bord Web

Le serveur écoute sur le port `8000`.

### Option A : Depuis le navigateur de la VM Ubuntu
Ouvrez votre navigateur web dans la VM et accédez à :
👉 **`http://localhost:8000`**

### Option B : Depuis le navigateur de votre machine hôte (Windows / Mac)
1. Dans le terminal de la VM Ubuntu, trouvez son adresse IP locale :
   ```bash
   hostname -I
   # ou
   ip a
   ```
2. Sur votre machine hôte, ouvrez votre navigateur et tapez :
   👉 **`http://<ADRESSE_IP_VM>:8000`**  
   *(Exemple : `http://192.168.1.45:8000` ou `http://192.168.56.101:8000` selon le type de réseau de la VM).*

---

## 6. Exécution des Benchmarks dans le Conteneur

Vous n'avez pas besoin d'installer Python sur votre VM pour exécuter les benchmarks. Vous pouvez exécuter les scripts directement à l'intérieur du conteneur Docker en cours d'exécution via `docker compose exec` :

### 1. Scénarios bancaires réels (Agios trimestriels & Micro-crédit Mobile Money)
```bash
docker compose exec cloud-he-server python benchmarks/scenarios_financiers_reels.py
```

### 2. Banc de test multi-paliers (Échelles Chapitre III : N = 10, 100, 1 000, 10 000)
```bash
# Exécution complète multi-paliers avec entrelacement d'ordre (A/B testing)
docker compose exec cloud-he-server python benchmarks/run_benchmarks.py --tiers 10,100,1000,10000

# Mode validation rapide (N=10, 100)
docker compose exec cloud-he-server python benchmarks/run_benchmarks.py --quick
```

### 3. Exécution depuis votre machine locale vers le Cloud Hetzner (Mesures Réseau Réel)
Depuis votre machine cliente Windows ou Linux (hors du Cloud) :
```bash
# Mesures avec latence réseau transcontinentale et débit réel vers la VM Hetzner
python benchmarks/run_benchmarks_cloud.py --host <IP_PUBLIQUE_HETZNER> --tiers 10,100,1000
```

### 3. Démonstration des limites cryptographiques (Bruit BFV, etc.)
```bash
docker compose exec cloud-he-server python benchmarks/demonstrer_limites.py
```

### 4. Audit et comparatif de sécurité (NIST / Standard HomomorphicEncryption.org)
```bash
docker compose exec cloud-he-server python benchmarks/comparer_securite_parametres.py --quick
```

---

## 7. Commandes d'Exploitation Courantes

| Action | Commande |
| :--- | :--- |
| **Démarrer** le service en arrière-plan | `docker compose up -d` |
| **Arrêter** le service | `docker compose down` |
| **Redémarrer** le service | `docker compose restart` |
| **Reconstruire** après modifications du code | `docker compose up --build -d` |
| **Voir les logs** en direct | `docker compose logs -f` |
| **Ouvrir un shell Bash** dans le conteneur | `docker compose exec cloud-he-server bash` |

### Procédure de mise à jour du code (Git Pull)
```bash
git pull
docker compose up --build -d
```

---

## 8. Résolution des Problèmes Fréquents

### Problème 1 : `permission denied while trying to connect to the Docker daemon socket`
**Cause :** Votre utilisateur Ubuntu n'a pas encore pris en compte le groupe `docker`.  
**Solution :**
```bash
sudo usermod -aG docker $USER
newgrp docker
# Ou exécutez la commande avec sudo : sudo docker compose up -d
```

### Problème 2 : Impossible d'accéder au port 8000 depuis l'hôte Windows
**Causes possibles :**
1. **Firewall Ubuntu (UFW) :**
   ```bash
   sudo ufw allow 8000/tcp
   ```
2. **Type de réseau de la VM (VirtualBox / VMware) :**
   * En mode **NAT**, configurez une redirection de port (*Port Forwarding*) dans les paramètres de la VM : Port hôte `8000` vers Port invité `8000`.
   * En mode **Accès par pont (Bridged Adapter)** ou **Réseau hôte (Host-Only)**, utilisez directement l'IP retournée par `hostname -I`.
