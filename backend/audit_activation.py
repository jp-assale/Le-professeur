"""Test de la validation en un clic (lien WhatsApp -> activation unique) sur une base temporaire."""
import os
import sys
import tempfile
from datetime import date, timedelta

TMP = tempfile.mkdtemp(prefix="acttest-")
os.environ["DATA_DIR"] = TMP
os.environ["ADMIN_TOKEN"] = "test-token-xyz"
os.environ["PAY_WHATSAPP"] = "+223 70 00 00 00"
os.environ["PAY_ORANGE"] = "+223 71 11 11 11"
os.environ["PAY_BENEFICIARY"] = "Test Beneficiaire"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import app as A  # noqa: E402
import db  # noqa: E402
import subscription  # noqa: E402

assert db._DB_PATH.startswith(TMP)
c = A.app.test_client()
H = {"X-Admin-Token": "test-token-xyz"}
problems = []


def check(label, cond):
    print("  %-70s %s" % (label, "OK" if cond else "ECHEC"))
    if not cond:
        problems.append(label)


body = {"k": "req12345abcd", "device_id": "dev-abc123-999", "days": 30, "nom": "Aminata", "tel": "+223 70 12 34 56"}
check("sans jeton -> 403", c.post("/api/admin/activate-request", json=body).status_code == 403)
check("reference invalide -> 400", c.post("/api/admin/activate-request", json={**body, "k": "x"}, headers=H).status_code == 400)
check("code appareil invalide -> 400", c.post("/api/admin/activate-request", json={**body, "device_id": "a b"}, headers=H).status_code == 400)
check("duree 0 -> 400", c.post("/api/admin/activate-request", json={**body, "days": 0}, headers=H).status_code == 400)
check("duree texte -> 400", c.post("/api/admin/activate-request", json={**body, "days": "abc"}, headers=H).status_code == 400)
check("aucun abonnement cree par les refus", not subscription.is_premium("dev-abc123-999"))

r1 = c.post("/api/admin/activate-request", json=body, headers=H).get_json()
expected = (date.today() + timedelta(days=30)).isoformat()
check("1re validation : active 30 jours", r1["ok"] and not r1["already"] and r1["premium_until"] == expected)
check("l'eleve est bien illimite", subscription.is_premium("dev-abc123-999"))
check("l'eleve voit premium=true via /api/quota", c.get("/api/quota?device_id=dev-abc123-999").get_json()["premium"] is True)

r2 = c.post("/api/admin/activate-request", json=body, headers=H).get_json()
check("2e clic sur le meme lien : deja active, pas de doublon", r2["already"] and r2["premium_until"] == expected)

r3 = c.post("/api/admin/activate-request", json={**body, "k": "req-renouv-0001", "days": 60}, headers=H).get_json()
expected3 = (date.today() + timedelta(days=90)).isoformat()
check("renouvellement : +60 jours AJOUTES aux 30 restants (=90)", r3["premium_until"] == expected3)

conn = db.get_connection()
n = conn.execute("SELECT COUNT(*) FROM activation_requests").fetchone()[0]
conn.close()
check("2 demandes enregistrees (pas 3)", n == 2)

info = c.get("/api/pay-info").get_json()
check("/api/pay-info public : whatsapp en chiffres", info["whatsapp"] == "22370000000")
check("/api/pay-info : mode de paiement et beneficiaire", info["methods"] == [{"label": "Orange Money", "number": "+223 71 11 11 11"}] and info["beneficiary"] == "Test Beneficiaire")
print("RESUME : %d echec(s)." % len(problems))
sys.exit(1 if problems else 0)
