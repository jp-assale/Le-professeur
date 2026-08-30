# JPA Assistant Scolaire (MVP)

Appli web (PWA) qui aide les élèves d'Afrique de l'Ouest francophone à comprendre
leurs devoirs grâce à l'IA — pas juste des annales PDF statiques, une vraie
explication étape par étape, adaptée au pays/niveau/matière choisis.

Nom affiché "JPA Assistant Scolaire" (l'IA se présente comme "Le Prof JPA" dans
le chat) — l'`appId` technique (`com.leprofesseur.app`) reste distinct du nom
affiché et est définitif : lié au keystore de signature et déjà utilisé pour la
publication Play Store, ne plus le changer.

## Comment ça marche

- **Frontend** (`frontend/`) : HTML/CSS/JS pur, PWA installable, pensé mobile-first.
  Rendu Markdown + LaTeX (bibliothèques `marked`/`KaTeX`/`DOMPurify` auto-hébergées
  dans `frontend/vendor/`) pour que les réponses de l'IA (formules, tableaux,
  titres) s'affichent proprement au lieu du texte brut.
- **Backend** (`backend/`) : Flask (Python). Appelle l'API Claude (modèle Haiku,
  économique) avec un prompt système adapté au pays/niveau/matière. Applique un
  quota de questions gratuites par jour et par appareil (+ garde-fou par IP).
  Surveillance d'erreurs Sentry intégrée mais désactivée tant que `SENTRY_DSN`
  n'est pas défini (voir `.env.example`).
- **Android** (`android/`) : projet Capacitor qui embarque `frontend/` dans une
  appli native. `appId` = `com.leprofesseur.app` (définitif).

## Lancer en local

```bash
cd backend
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Édite `backend/.env` et mets ta clé API Anthropic (créée sur
[console.anthropic.com](https://console.anthropic.com), **distincte** de ton
abonnement Claude Code — facturée séparément à l'usage).

```bash
python app.py
```

Ouvre `http://localhost:5000`.

## État actuel (MVP)

Fait :
- Sélection pays / niveau / matière — **6 pays** francophones d'Afrique de
  l'Ouest (Mali, Sénégal, Côte d'Ivoire, Burkina Faso, Bénin, Guinée — Togo et
  Niger retirés temporairement, voir plus bas) × 3 niveaux × **10 matières**
  (Mathématiques, Français, Physique-Chimie, SVT, Histoire-Géographie, Anglais,
  Philosophie, Économie, Allemand, Espagnol)
- Chat texte avec l'IA, prompt pédagogique (explique au lieu de juste donner la
  réponse), formules mathématiques et tableaux rendus proprement (KaTeX + Markdown)
- Upload photo/PDF de son propre sujet, corrigé pas-à-pas par l'IA
- **Bibliothèque de 1505 vrais sujets d'examens** (BAC/BEPC/DEF/BFEM/CEP/CEE/
  CEPE/CFEE), stockée en dur dans `backend/pdf_seed/manifest.json` (committé,
  survit aux redéploiements) avec les PDF eux-mêmes hébergés en externe sur des
  GitHub Releases du dépôt (`pdf-sujets-v1`/`v2`/...) — trop volumineux pour git
  directement. Import fait via les scripts `backend/import_pdfs*.py` (résumables,
  détectent les doublons pays+niveau+matière+titre avant d'importer). Seuls des
  fichiers fournis directement par l'utilisateur ont été utilisés — **jamais de
  scraping de site tiers**, règle stricte pour raisons de droit d'auteur.
- Quota gratuit quotidien par appareil **et** par IP (garde-fou anti-reset via
  réinstallation), message d'incitation à l'abonnement une fois épuisé
- Cache hors-ligne pour le contenu déjà consulté (curriculum) — seul le chat IA
  a besoin du réseau
- **Série de jours consécutifs** (`🔥`) : badge purement local (localStorage,
  aucun appel serveur), incrémenté après une vraie interaction (question, sujet
  ouvert, quiz) — pas juste à l'ouverture de l'appli
- Signalement d'erreur (`⚠️`) : les élèves peuvent signaler un exercice ou une
  réponse fausse → `backend/reports.jsonl`, à relire régulièrement
- **Surveillance d'erreurs Sentry** (backend) : prête, désactivée tant que
  `SENTRY_DSN` n'est pas configuré (compte gratuit à créer sur sentry.io) —
  ne remonte jamais le contenu des questions/photos des élèves
- Suivi réel du coût par appel IA → `backend/usage_log.jsonl`
- **Intégration CinetPay codée** (`backend/cinetpay.py`) : génère un lien de
  paiement, n'active l'illimité qu'après re-vérification server-à-server (jamais
  sur la seule foi du webhook). Reste à faire : compte marchand CinetPay actif
  (bloqué sur leur support, RCCM disponible côté utilisateur) — PayDunya et
  FedaPay identifiés comme alternatives équivalentes si besoin, même contraintes
  KYC réglementaires
