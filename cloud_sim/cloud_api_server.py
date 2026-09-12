"""
Serveur Cloud REST API (Option B — cf. note technique section 3.3).

Ce serveur simule un véritable fournisseur Cloud distant écoutant sur le réseau HTTP.
Il ne possède et ne génère JAMAIS de clé privée.
Il reçoit les chiffrés et la clé publique/contexte depuis le réseau client,
effectue les opérations homomorphes et renvoie le chiffré résultat.
"""

import json
import os
import sys
import time
import base64
import threading
import tracemalloc
import psutil
from http.server import HTTPServer, BaseHTTPRequestHandler

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from config import CLOUD_HOST, CLOUD_PORT
from schemes.paillier_ops import PaillierScheme
from schemes.bfv_ops import BFVScheme
from Pyfhel import Pyfhel, PyCtxt
from phe import paillier

# Import du module de comparaison de sécurité
from benchmarks.comparer_securite_parametres import (
    evaluer_paillier, evaluer_bfv, charger_ou_generer_donnees
)
from config import BFV_PLAIN_MODULUS_BITS

CURRENT_PROCESS = psutil.Process(os.getpid())
# Init cpu percent measurement
try:
    psutil.cpu_percent(interval=None)
except Exception:
    pass


def capturer_metriques_systeme():
    """Capture l'état instantané des ressources Cloud (CPU, RAM, Processus)."""
    try:
        mem_info = CURRENT_PROCESS.memory_info()
        vm = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=None)

        return {
            "process_rss_mb": round(mem_info.rss / (1024 * 1024), 2),
            "process_vms_mb": round(mem_info.vms / (1024 * 1024), 2),
            "system_cpu_percent": cpu_percent,
            "system_ram_used_percent": vm.percent,
            "system_ram_total_mb": round(vm.total / (1024 * 1024), 1),
            "system_ram_used_mb": round(vm.used / (1024 * 1024), 1),
            "system_ram_available_mb": round(vm.available / (1024 * 1024), 1),
            "cpu_count": psutil.cpu_count(logical=True),
            "status": "online"
        }
    except Exception as e:
        return {"error": str(e), "status": "error"}


