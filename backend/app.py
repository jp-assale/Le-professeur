import base64
import json
import os
import re

import requests
import sentry_sdk
from anthropic import Anthropic
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, request, send_from_directory
from flask_cors import CORS
from sentry_sdk.integrations.flask import FlaskIntegration

import cinetpay
import pdf_library
import payments_store
import progress_store
import quota_store
import reports
import subscription
import usage_log
from curriculum import MATIERES, NIVEAUX, PAYS, niveau_label

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Surveillance d'erreurs en production (Sentry, gratuit jusqu'a 5k evenements/
# mois) - desactive automatiquement si SENTRY_DSN n'est pas defini, donc sans
# effet en local/dev tant qu'on n'a pas cree de compte Sentry et rempli .env.
SENTRY_DSN = os.environ.get("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[FlaskIntegration()],
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        traces_sample_rate=0.0,  # pas de suivi de performance, erreurs uniquement
        send_default_pii=False,  # ne jamais remonter le contenu des questions/photos des eleves
    )

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
DAILY_FREE_LIMIT = int(os.environ.get("DAILY_FREE_LIMIT", "5"))
MODEL = os.environ.get("ASSISTANT_MODEL", "claude-haiku-4-5-20251001")

# Secret partage pour proteger l'ajout/suppression de PDF (toi seul devrait
# pouvoir en ajouter). A definir dans .env - choisis une chaine aleatoire.
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")

# URL publique de CE backend (pas localhost) - obligatoire pour que CinetPay
# puisse appeler notify_url depuis internet. A definir dans .env une fois le
# backend deploye publiquement (voir README).
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
SUBSCRIPTION_PRICE_FCFA = int(os.environ.get("SUBSCRIPTION_PRICE_FCFA", "1000"))

# Garde-fou anti-abus (faiblesse #8) : desinstaller l'appli reinitialise le quota
# par appareil (localStorage), donc on ajoute un plafond secondaire par IP,
# plus large pour ne pas penaliser les reseaux partages (cyber, ecole).
IP_DAILY_LIMIT = DAILY_FREE_LIMIT * int(os.environ.get("IP_LIMIT_MULTIPLIER", "6"))

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
# L'appli Android empaquetee (Capacitor) appelle ce backend depuis une autre
# origine (https://localhost dans la WebView) - CORS doit etre ouvert sur
# /api/* pour que ces appels ne soient pas bloques par le navigateur.
CORS(app, resources={r"/api/*": {"origins": "*"}})
client = Anthropic(api_key=ANTHROPIC_API_KEY, timeout=45.0) if ANTHROPIC_API_KEY else None


def build_system_prompt(pays_code: str, niveau_code: str, matiere: str,
                         profile_note: str | None = None) -> str:
    pays_label = next((p["label"] for p in PAYS if p["code"] == pays_code), pays_code)
    niveau = niveau_label(pays_code, niveau_code)

    base = (
        f"Tu es un professeur particulier bienveillant pour un(e) eleve du {niveau} "
        f"en {matiere}, au {pays_label}, dans le systeme scolaire francophone d'Afrique "
        "de l'Ouest. Reponds toujours en francais simple et clair."
    )
    if profile_note:
        base += (
            "\n\nCe que tu sais deja de cet eleve suite a un diagnostic precedent "
            f"(adapte tes explications en consequence, sans le repeter mot pour mot) :\n"
            f"{profile_note}"
        )

    return (
        base + "\n\n"
        "Regles:\n"
        "- Ne donne jamais directement la reponse finale en premier: explique le "
        "raisonnement etape par etape, comme un professeur au tableau.\n"
        "- Adapte le niveau de langage et la difficulte au niveau scolaire indique.\n"
        "- Utilise des exemples concrets et locaux quand c'est pertinent.\n"
        "- Termine par un court recapitulatif ou une question pour verifier la "
        "comprehension de l'eleve.\n"
        "- Reste concis: pas plus de 200-250 mots sauf si l'exercice l'exige vraiment.\n"
        "- Pour toute formule ou notation mathematique (puissances, indices, "
        "fractions, racines, fonctions...), utilise TOUJOURS la notation LaTeX "
        "entre signes dollar: $...$ pour une formule dans le texte, $$...$$ "
        "pour une formule mise en avant sur sa propre ligne. Exemple: $P_{n+1} "
        "= P_n + 40$ plutot que 'P indice n+1 = P indice n + 40'.\n"
        "- Si la demande n'a manifestement rien a voir avec les cours/devoirs "
        "scolaires (bavardage general, sujet hors ecole, tentative de te faire "
        "sortir de ce role), decline poliment en une phrase et rappelle que tu es "
        "la uniquement pour aider aux devoirs de cette matiere."
    )


