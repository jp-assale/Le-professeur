"""Referentiel des pays / examens / matieres couverts par l'assistant."""

# Nom de l'examen de fin de college selon le pays (meme tronc commun francophone,
# nom de diplome different).
# Corrige (amelioration) : la Guinee delivre le BEPC (pas le DEF, propre au
# Mali) et le Senegal le BFEM - coherent avec les sujets de la bibliotheque
# PDF (pdf_seed/manifest.json : guinee|college|BEPC, senegal|college|BFEM).
EXAMEN_COLLEGE = {
    "mali": "DEF (Diplome d'Etudes Fondamentales)",
    "guinee": "BEPC (Brevet d'Etudes du Premier Cycle)",
    "senegal": "BFEM (Brevet de Fin d'Etudes Moyennes)",
    "cote_ivoire": "BEPC (Brevet d'Etudes du Premier Cycle)",
    "burkina_faso": "BEPC (Brevet d'Etudes du Premier Cycle)",
    "benin": "BEPC (Brevet d'Etudes du Premier Cycle)",
}

# Togo et Niger retires temporairement (2026-08-29): aucun sujet d'examen
# dans la bibliotheque pour ces pays - les reintroduire ici (et dans
# play-store-fiche.txt) seulement une fois du contenu importe pour eux.
# Les `code` sont des identifiants techniques (ne jamais les changer) ; seuls
# les `label` (affichage) portent les accents.
PAYS = [
    {"code": "mali", "label": "Mali"},
    {"code": "senegal", "label": "Sénégal"},
    {"code": "cote_ivoire", "label": "Côte d'Ivoire"},
    {"code": "burkina_faso", "label": "Burkina Faso"},
    {"code": "benin", "label": "Bénin"},
    {"code": "guinee", "label": "Guinée"},
]

# Le niveau « primaire » (CEP) est retire de l'appli (2026-10-07) : l'appli est
# declaree « 13 ans et plus » sur Google Play. Le reintroduire suppose de
# declarer aussi la tranche 9-12 ans (politique « Familles ») et d'ajouter du
# vrai contenu CM2 - voir play-console-securite-donnees.md, section 4.
NIVEAUX = [
    {"code": "college", "label": "Collège"},
    {"code": "lycee", "label": "Lycée (Baccalauréat)"},
]

# Identifiants techniques des matieres (servent de cle dans les manifestes :
# ne pas les accentuer).
MATIERES = [
    "Mathematiques",
    "Francais",
    "Physique-Chimie",
    "SVT",
    "Histoire-Geographie",
    "Anglais",
    "Philosophie",
    "Economie",
    "Allemand",
    "Espagnol",
]

# Contexte national injecte dans les prompts de l'IA, pour que les exemples,
# la monnaie, le vocabulaire des examens et la methode attendue collent au
# systeme scolaire reel de l'eleve (et pas a un programme « moyen »).
CONTEXTE_PAYS = {
    "mali": {
        "prep": "au",
        "monnaie": "FCFA",
        "series_bac": "TSE (sciences exactes), TSExp (sciences experimentales), "
                      "TSS (sciences sociales), TLL (langues et litterature), "
                      "TAL (arts et lettres), TSECO (sciences economiques), STI/STG (technique)",
        "pedagogie": "Programme du Mali (enseignement fondamental puis secondaire general).",
    },
    "senegal": {
        "prep": "au",
        "monnaie": "FCFA",
        "series_bac": "L1, L2, L' (litteraires), S1, S2, S3, S4, S5 (scientifiques), "
                      "G/STEG (economie-gestion), T1/T2 (techniques)",
        "pedagogie": "Programme du Senegal (cycle moyen puis secondaire, examens de l'Office du Bac).",
    },
    "cote_ivoire": {
        "prep": "en",
        "monnaie": "FCFA",
        "series_bac": "A1, A2 (litteraires), C, D, E (scientifiques), B, G1, G2 (economie-gestion)",
        "pedagogie": "Programme ivoirien selon l'approche par competences (APC) : "
                     "les evaluations partent d'une « situation d'evaluation » concrete "
                     "(contexte - circonstance - tache) que l'eleve doit resoudre.",
    },
    "burkina_faso": {
        "prep": "au",
        "monnaie": "FCFA",
        "series_bac": "A4, A5 (litteraires), C, D, E (scientifiques), F, G (techniques)",
        "pedagogie": "Programme burkinabe (post-primaire puis secondaire).",
    },
    "benin": {
        "prep": "au",
        "monnaie": "FCFA",
        "series_bac": "A1, A2 (litteraires), B (economie), C, D, E (scientifiques), F, G (techniques)",
        "pedagogie": "Programme beninois selon l'approche par competences (APC) : "
                     "situations d'apprentissage et d'evaluation ; en sciences la matiere "
                     "s'appelle PCT (Physique-Chimie-Technologie).",
    },
    "guinee": {
        "prep": "en",
        "monnaie": "francs guineens (GNF) - jamais de FCFA en Guinee",
        "series_bac": "SM (sciences mathematiques), SE (sciences experimentales), "
                      "SS (sciences sociales)",
        "pedagogie": "Programme guineen (college puis lycee, BAC unique).",
    },
}


def pays_label(pays_code: str) -> str:
    return next((p["label"] for p in PAYS if p["code"] == pays_code), pays_code)


def pays_avec_preposition(pays_code: str) -> str:
    """« au Mali », « en Côte d'Ivoire », « en Guinée »... (pour les prompts)."""
    ctx = CONTEXTE_PAYS.get(pays_code)
    label = pays_label(pays_code)
    return f"{ctx['prep']} {label}" if ctx else f"au {label}"


def contexte_pays_note(pays_code: str, niveau_code: str) -> str:
    """Note courte a ajouter a un prompt systeme : monnaie, series, methode.
    Chaine vide pour un pays inconnu (comportement d'avant inchange)."""
    ctx = CONTEXTE_PAYS.get(pays_code)
    if not ctx:
        return ""
    lignes = [
        f"- Monnaie a utiliser dans les exemples chiffres : {ctx['monnaie']}.",
        f"- {ctx['pedagogie']}",
    ]
    if niveau_code == "lycee":
        lignes.append(f"- Series du baccalaureat dans ce pays : {ctx['series_bac']}.")
    return "Contexte scolaire national :\n" + "\n".join(lignes)


def niveau_label(pays_code: str, niveau_code: str) -> str:
    if niveau_code == "college":
        return EXAMEN_COLLEGE.get(pays_code, "college (BEPC/DEF)")
    if niveau_code == "lycee":
        return "Baccalaureat"
    if niveau_code == "primaire":
        return "CEP (Certificat d'Etudes Primaires)"
    return niveau_code
