"""Tests du contenu « Cours » et des routes associees (bibliotheque standard,
aucune dependance de test a installer).

    cd backend
    python -m unittest discover tests -v
"""
import json
import os
import sys
import tempfile
import unittest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
# Les fichiers de donnees (quota, logs...) vont dans un dossier jetable.
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="lp-tests-"))

import build_enrichments  # noqa: E402
import cours_library  # noqa: E402
import curriculum  # noqa: E402

SEED = os.path.join(BACKEND, "cours_seed")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestContenu(unittest.TestCase):
    def test_sources_enrichissements_valides(self):
        # Construit en memoire et verifie la structure (aucune ecriture).
        self.assertEqual(build_enrichments.build(check_only=True), 0)

    def test_chaque_lecon_du_manifeste_existe(self):
        for m in _load(os.path.join(SEED, "manifest.json")):
            self.assertTrue(
                os.path.exists(os.path.join(SEED, "lessons", m["slug"] + ".json")), m["slug"]
            )

    def test_quiz_flash_une_seule_bonne_reponse(self):
        for m in _load(os.path.join(SEED, "manifest.json")):
            lesson = _load(os.path.join(SEED, "lessons", m["slug"] + ".json"))
            bonnes = [c for c in lesson["quiz"]["choices"] if c.get("correct")]
            self.assertEqual(len(bonnes), 1, m["slug"])

    def test_enrichissements_a_jour(self):
        # enrichments/ doit correspondre exactement aux sources (sinon :
        # lancer « python build_enrichments.py » avant de committer).
        out = {f[:-5] for f in os.listdir(os.path.join(SEED, "enrichments"))}
        mapped = set()
        for name in os.listdir(os.path.join(SEED, "enrichments_src")):
            if name.endswith(".json"):
                mapped |= set(_load(os.path.join(SEED, "enrichments_src", name))["map"])
        self.assertEqual(out, mapped)

    def test_methodes_structure(self):
        ids = set()
        for f in _load(os.path.join(SEED, "methodes.json")):
            self.assertNotIn(f["id"], ids)
            ids.add(f["id"])
            self.assertTrue(f["titre"] and f["sections"])
            for s in f["sections"]:
                self.assertTrue(s["titre"] and s["points"])


class TestBibliotheque(unittest.TestCase):
    def test_complement_superpose_sans_ecraser(self):
        slug = "cote-ivoire-college-mathematiques-calcul-litteral"
        brute = _load(os.path.join(SEED, "lessons", slug + ".json"))
        lesson = cours_library.get_lesson(slug)
        self.assertTrue(lesson["enrichi"])
        self.assertEqual(lesson["intro"], brute["intro"])
        self.assertEqual(lesson["quiz"], brute["quiz"])
        self.assertGreaterEqual(len(lesson["exercices"]), 2)

    def test_slug_dangereux_refuse(self):
        self.assertIsNone(cours_library.get_lesson("../manifest"))
        self.assertIsNone(cours_library.get_lesson(""))

    def test_ordre_officiel_des_chapitres(self):
        chapitres = [
            m["chapitre"]
            for m in cours_library.list_lessons("cote_ivoire", "lycee", "Mathematiques")
            if m.get("serie") == "D"
        ]
        self.assertLess(chapitres.index("Primitives"), chapitres.index("Calcul intégral"))
        self.assertLess(chapitres.index("Fonctions logarithmes"), chapitres.index("Fonctions exponentielles et fonctions puissances"))

    def test_repli_regional_conserve(self):
        lecons = cours_library.list_lessons("guinee", "college", "Mathematiques")
        self.assertTrue(lecons)
        self.assertTrue(all(m.get("fallback_for") == "guinee" for m in lecons))

    def test_methodes_filtrees_par_pays(self):
        ci = {f["id"] for f in cours_library.list_methodes("lycee", "Philosophie", "cote_ivoire")}
        ml = {f["id"] for f in cours_library.list_methodes("lycee", "Philosophie", "mali")}
        self.assertIn("situation-evaluation-apc", ci)
        self.assertNotIn("situation-evaluation-apc", ml)
        self.assertIn("dissertation-philo", ml)


class TestReferentiel(unittest.TestCase):
    def test_examens_college(self):
        self.assertIn("BEPC", curriculum.niveau_label("guinee", "college"))
        self.assertIn("BFEM", curriculum.niveau_label("senegal", "college"))
        self.assertIn("DEF", curriculum.niveau_label("mali", "college"))

    def test_contexte_pays(self):
        self.assertIn("GNF", curriculum.contexte_pays_note("guinee", "lycee"))
        self.assertIn("FCFA", curriculum.contexte_pays_note("mali", "college"))
        self.assertEqual(curriculum.contexte_pays_note("inconnu", "lycee"), "")
        self.assertEqual(curriculum.pays_avec_preposition("cote_ivoire"), "en Côte d'Ivoire")


class TestRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app as app_module
        cls.client = app_module.app.test_client()

    def test_lecon_enrichie(self):
        r = self.client.get("/api/cours/cote-ivoire-college-mathematiques-calcul-litteral")
        self.assertEqual(r.status_code, 200)
        self.assertIn("exercices", r.get_json())

    def test_lecon_inconnue(self):
        self.assertEqual(self.client.get("/api/cours/nexiste-pas").status_code, 404)

    def test_methodes(self):
        r = self.client.get("/api/methodes?niveau=lycee&matiere=Philosophie&pays=mali")
        ids = [f["id"] for f in r.get_json()]
        self.assertIn("dissertation-philo", ids)
        r = self.client.get("/api/methodes/dissertation-philo")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/api/methodes/inconnue").status_code, 404)

    def test_curriculum_codes_inchanges(self):
        data = self.client.get("/api/curriculum").get_json()
        self.assertEqual(
            [p["code"] for p in data["pays"]],
            ["mali", "senegal", "cote_ivoire", "burkina_faso", "benin", "guinee"],
        )


if __name__ == "__main__":
    unittest.main()
