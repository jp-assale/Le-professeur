# Le Professeur — Assistant scolaire IA (MVP)

Appli web (PWA) qui aide les élèves d'Afrique de l'Ouest francophone à comprendre
leurs devoirs grâce à l'IA — pas juste des annales PDF statiques, une vraie
explication étape par étape, adaptée au pays/niveau/matière choisis.

Nom "Le Professeur" — l'`appId` technique (`com.aida.assistant`) reste un
placeholder distinct, à figer avant publication (voir plus bas).

## Comment ça marche

- **Frontend** (`frontend/`) : HTML/CSS/JS pur, PWA installable, pensé mobile-first.
- **Backend** (`backend/`) : Flask (Python). Appelle l'API Claude (modèle Haiku,
  économique) avec un prompt système adapté au pays/niveau/matière. Applique un
  quota de questions gratuites par jour et par appareil (stocké dans
  `backend/quota.json` pour le MVP — à remplacer par une vraie base avant la prod).
- **Android** (`android/`) : projet Capacitor généré (`npx cap add android`), qui
  embarque `frontend/` dans une appli native. `appId` actuellement
  `com.aida.assistant` dans `capacitor.config.json` — **c'est un placeholder,
  à figer avant la première publication** (le nom de package ne peut plus
  changer une fois publié sur le Play Store).

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
- Sélection pays / niveau / matière (8 pays francophones d'Afrique de l'Ouest)
- Chat texte avec l'IA, prompt pédagogique (explique au lieu de juste donner la réponse)
- Banque de 29 exercices type examen ("Sujets d'examen") + upload photo/PDF de son
  propre sujet, corrigés pas-à-pas par l'IA
- Quota gratuit quotidien par appareil **et** par IP (garde-fou anti-reset via
  réinstallation), message d'incitation à l'abonnement une fois épuisé
- Cache hors-ligne pour le contenu déjà consulté (curriculum, sujets d'examen) —
  seul le chat IA a besoin du réseau
- Signalement d'erreur (`⚠️`) : les élèves peuvent signaler un exercice ou une
  réponse fausse → `backend/reports.jsonl`, à relire régulièrement
- Suivi réel du coût par appel IA → `backend/usage_log.jsonl` (tarifs approximatifs,
  à vérifier sur la page pricing d'Anthropic)
- **Intégration CinetPay codée** (`backend/cinetpay.py`, `backend/payments_store.py`,
  endpoints `/api/subscribe` et `/api/cinetpay/webhook`) : génère un lien de
  paiement CinetPay, et n'active l'illimité qu'après re-vérification
  server-à-server du paiement (jamais sur la seule foi du webhook). Reste à
  faire : créer le compte marchand CinetPay (KYC, à faire par toi — voir
  section dédiée plus bas), mettre les vraies clés dans `.env`, et confirmer
  les noms de champs/codes de statut avec un vrai paiement test (la doc
  publique a été utilisée, pas un test réel — voir les commentaires "A
  VERIFIER" dans `cinetpay.py`)
- Page de confidentialité (`frontend/privacy.html`) + code appareil récupérable
  (`🔑`) pour changer de téléphone sans perdre son quota
- **Toolchain Android complète installée** : Node.js, JDK 21, SDK Android
  (platform-tools, build-tools 35, platform 35) — voir "Compiler l'APK" ci-dessous
- **Backend déployé publiquement et fonctionnel** : https://le-professeur.onrender.com
  (Render, plan gratuit). Redéploie automatiquement à chaque `git push` sur `main`.
  ⚠️ Plan gratuit = le service s'endort après inactivité (jusqu'à ~50s de délai
  au premier appel) et le disque est **éphémère** (fichiers `*.json`/`*.jsonl`/
  PDF perdus à chaque redéploiement) — a upgrader avant une vraie mise en prod
- **Vraie clé API Anthropic configurée et testée** — le chat répond réellement,
  en production
- **CORS ouvert sur `/api/*`** (`flask-cors`) — necessaire car l'appli Android
  empaquetée appelle ce backend depuis une autre origine
- **`frontend/js/config.js` detecte automatiquement le contexte** : URL relative
  en navigateur normal (local ou sur le domaine de prod), URL absolue du
  backend Render uniquement dans l'appli Android empaquetée (detection via
  `Capacitor.isNativePlatform()`)
- **Bibliothèque de vrais PDF d'examens** (`backend/pdf_library.py`,
  `frontend/admin.html`) : page d'administration pour ajouter/supprimer de
  vrais sujets PDF (protégée par `ADMIN_TOKEN`), affichés séparément des
  exercices originaux dans le panneau "Sujets d'examen", avec un bouton
  "Corriger avec Le Professeur" qui réutilise le pipeline vision existant
- **APK compilé et connecté au backend réel** — testé, le chat répond vraiment
  sur un appareil
- **Quiz automatique** (`📝`) : génère 3-4 QCM sur la dernière explication donnée,
  notation immédiate avec explication par question, score envoyé à la
  progression
