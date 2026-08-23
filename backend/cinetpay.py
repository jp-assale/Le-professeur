"""Integration CinetPay (Checkout API v2) pour l'abonnement illimite.

Documentation officielle : https://docs.cinetpay.com/api/1.0-fr/checkout/initialisation
A VERIFIER une fois le compte marchand actif (sandbox/production) : les noms de
champs et codes de statut ci-dessous viennent de la doc publique, pas d'un test
reel avec de vraies cles API - reconfirme-les avec un premier paiement test
avant de faire confiance a ce module en production.

Principe de securite : on ne credite JAMAIS un abonnement sur la seule foi de
l'appel recu sur notify_url (webhook) - on rappelle systematiquement l'API
CinetPay ("check") pour verifier le statut server-a-server. Le webhook sert
uniquement de declencheur ("va verifier cette transaction"), jamais de preuve
en lui-meme.
"""
import os

import requests

API_BASE = "https://api-checkout.cinetpay.com/v2"

CINETPAY_API_KEY = os.environ.get("CINETPAY_API_KEY")
CINETPAY_SITE_ID = os.environ.get("CINETPAY_SITE_ID")


def is_configured() -> bool:
    return bool(CINETPAY_API_KEY and CINETPAY_SITE_ID)


def create_payment(transaction_id: str, amount_fcfa: int, description: str,
                    notify_url: str, return_url: str) -> dict:
    """Demande a CinetPay un lien de paiement hebergee. Retourne le JSON de
    reponse CinetPay ({code, message, data: {payment_url, ...}, ...})."""
    payload = {
        "apikey": CINETPAY_API_KEY,
        "site_id": CINETPAY_SITE_ID,
        "transaction_id": transaction_id,
        "amount": amount_fcfa,
        "currency": "XOF",
        "description": description,
        "notify_url": notify_url,
        "return_url": return_url,
        "channels": "ALL",
        "lang": "fr",
    }
    resp = requests.post(f"{API_BASE}/payment", json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def check_transaction(transaction_id: str) -> dict:
    """Interroge CinetPay pour le vrai statut d'une transaction (source de
    verite, a utiliser depuis le webhook - jamais depuis le frontend)."""
    payload = {
        "apikey": CINETPAY_API_KEY,
        "site_id": CINETPAY_SITE_ID,
        "transaction_id": transaction_id,
    }
    resp = requests.post(f"{API_BASE}/payment/check", json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def is_success(check_response: dict) -> bool:
    """A RECONFIRMER avec un vrai test : d'apres la doc publique, un paiement
    reussi renvoie code == '00' et data.status == 'ACCEPTED'."""
    data = check_response.get("data") or {}
    return check_response.get("code") == "00" and data.get("status") == "ACCEPTED"