class CloudHEHTTPRequestHandler(BaseHTTPRequestHandler):
    """Handler HTTP REST API pour les calculs homomorphes Cloud."""

    def log_message(self, format, *args):
        # Désactiver le journal de requêtes verbeux dans la console
        return

    def _send_json_response(self, data, status_code=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def servir_fichier_statique(self, path_relatif, content_type):
        path_abs = os.path.join(ROOT_DIR, path_relatif)
        if os.path.exists(path_abs):
            with open(path_abs, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self._send_json_response({"error": f"Fichier {path_relatif} introuvable"}, status_code=404)

    def do_GET(self):
        if self.path == "/health":
            self._send_json_response({"status": "ok", "service": "Cloud HE REST Server"})
        elif self.path == "/api/cloud/system-stats":
            self._send_json_response(capturer_metriques_systeme())
        elif self.path == "/" or self.path == "/index.html":
            self.servir_fichier_statique("web_ui/index.html", "text/html; charset=utf-8")
        elif self.path == "/style.css":
            self.servir_fichier_statique("web_ui/style.css", "text/css")
        elif self.path == "/app.js":
            self.servir_fichier_statique("web_ui/app.js", "application/javascript")
        else:
            self._send_json_response({"error": "Endpoint introuvable"}, status_code=404)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            self._send_json_response({"error": f"JSON invalide: {str(e)}"}, status_code=400)
            return

        if self.path == "/api/paillier/somme":
            self.traiter_paillier_somme(payload)
        elif self.path == "/api/bfv/somme":
            self.traiter_bfv_somme(payload)
        elif self.path == "/api/benchmark/securite":
            self.traiter_benchmark_securite(payload)
        else:
            self._send_json_response({"error": f"Endpoint {self.path} non géré"}, status_code=404)

    def traiter_paillier_somme(self, payload):
        """Calcul homomorphe Paillier sur le serveur Cloud avec profilage de ressources."""
        tracemalloc.start()
        t0_cpu = time.process_time()
        t0 = time.perf_counter()

        pk_dict = payload.get("public_key")
        chiffres_data = payload.get("ciphertexts", [])

        if not pk_dict or not chiffres_data:
            tracemalloc.stop()
            self._send_json_response({"error": "Champs public_key ou ciphertexts manquants"}, status_code=400)
            return

        pk = PaillierScheme.deserialiser_cle_publique(pk_dict)
        chiffres = [PaillierScheme.deserialiser_chiffre(c, pk) for c in chiffres_data]

        # Addition homomorphe native (sans clé privée)
        somme_chiffree = chiffres[0]
        for c in chiffres[1:]:
            somme_chiffree += c

        t_calcul = time.perf_counter() - t0
        t_cpu = time.process_time() - t0_cpu
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        res_serialized = PaillierScheme.serialiser_chiffre(somme_chiffree)
        sys_stats = capturer_metriques_systeme()

        self._send_json_response({
            "result": res_serialized,
            "temps_calcul_cloud_sec": t_calcul,
            "nb_chiffres": len(chiffres),
            "cloud_metrics": {
                "temps_calcul_sec": t_calcul,
                "temps_cpu_sec": t_cpu,
                "memoire_pic_ko": round(peak_bytes / 1024, 2),
                "memoire_pic_mo": round(peak_bytes / (1024 * 1024), 4),
                "process_ram_mb": sys_stats.get("process_rss_mb", 0),
                "system_cpu_percent": sys_stats.get("system_cpu_percent", 0),
                "system_ram_used_percent": sys_stats.get("system_ram_used_percent", 0),
                "system_ram_used_mb": sys_stats.get("system_ram_used_mb", 0),
                "system_ram_total_mb": sys_stats.get("system_ram_total_mb", 0)
            }
        })

    def traiter_bfv_somme(self, payload):
        """Calcul homomorphe BFV sur le serveur Cloud avec profilage de ressources."""
        tracemalloc.start()
        t0_cpu = time.process_time()
        t0 = time.perf_counter()

        context_dict = payload.get("context")
        chiffres_b64 = payload.get("ciphertexts", [])

        if not context_dict or not chiffres_b64:
            tracemalloc.stop()
            self._send_json_response({"error": "Champs context ou ciphertexts manquants"}, status_code=400)
            return

        he_serv = BFVScheme.deserialiser_contexte(context_dict)

        # Reconstitution des objets PyCtxt côté serveur
        chiffres = []
        for b64 in chiffres_b64:
            ctxt = PyCtxt(pyfhel=he_serv)
            ctxt.from_bytes(base64.b64decode(b64))
            chiffres.append(ctxt)

        # Addition homomorphe BFV native
        somme_chiffree = chiffres[0].copy()
        for c in chiffres[1:]:
            somme_chiffree += c

        t_calcul = time.perf_counter() - t0
        t_cpu = time.process_time() - t0_cpu
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        res_b64 = base64.b64encode(somme_chiffree.to_bytes()).decode("utf-8")
        sys_stats = capturer_metriques_systeme()

        self._send_json_response({
            "result": res_b64,
            "temps_calcul_cloud_sec": t_calcul,
            "nb_chiffres": len(chiffres),
            "cloud_metrics": {
                "temps_calcul_sec": t_calcul,
                "temps_cpu_sec": t_cpu,
                "memoire_pic_ko": round(peak_bytes / 1024, 2),
                "memoire_pic_mo": round(peak_bytes / (1024 * 1024), 4),
                "process_ram_mb": sys_stats.get("process_rss_mb", 0),
                "system_cpu_percent": sys_stats.get("system_cpu_percent", 0),
                "system_ram_used_percent": sys_stats.get("system_ram_used_percent", 0),
                "system_ram_used_mb": sys_stats.get("system_ram_used_mb", 0),
                "system_ram_total_mb": sys_stats.get("system_ram_total_mb", 0)
            }
        })

    def traiter_benchmark_securite(self, payload):
        """Lance la comparaison de sécurité multi-paramètres côté serveur Cloud."""
        nb_transactions = payload.get("nb_transactions", 30)
        nb_repetitions = payload.get("nb_repetitions", 1)

        # Configs Paillier demandées
        paillier_configs = payload.get("paillier_configs", [1024, 2048, 3072])
        # Configs BFV demandées : liste de [degree, sec_level]
        bfv_configs = payload.get("bfv_configs", [[4096, 128], [8192, 128], [16384, 128]])

        try:
            valeurs = charger_ou_generer_donnees(nb_transactions)
            resultats = []

            # Paillier
            for ks in paillier_configs:
                res = evaluer_paillier(int(ks), valeurs, nb_repetitions=nb_repetitions)
                resultats.append(res)

            # BFV
            for cfg in bfv_configs:
                deg, sec = int(cfg[0]), int(cfg[1])
                res = evaluer_bfv(deg, sec, BFV_PLAIN_MODULUS_BITS, valeurs, nb_repetitions=nb_repetitions)
                if res:
                    resultats.append(res)

            self._send_json_response({
                "status": "ok",
                "nb_transactions": len(valeurs),
                "nb_repetitions": nb_repetitions,
                "resultats": resultats
            })
        except Exception as e:
            self._send_json_response({"error": str(e)}, status_code=500)


def demarrer_serveur(host=None, port=CLOUD_PORT):
    if host is None:
        host = os.environ.get("BIND_HOST", "0.0.0.0")
    server_address = (host, port)
    httpd = HTTPServer(server_address, CloudHEHTTPRequestHandler)
    url_console = f"http://localhost:{port}" if host == "0.0.0.0" else f"http://{host}:{port}"
    print(f"[OK] Serveur Cloud REST API démarré. Accès Web: {url_console}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt du serveur Cloud.")
        httpd.server_close()


if __name__ == "__main__":
    demarrer_serveur()
