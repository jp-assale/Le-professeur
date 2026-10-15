"""Synthese vocale cote serveur : voix MASCULINE francaise identique sur tous
les telephones (la voix du systeme Android ne permet pas de garantir le genre).

Fournisseurs, dans cet ordre :
 1. Azure Speech (officiel) si AZURE_SPEECH_KEY + AZURE_SPEECH_REGION sont definis ;
 2. edge-tts : voix neuronale Microsoft fr-FR-HenriNeural, sans cle (acces non
    officiel, peut etre bloque a tout moment) ;
 3. Piper : voix libre « tom » (masculine), hebergee sur notre serveur, sans
    compte ni quota. Le modele (~63 Mo, licence AGPLv3) est telecharge au premier
    usage dans DATA_DIR/piper, il n'est pas dans le depot. DESACTIVE par defaut
    (TTS_PIPER=1 pour l'activer) : voix robotique peu appreciee, et son
    chargement en memoire (~190 Mo par processus) a fait redemarrer le serveur
    de 512 Mo le 15/10/2026 quand edge-tts etait bloque. Sans lui, si Microsoft
    ne repond pas, l'appli lit avec la voix du telephone.

Si edge-tts renvoie « 403 », mettre a jour le paquet (requirements.txt) :
Microsoft change regulierement le jeton attendu (bloque en 7.2.8, repare en 7.3.1).

Les audios sont mis en cache sur disque (DATA_DIR/tts_cache) : un meme texte,
par exemple une reponse ecoutee par plusieurs eleves, n'est synthetise qu'une fois.
"""
import asyncio
import hashlib
import io
import os
import threading
import time
import wave

import requests

from paths import DATA_DIR

VOICE = os.environ.get("TTS_VOICE", "fr-FR-HenriNeural")
AZURE_KEY = os.environ.get("AZURE_SPEECH_KEY", "")
AZURE_REGION = os.environ.get("AZURE_SPEECH_REGION", "")
CACHE_DIR = os.path.join(DATA_DIR, "tts_cache")
CACHE_MAX_BYTES = 300 * 1024 * 1024
CACHE_MAX_AGE_DAYS = 14
MAX_CHARS = 2500
EDGE_TIMEOUT = 20  # secondes avant de basculer sur Piper

PIPER_ENABLED = os.environ.get("TTS_PIPER", "0") == "1"
PIPER_DIR = os.path.join(DATA_DIR, "piper")
PIPER_NAME = "fr_FR-tom-medium"
PIPER_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/tom/medium/" + PIPER_NAME

_lock = threading.Lock()
_piper_lock = threading.Lock()  # un seul chargement du modele, meme avec 32 fils


def clamp_rate(value) -> float:
    """Vitesse demandee par l'appli, bornee (1 = normale)."""
    try:
        return round(min(1.1, max(0.6, float(value))), 2)
    except (TypeError, ValueError):
        return 0.9


def _pct(rate: float) -> str:
    """Vitesse -> pourcentage relatif accepte par Azure / edge-tts (« -28% »)."""
    return f"{round((rate - 1) * 100):+d}%"


def _cache_path(text: str, ext: str, rate: float) -> str:
    # mp3 = voix Microsoft (VOICE), wav = voix Piper : cles distinctes, pour
    # qu'un changement de VOICE ne ressorte jamais un audio d'une autre voix.
    voix = VOICE if ext == "mp3" else PIPER_NAME
    key = hashlib.sha256((voix + "|" + str(rate) + "|" + text).encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, key + "." + ext)


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
    # Conservation limitee : un audio de plus de CACHE_MAX_AGE_DAYS jours est supprime
    # (annonce dans privacy.html), meme si la taille maximale n'est pas atteinte.
    expired = time.time() - CACHE_MAX_AGE_DAYS * 86400
    for mtime, size, p in files:
        if mtime < expired:
            try:
                os.remove(p)
            except OSError:
                pass
    files = [f for f in files if f[0] >= expired]
    total = sum(f[1] for f in files)
    for _, size, p in sorted(files):
        if total <= CACHE_MAX_BYTES:
            break
        try:
            os.remove(p)
            total -= size
        except OSError:
            pass