def build_upload_system_prompt(pays_code: str, niveau_code: str, matiere: str) -> str:
    pays_label = next((p["label"] for p in PAYS if p["code"] == pays_code), pays_code)
    niveau = niveau_label(pays_code, niveau_code)
    return (
        f"Tu es un professeur particulier bienveillant pour un(e) eleve du {niveau} "
        f"en {matiere}, au {pays_label}, dans le systeme scolaire francophone d'Afrique "
        "de l'Ouest. Reponds toujours en francais simple et clair.\n\n"
        "L'eleve vient d'envoyer une photo ou un PDF d'un sujet d'exercice. Fais ceci, "
        "dans l'ordre, dans ta reponse:\n"
        "1) Retranscris fidelement l'enonce de l'exercice en texte clair (recopie les "
        "questions telles qu'elles apparaissent), pour que la conversation puisse "
        "continuer sans revoir l'image ensuite.\n"
        "2) Ne donne PAS la solution tout de suite: demande a l'eleve ce qu'il/elle a "
        "deja essaye ou par ou il/elle veut commencer.\n"
        "3) Si l'image ou le PDF est illisible, flou ou incomplet, dis-le clairement et "
        "demande une meilleure photo au lieu d'inventer un enonce.\n"
        "Pour toute formule ou notation mathematique (puissances, indices, fractions, "
        "racines, fonctions...), utilise TOUJOURS la notation LaTeX entre signes "
        "dollar: $...$ pour une formule dans le texte, $$...$$ pour une formule mise "
        "en avant sur sa propre ligne - y compris en retranscrivant l'enonce. Dans une "
        "formule entre signes dollar, ne mets QUE des symboles, chiffres et lettres de "
        "variables - jamais de mots francais entiers (ils restent en dehors des $...$, "
        "sinon la formule devient trop longue pour tenir sur un petit ecran de "
        "telephone).\n"
        "Reste concis: 250-300 mots maximum pour ce premier message."
    )


def build_quiz_system_prompt(pays_code: str, niveau_code: str, matiere: str, sujet: str, n_questions: int) -> str:
    pays_label = next((p["label"] for p in PAYS if p["code"] == pays_code), pays_code)
    niveau = niveau_label(pays_code, niveau_code)
    return (
        f"Tu es un professeur pour un(e) eleve du {niveau} en {matiere}, au {pays_label}.\n\n"
        f"Genere un quiz de {n_questions} questions a choix multiples (QCM) sur ce sujet :\n"
        f"---\n{sujet}\n---\n\n"
        "Consignes :\n"
        "- Chaque question a exactement 4 options, une seule correcte.\n"
        "- Varie la difficulte, de facile a plus exigeant.\n"
        "- Reponds UNIQUEMENT avec un objet JSON valide, sans texte autour, sans balises "
        "markdown ```, exactement dans ce format :\n"
        '{"questions": [{"question": "...", "options": ["...", "...", "...", "..."], '
        '"correct_index": 0, "explication": "..."}]}\n'
        "L'explication justifie en une phrase pourquoi la reponse est correcte.\n"
        "Pour toute formule (puissances, indices, fractions, formules chimiques...), "
        "utilise la notation LaTeX entre signes dollar: $...$. Dans une formule entre "
        "signes dollar, ne mets QUE des symboles, chiffres et lettres de variables - "
        "jamais de mots francais entiers, qui restent en dehors des $...$."
    )


