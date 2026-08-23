"""Referentiel des pays / examens / matieres couverts par l'assistant."""

# Nom de l'examen de fin de college selon le pays (meme tronc commun francophone,
# nom de diplome different).
EXAMEN_COLLEGE = {
    "mali": "DEF (Diplome d'Etudes Fondamentales)",
    "niger": "DEF (Diplome d'Etudes Fondamentales)",
    "guinee": "DEF (Diplome d'Etudes Fondamentales)",
    "senegal": "BEPC (Brevet de Fin d'Etudes Moyennes)",
    "cote_ivoire": "BEPC (Brevet d'Etudes du Premier Cycle)",
    "burkina_faso": "BEPC (Brevet d'Etudes du Premier Cycle)",
    "benin": "BEPC (Brevet d'Etudes du Premier Cycle)",
    "togo": "BEPC (Brevet d'Etudes du Premier Cycle)",
}

PAYS = [
    {"code": "mali", "label": "Mali"},
    {"code": "senegal", "label": "Senegal"},
    {"code": "cote_ivoire", "label": "Cote d'Ivoire"},
    {"code": "burkina_faso", "label": "Burkina Faso"},
    {"code": "benin", "label": "Benin"},
    {"code": "togo", "label": "Togo"},
    {"code": "niger", "label": "Niger"},
    {"code": "guinee", "label": "Guinee"},
]

NIVEAUX = [
    {"code": "primaire", "label": "Primaire (CEP)"},
    {"code": "college", "label": "College"},
    {"code": "lycee", "label": "Lycee (Baccalaureat)"},
]

MATIERES = [
    "Mathematiques",
    "Francais",
    "Physique-Chimie",
    "SVT",
    "Histoire-Geographie",
    "Anglais",
    "Philosophie",
]


def niveau_label(pays_code: str, niveau_code: str) -> str:
    if niveau_code == "college":
        return EXAMEN_COLLEGE.get(pays_code, "college (BEPC/DEF)")
    if niveau_code == "lycee":
        return "Baccalaureat"
    if niveau_code == "primaire":
        return "CEP (Certificat d'Etudes Primaires)"
    return niveau_code
