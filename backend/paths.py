"""Repertoire de stockage des fichiers de donnees (quota, abonnements, logs).

En local, ca reste a cote du code (comportement inchange). En production sur
Fly.io, DATA_DIR pointe vers le volume persistant monte (voir fly.toml et
DATA_DIR dans les secrets/env), pour que ces fichiers survivent aux
redeploiements et redemarrages du serveur.
"""
import os

DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
os.makedirs(DATA_DIR, exist_ok=True)