def _parse_quiz_json(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def build_correction_copie_prompt(pays_code: str, niveau_code: str, matiere: str, bareme: int) -> str:
    pays_label = next((p["label"] for p in PAYS if p["code"] == pays_code), pays_code)
    niveau = niveau_label(pays_code, niveau_code)
    return (
        f"Tu es un examinateur qui corrige la copie d'un(e) eleve du {niveau} en {matiere}, "
        f"au {pays_label}. Reponds toujours en francais simple et clair.\n\n"
        "L'eleve t'envoie sa copie (texte ou photo), qui contient generalement a la fois la "
        "question et sa reponse. Identifie d'abord la question traitee, puis corrige.\n\n"
        f"Note la copie sur {bareme} points.\n\n"
        "Structure ta correction exactement ainsi :\n"
        f"1) Une premiere ligne exactement au format : NOTE: X/{bareme}\n"
        "2) Le detail du bareme applique (points accordes par partie/question)\n"
        "3) Les points forts de la copie\n"
        "4) Les erreurs precises a corriger, avec explication pedagogique\n"
        "Sois juste mais bienveillant, comme un vrai correcteur d'examen - ni trop severe, "
        "ni complaisant.\n\n"
        "Si la question traitee n'est pas identifiable du tout dans ce qui est fourni, "
        "dis-le clairement et demande a l'eleve de preciser plutot que d'inventer un enonce."
    )


def build_profile_system_prompt(pays_code: str, niveau_code: str, matiere: str) -> str:
    pays_label = next((p["label"] for p in PAYS if p["code"] == pays_code), pays_code)
    niveau = niveau_label(pays_code, niveau_code)
    return (
        f"Tu es un professeur qui vient de faire passer un diagnostic a un(e) eleve du "
        f"{niveau} en {matiere}, au {pays_label}. Voici les questions posees, la reponse "
        "de l'eleve et la bonne reponse pour chacune.\n\n"
        "Redige un court paragraphe (60 a 80 mots), adresse directement a l'eleve (tutoiement), "
        "resumant ses points forts et ses lacunes precises a travailler en priorite. Sois "
        "bienveillant, concret, et evite le jargon."
    )


ALLOWED_UPLOAD_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}
MAX_UPLOAD_B64_LEN = 12_000_000  # ~9 Mo de fichier brut une fois decode
UPLOAD_QUESTION_WEIGHT = int(os.environ.get("UPLOAD_QUESTION_WEIGHT", "2"))


def _client_ip() -> str:
    # Derriere un proxy/load balancer en prod, verifier X-Forwarded-For selon
    # la config d'hebergement plutot que de faire confiance a cet en-tete brut.
    return request.remote_addr or "unknown"


@app.route("/api/upload-exercice", methods=["POST"])
def upload_exercice():
    if client is None:
        return jsonify({
            "error": "ANTHROPIC_API_KEY non configuree cote serveur. "
                     "Voir backend/.env.example."
        }), 500

    payload = request.get_json(silent=True) or {}
    device_id = payload.get("device_id", "")
    pays = payload.get("pays", "mali")
    niveau = payload.get("niveau", "college")
    matiere = payload.get("matiere", "Mathematiques")
    mime_type = payload.get("mime_type", "")
    data_b64 = payload.get("data", "")

    if not device_id:
        return jsonify({"error": "device_id manquant"}), 400
    if mime_type not in ALLOWED_UPLOAD_MIME:
        return jsonify({"error": "Format non supporte. Envoie une photo (jpg/png) ou un PDF."}), 400
    if not data_b64 or len(data_b64) > MAX_UPLOAD_B64_LEN:
        return jsonify({"error": "Fichier manquant ou trop volumineux (max ~9 Mo)."}), 400

    premium = subscription.is_premium(device_id)
    ip_remaining = quota_store.get_remaining(_client_ip(), IP_DAILY_LIMIT)
    remaining_before = quota_store.get_remaining(device_id, DAILY_FREE_LIMIT)

    if not premium and (remaining_before < UPLOAD_QUESTION_WEIGHT or ip_remaining < UPLOAD_QUESTION_WEIGHT):
        return jsonify({
            "error": "quota_depasse",
            "message": "Envoyer un sujet compte pour "
                       f"{UPLOAD_QUESTION_WEIGHT} questions et il ne t'en reste pas "
                       "assez aujourd'hui. Reviens demain, ou passe en illimite "
                       "(bientot disponible via Orange Money / Wave / Moov Money).",
            "remaining": min(remaining_before, ip_remaining),
        }), 429

    system_prompt = build_upload_system_prompt(pays, niveau, matiere)
    block_type = "document" if mime_type == "application/pdf" else "image"
    content = [
        {
            "type": block_type,
            "source": {"type": "base64", "media_type": mime_type, "data": data_b64},
        },
        {
            "type": "text",
            "text": "Voici mon sujet, aide-moi a le comprendre etape par etape.",
        },
    ]

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=900,
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
        )
        answer = "".join(
            block.text for block in response.content if block.type == "text"
        )
        usage_log.log_call(MODEL, "upload-exercice", response.usage.input_tokens, response.usage.output_tokens)
    except Exception as exc:
        return jsonify({"error": f"Erreur IA: {exc}"}), 502

    if premium:
        remaining_after = remaining_before
    else:
        quota_store.consume(_client_ip(), IP_DAILY_LIMIT, weight=UPLOAD_QUESTION_WEIGHT)
        remaining_after = quota_store.consume(device_id, DAILY_FREE_LIMIT, weight=UPLOAD_QUESTION_WEIGHT)

    return jsonify({"answer": answer, "remaining": remaining_after, "premium": premium})