def _azure(text: str, rate: float) -> bytes:
    ssml = (
        "<speak version='1.0' xml:lang='fr-FR'>"
        f"<voice name='{VOICE}'><prosody rate='{_pct(rate)}'>"
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


def _edge(text: str, rate: float) -> bytes:
    import edge_tts

    async def run() -> bytes:
        out = bytearray()
        async for chunk in edge_tts.Communicate(text, VOICE, rate=_pct(rate)).stream():
            if chunk["type"] == "audio":
                out.extend(chunk["data"])
        return bytes(out)

    return asyncio.run(asyncio.wait_for(run(), EDGE_TIMEOUT))


_piper_voice = None


def _piper_load():
    with _piper_lock:
        return _piper_load_locked()


def _piper_load_locked():
    global _piper_voice
    if _piper_voice is not None:
        return _piper_voice
    from piper import PiperVoice

    os.makedirs(PIPER_DIR, exist_ok=True)
    for ext in (".onnx", ".onnx.json"):
        path = os.path.join(PIPER_DIR, PIPER_NAME + ext)
        if os.path.exists(path):
            continue
        r = requests.get(PIPER_URL + ext, timeout=120)
        r.raise_for_status()
        with open(path + ".tmp", "wb") as f:
            f.write(r.content)
        os.replace(path + ".tmp", path)
    # Session ONNX construite ici plutot que par PiperVoice.load : sans le pool
    # memoire (arena) d'onnxruntime, un worker passe de ~350 Mo a ~95 Mo apres
    # une synthese (limite Render : 512 Mo pour tous les workers).
    import json
    from pathlib import Path

    import onnxruntime
    from piper.config import PiperConfig
    from piper.voice import ESPEAK_DATA_DIR

    model = os.path.join(PIPER_DIR, PIPER_NAME + ".onnx")
    with open(model + ".json", encoding="utf-8") as f:
        config = PiperConfig.from_dict(json.load(f))
    opts = onnxruntime.SessionOptions()
    opts.enable_cpu_mem_arena = False
    opts.enable_mem_pattern = False
    opts.intra_op_num_threads = 1
    session = onnxruntime.InferenceSession(model, sess_options=opts, providers=["CPUExecutionProvider"])
    _piper_voice = PiperVoice(config=config, session=session, espeak_data_dir=Path(ESPEAK_DATA_DIR),
                              download_dir=Path(PIPER_DIR))
    return _piper_voice


def _piper(text: str, rate: float) -> bytes:
    from piper import SynthesisConfig

    voice = _piper_load()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        # length_scale > 1 = parole plus lente (1 / vitesse).
        voice.synthesize_wav(text, wav, syn_config=SynthesisConfig(length_scale=1.0 / rate))
    return buf.getvalue()


def _read_cache(text: str, ext: str, rate: float) -> bytes | None:
    path = _cache_path(text, ext, rate)
    if not os.path.exists(path):
        return None
    os.utime(path, None)
    with open(path, "rb") as f:
        return f.read()


def synthesize(text: str, engine: str = "", rate: float = 0.9) -> tuple:
    """Retourne (audio, extension) : mp3 (Azure/edge) ou wav (Piper).
    `engine` force un fournisseur sans passer par le cache, pour les tests
    admin : "microsoft" (Azure/edge) ou "piper"."""
    text = text.strip()[:MAX_CHARS]
    if not text:
        raise ValueError("texte vide")
    if not engine:
        cached = _read_cache(text, "mp3", rate)
        if cached:
            return cached, "mp3"

    providers = []
    if engine != "piper":
        if AZURE_KEY and AZURE_REGION:
            providers.append((_azure, "mp3"))
        providers.append((_edge, "mp3"))
    if PIPER_ENABLED and engine != "microsoft":
        # Voix de secours : un audio Piper deja en cache n'est servi que si
        # Microsoft ne repond pas (sinon la voix choisie reprendrait le dessus).
        if not engine:
            providers.append((lambda t, r: _read_cache(t, "wav", r) or b"", "wav"))
        providers.append((_piper, "wav"))

    audio, ext = b"", ""
    for fn, e in providers:
        try:
            audio = fn(text, rate)
        except Exception:
            audio = b""
        if audio:
            ext = e
            break
    if not audio:
        raise RuntimeError("synthese impossible")

    if not engine:
        with _lock:
            os.makedirs(CACHE_DIR, exist_ok=True)
            path = _cache_path(text, ext, rate)
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(audio)
            os.replace(tmp, path)
            _prune_cache()
    return audio, ext


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
