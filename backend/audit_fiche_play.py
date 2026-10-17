"""Verifie une fiche Play Store (par defaut play-store-fiche-v2.txt) contre les motifs de refus
« Metadonnees » de Google Play (rapport du 12/10/2026 : « Description inexacte / manque de
clarte ») et, si la fiche en contient, ses legendes et textes alternatifs de captures.
Usage : python backend/audit_fiche_play.py [play-store-fiche-v3.txt]"""
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FICHE = sys.argv[1] if len(sys.argv) > 1 else "play-store-fiche-v2.txt"
txt = open(os.path.join(ROOT, FICHE), encoding="utf-8").read()


def section(name):
    m = re.search(r"--- " + re.escape(name) + r"[^\n]*---\n(.*?)(?=\n--- |\Z)", txt, re.S)
    return m.group(1).strip() if m else ""


titre = section("Nom de l'appli").splitlines()[0].strip()
court = section("Description courte")
longue = section("Description longue")
corps = titre + "\n" + court + "\n" + longue
problems = []


def check(label, ok, detail=""):
    print("  %-78s %s %s" % (label, "OK " if ok else "ECHEC", detail))
    if not ok:
        problems.append(label)


emoji = re.compile("[←-⯿☀-➿\U0001F000-\U0001FAFF‍️]")
caps = re.findall(r"\b[A-ZÉÈÀÂÊÎÔÛÇ]{4,}\b", corps)
marques = ("orange", "wave", "moov", "mtn", "whatsapp", "facebook", "tiktok", "youtube", "google", "chatgpt", "openai", "anthropic", "claude")
superl_mots = ("meilleur", "n°1", "numéro 1", "#1", "le plus", "garanti", "100 %", "100%", "gratuit", "promo", "offre")
brands = [b for b in marques if b in corps.lower()]
superl = [w for w in superl_mots if w in corps.lower()]
words = re.findall(r"[a-zàâçéèêëîïôûùüÿœ']{5,}", longue.lower())
top = max(((w, words.count(w)) for w in set(words)), key=lambda x: x[1]) if words else ("", 0)

print("=== Controle de %s face au rapport Google (Metadonnees) ===" % FICHE)
check("Nom : 30 caracteres max", len(titre) <= 30, "(%d)" % len(titre))
check("Description courte : 80 caracteres max", len(court) <= 80, "(%d)" % len(court))
check("Description longue : 4000 caracteres max", len(longue) <= 4000, "(%d)" % len(longue))
check("Aucun emoji (la v1 en avait dans chaque titre de section)", not emoji.search(corps))
check("Aucun mot en MAJUSCULES (v1 : « CE QUE TU PEUX FAIRE », « GRATUIT… »)", not caps, str(caps[:3]))
check("Aucune marque tierce citee (v1 : Orange Money, Wave, Moov Money)", not brands, str(brands))
check("Pas de mots promotionnels / superlatifs ni « gratuit »", not superl, str(superl))
check("Pas de repetition excessive d'un mot-cle (max 12 fois)", top[1] <= 12, "(%s : %d)" % top)
check("Le nom de l'appli est repete dans la description (coherence)", titre.lower() in longue.lower())
check("La 1re phrase dit ce que fait l'appli (aide aux devoirs, question, explication)",
      all(k in longue.split("\n")[0].lower() for k in ("aide aux devoirs", "question", "explique")))
check("La fonction de base est decrite avant les options", longue.lower().index("tu poses") < longue.lower().index("ce que tu peux faire"))
check("Les fonctions citees existent dans l'appli (voix, cours, schemas, quiz, sujets, dictee)",
      all(k in longue.lower() for k in ("voix", "leçons", "schéma", "quiz", "sujets d'examen", "micro")))
check("Le public est precise (college et lycee, pays)", "collège" in longue.lower() and "lycée" in longue.lower() and "mali" in longue.lower())
check("Aucune mention du niveau Primaire / d'enfants", not re.search(r"primaire|enfant|cm2|cep\b", corps.lower()))
check("L'IA et ses limites sont annoncees (transparence)", "intelligence artificielle" in longue.lower() and "erreurs" in longue.lower())
check("Pas de temoignage ni de note (« 5 etoiles », avis)", not re.search(r"étoile|avis|témoign|utilisateurs? disent", corps.lower()))

# Captures d'ecran (fiche v3) : texte dans l'image et textes alternatifs.
legendes = [l.split("|", 1)[1].strip() for l in section("Légendes des captures d'écran").splitlines() if "|" in l]
alts = [l.split("|", 1)[1].strip() for l in section("Textes alternatifs des captures").splitlines() if "|" in l]
notes = re.sub(r"</?fr-FR>", "", section("Notes de version")).strip()
if legendes or alts:
    images = "\n".join(legendes + alts + [notes])
    cta = re.compile(r"\b(télécharge\w*|install\w*|essaie|essayez|essayer|jouer|joue|clique\w*|découvre)\b", re.I)
    check("Captures : 2 a 8 legendes", 2 <= len(legendes) <= 8, "(%d)" % len(legendes))
    check("Captures : un texte alternatif par capture, 140 caracteres max",
          len(alts) == len(legendes) and all(len(a) <= 140 for a in alts), str([len(a) for a in alts]))
    check("Textes alternatifs sans « image de » ni « photo de » en tete",
          not any(a.lower().startswith(("image de", "photo de")) for a in alts))
    check("Captures et notes : aucun appel a l'action (telecharger, installer, essayer...)",
          not cta.search(images), str(cta.findall(images)[:3]))
    check("Captures et notes : ni emoji, ni prix, ni promotion, ni classement",
          not emoji.search(images) and not [w for w in superl_mots if w in images.lower()]
          and not re.search(r"\d+\s?(fcfa|€|\$)|téléchargements|populaire|nouveau\b", images.lower()))
    check("Captures et notes : aucune marque tierce", not [b for b in marques if b in images.lower()])
print("RESUME : %d point(s) a corriger." % len(problems))
sys.exit(1 if problems else 0)
