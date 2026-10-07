"""Test du droit a l'effacement sur une base temporaire (n'utilise jamais les vraies donnees)."""
import os
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="deltest-")
os.environ["DATA_DIR"] = TMP
os.environ["ADMIN_TOKEN"] = "test-token-xyz"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import app as A  # noqa: E402
import db  # noqa: E402
import payments_store  # noqa: E402
import progress_store  # noqa: E402
import quota_store  # noqa: E402
import reports  # noqa: E402
import subscription  # noqa: E402

assert db._DB_PATH.startswith(TMP), "la base de test n'est pas isolee : " + db._DB_PATH
c = A.app.test_client()
H = {"X-Admin-Token": "test-token-xyz"}
problems = []


def count(dev):
    conn = db.get_connection()
    try:
        return {t: conn.execute("SELECT COUNT(*) FROM %s WHERE device_id=?" % t, (dev,)).fetchone()[0]
                for t in ("progress_events", "reports", "payments", "quota", "subscriptions")}
    finally:
        conn.close()


for dev in ("dev-expire", "dev-actif", "dev-autre"):
    progress_store.log_event(dev, "ask", "mali", "college", "Mathematiques")
    progress_store.log_event(dev, "quiz", "mali", "college", "Mathematiques", 3, 5)
    reports.add_report(dev, "ctx", "extrait", "commentaire")
    quota_store.consume(dev, 5)
    payments_store.create_transaction(dev)
    subscription.set_premium(dev, True, days=30, contact="+223 70 00 00 00")
conn = db.get_connection()
conn.execute("UPDATE subscriptions SET premium_until='2020-01-01' WHERE device_id='dev-expire'")
conn.commit()
conn.close()


def check(label, cond):
    print("  %-62s %s" % (label, "OK" if cond else "ECHEC"))
    if not cond:
        problems.append(label)


check("sans jeton -> 403", c.post("/api/admin/delete-device", json={"device_id": "dev-expire"}).status_code == 403)
check("sans device_id -> 400", c.post("/api/admin/delete-device", json={}, headers=H).status_code == 400)

r = c.post("/api/admin/delete-device", json={"device_id": "dev-expire"}, headers=H)
after = count("dev-expire")
check("abonnement expire : tout est supprime (contact compris)", r.status_code == 200 and sum(after.values()) == 0)

r = c.post("/api/admin/delete-device", json={"device_id": "dev-actif"}, headers=H)
after = count("dev-actif")
check("abonnement actif sans case : donnees effacees, abonnement garde",
      after["subscriptions"] == 1 and after["progress_events"] == after["reports"] == after["payments"] == after["quota"] == 0)
check("reponse indique 'abonnement_actif_conserve'", r.get_json()["supprime"]["abonnement_actif_conserve"] == 1)

c.post("/api/admin/delete-device", json={"device_id": "dev-actif", "include_subscription": True}, headers=H)
check("abonnement actif avec case : tout est supprime", sum(count("dev-actif").values()) == 0)

other = count("dev-autre")
check("un autre appareil n'est pas touche", other["progress_events"] == 2 and other["subscriptions"] == 1 and other["reports"] == 1)
print("RESUME : %d echec(s)." % len(problems))
sys.exit(1 if problems else 0)
