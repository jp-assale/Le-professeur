"""Tests du paiement automatique (/api/paiement-auto) : le registre de JPA Concours
est remplace par un faux, aucun appel reseau.

    cd backend
    python -m unittest discover tests -v
"""
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from types import SimpleNamespace

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="lp-tests-"))

import app as app_module  # noqa: E402
import subscription  # noqa: E402


class FauxRegistre:
    """Remplace requests.post vers le registre : un seul paiement de `montant` F,
    au numero 76123456, utilisable une seule fois."""

    def __init__(self, montant=2500, panne=False):
        self.montant = montant
        self.panne = panne
        self.utilise = False
        self.appels = []

    def post(self, url, timeout=None, headers=None, json=None):
        self.appels.append({"url": url, "headers": headers, "json": json})
        if self.panne:
            raise app_module.requests.ConnectionError("registre injoignable")
        if (headers or {}).get("X-Paiement-Cle") != "cle-de-test":
            return self._rep(403, {"error": "interdit"})
        if self.utilise or not (json["numero"].endswith("76123456") or json["reference"] == "PP261019.1234"):
            return self._rep(404, {"error": "introuvable", "code": "paiement_introuvable"})
        if self.montant < json["montant_min"]:
            return self._rep(400, {"error": "insuffisant", "code": "paiement_insuffisant", "recu": self.montant})
        self.utilise = True
        return self._rep(200, {"ok": True, "montant": self.montant, "operateur": "orange", "numero": "76123456"})

    @staticmethod
    def _rep(code, corps):
        import json as _json
        return SimpleNamespace(status_code=code, ok=code < 400, content=b"x", json=lambda: corps,
                               text=_json.dumps(corps))


class PaiementAuto(unittest.TestCase):
    _n = 0

    def setUp(self):
        PaiementAuto._n += 1
        self.device = f"dev-paie{PaiementAuto._n}-{id(self)}"
        self.http = app_module.app.test_client()
        self.registre = FauxRegistre()
        self._orig_post = app_module.requests.post
        app_module.requests.post = self.registre.post
        os.environ["PAIEMENT_CLE"] = "cle-de-test"

    def tearDown(self):
        app_module.requests.post = self._orig_post
        os.environ.pop("PAIEMENT_CLE", None)

    def payer(self, **extra):
        corps = {"device_id": self.device, "plan": "1-mois", "numero": "+223 76 12 34 56", "reference": ""}
        corps.update(extra)
        return self.http.post("/api/paiement-auto", json=corps)

    def test_paiement_trouve_active_30_jours(self):
        r = self.payer()
        self.assertEqual(r.status_code, 200, r.get_json())
        attendu = (date.today() + timedelta(days=30)).isoformat()
        self.assertEqual(r.get_json()["premium_until"], attendu)
        self.assertTrue(subscription.is_premium(self.device))
        appel = self.registre.appels[0]["json"]
        self.assertEqual((appel["app"], appel["client"], appel["formule"], appel["montant_min"]),
                         ("scolaire", self.device, "1-mois", 2500))
        self.assertEqual(appel["numero"], "22376123456")  # chiffres seulement

    def test_meme_paiement_ne_sert_qu_une_fois(self):
        self.assertEqual(self.payer().status_code, 200)
        autre = self.payer(device_id=self.device + "-b")
        self.assertEqual(autre.status_code, 404)
        self.assertFalse(subscription.is_premium(self.device + "-b"))

    def test_abonnement_en_cours_prolonge(self):
        subscription.set_premium(self.device, True, days=10)
        r = self.payer(plan="2-mois", numero="", reference="PP261019.1234")
        # 4 500 F demandes, 2 500 F recus : refuse, rien n'est consomme.
        self.assertEqual(r.status_code, 400)
        self.assertIn("2 500 F", r.get_json()["error"])
        self.registre.montant = 4500
        r = self.payer(plan="2-mois", numero="", reference="PP261019.1234")
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["premium_until"], (date.today() + timedelta(days=70)).isoformat())

    def test_numero_inconnu_puis_blocage(self):
        for _ in range(app_module.PAIEMENT_ESSAIS_JOUR):
            self.assertEqual(self.payer(numero="70000000").status_code, 404)
        self.assertEqual(self.payer().status_code, 429)  # trop d'essais aujourd'hui, meme avec le bon numero
        self.assertFalse(subscription.is_premium(self.device))

    def test_requetes_invalides(self):
        self.assertEqual(self.payer(device_id="x").status_code, 400)
        self.assertEqual(self.payer(plan="10-ans").status_code, 400)
        self.assertEqual(self.payer(numero="12").status_code, 400)
        self.assertEqual(self.registre.appels, [])

    def test_sans_cle_ou_registre_en_panne(self):
        os.environ.pop("PAIEMENT_CLE")
        self.assertEqual(self.payer().status_code, 503)
        self.assertFalse(self.http.get("/api/pay-info").get_json()["paiement_auto"])
        os.environ["PAIEMENT_CLE"] = "cle-de-test"
        self.assertTrue(self.http.get("/api/pay-info").get_json()["paiement_auto"])
        self.registre.panne = True
        r = self.payer()
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.get_json()["code"], "paiement_indisponible")
        self.assertFalse(subscription.is_premium(self.device))

    def test_mauvaise_cle_refusee_par_le_registre(self):
        os.environ["PAIEMENT_CLE"] = "mauvaise"
        self.assertEqual(self.payer().status_code, 503)
        self.assertFalse(subscription.is_premium(self.device))


