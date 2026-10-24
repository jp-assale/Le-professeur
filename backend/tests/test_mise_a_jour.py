"""Mise a jour obligatoire de l'appli Android (ANDROID_VERSION_MIN, reglee dans Render).

    cd backend
    python -m unittest discover tests -v
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="lp-tests-"))

import app as app_module  # noqa: E402

ANDROID = {"Origin": "https://localhost"}


class FauxClient:
    def __init__(self):
        self.messages = self

    def create(self, **kwargs):
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="Explication.")], stop_reason="end_turn",
                               usage=SimpleNamespace(input_tokens=100, output_tokens=50))


class MiseAJour(unittest.TestCase):
    _n = 0

    def setUp(self):
        MiseAJour._n += 1
        self.device = f"dev-maj{MiseAJour._n}-{id(self)}"
        self.http = app_module.app.test_client()
        self._client = app_module.client
        app_module.client = FauxClient()
        os.environ.pop("ANDROID_VERSION_MIN", None)

    def tearDown(self):
        app_module.client = self._client
        os.environ.pop("ANDROID_VERSION_MIN", None)

    def demander(self, url="/api/ask", headers=ANDROID):
        return self.http.post(url, headers=headers, json={"device_id": self.device, "question": "2x + 5 = 13 ?"})

    def test_desactive_par_defaut(self):
        self.assertEqual(self.http.get(f"/api/quota?device_id={self.device}").get_json()["android_min"], 0)
        self.assertEqual(self.demander().status_code, 200)  # 2.21 : rien ne change tant que rien n'est regle

    def test_anciennes_versions_bloquees(self):
        os.environ["ANDROID_VERSION_MIN"] = "38"
        self.assertEqual(self.http.get(f"/api/quota?device_id={self.device}").get_json()["android_min"], 38)
        r = self.demander()  # 2.21 : n'envoie pas sa version
        self.assertEqual(r.status_code, 426)
        self.assertEqual(r.get_json()["error"], "mise_a_jour")
        self.assertIn("Google Play", r.get_json()["message"])  # affiche tel quel par la 2.21
        self.assertNotIn("http", r.get_json()["message"])
        self.assertIn("access-control-allow-origin", {k.lower() for k in r.headers.keys()})  # lisible par l'appli
        self.assertEqual(self.demander("/api/ask?av=37").status_code, 426)
        self.assertEqual(self.demander("/api/pdf-sujets/x/corriger").status_code, 426)
        self.assertEqual(self.demander("/api/ask?av=38").status_code, 200)  # 2.22 a jour

    def test_site_et_autres_routes_jamais_bloques(self):
        os.environ["ANDROID_VERSION_MIN"] = "99"
        self.assertEqual(self.demander(headers={}).status_code, 200)  # site web
        self.assertEqual(self.http.get(f"/api/quota?device_id={self.device}", headers=ANDROID).status_code, 200)
        r = self.http.post("/api/funnel", headers=ANDROID, json={"device_id": self.device, "etape": "offre_vue"})
        self.assertNotEqual(r.status_code, 426)

    def test_version_de_l_appli_a_jour(self):
        js = self.http.get("/js/app.js").get_data(as_text=True)
        gradle = open(os.path.join(BACKEND, "..", "android", "app", "build.gradle"), encoding="utf-8").read()
        code_gradle = int(re.search(r"versionCode (\d+)", gradle).group(1))
        code_js = int(re.search(r"const APP_VERSION_CODE = (\d+);", js).group(1))
        self.assertEqual(code_js, code_gradle, "changer APP_VERSION_CODE dans app.js a chaque nouvelle version Android")
        self.assertIn("verifierVersionAppli(data.android_min);", js)
        self.assertIn('const PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=com.leprofesseur.app";', js)

    @unittest.skipUnless(shutil.which("node"), "node absent")
    def test_app_js_sans_erreur_de_syntaxe(self):
        # Une constante declaree deux fois (PLAY_STORE_URL, 24/10/2026) cassait tout le site.
        chemin = os.path.join(BACKEND, "..", "frontend", "js", "app.js")
        r = subprocess.run(["node", "--check", chemin], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
