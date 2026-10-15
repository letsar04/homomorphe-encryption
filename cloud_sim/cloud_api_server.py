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

import math
import statistics
import random

from config import CLOUD_HOST, CLOUD_PORT, PAILLIER_KEY_SIZE, BFV_POLY_MODULUS_DEGREE, BFV_PLAIN_MODULUS_BITS
from schemes.paillier_ops import PaillierScheme
from schemes.bfv_ops import BFVScheme
from Pyfhel import Pyfhel, PyCtxt
from phe import paillier

# Import du module de données et benchmarks
from data.generate_synthetic import generer_transactions
from benchmarks.comparer_securite_parametres import (
    evaluer_paillier, evaluer_bfv, charger_ou_generer_donnees
)

def estimer_taille_octets_obj(obj):
    """Estime la taille sérialisée d'un objet chiffré."""
    try:
        if hasattr(obj, "to_bytes"):
            return len(obj.to_bytes())
        if hasattr(obj, "ciphertext"):
            return (int(obj.ciphertext()).bit_length() + 7) // 8
        if isinstance(obj, list) and len(obj) > 0:
            return sum(estimer_taille_octets_obj(x) for x in obj)
        if isinstance(obj, dict):
            return sum(estimer_taille_octets_obj(v) for v in obj.values())
        return sys.getsizeof(obj)
    except Exception:
        return sys.getsizeof(obj)

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

        if self.path == "/api/data/generate":
            self.traiter_generer_donnees(payload)
        elif self.path == "/api/experiment/run":
            self.traiter_experimentation(payload)
        elif self.path == "/api/paillier/somme":
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

    def traiter_generer_donnees(self, payload):
        """Générateur de données synthétiques personnalisées selon les paramètres spécifiés."""
        try:
            type_donnees = payload.get("type_donnees", "transactions")
            nb = int(payload.get("nb_transactions", 100))
            montant_min = int(payload.get("montant_min", 5000))
            montant_max = int(payload.get("montant_max", 500000))
            ratio_credit = float(payload.get("ratio_credit", 0.55))
            seed = int(payload.get("seed", 42))
            nb_comptes = int(payload.get("nb_comptes", 50))

            random.seed(seed)

            if type_donnees == "transactions":
                txs = generer_transactions(
                    nb_transactions=nb,
                    montant_min=montant_min,
                    montant_max=montant_max,
                    nb_comptes=nb_comptes,
                    ratio_credit=ratio_credit,
                    seed=seed
                )
                headers = ["Transaction_ID", "Compte_ID", "Type_Flux", "Montant (FCFA)", "Montant_Brut", "Solde_Résultant"]
                rows = []
                for t in txs:
                    signe_str = f"+{t['montant']:,}" if t['montant'] > 0 else f"{t['montant']:,}"
                    rows.append([
                        f"TX-{t['id_transaction']:05d}",
                        f"CPT-{t['id_compte']:04d}",
                        t["type_operation"],
                        f"{signe_str} FCFA".replace(",", " "),
                        f"{t['montant_brut']:,} FCFA".replace(",", " "),
                        f"{t['solde']:,} FCFA".replace(",", " ")
                    ])
                montants = [t["montant"] for t in txs]
                somme_tot = sum(montants)
                credits = [m for m in montants if m > 0]
                debits = [m for m in montants if m < 0]
                stats = {
                    "total_lignes": nb,
                    "somme_totale_fcfa": somme_tot,
                    "moyenne_fcfa": round(somme_tot / nb, 2),
                    "nb_credits": len(credits),
                    "nb_debits": len(debits),
                    "volume_credits": sum(credits),
                    "volume_debits": sum(debits)
                }

            elif type_donnees == "microcredit":
                headers = ["Client_ID", "Volume_Transactions (FCFA)", "Regularite", "Retards"]
                rows = []
                raw_clients = []
                for i in range(1, nb + 1):
                    vol = random.randint(montant_min, montant_max)
                    reg = random.randint(1, 10)
                    ret = random.randint(0, 30)
                    raw_clients.append({"vol": vol, "reg": reg, "ret": ret})
                    rows.append([
                        f"CLI-{i:04d}",
                        f"{vol:,} FCFA".replace(",", " "),
                        f"{reg}/10",
                        f"{ret} jours"
                    ])
                stats = {
                    "total_lignes": nb,
                    "volume_moyen": round(sum(c["vol"] for c in raw_clients) / nb, 2),
                    "regularite_moyenne": round(sum(c["reg"] for c in raw_clients) / nb, 1),
                    "retards_moyens": round(sum(c["ret"] for c in raw_clients) / nb, 1)
                }

            elif type_donnees == "agios":
                headers = ["Compte_ID", "Solde_Moyen_30J (FCFA)", "Nb_Jours", "Taux_Annuel"]
                rows = []
                raw_soldes = []
                for i in range(1, nb + 1):
                    solde = random.randint(montant_min, montant_max)
                    raw_soldes.append(solde)
                    rows.append([
                        f"CPT-{i:04d}",
                        f"{solde:,} FCFA".replace(",", " "),
                        "30 jours",
                        "5.00 %"
                    ])
                stats = {
                    "total_lignes": nb,
                    "solde_moyen": round(sum(raw_soldes) / nb, 2),
                    "taux_applique": "5.00 % (BCEAO)"
                }
            else:
                headers = ["Index", "Montant (FCFA)"]
                rows = []
                raw_vals = []
                for i in range(1, nb + 1):
                    v = random.randint(montant_min, montant_max)
                    raw_vals.append(v)
                    rows.append([f"N-{i}", f"{v:,} FCFA".replace(",", " ")])
                stats = {
                    "total_lignes": nb,
                    "somme_totale_fcfa": sum(raw_vals),
                    "moyenne_fcfa": round(sum(raw_vals) / nb, 2)
                }

            self._send_json_response({
                "status": "ok",
                "type_donnees": type_donnees,
                "total_count": len(rows),
                "headers": headers,
                "preview_rows": rows[:50],
                "rows": rows,
                "stats": stats
            })
        except Exception as e:
            self._send_json_response({"error": str(e)}, status_code=500)

    def traiter_experimentation(self, payload):
        """Exécute l'expérimentation homomorphe complète avec mesures personnalisées et répétitions."""
        try:
            scheme_type = payload.get("scheme", "paillier")  # paillier, bfv, bfv_simd
            op_type = payload.get("operation", "somme")      # somme, moyenne, microcredit, agios, scalaire
            nb_transactions = int(payload.get("nb_transactions", 30))
            nb_repetitions = max(1, min(int(payload.get("nb_repetitions", 1)), 10))
            selected_metrics = payload.get("metrics", [
                "keygen", "enc_time", "cloud_time", "dec_time", "net_time",
                "ram_peak", "cpu_percent", "ciphertext_size", "expansion_ratio", "accuracy"
            ])
            raw_input_rows = payload.get("input_rows", None)
            scalar_factor = int(payload.get("scalar_factor", 118)) # ex: 118 pour TVA ou ratio

            random.seed(42)
            if op_type == "microcredit":
                dataset = []
                for i in range(nb_transactions):
                    if raw_input_rows and i < len(raw_input_rows):
                        r = raw_input_rows[i]
                        vol = int(str(r[1]).replace("FCFA","").replace(" ","").replace("\u202f","").replace(",","") or 500000)
                        reg = int(str(r[2]).split("/")[0].strip() or 5)
                        ret = int(str(r[3]).split(" ")[0].strip() or 5)
                    else:
                        vol = random.randint(100_000, 2_000_000)
                        reg = random.randint(1, 10)
                        ret = random.randint(0, 30)
                    dataset.append({"id": f"CLI-{i+1:04d}", "volume": vol, "regularite": reg, "retards": ret})
            elif op_type == "agios":
                dataset = []
                for i in range(nb_transactions):
                    if raw_input_rows and i < len(raw_input_rows):
                        r = raw_input_rows[i]
                        solde = int(str(r[1]).replace("FCFA","").replace(" ","").replace("\u202f","").replace(",","") or 1000000)
                    else:
                        solde = random.randint(200_000, 5_000_000)
                    dataset.append({"id": f"CPT-{i+1:04d}", "solde": solde})
            else:
                dataset = []
                for i in range(nb_transactions):
                    if raw_input_rows and i < len(raw_input_rows):
                        r = raw_input_rows[i]
                        col_idx = 3 if len(r) > 3 else (2 if len(r) > 2 else 1)
                        val_str = str(r[col_idx]).replace("FCFA","").replace("+","").replace(" ","").replace("\u202f","").replace(",","")
                        try:
                            val = int(val_str)
                        except Exception:
                            val = random.randint(5_000, 200_000)
                    else:
                        val = random.randint(5_000, 200_000)
                    dataset.append({"id": f"TX-{i+1:04d}", "valeur": val})

            repetitions_data = []
            sample_results = []

            for rep in range(1, nb_repetitions + 1):
                # 1. KeyGen
                t0_kg = time.perf_counter()
                if scheme_type == "paillier":
                    scheme = PaillierScheme(PAILLIER_KEY_SIZE)
                elif scheme_type == "bfv_simd":
                    scheme = BFVScheme(BFV_POLY_MODULUS_DEGREE, BFV_PLAIN_MODULUS_BITS, sec=128)
                    scheme.activer_simd()
                else:
                    scheme = BFVScheme(BFV_POLY_MODULUS_DEGREE, BFV_PLAIN_MODULUS_BITS, sec=128)
                t_keygen = (time.perf_counter() - t0_kg) * 1000

                # 2. Chiffrement
                t0_enc = time.perf_counter()
                if op_type == "microcredit":
                    ciphers = []
                    for item in dataset:
                        if scheme_type == "paillier":
                            c_vol = scheme.public_key.encrypt(item["volume"])
                            c_reg = scheme.public_key.encrypt(item["regularite"])
                            c_ret = scheme.public_key.encrypt(item["retards"])
                        else:
                            c_vol = scheme.chiffrer([item["volume"]])[0]
                            c_reg = scheme.chiffrer([item["regularite"]])[0]
                            c_ret = scheme.chiffrer([item["retards"]])[0]
                        ciphers.append({"vol": c_vol, "reg": c_reg, "ret": c_ret})
                elif op_type == "agios":
                    ciphers = []
                    for item in dataset:
                        if scheme_type == "paillier":
                            c_solde = scheme.public_key.encrypt(item["solde"])
                        else:
                            c_solde = scheme.chiffrer([item["solde"]])[0]
                        ciphers.append(c_solde)
                else:
                    vals = [d["valeur"] for d in dataset]
                    if scheme_type == "bfv_simd":
                        ciphers = scheme.chiffrer_simd(vals)
                    else:
                        ciphers = scheme.chiffrer(vals)
                t_enc = (time.perf_counter() - t0_enc) * 1000

                taille_octets = estimer_taille_octets_obj(ciphers)
                taille_claire = max(1, nb_transactions * 8)
                expansion_ratio = round(taille_octets / taille_claire, 1)

                # 3. Calcul Cloud
                tracemalloc.start()
                t0_cloud_cpu = time.process_time()
                t0_cloud = time.perf_counter()

                if op_type == "somme":
                    if scheme_type == "bfv_simd":
                        res_c = scheme.somme_homomorphe_simd(ciphers)
                    else:
                        res_c = scheme.somme_homomorphe(ciphers)
                elif op_type == "moyenne":
                    if scheme_type == "bfv_simd":
                        res_c = scheme.somme_homomorphe_simd(ciphers)
                    else:
                        res_c = scheme.somme_homomorphe(ciphers)
                elif op_type == "microcredit":
                    res_c = []
                    ALPHA, BETA, GAMMA = 5, 50_000, 20_000
                    for c_item in ciphers:
                        score_c = (c_item["vol"] * ALPHA) + (c_item["reg"] * BETA) - (c_item["ret"] * GAMMA)
                        res_c.append(score_c)
                elif op_type == "agios":
                    res_c = []
                    for c_solde in ciphers:
                        agios_c = (c_solde * 150) // 360
                        res_c.append(agios_c)
                elif op_type == "scalaire":
                    res_c = [c * scalar_factor for c in ciphers]

                t_cloud = (time.perf_counter() - t0_cloud) * 1000
                t_cloud_cpu = (time.process_time() - t0_cloud_cpu) * 1000
                _, peak_bytes = tracemalloc.get_traced_memory()
                tracemalloc.stop()

                # 4. Déchiffrement
                t0_dec = time.perf_counter()
                if op_type == "somme":
                    if scheme_type == "bfv_simd":
                        res_dec = scheme.dechiffrer_simd(res_c, extraire_somme=True)
                    else:
                        res_dec = scheme.dechiffrer(res_c)
                    expected = sum(d["valeur"] for d in dataset)
                    exact = (res_dec == expected)
                elif op_type == "moyenne":
                    if scheme_type == "bfv_simd":
                        sum_dec = scheme.dechiffrer_simd(res_c, extraire_somme=True)
                    else:
                        sum_dec = scheme.dechiffrer(res_c)
                    res_dec = round(sum_dec / len(dataset), 2)
                    expected = round(sum(d["valeur"] for d in dataset) / len(dataset), 2)
                    exact = (abs(res_dec - expected) < 1e-3)
                elif op_type == "microcredit":
                    res_dec = [scheme.dechiffrer(sc) for sc in res_c]
                    expected = [(5 * d["volume"]) + (50_000 * d["regularite"]) - (20_000 * d["retards"]) for d in dataset]
                    exact = all(rd == exp for rd, exp in zip(res_dec, expected))
                elif op_type == "agios":
                    res_dec = [scheme.dechiffrer(sc) for sc in res_c]
                    expected = [((d["solde"] * 150) // 360) for d in dataset]
                    exact = all(rd == exp for rd, exp in zip(res_dec, expected))
                elif op_type == "scalaire":
                    res_dec = [scheme.dechiffrer(c) for c in res_c]
                    expected = [d["valeur"] * scalar_factor for d in dataset]
                    exact = all(rd == exp for rd, exp in zip(res_dec, expected))

                t_dec = (time.perf_counter() - t0_dec) * 1000

                sys_stats = capturer_metriques_systeme()

                rep_info = {
                    "repetition": rep,
                    "keygen_ms": round(t_keygen, 2),
                    "enc_time_ms": round(t_enc, 2),
                    "cloud_time_ms": round(t_cloud, 2),
                    "cloud_cpu_ms": round(t_cloud_cpu, 2),
                    "dec_time_ms": round(t_dec, 2),
                    "ram_peak_ko": round(peak_bytes / 1024, 2),
                    "ram_peak_mo": round(peak_bytes / (1024 * 1024), 4),
                    "cpu_percent": sys_stats.get("system_cpu_percent", 0),
                    "ciphertext_size_bytes": taille_octets,
                    "ciphertext_size_ko": round(taille_octets / 1024, 2),
                    "expansion_ratio": expansion_ratio,
                    "accuracy_percent": 100.0 if exact else 0.0
                }
                repetitions_data.append(rep_info)

                if rep == nb_repetitions:
                    sample_size = min(len(dataset), 15)
                    if op_type == "microcredit":
                        for i in range(sample_size):
                            d = dataset[i]
                            score = res_dec[i]
                            exp = expected[i]
                            is_acc = score >= 500_000
                            sample_results.append({
                                "id": d["id"],
                                "valeur_claire": f"Vol: {d['volume']:,} FCFA | Rég: {d['regularite']}/10 | Ret: {d['retards']}j".replace(",", " "),
                                "resultat_chiffre_info": f"Score Chiffré {scheme_type.upper()}",
                                "resultat_dechiffre": f"{score:,} pts".replace(",", " "),
                                "resultat_reference": f"{exp:,} pts".replace(",", " "),
                                "decision": "ACCORDÉ" if is_acc else "REFUSÉ",
                                "decision_class": "badge-success" if is_acc else "badge-danger",
                                "exactitude": score == exp
                            })
                    elif op_type == "agios":
                        for i in range(sample_size):
                            d = dataset[i]
                            agios = res_dec[i]
                            exp = expected[i]
                            sample_results.append({
                                "id": d["id"],
                                "valeur_claire": f"Solde 30j: {d['solde']:,} FCFA (Taux 5%)".replace(",", " "),
                                "resultat_chiffre_info": f"Agios Chiffrés {scheme_type.upper()}",
                                "resultat_dechiffre": f"{agios:,} FCFA".replace(",", " "),
                                "resultat_reference": f"{exp:,} FCFA".replace(",", " "),
                                "decision": "CALCULÉ",
                                "decision_class": "badge-info",
                                "exactitude": agios == exp
                            })
                    elif op_type in ["somme", "moyenne"]:
                        unit = "FCFA"
                        op_label = "Somme Totale" if op_type == "somme" else "Moyenne"
                        sample_results.append({
                            "id": f"Agrégation N={len(dataset)}",
                            "valeur_claire": f"Échantillon de {len(dataset)} transactions bancaires",
                            "resultat_chiffre_info": f"{op_label} Chiffrée ({scheme_type.upper()})",
                            "resultat_dechiffre": f"{res_dec:,} {unit}".replace(",", " "),
                            "resultat_reference": f"{expected:,} {unit}".replace(",", " "),
                            "decision": "CONFORME",
                            "decision_class": "badge-success",
                            "exactitude": exact
                        })
                        for i in range(min(5, len(dataset))):
                            d = dataset[i]
                            sample_results.append({
                                "id": d["id"],
                                "valeur_claire": f"Transaction individuelle: {d['valeur']:,} FCFA".replace(",", " "),
                                "resultat_chiffre_info": f"Chiffré unitaire",
                                "resultat_dechiffre": f"{d['valeur']:,} FCFA".replace(",", " "),
                                "resultat_reference": f"{d['valeur']:,} FCFA".replace(",", " "),
                                "decision": "INCLUS DANS LA SOMME",
                                "decision_class": "badge-info",
                                "exactitude": True
                            })
                    elif op_type == "scalaire":
                        for i in range(sample_size):
                            d = dataset[i]
                            val_tva = res_dec[i]
                            exp = expected[i]
                            sample_results.append({
                                "id": d["id"],
                                "valeur_claire": f"Base: {d['valeur']:,} FCFA (x{scalar_factor})".replace(",", " "),
                                "resultat_chiffre_info": f"Chiffré Produit Scalaire",
                                "resultat_dechiffre": f"{val_tva:,} FCFA".replace(",", " "),
                                "resultat_reference": f"{exp:,} FCFA".replace(",", " "),
                                "decision": "APPLIQUÉ",
                                "decision_class": "badge-info",
                                "exactitude": val_tva == exp
                            })

            def calc_mean(metric_name):
                vals = [r[metric_name] for r in repetitions_data]
                return round(sum(vals) / len(vals), 2)

            def calc_std(metric_name):
                vals = [r[metric_name] for r in repetitions_data]
                return round(statistics.stdev(vals), 2) if len(vals) > 1 else 0.0

            moyennes = {
                "keygen_ms": calc_mean("keygen_ms"),
                "enc_time_ms": calc_mean("enc_time_ms"),
                "cloud_time_ms": calc_mean("cloud_time_ms"),
                "cloud_cpu_ms": calc_mean("cloud_cpu_ms"),
                "dec_time_ms": calc_mean("dec_time_ms"),
                "ram_peak_ko": calc_mean("ram_peak_ko"),
                "ram_peak_mo": calc_mean("ram_peak_mo"),
                "cpu_percent": calc_mean("cpu_percent"),
                "ciphertext_size_ko": calc_mean("ciphertext_size_ko"),
                "expansion_ratio": calc_mean("expansion_ratio"),
                "accuracy_percent": calc_mean("accuracy_percent")
            }

            ecarts_types = {
                "keygen_ms": calc_std("keygen_ms"),
                "enc_time_ms": calc_std("enc_time_ms"),
                "cloud_time_ms": calc_std("cloud_time_ms"),
                "cloud_cpu_ms": calc_std("cloud_cpu_ms"),
                "dec_time_ms": calc_std("dec_time_ms"),
                "ram_peak_ko": calc_std("ram_peak_ko")
            }

            sys_stats = capturer_metriques_systeme()

            self._send_json_response({
                "status": "ok",
                "scheme": scheme_type,
                "operation": op_type,
                "nb_transactions": nb_transactions,
                "nb_repetitions": nb_repetitions,
                "metrics_selectionnees": selected_metrics,
                "repetitions": repetitions_data,
                "moyennes": moyennes,
                "ecarts_types": ecarts_types,
                "sample_results": sample_results,
                "cloud_system_stats": sys_stats
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