- **Diagnostic de niveau** (`🎯`) : quiz de 6 questions couvrant les bases de la
  matière choisie ; à la fin, un bilan personnalisé est généré par l'IA et
  **mémorisé** — les futures explications de cet élève en tiennent compte
  automatiquement (`progress_store.py`, injecté dans le prompt système)
- **Correction de copie** (`✍️`) : l'élève rédige ou photographie sa réponse
  complète à un exercice, l'IA la note sur barème comme un examinateur (note
  extraite automatiquement pour la progression)
- **Suivi de progression — backend prêt, bouton retiré de l'interface** :
  `backend/progress_store.py` et `/api/progress` fonctionnent (testés), mais
  le bouton `📊` a été retiré du frontend à la demande de l'utilisateur après
  un long débogage ayant révélé que le plan gratuit Render met le service en
  veille après inactivité (écran de réveil "Application loading" pouvant
  ressembler à un blocage) — corrigible avec un plan payant (~7$/mois),
  refusé pour l'instant. Le diagnostic/quiz continuent d'alimenter
  `progress_store` en arrière-plan, prêt à réafficher un tableau de bord plus
  tard si besoin.

- **Icônes réelles générées** (`backend/gen_icons.py` - chapeau de diplôme blanc
  sur fond vert marque) : PWA (`frontend/icons/`) et toutes les densités
  Android (mipmap-*), relancer le script si le design doit changer
- **Package Android finalisé** : `com.leprofesseur.app` (remplace le
  `com.aida.assistant` provisoire) - permanent maintenant que l'APK debug a
  été partagé, à ne plus changer
- **Build signé prêt pour le Play Store** : clé de signature générée
  (`keystore/le-professeur-release.keystore`, **jamais commit, à sauvegarder
  ailleurs aussi** - sa perte empêche toute mise à jour future de l'appli),
  configurée dans `android/keystore.properties` (non commit). `bundleRelease`
  produit l'AAB signé à uploader sur Play Console
- **Bibliothèque de vrais PDF avec stockage permanent** (`backend/pdf_seed/`,
  committé dans git - survit aux redéploiements, contrairement aux uploads
  via `/admin.html` qui restent éphémères sur Render gratuit) - 1 sujet réel
  ajouté (BEPC Anglais 2026, Côte d'Ivoire), à enrichir

Pas encore fait (décisions à prendre avec toi) :
- **Compte Google Play Console** — 25$ US, paiement unique, à créer par toi
  (je ne peux pas créer de compte ni entrer d'infos de paiement à ta place).
  Une fois fait : uploader `app-release.aab`, remplir la fiche (description,
  captures d'écran, formulaire Data Safety), soumettre à la revue Google
- **Vrai paiement CinetPay** — compte marchand en cours de création (RCCM
  disponible), en attente de leur réponse sur le bug d'inscription
- **Stockage persistant pour le reste** (quota, abonnements) — sur Render
  gratuit, ces fichiers disparaissent au redéploiement (les PDF, eux, sont
  maintenant permanents via `pdf_seed/`). Nécessaire avant la prod : disque
  payant Render, ou vraie base de données
- **Plus de vrais PDF officiels** — la bibliothèque n'en a qu'un ; donne-moi le
  chemin de tout fichier obtenu légitimement (CNECE, annales papier
  scannées...) pour que je l'ajoute de façon permanente

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
pour que les fichiers web soient recopiés dans le projet Android.
- Remplacer le stockage JSON (quota, reports, subscriptions) par une vraie base de
  données avant la mise en production (les fichiers locaux ne tiennent pas la
  charge à plusieurs utilisateurs simultanés)
- Relecture des 29 exercices par un(e) enseignant(e) local(e) — le mécanisme de
  signalement aide mais ne remplace pas une vraie relecture initiale
- Choix stratégique : rester pan-régional (8 pays) ou concentrer l'effort sur le
  Mali d'abord pour mieux valider avant d'étendre

## Ajouter de vrais sujets PDF

Va sur `/admin.html` (ex: https://le-professeur.onrender.com/admin.html), colle
ton `ADMIN_TOKEN` (défini dans les variables d'environnement Render/`.env`),
remplis le formulaire et choisis le fichier PDF. Le PDF apparaît alors dans le
panneau "Sujets d'examen" de l'appli, dans une section séparée des exercices
originaux, avec un lien pour le consulter et un bouton pour le travailler avec
l'IA.

Sources légitimes uniquement : PDF fournis par CNECE/ministère sur demande
directe, annales papier que tu as achetées et scannées, documents de ton
école. Ne jamais ajouter de PDF récupérés sur des sites d'agrégation tiers
(voir la discussion sur le droit d'auteur plus haut dans le projet).

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

## Coûts à anticiper

Chaque question posée = un appel à l'API Claude = un coût réel (facturé à l'usage
sur ton compte console.anthropic.com). Le quota gratuit par appareil sert à
protéger la marge — à ajuster (`DAILY_FREE_LIMIT` dans `.env`) selon ce que le
budget permet avant qu'un abonnement payant compense.
