"""Tests des envois de photos et de PDF (memoire bornee du serveur de 512 Mo,
redemarrage du 24/10/2026) : l'appel a l'IA est remplace par un faux client.

    cd backend
    python -m unittest discover tests -v
"""
import os
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="lp-tests-"))

import app as app_module  # noqa: E402


class FauxClient:
    """Repond apres `attente` secondes en notant le volume de fichiers en cours."""

    def __init__(self, attente=0.0):
        self.messages = self
        self.attente = attente
        self.vus = []

    def create(self, **kwargs):
        self.vus.append(app_module._fichiers_en_cours)
        time.sleep(self.attente)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="Correction.")], stop_reason="end_turn",
                               usage=SimpleNamespace(input_tokens=1500, output_tokens=300))


class Envois(unittest.TestCase):
    _n = 0

    def setUp(self):
        self._orig = (app_module.client, app_module.FICHIERS_EN_COURS_MAX, app_module.AI_QUEUE_WAIT_S)
        app_module.client = FauxClient()
        Envois._n += 1

    def tearDown(self):
        app_module.client, app_module.FICHIERS_EN_COURS_MAX, app_module.AI_QUEUE_WAIT_S = self._orig

    def envoyer(self, taille, route="/api/upload-exercice", **extra):
        corps = {"device_id": f"dev-envoi{Envois._n}-{id(self)}-{taille}", "mime_type": "image/jpeg",
                 "data": "A" * taille, "pays": "mali", "niveau": "college", "matiere": "Mathematiques"}
        corps.update(extra)
        return app_module.app.test_client().post(route, json=corps)

    def test_photo_reduite_passe_et_libere_la_place(self):
        r = self.envoyer(400_000)
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertGreater(app_module.client.vus[0], 400_000)  # place reservee pendant l'appel a l'IA
        self.assertEqual(app_module._fichiers_en_cours, 0)  # puis rendue

    def test_envoi_trop_gros_refuse_sans_le_lire(self):
        r = self.envoyer(app_module.MAX_UPLOAD_B64_LEN + 200_000)
        self.assertEqual(r.status_code, 413)
        self.assertIn("volumineux", r.get_json()["error"])
        self.assertEqual(app_module.client.vus, [])
        r = self.envoyer(app_module.MAX_UPLOAD_B64_LEN + 10, route="/api/correction-copie")
        self.assertEqual(r.status_code, 400)  # avant : aucune limite sur cette route
        self.assertEqual(app_module.client.vus, [])

    def test_volume_en_cours_borne(self):
        """Plafond de 1 Mo : deux photos de 0,6 Mo passent l'une apres l'autre,
        jamais ensemble ; une troisieme qui attend trop recoit « reessaie »."""
        app_module.FICHIERS_EN_COURS_MAX = 1_000_000
        app_module.client = FauxClient(attente=0.4)
        codes = []
        fils = [threading.Thread(target=lambda: codes.append(self.envoyer(600_000).status_code)) for _ in range(2)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()
        self.assertEqual(sorted(codes), [200, 200])
        self.assertTrue(all(v <= 1_000_000 for v in app_module.client.vus), app_module.client.vus)

        app_module.AI_QUEUE_WAIT_S = 0.1
        with app_module._place_fichier(900_000):
            r = self.envoyer(600_000)
        self.assertEqual(r.status_code, 503)
        self.assertIn("Reessaie", r.get_json()["error"])
        self.assertEqual(app_module._fichiers_en_cours, 0)

    def test_un_fichier_plus_gros_que_le_plafond_passe_seul(self):
        app_module.FICHIERS_EN_COURS_MAX = 100_000
        self.assertEqual(self.envoyer(300_000).status_code, 200)
        self.assertEqual(app_module._fichiers_en_cours, 0)

    def test_le_site_reduit_les_photos(self):
        http = app_module.app.test_client()
        js = http.get("/js/app.js").get_data(as_text=True)
        self.assertIn("const PHOTO_COTE_MAX = 1600;", js)
        self.assertIn("file = await reduirePhoto(file);", js)
        self.assertIn('canvas.toBlob(resolve, "image/jpeg", 0.85)', js)


if __name__ == "__main__":
    unittest.main()
