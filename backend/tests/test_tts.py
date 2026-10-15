"""Tests de la synthese vocale serveur (sans appel reseau : la voix Microsoft
est remplacee par une fausse fonction).

    cd backend
    python -m unittest discover tests -v
"""
import os
import sys
import tempfile
import unittest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="lp-tests-"))

import tts_server  # noqa: E402


class TestVoix(unittest.TestCase):
    def setUp(self):
        self._orig = (tts_server._edge, tts_server._piper, tts_server.PIPER_ENABLED, tts_server.CACHE_DIR)
        tts_server.CACHE_DIR = tempfile.mkdtemp(prefix="lp-tts-")
        tts_server.PIPER_ENABLED = False
        self.appels_piper = 0

        def faux_piper(text, rate):
            self.appels_piper += 1
            return b"WAV"
        tts_server._piper = faux_piper

    def tearDown(self):
        tts_server._edge, tts_server._piper, tts_server.PIPER_ENABLED, tts_server.CACHE_DIR = self._orig

    def test_voix_microsoft_puis_cache(self):
        appels = []
        tts_server._edge = lambda t, r: appels.append(t) or b"MP3"
        self.assertEqual(tts_server.synthesize("Bonjour.", "", 0.9), (b"MP3", "mp3"))
        self.assertEqual(tts_server.synthesize("Bonjour.", "", 0.9), (b"MP3", "mp3"))
        self.assertEqual(len(appels), 1)  # le 2e passage vient du cache

    def test_piper_desactive_par_defaut(self):
        def bloque(t, r):
            raise RuntimeError("403")
        tts_server._edge = bloque
        with self.assertRaises(RuntimeError):
            tts_server.synthesize("Texte jamais lu.", "", 0.9)
        self.assertEqual(self.appels_piper, 0)  # pas de chargement du modele en memoire

    def test_ancien_audio_piper_ignore_si_microsoft_repond(self):
        tts_server.PIPER_ENABLED = True
        def bloque(t, r):
            raise RuntimeError("403")
        tts_server._edge = bloque
        self.assertEqual(tts_server.synthesize("Salut.", "", 0.9), (b"WAV", "wav"))
        tts_server._edge = lambda t, r: b"MP3"
        self.assertEqual(tts_server.synthesize("Salut.", "", 0.9), (b"MP3", "mp3"))


if __name__ == "__main__":
    unittest.main()
