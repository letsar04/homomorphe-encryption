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
from http.server import HTTPServer, BaseHTTPRequestHandler

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from config import CLOUD_HOST, CLOUD_PORT
from schemes.paillier_ops import PaillierScheme
from schemes.bfv_ops import BFVScheme
from Pyfhel import Pyfhel, PyCtxt
from phe import paillier


class CloudHEHTTPRequestHandler(BaseHTTPRequestHandler):
    """Handler HTTP REST API pour les calculs homomorphes Cloud."""

    def log_message(self, format, *args):
        # Désactiver le journal de requêtes verbeux dans la console
        return

    def _send_json_response(self, data, status_code=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
        else:
            self._send_json_response({"error": f"Endpoint {self.path} non géré"}, status_code=404)

    def traiter_paillier_somme(self, payload):
        """Calcul homomorphe Paillier sur le serveur Cloud."""
        t0 = time.perf_counter()

        pk_dict = payload.get("public_key")
        chiffres_data = payload.get("ciphertexts", [])

        if not pk_dict or not chiffres_data:
            self._send_json_response({"error": "Champs public_key ou ciphertexts manquants"}, status_code=400)
            return

        pk = PaillierScheme.deserialiser_cle_publique(pk_dict)
        chiffres = [PaillierScheme.deserialiser_chiffre(c, pk) for c in chiffres_data]

        # Addition homomorphe native (sans clé privée)
        somme_chiffree = chiffres[0]
        for c in chiffres[1:]:
            somme_chiffree += c

        t_calcul = time.perf_counter() - t0

        res_serialized = PaillierScheme.serialiser_chiffre(somme_chiffree)

        self._send_json_response({
            "result": res_serialized,
            "temps_calcul_cloud_sec": t_calcul,
            "nb_chiffres": len(chiffres)
        })

    def traiter_bfv_somme(self, payload):
        """Calcul homomorphe BFV sur le serveur Cloud."""
        t0 = time.perf_counter()

        context_dict = payload.get("context")
        chiffres_b64 = payload.get("ciphertexts", [])

        if not context_dict or not chiffres_b64:
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

        res_b64 = base64.b64encode(somme_chiffree.to_bytes()).decode("utf-8")

        self._send_json_response({
            "result": res_b64,
            "temps_calcul_cloud_sec": t_calcul,
            "nb_chiffres": len(chiffres)
        })


def demarrer_serveur(host=None, port=CLOUD_PORT):
    if host is None:
        host = os.environ.get("BIND_HOST", "0.0.0.0")
    server_address = (host, port)
    httpd = HTTPServer(server_address, CloudHEHTTPRequestHandler)
    print(f"[OK] Serveur Cloud REST API démarré sur http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt du serveur Cloud.")
        httpd.server_close()


if __name__ == "__main__":
    demarrer_serveur()