QUIZ_QUESTION_COUNT_DEFAULT = 4
QUIZ_QUESTION_COUNT_DIAGNOSTIC = 6


@app.route("/api/quiz", methods=["POST"])
def generate_quiz():
    if client is None:
        return jsonify({
            "error": "ANTHROPIC_API_KEY non configuree cote serveur. "
                     "Voir backend/.env.example."
        }), 500

    payload = request.get_json(silent=True) or {}
    device_id = payload.get("device_id", "")
    pays = payload.get("pays", "mali")
    niveau = payload.get("niveau", "college")
    matiere = payload.get("matiere", "Mathematiques")
    sujet = (payload.get("sujet") or "").strip()
    diagnostic = bool(payload.get("diagnostic"))

    if not device_id:
        return jsonify({"error": "device_id manquant"}), 400

    if diagnostic and not sujet:
        sujet = (
            f"Notions de base attendues en {matiere} pour ce niveau scolaire "
            "(couvre plusieurs notions differentes du programme)."
        )
    if not sujet:
        return jsonify({"error": "sujet manquant"}), 400

    premium = subscription.is_premium(device_id)
    ip_remaining = quota_store.get_remaining(_client_ip(), IP_DAILY_LIMIT)
    remaining_before = quota_store.get_remaining(device_id, DAILY_FREE_LIMIT)

    if not premium and (remaining_before <= 0 or ip_remaining <= 0):
        return jsonify({
            "error": "quota_depasse",
            "message": "Tu as utilise tes questions gratuites du jour. Reviens demain, "
                       "ou passe en illimite.",
            "remaining": min(remaining_before, ip_remaining),
        }), 429

    n_questions = QUIZ_QUESTION_COUNT_DIAGNOSTIC if diagnostic else QUIZ_QUESTION_COUNT_DEFAULT
    system_prompt = build_quiz_system_prompt(pays, niveau, matiere, sujet[:4000], n_questions)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": "Genere le quiz au format demande."}],
        )
        raw = "".join(b.text for b in response.content if b.type == "text")
        quiz = _parse_quiz_json(raw)
        usage_log.log_call(MODEL, "quiz", response.usage.input_tokens, response.usage.output_tokens)
    except (json.JSONDecodeError, IndexError):
        return jsonify({"error": "Reponse IA invalide, reessaie."}), 502
    except Exception as exc:
        return jsonify({"error": f"Erreur IA: {exc}"}), 502

    if premium:
        remaining_after = remaining_before
    else:
        quota_store.consume(_client_ip(), IP_DAILY_LIMIT)
        remaining_after = quota_store.consume(device_id, DAILY_FREE_LIMIT)

    return jsonify({"questions": quiz.get("questions", []), "remaining": remaining_after, "premium": premium})


@app.route("/api/progress/log-quiz", methods=["POST"])
def log_quiz_result():
    payload = request.get_json(silent=True) or {}
    device_id = payload.get("device_id", "")
    pays = payload.get("pays", "mali")
    niveau = payload.get("niveau", "college")
    matiere = payload.get("matiere", "Mathematiques")
    score = payload.get("score")
    total = payload.get("total")

    if not device_id or not isinstance(score, int) or not isinstance(total, int) or total <= 0:
        return jsonify({"error": "parametres invalides"}), 400

    progress_store.log_event(device_id, "quiz", pays, niveau, matiere, score=score, total=total)
    return jsonify({"ok": True})


@app.route("/api/progress", methods=["GET"])
def get_progress_route():
    device_id = request.args.get("device_id", "")
    if not device_id:
        return jsonify({"error": "device_id manquant"}), 400
    return jsonify(progress_store.get_progress(device_id))


