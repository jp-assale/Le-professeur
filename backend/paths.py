"""Repertoire de stockage des fichiers de donnees (quota, abonnements, logs).

En local, ca reste a cote du code (comportement inchange). En production sur
Render, DATA_DIR pointe vers le disque persistant monte sur /var/data (voir
la variable d'environnement DATA_DIR dans le dashboard Render), pour que ces
fichiers survivent aux redeploiements et redemarrages du serveur.
"""
import os

DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
os.makedirs(DATA_DIR, exist_ok=True)
