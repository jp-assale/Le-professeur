"""Statut d'abonnement par appareil (faiblesse #3 : aucune monetisation reelle).

C'est un scaffold, PAS une integration de paiement fonctionnelle. Personne ne
peut devenir premium via ce fichier a lui seul.

TODO pour une vraie mise en prod (actions humaines, pas du code) :
1) Creer un compte marchand CinetPay (console.cinetpay.com) - KYC obligatoire,
   a faire par le porteur du projet, pas par une IA.
2) Implementer /api/cinetpay/webhook cote serveur : verifier la signature
   CinetPay du callback de paiement, puis SEULEMENT APRES verification
   serveur-a-serveur reussie, appeler set_premium(device_id, True). Ne jamais
   activer premium sur un simple retour du frontend (facile a falsifier).
3) Definir un vrai prix en FCFA et une duree d'abonnement (ce fichier ne gere
   pas encore l'expiration - a ajouter avec la vraie integration).
"""
import json
import os
import threading
from datetime import date

from paths import DATA_DIR

_LOCK = threading.Lock()
_STORE_PATH = os.path.join(DATA_DIR, "subscriptions.json")


def _load() -> dict:
    if not os.path.exists(_STORE_PATH):
        return {}
    with open(_STORE_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(data: dict) -> None:
    with open(_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)


def is_premium(device_id: str) -> bool:
    with _LOCK:
        entry = _load().get(device_id)
        return bool(entry and entry.get("premium"))


def set_premium(device_id: str, value: bool) -> None:
    with _LOCK:
        data = _load()
        data[device_id] = {"premium": value, "updated": date.today().isoformat()}
        _save(data)