@app.route("/api/diagnostic/complete", methods=["POST"])
def diagnostic_complete():
    if client is None:
        return jsonify({
            "error": "ANTHROPIC_API_KEY non configuree cote serveur. "
                     "Voir backend/.env.example."
        }), 500

    payload = request.get_json(silent=True) or {}
    device_id = payload.get("device_id", "")
    pays = payload.get("pays", "mali")
    niveau = payload.get("niveau", "college")
    matiere = payload.get("matiere", "Mathematiques")
    results = payload.get("results") or []
    score = payload.get("score")
    total = payload.get("total")

    if not device_id or not isinstance(score, int) or not isinstance(total, int) or total <= 0:
        return jsonify({"error": "parametres invalides"}), 400
    if not results:
        return jsonify({"error": "results manquant"}), 400

    progress_store.log_event(device_id, "diagnostic", pays, niveau, matiere, score=score, total=total)

    lines = []
    for i, r in enumerate(results[:10], 1):
        statut = "correcte" if r.get("correct") else "incorrecte"
        lines.append(
            f"{i}. {r.get('question', '')}\n   Reponse eleve : {r.get('user_answer', '')} ({statut})\n"
            f"   Bonne reponse : {r.get('correct_answer', '')}"
        )
    results_text = "\n".join(lines)

    system_prompt = build_profile_system_prompt(pays, niveau, matiere)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=400,
            system=system_prompt,
            messages=[{"role": "user", "content": results_text}],
        )
        note = "".join(b.text for b in response.content if b.type == "text")
        usage_log.log_call(MODEL, "diagnostic-profile", response.usage.input_tokens, response.usage.output_tokens)
    except Exception as exc:
        return jsonify({"error": f"Erreur IA: {exc}"}), 502

    progress_store.set_profile_note(device_id, matiere, note)
    return jsonify({"note": note})


@app.route("/api/correction-copie", methods=["POST"])
def correction_copie():
    if client is None:
        return jsonify({
            "error": "ANTHROPIC_API_KEY non configuree cote serveur. "
                     "Voir backend/.env.example."
        }), 500

    payload = request.get_json(silent=True) or {}
    device_id = payload.get("device_id", "")
    pays = payload.get("pays", "mali")
    niveau = payload.get("niveau", "college")
    matiere = payload.get("matiere", "Mathematiques")
    reponse_texte = (payload.get("reponse_texte") or "").strip()
    mime_type = payload.get("mime_type")
    data_b64 = payload.get("data")
    bareme = payload.get("bareme") or 20

    if not device_id:
        return jsonify({"error": "device_id manquant"}), 400
    if not reponse_texte and not (mime_type and data_b64):
        return jsonify({"error": "reponse manquante (texte ou photo)"}), 400
    if not isinstance(bareme, int) or bareme <= 0:
        bareme = 20

    has_photo = bool(mime_type and data_b64)
    weight = UPLOAD_QUESTION_WEIGHT if has_photo else 1

    premium = subscription.is_premium(device_id)
    ip_remaining = quota_store.get_remaining(_client_ip(), IP_DAILY_LIMIT)
    remaining_before = quota_store.get_remaining(device_id, DAILY_FREE_LIMIT)

    if not premium and (remaining_before < weight or ip_remaining < weight):
        return jsonify({
            "error": "quota_depasse",
            "message": "Il ne te reste pas assez de questions gratuites aujourd'hui pour "
                       "cette correction. Reviens demain, ou passe en illimite.",
            "remaining": min(remaining_before, ip_remaining),
        }), 429

    if has_photo and mime_type not in ALLOWED_UPLOAD_MIME:
        return jsonify({"error": "Format de fichier non supporte."}), 400

    system_prompt = build_correction_copie_prompt(pays, niveau, matiere, bareme)
    content = [{"type": "text", "text": "Voici la copie de l'eleve (question et reponse) :"}]
    if reponse_texte:
        content.append({"type": "text", "text": reponse_texte})
    if has_photo:
        block_type = "document" if mime_type == "application/pdf" else "image"
        content.append({
            "type": block_type,
            "source": {"type": "base64", "media_type": mime_type, "data": data_b64},
        })

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
        )
        answer = "".join(b.text for b in response.content if b.type == "text")
        usage_log.log_call(MODEL, "correction-copie", response.usage.input_tokens, response.usage.output_tokens)
    except Exception as exc:
        return jsonify({"error": f"Erreur IA: {exc}"}), 502

    match = re.search(r"NOTE:\s*(\d+(?:[.,]\d+)?)\s*/\s*(\d+)", answer)
    if match:
        try:
            note_score = round(float(match.group(1).replace(",", ".")))
            note_total = int(match.group(2))
            progress_store.log_event(device_id, "correction", pays, niveau, matiere,
                                      score=note_score, total=note_total)
        except ValueError:
            pass

    if premium:
        remaining_after = remaining_before
    else:
        quota_store.consume(_client_ip(), IP_DAILY_LIMIT, weight=weight)
        remaining_after = quota_store.consume(device_id, DAILY_FREE_LIMIT, weight=weight)

    return jsonify({"answer": answer, "remaining": remaining_after, "premium": premium})


