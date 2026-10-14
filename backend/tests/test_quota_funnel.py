"""Tests du plafond d'usage de l'illimite et de l'entonnoir d'acquisition
(bibliotheque standard, l'appel a l'IA est remplace par un faux client).

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
import data_deletion  # noqa: E402
import db  # noqa: E402
import funnel  # noqa: E402
import subscription  # noqa: E402

ADMIN = {"X-Admin-Token": "jeton-de-test"}
ANDROID = {"Origin": "https://localhost"}


class FauxClient:
    """Remplace le client Anthropic : repond toujours la meme chose."""

    def __init__(self, texte="Explication."):
        self.messages = self
        self.appels = 0
        self.texte = texte
        self.derniers_parametres = {}

    def create(self, **kwargs):
        self.appels += 1
        self.derniers_parametres = kwargs
        # Comme Haiku 5.5 : un bloc de reflexion (texte vide) avant la reponse.
        content = [SimpleNamespace(type="thinking", thinking="", signature="x")]
        if self.texte:
            content.append(SimpleNamespace(type="text", text=self.texte))
        return SimpleNamespace(
            content=content,
            stop_reason="end_turn" if self.texte else "refusal",
            # Taille realiste : un cout arrondi a 0 $ fausserait les tests du budget.
            usage=SimpleNamespace(input_tokens=600, output_tokens=700),
        )


class Base(unittest.TestCase):
    _n = 0

    def setUp(self):
        self.faux = FauxClient()
        self._orig = (app_module.client, app_module.ADMIN_TOKEN, app_module.PREMIUM_DAILY_LIMIT)
        app_module.client = self.faux
        app_module.ADMIN_TOKEN = ADMIN["X-Admin-Token"]
        app_module.PREMIUM_DAILY_LIMIT = 3
        self.http = app_module.app.test_client()
        # Appareil et IP neufs a chaque test : les compteurs ne se melangent pas.
        Base._n += 1
        self.device = f"dev-test{Base._n}-{id(self)}"
        self.ip = {"REMOTE_ADDR": f"203.0.113.{Base._n}"}

    def tearDown(self):
        app_module.client, app_module.ADMIN_TOKEN, app_module.PREMIUM_DAILY_LIMIT = self._orig

    def ask(self):
        return self.http.post("/api/ask", json={"device_id": self.device, "question": "2+2 ?"},
                              environ_base=self.ip)

    def etapes(self):
        conn = db.get_connection()
        try:
            rows = conn.execute("SELECT etape, plateforme FROM funnel_events WHERE device_id = ?",
                                (self.device,)).fetchall()
        finally:
            conn.close()
        return dict(rows)


class TestPlafondPremium(Base):
    def test_premium_bloque_au_plafond_sans_appel_ia(self):
        subscription.set_premium(self.device, True)
        for _ in range(3):
            r = self.ask()
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.get_json()["premium"])
        r = self.ask()
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.get_json()["error"], "plafond_premium")
        self.assertEqual(self.faux.appels, 3)
        self.assertIn(funnel.ETAPE_PLAFOND, self.etapes())

    def test_photo_compte_double_pour_le_plafond(self):
        subscription.set_premium(self.device, True)
        photo = {"device_id": self.device, "mime_type": "image/png", "data": "aGVsbG8="}
        self.assertEqual(self.http.post("/api/upload-exercice", json=photo, environ_base=self.ip).status_code, 200)
        # 1 restante sur 3 : une 2e photo (poids 2) est refusee, une question passe.
        self.assertEqual(self.http.post("/api/upload-exercice", json=photo, environ_base=self.ip).status_code, 429)
        self.assertEqual(self.ask().status_code, 200)

    def test_plafond_premium_ne_touche_pas_le_quota_gratuit(self):
        subscription.set_premium(self.device, True)
        self.ask()
        r = self.http.get("/api/quota?device_id=" + self.device)
        self.assertEqual(r.get_json()["remaining"], app_module.DAILY_FREE_LIMIT)

    def test_gratuit_inchange(self):
        for _ in range(app_module.DAILY_FREE_LIMIT):
            self.assertEqual(self.ask().status_code, 200)
        r = self.ask()
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.get_json()["error"], "quota_depasse")


class TestEntonnoir(Base):
    def test_etapes_constatees_par_le_serveur(self):
        self.http.get("/api/quota?device_id=" + self.device, headers=ANDROID)
        self.assertEqual(self.etapes(), {"ouverture": "android"})
        self.ask()
        self.assertIn("premiere_question", self.etapes())
        for _ in range(app_module.DAILY_FREE_LIMIT):
            self.ask()
        self.assertIn("quota_atteint", self.etapes())

    def test_etapes_signalees_par_l_appli(self):
        r = self.http.post("/api/funnel", json={"device_id": self.device, "etape": "offre_vue"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.etapes(), {"offre_vue": "web"})
        # L'appli ne peut pas declarer elle-meme un paiement ni une etape inconnue.
        for etape in ("paiement", "nimporte"):
            r = self.http.post("/api/funnel", json={"device_id": self.device, "etape": etape})
            self.assertEqual(r.status_code, 400)
        self.assertNotIn("paiement", self.etapes())

    def test_activation_compte_le_paiement_une_fois(self):
        demande = {"k": "ref" + self.device[-12:].replace("-", "x"), "device_id": self.device, "days": 30}
        for _ in range(2):
            r = self.http.post("/api/admin/activate-request", json=demande, headers=ADMIN)
            self.assertEqual(r.status_code, 200)
        self.assertIn("paiement", self.etapes())

    def test_cohorte_par_date(self):
        self.http.get("/api/quota?device_id=" + self.device)
        r = self.http.get("/api/admin/funnel?depuis=2000-01-01", headers=ADMIN)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual([e["etape"] for e in data["etapes"]][0], "ouverture")
        self.assertGreaterEqual(data["etapes"][0]["appareils"], 1)
        futur = self.http.get("/api/admin/funnel?depuis=2999-01-01", headers=ADMIN).get_json()
        self.assertEqual(futur["etapes"][0]["appareils"], 0)
        self.assertEqual(self.http.get("/api/admin/funnel?depuis=hier", headers=ADMIN).status_code, 400)
        self.assertEqual(self.http.get("/api/admin/funnel").status_code, 403)

    def test_effacement_supprime_entonnoir_et_plafond(self):
        subscription.set_premium(self.device, True)
        self.ask()
        counts = data_deletion.delete_device_data(self.device, include_subscription=True)
        self.assertGreaterEqual(counts["funnel_events"], 1)
        self.assertEqual(self.etapes(), {})
        conn = db.get_connection()
        try:
            reste = conn.execute("SELECT COUNT(*) FROM quota WHERE device_id = ?",
                                 ("premium:" + self.device,)).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(reste, 0)

    def test_stats_admin_stockage_et_comptage(self):
        data = self.http.get("/api/admin/stats", headers=ADMIN).get_json()
        self.assertIn("stockage_persistant", data)
        self.assertEqual(data["plafond_premium_jour"], 3)


class TestModeleIA(Base):
    def test_bloc_de_reflexion_ignore(self):
        r = self.ask()
        self.assertEqual(r.get_json()["answer"], "Explication.")
        self.assertEqual(self.faux.derniers_parametres["model"], app_module.MODEL)
        for cle, valeur in app_module.AI_PARAMS.items():
            self.assertEqual(self.faux.derniers_parametres[cle], valeur)

    def test_reponse_vide_message_clair_sans_consommer_le_quota(self):
        self.faux.texte = ""
        r = self.ask()
        self.assertEqual(r.status_code, 502)
        self.assertIn("Reformule", r.get_json()["error"])
        q = self.http.get("/api/quota?device_id=" + self.device).get_json()
        self.assertEqual(q["remaining"], q["limit"])

    def test_serveur_occupe_reponse_claire_sans_consommer_le_quota(self):
        import threading
        slots, attente = app_module._ia_slots, app_module.AI_QUEUE_WAIT_S
        app_module._ia_slots = threading.BoundedSemaphore(1)
        app_module.AI_QUEUE_WAIT_S = 0.05
        app_module._ia_slots.acquire()  # une question deja en cours, plus de place
        try:
            r = self.ask()
        finally:
            app_module._ia_slots.release()
            app_module._ia_slots, app_module.AI_QUEUE_WAIT_S = slots, attente
        self.assertEqual(r.status_code, 503)
        self.assertIn("Reessaie", r.get_json()["error"])
        self.assertEqual(self.faux.appels, 0)
        q = self.http.get("/api/quota?device_id=" + self.device).get_json()
        self.assertEqual(q["remaining"], q["limit"])

    def test_plafond_de_longueur(self):
        if app_module._ANCIEN_MODELE:
            self.assertEqual(app_module._cap(1000), 1000)
        else:
            self.assertGreater(app_module._cap(1000), 1000)


class TestPlafondBudgetGratuit(Base):
    def setUp(self):
        super().setUp()
        import usage_log
        self.usage_log = usage_log
        self._budget = usage_log.FREE_MONTHLY_BUDGET_USD
        usage_log._cache_gratuit["expire"] = 0  # pas de valeur memorisee d'un autre test

    def tearDown(self):
        self.usage_log.FREE_MONTHLY_BUDGET_USD = self._budget
        self.usage_log._cache_gratuit["expire"] = 0
        super().tearDown()

    def test_couts_etiquetes_gratuit_ou_premium(self):
        avant = self.usage_log.month_cost_usd("premium")
        subscription.set_premium(self.device, True)
        self.ask()
        self.assertGreater(self.usage_log.month_cost_usd("premium"), avant)

    def test_budget_atteint_reduit_le_gratuit_mais_pas_les_abonnes(self):
        self.usage_log.FREE_MONTHLY_BUDGET_USD = 1e-9  # deja depasse par les tests precedents ou celui-ci
        self.ask()
        self.usage_log._cache_gratuit["expire"] = 0
        q = self.http.get("/api/quota?device_id=" + self.device).get_json()
        self.assertEqual(q["limit"], min(app_module.DAILY_FREE_LIMIT, app_module.FREE_LIMIT_OVER_BUDGET))
        while self.ask().status_code == 200:
            pass
        self.assertLessEqual(self.faux.appels, app_module.FREE_LIMIT_OVER_BUDGET + 1)
        abonne = self.device + "-abo"
        subscription.set_premium(abonne, True)
        r = self.http.post("/api/ask", json={"device_id": abonne, "question": "?"}, environ_base=self.ip)
        self.assertEqual(r.status_code, 200)

    def test_budget_non_atteint_quota_normal(self):
        self.usage_log.FREE_MONTHLY_BUDGET_USD = 1e9
        q = self.http.get("/api/quota?device_id=" + self.device).get_json()
        self.assertEqual(q["limit"], app_module.DAILY_FREE_LIMIT)


class TestRattrapage(unittest.TestCase):
    def test_appareils_existants_rattrapes(self):
        conn = db.get_connection()
        try:
            conn.execute("INSERT INTO progress_events (ts, device_id, type) VALUES "
                         "('2026-09-01T10:00:00', 'dev-ancien', 'ask')")
            conn.execute("INSERT INTO quota (device_id, date, count) VALUES ('198.51.100.7', '2026-09-02', 3)")
            conn.execute("DELETE FROM _migrations WHERE name = 'funnel_backfill_v1'")
            conn.commit()
            db._migrate_funnel_backfill(conn)
            etapes = dict(conn.execute(
                "SELECT etape, ts FROM funnel_events WHERE device_id = 'dev-ancien'").fetchall())
            ip = conn.execute("SELECT COUNT(*) FROM funnel_events WHERE device_id = '198.51.100.7'").fetchone()[0]
            db._migrate_funnel_backfill(conn)  # deuxieme passage : sans effet
        finally:
            conn.close()
        self.assertEqual(etapes["ouverture"], "2026-09-01T10:00:00")
        self.assertIn("premiere_question", etapes)
        self.assertEqual(ip, 0)


if __name__ == "__main__":
    unittest.main()
