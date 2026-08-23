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
- **Premier APK debug compilé avec succès** (`android/app/build/outputs/apk/debug/app-debug.apk`,
  ~3,9 Mo) — preuve que la chaîne de compilation fonctionne de bout en bout

Pas encore fait (décisions à prendre avec toi) :
- **Icônes PWA réelles** (`frontend/icons/icon-192.png`, `icon-512.png` manquants)
  — l'APK actuel utilise les icônes par défaut de Capacitor, à remplacer avant
  publication
- **Vrai paiement CinetPay** — nécessite que tu créés le compte marchand (KYC),
  je ne peux pas le faire à ta place
- **Backend pas encore déployé publiquement** — l'APK actuel pointe vers
  `AIDA_API_BASE_URL = ""` (vide), donc il ne fonctionnera sur un vrai téléphone
  que si le backend tourne sur le même réseau/`localhost` accessible. Pour un
  vrai test ou une publication, il faut héberger `backend/` quelque part de
  public (Render, Fly.io, VPS...) puis mettre l'URL dans
  `frontend/js/config.js` et relancer `npx cap sync android` + rebuild
- **APK non signé pour la release** — celui compilé est un build *debug*
  (installable pour tester, pas publiable tel quel). Il faudra générer une clé
  de signature et un build *release* avant le Play Store
- **`appId` encore un placeholder** (`com.aida.assistant` dans
  `capacitor.config.json`) — à figer avant la première publication (permanent
  une fois publié)

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
