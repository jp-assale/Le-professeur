import os

from anthropic import Anthropic
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

import cinetpay
import payments_store
import quota_store
import reports
import subscription
import usage_log
from curriculum import MATIERES, NIVEAUX, PAYS, niveau_label
from epreuves import get_epreuve, list_epreuves

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
DAILY_FREE_LIMIT = int(os.environ.get("DAILY_FREE_LIMIT", "5"))
MODEL = os.environ.get("ASSISTANT_MODEL", "claude-haiku-4-5-20251001")

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
client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None


def build_system_prompt(pays_code: str, niveau_code: str, matiere: str, epreuve: dict | None = None) -> str:
    pays_label = next((p["label"] for p in PAYS if p["code"] == pays_code), pays_code)
    niveau = niveau_label(pays_code, niveau_code)

    base = (
        f"Tu es un professeur particulier bienveillant pour un(e) eleve du {niveau} "
        f"en {matiere}, au {pays_label}, dans le systeme scolaire francophone d'Afrique "
        "de l'Ouest. Reponds toujours en francais simple et clair."
    )

    if epreuve:
        return (
            base + "\n\n"
            f"L'eleve travaille actuellement sur un sujet type '{epreuve['titre']}'. "
            "Voici l'enonce complet de l'exercice:\n"
            "---\n" + epreuve["enonce"] + "\n---\n\n"
            "Tu joues le role d'un correcteur qui aide l'eleve a resoudre CET exercice "
            "precis, pas un autre.\n\n"
            "Regles:\n"
            "- Au tout premier message, ne donne pas la solution: demande a l'eleve ce "
            "qu'il/elle a deja essaye ou par ou il/elle veut commencer.\n"
            "- Guide etape par etape, valide ce qui est juste, corrige les erreurs avec "
            "bienveillance, sans donner la reponse finale trop vite.\n"
            "- Si l'eleve bloque completement ou demande explicitement la solution, "
            "donne alors une correction complete et pedagogique de la question posee.\n"
            "- Reste concis a chaque message: 200-250 mots maximum.\n"
            "- Si l'eleve devie completement vers un sujet hors devoirs, ramene-le "
            "poliment vers l'exercice en cours."
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
        "Reste concis: 250-300 mots maximum pour ce premier message."
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


@app.route("/api/curriculum", methods=["GET"])
def get_curriculum():
    return jsonify({"pays": PAYS, "niveaux": NIVEAUX, "matieres": MATIERES})


@app.route("/api/epreuves", methods=["GET"])
def get_epreuves():
    pays = request.args.get("pays") or None
    niveau = request.args.get("niveau") or None
    matiere = request.args.get("matiere") or None
    return jsonify(list_epreuves(pays, niveau, matiere))


@app.route("/api/epreuves/<epreuve_id>", methods=["GET"])
def get_one_epreuve(epreuve_id):
    epreuve = get_epreuve(epreuve_id)
    if not epreuve:
        return jsonify({"error": "epreuve introuvable"}), 404
    return jsonify(epreuve)


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
            description="Abonnement illimite - Le Professeur",
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
    epreuve_id = payload.get("epreuve_id")
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

    epreuve = get_epreuve(epreuve_id) if epreuve_id else None
    system_prompt = build_system_prompt(pays, niveau, matiere, epreuve)

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
            max_tokens=800,
            system=system_prompt,
            messages=messages,
        )
        answer = "".join(
            block.text for block in response.content if block.type == "text"
        )
        usage_log.log_call(MODEL, "ask", response.usage.input_tokens, response.usage.output_tokens)
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