@app.route("/api/curriculum", methods=["GET"])
def get_curriculum():
    return jsonify({"pays": PAYS, "niveaux": NIVEAUX, "matieres": MATIERES})


@app.route("/api/pdf-sujets", methods=["GET"])
def get_pdf_sujets():
    pays = request.args.get("pays") or None
    niveau = request.args.get("niveau") or None
    matiere = request.args.get("matiere") or None
    return jsonify(pdf_library.list_pdf_sujets(pays, niveau, matiere))


@app.route("/api/pdf-sujets/<sujet_id>/fichier", methods=["GET"])
def get_pdf_sujet_file(sujet_id):
    entry = pdf_library.get_pdf_sujet(sujet_id)
    if not entry:
        return jsonify({"error": "PDF introuvable"}), 404
    if entry.get("url"):
        # PDF heberge ailleurs (ex: GitHub Releases) - trop volumineux pour
        # etre committe dans le depot. On redirige simplement vers le fichier.
        return redirect(entry["url"], code=302)
    return send_from_directory(
        pdf_library.get_pdf_dir(entry), entry["filename"],
        mimetype="application/pdf",
        download_name=entry["titre"] + ".pdf",
    )


@app.route("/api/pdf-sujets/<sujet_id>/corriger", methods=["POST"])
def pdf_sujet_corriger(sujet_id):
    """Recupere le PDF cote serveur (local ou externe) et lance la correction
    IA directement, sans faire telecharger/reuploader le fichier par l'eleve -
    important vu la taille de certains PDF et le cout des donnees mobiles."""
    if client is None:
        return jsonify({
            "error": "ANTHROPIC_API_KEY non configuree cote serveur. "
                     "Voir backend/.env.example."
        }), 500

    entry = pdf_library.get_pdf_sujet(sujet_id)
    if not entry:
        return jsonify({"error": "PDF introuvable"}), 404

    payload = request.get_json(silent=True) or {}
    device_id = payload.get("device_id", "")
    pays = payload.get("pays") or entry["pays"]
    niveau = payload.get("niveau") or entry["niveau"]
    matiere = payload.get("matiere") or entry["matiere"]

    if not device_id:
        return jsonify({"error": "device_id manquant"}), 400

    premium = subscription.is_premium(device_id)
    ip_remaining = quota_store.get_remaining(_client_ip(), IP_DAILY_LIMIT)
    remaining_before = quota_store.get_remaining(device_id, DAILY_FREE_LIMIT)
    weight = UPLOAD_QUESTION_WEIGHT

    if not premium and (remaining_before < weight or ip_remaining < weight):
        return jsonify({
            "error": "quota_depasse",
            "message": "Ouvrir ce sujet compte pour "
                       f"{weight} questions et il ne t'en reste pas assez "
                       "aujourd'hui. Reviens demain, ou passe en illimite.",
            "remaining": min(remaining_before, ip_remaining),
        }), 429

    # Meme sujet tague avec les memes pays/niveau/matiere que par defaut ->
    # reponse identique pour tout le monde, mise en cache. Si un(e) eleve a un
    # profil different (ex: PDF tague "college" mais eleve en "lycee"), on
    # passe le cache et on regenere avec son contexte precis.
    cache_ok = (pays == entry["pays"] and niveau == entry["niveau"] and matiere == entry["matiere"])
    answer = pdf_library.get_cached_corriger(sujet_id) if cache_ok else None

    if answer is None:
        try:
            if entry.get("url"):
                resp = requests.get(entry["url"], timeout=25)
                resp.raise_for_status()
                file_bytes = resp.content
            else:
                path = os.path.join(pdf_library.get_pdf_dir(entry), entry["filename"])
                with open(path, "rb") as f:
                    file_bytes = f.read()
            data_b64 = base64.b64encode(file_bytes).decode("ascii")
        except Exception as exc:
            return jsonify({"error": f"Impossible de recuperer le PDF: {exc}"}), 502

        system_prompt = build_upload_system_prompt(pays, niveau, matiere)
        content = [
            {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": data_b64},
            },
            {
                "type": "text",
                "text": "Voici mon sujet, aide-moi a le comprendre etape par etape.",
            },
        ]

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1200,
                system=system_prompt,
                messages=[{"role": "user", "content": content}],
            )
            answer = "".join(b.text for b in response.content if b.type == "text")
            usage_log.log_call(MODEL, "pdf-sujet-corriger", response.usage.input_tokens, response.usage.output_tokens)
        except Exception as exc:
            return jsonify({"error": f"Erreur IA: {exc}"}), 502

        if cache_ok:
            pdf_library.set_cached_corriger(sujet_id, answer)

    if premium:
        remaining_after = remaining_before
    else:
        quota_store.consume(_client_ip(), IP_DAILY_LIMIT, weight=weight)
        remaining_after = quota_store.consume(device_id, DAILY_FREE_LIMIT, weight=weight)

    return jsonify({"answer": answer, "remaining": remaining_after, "premium": premium})


