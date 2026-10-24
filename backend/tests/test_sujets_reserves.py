"""Sujets d'examens depuis le 24/10/2026 : les PDF restent gratuits pour tous,
leur correction par le Prof JPA est reservee a l'acces illimite (verifie par le serveur).

    cd backend
    python -m unittest discover tests -v
"""
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="lp-tests-"))

import app as app_module  # noqa: E402
import pdf_library  # noqa: E402
import subscription  # noqa: E402


class FauxClient:
    def __init__(self):
        self.messages = self
        self.appels = 0

    def create(self, **kwargs):
        self.appels += 1
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="Correction du sujet.")],
                               stop_reason="end_turn", usage=SimpleNamespace(input_tokens=2000, output_tokens=400))


class CorrectionReservee(unittest.TestCase):
    _n = 0

    def setUp(self):
        CorrectionReservee._n += 1
        self.device = f"dev-sujets{CorrectionReservee._n}-{id(self)}"
        self.http = app_module.app.test_client()
        self.sujet = pdf_library.list_pdf_sujets()[0]
        self._orig = (app_module.client, app_module.requests.get)
        app_module.client = FauxClient()
        # Telechargement du PDF remplace : aucun appel reseau.
        app_module.requests.get = lambda url, timeout=None: SimpleNamespace(
            content=b"%PDF-1.4 sujet de test", raise_for_status=lambda: None)

    def tearDown(self):
        app_module.client, app_module.requests.get = self._orig

    def corriger(self, **extra):
        corps = {"device_id": self.device, "pays": "autre-pays"}  # profil different : pas de reponse en cache
        corps.update(extra)
        return self.http.post(f"/api/pdf-sujets/{self.sujet['id']}/corriger", json=corps)

    def test_les_sujets_restent_gratuits(self):
        r = self.http.get(f"/api/pdf-sujets?pays={self.sujet['pays']}")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.get_json(), list)  # format inchange pour les anciennes versions de l'appli
        self.assertTrue(r.get_json())
        r = self.http.get(f"/api/pdf-sujets/{self.sujet['id']}/fichier")  # sans abonnement ni device_id
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"], self.sujet["url"])

    def test_gratuit_ne_peut_pas_faire_corriger(self):
        r = self.corriger()
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json()["error"], "correction_reservee")
        message = r.get_json()["message"]
        self.assertIn("réservée", message)  # affiche tel quel par les anciennes versions de l'appli
        self.assertNotIn("http", message)  # ni lien ni prix (regles Google Play)
        self.assertNotIn("F", message.replace("Prof", ""))
        self.assertEqual(app_module.client.appels, 0)
        self.assertEqual(self.http.get(f"/api/quota?device_id={self.device}").get_json()["remaining"],
                         app_module.DAILY_FREE_LIMIT)  # rien de decompte

    def test_abonne_fait_corriger(self):
        subscription.set_premium(self.device, True, days=30)
        r = self.corriger()
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["answer"], "Correction du sujet.")
        self.assertEqual(app_module._fichiers_en_cours, 0)

    def test_abonnement_termine(self):
        subscription.set_premium(self.device, True, days=30)
        subscription.set_premium(self.device, False)
        self.assertEqual(self.corriger().status_code, 403)

    def test_le_site_affiche_le_cadenas_sur_la_correction(self):
        js = self.http.get("/js/app.js").get_data(as_text=True)
        self.assertIn('data.error === "correction_reservee"', js)
        self.assertIn('workBtn.textContent = "🔒 Corriger avec Le Prof JPA";', js)
        self.assertIn('viewLink.href = apiUrl("/api/pdf-sujets/" + s.id + "/fichier");', js)  # PDF ouvert a tous
        self.assertIn("if (isNativeApp()) openInfoIllimiteModal();", js)  # appli Android : aucune fenetre de paiement


if __name__ == "__main__":
    unittest.main()
