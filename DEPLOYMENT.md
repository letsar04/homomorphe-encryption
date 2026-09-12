# Guide de Configuration et Déploiement : Projet HE_Proto (De A à Z)

Ce document constitue le **guide officiel d'installation, de configuration et de déploiement** du prototype de Chiffrement Homomorphe Appliqué à la Banque Cloud et Mobile Money (**HE_Proto**).

---

## 📋 Table des Matières

1. [Partie I : Installation & Exécution en Local (PC de Développement)](#partie-i--installation--exécution-en-local)
   * 1.1 Prérequis Système
   * 1.2 Structure du Dépôt
   * 1.3 Création de l'Environnement Virtuel Python
   * 1.4 Installation des Dépendances
   * 1.5 Démarrage du Serveur & Dashboard Web Local
   * 1.6 Exécution des Benchmarks & Démos de Limites
2. [Partie II : Déploiement en Situation Réelle sur AWS Cloud (Instance EC2)](#partie-ii--déploiement-sur-aws-cloud-ec2)
   * 2.1 Création de l'Instance AWS EC2
   * 2.2 Configuration du Groupe de Sécurité AWS (Security Group - Port 8000)
   * 2.3 Connexion à l'Instance EC2
   * 2.4 Installation des Outils Système & Docker
   * 2.5 Déploiement avec Docker Compose
   * 2.6 Test de Santé & Accès Public
   * 2.7 Procédure de Mise à Jour Continue (CI/CD Manuelle)

---

# Partie I : Installation & Exécution en Local

### 1.1 Prérequis Système
* **Système d'exploitation** : Windows 10/11, macOS, ou Linux Ubuntu.
* **Python** : Python 3.11 recommandé (Python 3.14 déconseillé hors Docker en raison des compilations C++ Pyfhel).
* **Compilateurs C++** : CMake (>= 3.15) et Build Tools (GCC/Clang sous Linux/Mac, MSVC C++ Build Tools sous Windows).
* **Git** : Installé sur votre machine.

---

### 1.2 Structure du Dépôt

```text
HE_Proto/
├── config.py                       # Configuration centrale (clés, plages FCFA, ports)
├── Dockerfile                      # Image Docker serveur basée sur Python 3.11-slim
├── docker-compose.yml              # Orchestration des conteneurs Cloud
├── requirements.txt                # Dépendances Python (phe, Pyfhel, numpy, pandas)
├── DEPLOYMENT.md                  # Ce guide de déploiement
├── cloud_sim/                      # Moteur Serveur & Client Cloud REST API
│   ├── cloud_api_server.py         # Serveur HTTP REST & Hébergeur Web UI
│   ├── cloud_api_client.py         # Client HTTP pour l'envoi des payloads
│   └── local_server.py             # Simulatuer en mémoire
├── schemes/                        # Wrappers Cryptographiques Homomorphes
│   ├── paillier_ops.py             # Schéma Paillier (PHE - 2048 bits)
│   └── bfv_ops.py                  # Schéma BFV (FHE - Pyfhel / SEAL)
├── benchmarks/                     # Scripts de Mesures & Démos
│   ├── run_benchmarks.py           # Benchmark de performance principal
│   ├── run_benchmarks_cloud.py     # Benchmark avec transfert réseau HTTP
│   ├── demonstrer_limites.py       # Démonstration des 4 limites (Paillier & BFV)
│   ├── scenarios_financiers_reels.py# Scénarios Micro-Crédit Mobile Money & Agios
│   └── comparer_securite_parametres.py # Comparatif de sécurité & alignement 128 bits (NIST/RLWE)
├── web_ui/                         # Interface Graphique Web Corporate
│   ├── index.html                  # Structure HTML5 Dashboard
│   ├── style.css                   # Thème Corporate Clair (Banking)
│   └── app.js                      # Logique d'interaction et d'encryption
└── data/                           # Données synthétiques bancaires (FCFA)
```

---

### 1.3 Création de l'Environnement Virtuel Python

Ouvrez votre terminal dans le dossier du projet :

```bash
cd HE_Proto

# 1. Créer l'environnement virtuel nommé 'venv'
python -m venv venv

# 2. Activer l'environnement virtuel :
# Sous Windows (PowerShell) :
.\venv\Scripts\Activate.ps1

# Sous Windows (CMD) :
venv\Scripts\activate.bat

# Sous Linux / macOS :
source venv/bin/activate
```

---

### 1.4 Installation des Dépendances

Une fois le `venv` activé :

```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

---

### 1.5 Démarrage du Serveur & Dashboard Web Local

Lancez le serveur REST API et le serveur web d'un seul coup :

```bash
python cloud_sim/cloud_api_server.py
```

Accédez ensuite au Dashboard Web Corporate depuis votre navigateur :
👉 **`http://localhost:8000`** ou **`http://127.0.0.1:8000`**

---

### 1.6 Exécution des Benchmarks & Démos de Limites

Dans un second terminal avec l'environnement virtuel activé :

* **Démonstration pratique des limites (Paillier & BFV)** :
  ```bash
  python benchmarks/demonstrer_limites.py
  ```

* **Scénarios Financiers Réels (Micro-Crédit Mobile Money & Agios)** :
  ```bash
  python benchmarks/scenarios_financiers_reels.py
  ```

* **Comparatif selon les Paramètres de Sécurité & Alignement 128 bits (NIST/RLWE)** :
  ```bash
  python benchmarks/comparer_securite_parametres.py
  # Ou pour un test rapide :
  python benchmarks/comparer_securite_parametres.py --quick
  ```

* **Benchmark complet de performance** :
  ```bash
  python benchmarks/run_benchmarks.py
  ```

---

# Partie II : Déploiement sur AWS Cloud EC2

Cette partie décrit comment déployer le projet en **environnement de production réel** sur Amazon Web Services (AWS) pour qu'il soit accessible publiquement par des utilisateurs ou des jurys.

---

### 2.1 Création de l'Instance AWS EC2

1. Connectez-vous à la **Console AWS** -> Service **EC2**.
2. Cliquez sur **Lancer une instance** (*Launch Instance*).
3. **Nom de l'instance** : `proto-homomorphe`.
4. **Image Système (AMI)** : `Ubuntu Server 24.04 LTS` ou `Ubuntu 22.04 LTS` (64 bits x86).
5. **Type d'instance** :
   * Démonstration / Test : `t2.micro` (Éligible Offre Gratuite AWS).
   * Recommandé pour Benchmarks FHE (Pyfhel) : `t3.medium` ou `c6i.large` (2 vCPU, 4 Go RAM).
6. **Paire de clés** : Créez ou sélectionnez votre clé SSH (`.pem`).

---

### 2.2 Configuration du Groupe de Sécurité AWS (Security Group)

Dans la section **Paramètres réseau** (*Network Settings*) lors de la création de l'instance (ou via l'onglet Sécurité d'une instance existante) :

Ajoutez 2 règles d'entrée (*Inbound Rules*) :

| Type | Protocole | Plage de Ports | Source | Description |
| :--- | :--- | :---: | :--- | :--- |
| **SSH** | TCP | `22` | Mon IP ou `0.0.0.0/0` | Accès administration à distance |
| **Custom TCP** | TCP | `8000` | `0.0.0.0/0` (Anywhere IPv4) | Accès public au Dashboard Web & REST API |

---

### 2.3 Connexion à l'Instance EC2

Connectez-vous via SSH ou **EC2 Instance Connect** (navigateur AWS) :

```bash
ssh -i "votre_cle.pem" ubuntu@<IP_PUBLIQUE_DE_VOTRE_EC2>
```

---

### 2.4 Installation des Outils Système & Docker

Exécutez ces commandes sur votre serveur Ubuntu EC2 pour préparer l'environnement Docker :

```bash
# 1. Mise à jour des paquets système
sudo apt update && sudo apt upgrade -y

# 2. Installation de Git, Docker et Docker Compose
sudo apt install -y git docker.io docker-compose-v2

# 3. Ajouter l'utilisateur ubuntu au groupe docker (évite d'avoir à faire sudo à chaque fois)
sudo usermod -aG docker ubuntu
```

---

### 2.5 Déploiement avec Docker Compose

Clonez votre projet Git sur le serveur EC2 et lancez le conteneur Docker :

```bash
# 1. Cloner le dépôt Git
git clone <URL_DE_VOTRE_DEPOT_GIT>
cd HE_Proto  # (ou homomorphe-encryption selon le nom de votre dépôt)

# 2. Compiler et lancer le conteneur Docker en arrière-plan
sudo docker compose up --build -d
```

---

### 2.6 Test de Santé & Accès Public

1. **Vérification en ligne de commande sur le serveur** :
   ```bash
   curl http://localhost:8000/health
   ```
   *Réponse attendue :* `{"status": "ok", "service": "Cloud HE REST Server"}`

2. **Accès Public depuis le monde entier** :
   Partagez l'URL suivante à vos testeurs :
   👉 **`http://<IP_PUBLIQUE_DE_VOTRE_EC2>:8000`**

---

### 2.7 Procédure de Mise à Jour Continue (CI/CD Manuelle)

Lorsque vous apportez des modifications sur votre code local et les poussez sur Git :

Sur le serveur EC2, exécutez simplement :

```bash
cd ~/HE_Proto
git pull
sudo docker compose up --build -d
```

Docker détectera les fichiers modifiés, mettra à jour le conteneur et redémarrera le serveur en quelques secondes sans interruption de service !