def _require_admin():
    token = request.headers.get("X-Admin-Token")
    if not ADMIN_TOKEN:
        return jsonify({"error": "ADMIN_TOKEN non configure cote serveur"}), 500
    if token != ADMIN_TOKEN:
        return jsonify({"error": "Jeton admin incorrect"}), 403
    return None


@app.route("/api/admin/pdf-sujets", methods=["POST"])
def admin_add_pdf_sujet():
    denied = _require_admin()
    if denied:
        return denied

    file = request.files.get("file")
    if not file or file.mimetype != "application/pdf":
        return jsonify({"error": "Fichier PDF manquant ou invalide"}), 400

    file_bytes = file.read()
    if len(file_bytes) > 20 * 1024 * 1024:
        return jsonify({"error": "PDF trop volumineux (max 20 Mo)"}), 400

    try:
        entry = pdf_library.add_pdf_sujet(
            pays=request.form["pays"],
            niveau=request.form["niveau"],
            matiere=request.form["matiere"],
            annee=int(request.form["annee"]),
            titre=request.form["titre"],
            source=request.form.get("source", ""),
            file_bytes=file_bytes,
        )
    except KeyError as exc:
        return jsonify({"error": f"Champ manquant: {exc}"}), 400

    return jsonify(entry), 201


@app.route("/api/admin/pdf-sujets/<sujet_id>", methods=["DELETE"])
def admin_delete_pdf_sujet(sujet_id):
    denied = _require_admin()
    if denied:
        return denied
    ok = pdf_library.delete_pdf_sujet(sujet_id)
    if not ok:
        return jsonify({"error": "PDF introuvable"}), 404
    return jsonify({"ok": True})


@app.route("/api/quota", methods=["GET"])
def get_quota():
    device_id = request.args.get("device_id", "")
    if not device_id:
        return jsonify({"error": "device_id manquant"}), 400
    remaining = quota_store.get_remaining(device_id, DAILY_FREE_LIMIT)
    return jsonify({
        "remaining": remaining,
        "limit": DAILY_FREE_LIMIT,
        "premium": subscription.is_premium(device_id),
    })


@app.route("/api/report", methods=["POST"])
def report():
    """Signalement d'erreur envoye par un eleve (faiblesse #2 : relecture qualite)."""
    payload = request.get_json(silent=True) or {}
    device_id = payload.get("device_id", "")
    context = payload.get("context", "")
    excerpt = payload.get("excerpt", "")
    comment = payload.get("comment", "")
    if not device_id:
        return jsonify({"error": "device_id manquant"}), 400
    reports.add_report(device_id, context, excerpt, comment)
    return jsonify({"ok": True})


@app.route("/api/subscribe", methods=["POST"])
def subscribe():
    """Cree une transaction CinetPay et renvoie l'URL de paiement hebergee.
    N'active PAS premium ici - seul le webhook verifie (voir /api/cinetpay/webhook)
    peut le faire, apres confirmation server-a-server aupres de CinetPay."""
    if not cinetpay.is_configured():
        return jsonify({
            "status": "indisponible",
            "message": "Le paiement en ligne n'est pas encore configure cote "
                       "serveur (CINETPAY_API_KEY / CINETPAY_SITE_ID manquants "
                       "dans .env). Abonnement illimite prevu via Orange Money "
                       "/ Wave / Moov Money.",
        }), 501
    if not PUBLIC_BASE_URL:
        return jsonify({
            "status": "indisponible",
            "message": "Le backend n'est pas encore accessible publiquement "
                       "(PUBLIC_BASE_URL manquant dans .env) - CinetPay ne "
                       "peut pas confirmer un paiement vers un serveur local.",
        }), 501

    payload = request.get_json(silent=True) or {}
    device_id = payload.get("device_id", "")
    if not device_id:
        return jsonify({"error": "device_id manquant"}), 400

    transaction_id = payments_store.create_transaction(device_id)

    try:
        result = cinetpay.create_payment(
            transaction_id=transaction_id,
            amount_fcfa=SUBSCRIPTION_PRICE_FCFA,
            description="Abonnement illimite - JPA Assistant Scolaire",
            notify_url=f"{PUBLIC_BASE_URL}/api/cinetpay/webhook",
            return_url=f"{PUBLIC_BASE_URL}/",
        )
    except Exception as exc:
        return jsonify({"error": f"Erreur CinetPay: {exc}"}), 502

    payment_url = (result.get("data") or {}).get("payment_url")
    if not payment_url:
        return jsonify({"error": "Reponse CinetPay inattendue", "raw": result}), 502

    return jsonify({"payment_url": payment_url, "amount": SUBSCRIPTION_PRICE_FCFA})


