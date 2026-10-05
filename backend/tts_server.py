"""Synthese vocale cote serveur : voix MASCULINE francaise identique sur tous
les telephones (la voix du systeme Android ne permet pas de garantir le genre).

Deux fournisseurs, dans cet ordre :
 - Azure Speech (officiel) si AZURE_SPEECH_KEY + AZURE_SPEECH_REGION sont definis ;
 - sinon edge-tts (voix neuronales Microsoft, sans cle).
Voix par defaut : fr-FR-HenriNeural (modifiable via TTS_VOICE).

Les MP3 sont mis en cache sur disque (DATA_DIR/tts_cache) : un meme texte,
par exemple une reponse ecoutee par plusieurs eleves, n'est synthetise qu'une fois.
"""
import asyncio
import hashlib
import os
import threading
import time

import requests

from paths import DATA_DIR

VOICE = os.environ.get("TTS_VOICE", "fr-FR-HenriNeural")
AZURE_KEY = os.environ.get("AZURE_SPEECH_KEY", "")
AZURE_REGION = os.environ.get("AZURE_SPEECH_REGION", "")
CACHE_DIR = os.path.join(DATA_DIR, "tts_cache")
CACHE_MAX_BYTES = 300 * 1024 * 1024
MAX_CHARS = 2500

_lock = threading.Lock()


def _cache_path(text: str) -> str:
    key = hashlib.sha256((VOICE + "|" + text).encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, key + ".mp3")


def _prune_cache():
    """Supprime les fichiers les plus anciens au-dela de CACHE_MAX_BYTES."""
    files = []
    for name in os.listdir(CACHE_DIR):
        p = os.path.join(CACHE_DIR, name)
        try:
            st = os.stat(p)
            files.append((st.st_mtime, st.st_size, p))
        except OSError:
            continue
    total = sum(f[1] for f in files)
    for _, size, p in sorted(files):
        if total <= CACHE_MAX_BYTES:
            break
        try:
            os.remove(p)
            total -= size
        except OSError:
            pass


def _azure(text: str) -> bytes:
    ssml = (
        "<speak version='1.0' xml:lang='fr-FR'>"
        f"<voice name='{VOICE}'><prosody rate='-5%'>"
        + text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        + "</prosody></voice></speak>"
    )
    r = requests.post(
        f"https://{AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1",
        headers={
            "Ocp-Apim-Subscription-Key": AZURE_KEY,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
            "User-Agent": "jpa-assistant-scolaire",
        },
        data=ssml.encode("utf-8"),
        timeout=30,
    )
    r.raise_for_status()
    return r.content


def _edge(text: str) -> bytes:
    import edge_tts

    async def run() -> bytes:
        out = bytearray()
        async for chunk in edge_tts.Communicate(text, VOICE, rate="-5%").stream():
            if chunk["type"] == "audio":
                out.extend(chunk["data"])
        return bytes(out)

    return asyncio.run(run())


def synthesize(text: str) -> bytes:
    """Retourne un MP3 (leve une exception si tous les fournisseurs echouent)."""
    text = text.strip()[:MAX_CHARS]
    if not text:
        raise ValueError("texte vide")
    path = _cache_path(text)
    if os.path.exists(path):
        os.utime(path, None)
        with open(path, "rb") as f:
            return f.read()

    audio = b""
    if AZURE_KEY and AZURE_REGION:
        try:
            audio = _azure(text)
        except Exception:
            audio = b""
    if not audio:
        audio = _edge(text)
    if not audio:
        raise RuntimeError("synthese vide")

    with _lock:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(audio)
        os.replace(tmp, path)
        _prune_cache()
    return audio


# Limitation simple par IP (fenetre glissante) : la synthese coute du temps
# serveur (et de l'argent avec Azure), on evite qu'un script la sature.
_hits: dict = {}
RATE_MAX = 40
RATE_WINDOW = 600  # secondes


def allow(ip: str) -> bool:
    now = time.time()
    with _lock:
        recent = [t for t in _hits.get(ip, []) if now - t < RATE_WINDOW]
        if len(recent) >= RATE_MAX:
            _hits[ip] = recent
            return False
        recent.append(now)
        _hits[ip] = recent
        return True