- Page de confidentialité (`frontend/privacy.html`) + code appareil récupérable
  (`🔑`) pour changer de téléphone sans perdre son quota
- **Quiz automatique** (`📝`) et **diagnostic de niveau** (`🎯`) : QCM générés par
  l'IA, notation immédiate, bilan personnalisé mémorisé (`progress_store.py`)
  et réinjecté dans les futures explications de l'élève
- **Backend déployé publiquement** : https://le-professeur.onrender.com (Render,
  plan gratuit — service en veille après inactivité, disque éphémère pour tout
  sauf `pdf_seed/`)
- **Logo et identité visuelle** : bulle de dialogue + toque de graduation, style
  3D (dégradé + ombre portée), généré par script (voir historique git) — décliné
  PWA (192/512/apple-touch) et Android (icône classique + adaptative, calques
  fond/premier-plan séparés pour préserver le dégradé sous masquage cercle/carré)
- **Build signé prêt pour le Play Store** : keystore généré
  (`keystore/le-professeur-release.keystore`, **jamais commit, sauvegardé
  ailleurs** — sa perte empêcherait toute mise à jour future de l'appli).
  `bundleRelease` produit l'AAB signé.
- **Publication Play Store en cours** : compte développeur actif, fiche Store
  complète (description, icône, captures d'écran, déclarations de contenu et
  sécurité des données), release de test interne fonctionnelle et vérifiée de
  bout en bout. Prochaine étape : test fermé (12 testeurs minimum, 14 jours)
  avant l'accès en production, exigé par Google pour les nouveaux comptes.

Retiré volontairement (ne pas réintroduire sans qu'on en discute) :
- **Togo et Niger** — aucun sujet d'examen réel dans la bibliothèque pour ces
  pays ; retirés du sélecteur et de la fiche Store jusqu'à ce que du contenu
  soit importé
- **Exercices génériques écrits par l'IA** (`epreuves.py`, supprimé) — 29
  exercices non officiels, redondants une fois la bibliothèque de vrais sujets
  suffisamment fournie
- **Correction de copie** (`✍️`) — retirée pour recentrer l'effort
- **Tableau de bord de progression** (`📊`) — le backend (`progress_store.py`)
  tourne toujours en arrière-plan (diagnostic/quiz l'alimentent), mais le
  bouton a été retiré : l'écran de réveil du plan Render gratuit ("Application
  loading") ressemblait à un blocage. La série de jours consécutifs (`🔥`,
  purement locale) sert de remplacement léger pour la fidélisation.

Pas encore fait (décisions à prendre avec toi) :
- **Vrai paiement CinetPay** — voir section dédiée plus bas
- **Test fermé Play Store** — recruter les 12 testeurs
- **Stockage persistant** (quota, abonnements, cache PDF corrigé) — sur Render
  gratuit, ces fichiers disparaissent au redéploiement (les PDF eux-mêmes sont
  permanents via `pdf_seed/` + GitHub Releases). Nécessaire avant une forte
  charge : disque payant Render, ou vraie base de données
- **Matières récemment ajoutées mais partiellement couvertes** — Économie (23
  sujets), Allemand (19), Espagnol (27) : volume plus faible que les matières
  historiques, à enrichir si pertinent
- **Autres matières identifiées mais non ajoutées** — Étude de cas, EPS, Droit,
  SES, Mécanique, Russe... repérées dans les imports mais laissées de côté,
  décision à prendre si on veut les intégrer

## Compiler l'APK

```bash
$env:JAVA_HOME = "C:\Users\jp.assale\AppData\Local\Programs\Microsoft\jdk-21.0.12.1+1"
$env:ANDROID_HOME = "C:\Users\jp.assale\AppData\Local\Android\Sdk"
$env:Path = "$env:JAVA_HOME\bin;$env:Path"
cd android
.\gradlew.bat assembleDebug --no-daemon
```

L'APK sort dans `android/app/build/outputs/apk/debug/app-debug.apk`. Après toute
modification de `frontend/`, lancer `npx cap sync android` avant de recompiler
pour que les fichiers web soient recopiés dans le projet Android. Remplacer
`assembleDebug` par `bundleRelease` pour produire l'AAB signé de production
(sort dans `android/app/build/outputs/bundle/release/`).

## Ajouter de vrais sujets PDF

**Méthode principale (lots de fichiers)** : donne-moi le chemin d'un dossier
fourni directement par toi (jamais de scraping tiers), organisé par pays/niveau
si possible. J'analyse la structure, adapte le script d'import (voir
`backend/import_pdfs_ns2.py` comme référence la plus récente — détecte les
doublons contre la bibliothèque existante avant d'uploader), et committe le
résultat.

**Méthode ponctuelle (un seul fichier)** : va sur `/admin.html` (ex:
https://le-professeur.onrender.com/admin.html), colle ton `ADMIN_TOKEN`, remplis
le formulaire. Le PDF est alors stocké côté Render — **éphémère sur le plan
gratuit** (perdu au redéploiement), donc pour un ajout permanent transmets plutôt
le fichier directement.

Sources légitimes uniquement : PDF fournis par CNECE/ministère sur demande
directe, annales papier scannées, documents d'école. Ne jamais ajouter de PDF
récupérés sur des sites d'agrégation tiers (Scribd, fomesoutra.com, etc.).

## Créer le compte marchand CinetPay

Inscription : **https://app.cinetpay.com/signup/choice** (choisir le type de
compte - particulier ou entreprise).

Documents à préparer pour le KYC :
- Une pièce d'identité valide (scan)
- Le registre de commerce (RCCM) si tu t'inscris en tant qu'entreprise plutôt
  qu'en particulier
- Un compte pour recevoir les paiements (bancaire ou mobile money selon ce que
  CinetPay propose au moment de l'inscription)

CinetPay valide les documents puis active le compte marchand — support en cas
de blocage : `activations@cinetpay.com`. Une fois actif, récupère `apikey` et
`site_id` dans le tableau de bord et mets-les dans `backend/.env`.

Alternatives équivalentes si le blocage persiste : **PayDunya** (même
couverture mobile money : Orange Money, Wave, Moov, MTN) et **FedaPay**
(basé au Bénin) — même exigences KYC/RCCM, réglementaires et non spécifiques
à CinetPay.

## Coûts à anticiper

Chaque question posée = un appel à l'API Claude = un coût réel (facturé à l'usage
sur ton compte console.anthropic.com). Le quota gratuit par appareil sert à
protéger la marge — à ajuster (`DAILY_FREE_LIMIT` dans `.env`) selon ce que le
budget permet avant qu'un abonnement payant compense.
