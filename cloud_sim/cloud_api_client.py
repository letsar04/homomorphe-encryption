"""
Client HTTP Cloud — envoie des requêtes REST au serveur Cloud distant.
Mesure la latence réseau HTTP (aller-retour) et le volume d'octets échangés.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from config import CLOUD_HOST, CLOUD_PORT
from schemes.paillier_ops import PaillierScheme
from schemes.bfv_ops import BFVScheme


class CloudAPIClient:
    def __init__(self, host=CLOUD_HOST, port=CLOUD_PORT):
        self.base_url = f"http://{host}:{port}"

    def verifier_connexion(self):
        """Vérifie l'accessibilité du serveur Cloud."""
        url = f"{self.base_url}/health"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    return True
        except Exception:
            return False
        return False

    def _post_json(self, endpoint, data_dict):
        """Envoie une requête POST JSON et mesure le volume de données."""
        url = f"{self.base_url}{endpoint}"
        body_bytes = json.dumps(data_dict).encode("utf-8")
        octets_envoyes = len(body_bytes)

        req = urllib.request.Request(
            url,
            data=body_bytes,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        t0 = time.perf_counter()
        with urllib.request.urlopen(req) as response:
            resp_bytes = response.read()
            t_reseau_total = time.perf_counter() - t0

        octets_recus = len(resp_bytes)
        resp_json = json.loads(resp_bytes.decode("utf-8"))

        return resp_json, t_reseau_total, octets_envoyes, octets_recus

    def sommer_paillier(self, paillier_scheme, chiffres):
        """
        Sérialise et transmet des chiffrés Paillier au serveur Cloud,
        reçoit le résultat chiffré.
        """
        payload = {
            "public_key": paillier_scheme.serialiser_cle_publique(),
            "ciphertexts": [PaillierScheme.serialiser_chiffre(c) for c in chiffres]
        }

        resp, t_total, octets_env, octets_rec = self._post_json("/api/paillier/somme", payload)
        
        somme_chiffree = PaillierScheme.deserialiser_chiffre(
            resp["result"], paillier_scheme.public_key
        )
        t_calcul_cloud = resp["temps_calcul_cloud_sec"]
        t_latence_reseau = max(0.0, t_total - t_calcul_cloud)

        return {
            "somme_chiffree": somme_chiffree,
            "temps_reseau_total_sec": t_total,
            "temps_calcul_cloud_sec": t_calcul_cloud,
            "temps_latence_reseau_sec": t_latence_reseau,
            "octets_envoyes": octets_env,
            "octets_recus": octets_rec
        }

    def sommer_bfv(self, bfv_scheme, chiffres):
        """
        Sérialise et transmet le contexte BFV et les chiffrés au serveur Cloud,
        reçoit le résultat chiffré.
        """
        payload = {
            "context": bfv_scheme.serialiser_contexte(),
            "ciphertexts": [BFVScheme.serialiser_chiffre(c) for c in chiffres]
        }

        resp, t_total, octets_env, octets_rec = self._post_json("/api/bfv/somme", payload)

        somme_chiffree = bfv_scheme.deserialiser_chiffre(resp["result"])
        t_calcul_cloud = resp["temps_calcul_cloud_sec"]
        t_latence_reseau = max(0.0, t_total - t_calcul_cloud)

        return {
            "somme_chiffree": somme_chiffree,
            "temps_reseau_total_sec": t_total,
            "temps_calcul_cloud_sec": t_calcul_cloud,
            "temps_latence_reseau_sec": t_latence_reseau,
            "octets_envoyes": octets_env,
            "octets_recus": octets_rec
        }


if __name__ == "__main__":
    client = CloudAPIClient()
    if not client.verifier_connexion():
        print("[ERREUR] Le serveur Cloud REST n'est pas démarré. Lance d'abord python cloud_sim/cloud_api_server.py")
        sys.exit(1)
    
    print("[OK] Serveur Cloud REST accessible.")
    paillier_scheme = PaillierScheme()
    valeurs = [100, 200, 300]
    chiffres = paillier_scheme.chiffrer(valeurs)
    res = client.sommer_paillier(paillier_scheme, chiffres)
    somme_dechiffree = paillier_scheme.dechiffrer(res["somme_chiffree"])
    print(f"[OK] Test client Paillier Cloud API : {somme_dechiffree} (attendu {sum(valeurs)})")