class CodeAbonnement(unittest.TestCase):
    """Code d'abonnement XXXX-XXXX : donne par le site, tape dans l'appli (l'abonnement y passe)."""
    _n = 0

    def setUp(self):
        CodeAbonnement._n += 1
        n = f"{CodeAbonnement._n}-{id(self)}"
        self.site, self.appli, self.autre = f"dev-site{n}", f"dev-appli{n}", f"dev-autre{n}"
        self.http = app_module.app.test_client()
        self.ip = {"REMOTE_ADDR": f"198.51.100.{CodeAbonnement._n}"}
        app_module._paiement_echecs.clear()

    def code_de(self, device):
        return self.http.get(f"/api/abonnement/code?device_id={device}")

    def lier(self, device, code):
        return self.http.post("/api/abonnement/lier", json={"device_id": device, "code": code}, environ_base=self.ip)

    def test_pas_de_code_sans_abonnement(self):
        self.assertEqual(self.code_de(self.site).status_code, 404)

    def test_code_stable_et_lisible(self):
        subscription.set_premium(self.site, True, days=30)
        code = self.code_de(self.site).get_json()["code_abonnement"]
        self.assertRegex(code, r"^[2-9A-HJKMNP-Z]{4}-[2-9A-HJKMNP-Z]{4}$")
        self.assertEqual(self.code_de(self.site).get_json()["code_abonnement"], code)

    def test_le_code_fait_passer_l_abonnement_sur_l_appli(self):
        until = subscription.set_premium(self.site, True, days=20)
        code = self.code_de(self.site).get_json()["code_abonnement"]
        r = self.lier(self.appli, code.lower().replace("-", " "))  # saisie approximative acceptee
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["premium_until"], until)
        self.assertTrue(subscription.is_premium(self.appli))
        self.assertFalse(subscription.is_premium(self.site))  # passe, pas copie
        self.assertEqual(self.code_de(self.appli).get_json()["code_abonnement"], code)  # meme code, suit l'abonnement
        self.assertEqual(self.lier(self.appli, code).status_code, 200)  # deja lie : sans effet

    def test_jours_ajoutes_a_un_abonnement_deja_actif(self):
        subscription.set_premium(self.site, True, days=20)
        subscription.set_premium(self.appli, True, days=5)
        code = self.code_de(self.site).get_json()["code_abonnement"]
        r = self.lier(self.appli, code)
        self.assertEqual(r.get_json()["premium_until"], (date.today() + timedelta(days=25)).isoformat())

    def test_code_inconnu_expire_et_limites(self):
        self.assertEqual(self.lier(self.appli, "ABCD").status_code, 400)
        self.assertEqual(self.lier(self.appli, "2345-6789").status_code, 404)
        subscription.set_premium(self.site, True, days=20)
        code = self.code_de(self.site).get_json()["code_abonnement"]
        subscription.set_premium(self.site, False)
        self.assertEqual(self.lier(self.appli, code).status_code, 410)  # abonnement termine
        # Le code qui passe d'un telephone a l'autre en boucle est bloque pour la journee.
        subscription.set_premium(self.site, True, days=20)
        for device in (self.appli, self.autre, self.site):
            self.assertEqual(self.lier(device, code).status_code, 200)
        self.assertEqual(self.lier(self.appli, code).status_code, 429)

    def test_essais_au_hasard_bloques(self):
        for i in range(app_module.CODE_ESSAIS_JOUR):
            self.assertEqual(self.lier(f"{self.appli}-{i}", "2345-6789").status_code, 404)
        # Meme adresse IP, autre appareil : bloque aussi (on ne devine pas les codes en changeant d'appareil).
        self.assertEqual(self.lier(self.autre, "2345-6789").status_code, 429)

    def test_paiement_auto_renvoie_le_code(self):
        registre = FauxRegistre()
        orig = app_module.requests.post
        app_module.requests.post = registre.post
        os.environ["PAIEMENT_CLE"] = "cle-de-test"
        try:
            r = self.http.post("/api/paiement-auto", json={"device_id": self.site, "plan": "1-mois", "numero": "76123456"})
        finally:
            app_module.requests.post = orig
            os.environ.pop("PAIEMENT_CLE", None)
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["code_abonnement"], self.code_de(self.site).get_json()["code_abonnement"])


if __name__ == "__main__":
    unittest.main()