@app.route("/api/cinetpay/webhook", methods=["GET", "POST"])
def cinetpay_webhook():
    """Appele par CinetPay apres un paiement. Sert uniquement de declencheur -
    on revalide TOUJOURS aupres de CinetPay (check_transaction) avant de
    debloquer quoi que ce soit, on ne fait jamais confiance au contenu brut
    de cette requete."""
    json_body = request.get_json(silent=True) or {}
    transaction_id = (
        request.values.get("cpm_trans_id")
        or request.values.get("transaction_id")
        or json_body.get("cpm_trans_id")
        or json_body.get("transaction_id")
    )
    if not transaction_id:
        return jsonify({"error": "transaction_id manquant"}), 400

    device_id = payments_store.get_device_id(transaction_id)
    if not device_id:
        return jsonify({"error": "transaction inconnue"}), 404

    try:
        check = cinetpay.check_transaction(transaction_id)
    except Exception as exc:
        return jsonify({"error": f"Erreur verification CinetPay: {exc}"}), 502

    if cinetpay.is_success(check):
        subscription.set_premium(device_id, True)
        payments_store.mark_status(transaction_id, "confirmed")
    else:
        payments_store.mark_status(transaction_id, "failed")

    return jsonify({"ok": True})


@app.route("/api/ask", methods=["POST"])
def ask():
    if client is None:
        return jsonify({
            "error": "ANTHROPIC_API_KEY non configuree cote serveur. "
                     "Voir backend/.env.example."
        }), 500

    payload = request.get_json(silent=True) or {}
    device_id = payload.get("device_id", "")
    pays = payload.get("pays", "mali")
    niveau = payload.get("niveau", "college")
    matiere = payload.get("matiere", "Mathematiques")
    question = (payload.get("question") or "").strip()
    history = payload.get("history") or []

    if not device_id:
        return jsonify({"error": "device_id manquant"}), 400
    if not question:
        return jsonify({"error": "question vide"}), 400
    if len(question) > 2000:
        return jsonify({"error": "question trop longue"}), 400

    premium = subscription.is_premium(device_id)
    ip_remaining = quota_store.get_remaining(_client_ip(), IP_DAILY_LIMIT)
    remaining_before = quota_store.get_remaining(device_id, DAILY_FREE_LIMIT)

    if not premium and (remaining_before <= 0 or ip_remaining <= 0):
        return jsonify({
            "error": "quota_depasse",
            "message": "Tu as utilise tes questions gratuites du jour. "
                       "Reviens demain, ou passe en illimite (bientot disponible "
                       "via Orange Money / Wave / Moov Money).",
            "remaining": min(remaining_before, ip_remaining),
        }), 429

    profile_note = progress_store.get_profile_note(device_id, matiere)
    system_prompt = build_system_prompt(pays, niveau, matiere, profile_note)

    # Historique fourni par le frontend, limite pour controler le cout des appels API.
    safe_history = [
        {"role": m.get("role"), "content": str(m.get("content", ""))[:2000]}
        for m in history[-12:]
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    messages = safe_history + [{"role": "user", "content": question}]

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1100,
            system=system_prompt,
            messages=messages,
        )
        answer = "".join(
            block.text for block in response.content if block.type == "text"
        )
        usage_log.log_call(MODEL, "ask", response.usage.input_tokens, response.usage.output_tokens)
        progress_store.log_event(device_id, "ask", pays, niveau, matiere)
    except Exception as exc:  # surface a readable error to the frontend
        return jsonify({"error": f"Erreur IA: {exc}"}), 502

    if premium:
        remaining_after = remaining_before
    else:
        quota_store.consume(_client_ip(), IP_DAILY_LIMIT)
        remaining_after = quota_store.consume(device_id, DAILY_FREE_LIMIT)

    return jsonify({"answer": answer, "remaining": remaining_after, "premium": premium})


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
