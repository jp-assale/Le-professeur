# Play Console — réponses prêtes à recopier (app : JPA Academy, com.leprofesseur.app)

Basé sur le code réel de l'appli (version 2.10) : aucune pub, aucun outil d'analyse, aucun compte,
permissions Android = Internet + micro (dictée). Suivi d'erreurs (Sentry) côté serveur uniquement.

## 1. Sécurité des données → Collecte et sécurité

| Question | Réponse |
|---|---|
| Votre appli collecte-t-elle ou partage-t-elle des types de données utilisateur requis ? | **Oui** |
| Toutes les données collectées sont-elles chiffrées en transit ? | **Oui** (HTTPS partout) |
| Proposez-vous un moyen de demander la suppression des données ? | **Oui** — par e-mail à maintlog.sarl@gmail.com (indiqué dans la politique de confidentialité) |
| URL de la politique de confidentialité | https://le-professeur.onrender.com/privacy.html |
| Création de compte | Aucune (pas de connexion) |

## 2. Types de données (cocher seulement ceux-ci)

Règle Google : envoyer des données à un prestataire qui les traite POUR VOUS (Anthropic pour l'IA,
Microsoft pour la voix) n'est pas du « partage » → **Partagées : Non** partout.
(Si tu préfères être très prudent, tu peux cocher « Partagées » pour les questions, photos, PDF et prénom
avec la finalité « Fonctionnalité de l'appli » ; ce n'est pas faux, juste plus que nécessaire.)

| Catégorie Play → type | Collectée | Éphémère ? | Obligatoire / facultative | Finalités |
|---|---|---|---|---|
| Infos personnelles → **Nom** (prénom saisi par l'élève) | Oui | Non (l'audio de la salutation est gardé 14 jours) | Facultative | Fonctionnalité de l'appli, Personnalisation |
| Photos et vidéos → **Photos** (photo du sujet envoyée) | Oui | **Oui** (non conservée) | Facultative | Fonctionnalité de l'appli |
| Fichiers et documents → **Fichiers et documents** (PDF du sujet) | Oui | **Oui** | Facultative | Fonctionnalité de l'appli |
| Activité dans l'appli → **Autre contenu généré par l'utilisateur** (texte des questions) | Oui | **Oui** (non stocké en base) | Obligatoire pour utiliser l'IA | Fonctionnalité de l'appli |
| Activité dans l'appli → **Interactions avec l'appli** (matière, nb de questions, scores des quiz, dates) | Oui | Non | Obligatoire (automatique) | Fonctionnalité de l'appli, Personnalisation |
| Identifiants → **Identifiants d'appareil ou autres** (code appareil aléatoire ; adresse IP pour le compteur anti-abus) | Oui | Non | Obligatoire | Fonctionnalité de l'appli, Prévention de la fraude et sécurité |

**À NE PAS cocher** (non collectés par l'appli) : position, contacts, informations financières (le paiement se fait
par mobile money / WhatsApp, hors appli), santé, historique de navigation, messages, SMS, agenda,
journaux de plantage et diagnostics (aucun outil dans l'appli), enregistrements audio.

Pourquoi « enregistrements audio » = non : la dictée utilise la reconnaissance vocale du téléphone ; le serveur ne reçoit
que le texte (c'est écrit dans la politique de confidentialité).

## 3. Autres déclarations

- **Accès à l'appli** : aucune restriction, pas de connexion nécessaire.
- **Publicités** : **Non**, l'appli ne contient pas de publicité.
- **Classification du contenu** : catégorie « Référence, actualités ou éducation » ; pas de violence, pas de contenu sexuel,
  pas de jeux d'argent ; l'appli contient une IA générative (réponses générées par un modèle) → répondre **Oui** à
  « contenu généré par IA » s'il est demandé. Le bouton « ⚠️ Signaler une erreur » (menu Plus) répond à l'exigence de
  signalement du contenu IA.
- **Fonctionnalités financières** : Non. **Santé** : Non. **Actualités** : Non. **Gouvernement** : Non.
- **Permission RECORD_AUDIO** (si Google demande une justification) : « dictée vocale de la question de l'élève,
  uniquement quand il appuie sur le bouton micro ».

## 4. Public cible — DÉCISION À PRENDRE

La fiche actuelle dit « 13 ans et plus », mais l'appli propose aussi le niveau **Primaire (CEP)** (enfants d'environ 8-12 ans).
- **Option A (recommandée pour publier vite)** : déclarer « 13-15, 16-17, 18+ » (pas « moins de 13 ans ») ET retirer le niveau
  Primaire de l'appli avant publication (il n'y a que des sujets PDF de maths, aucune leçon).
- **Option B** : garder Primaire et déclarer aussi « 9-12 ans ». Google applique alors sa politique « Familles » : examen plus
  strict, déclarations supplémentaires, pas de collecte d'identifiant publicitaire (tu n'en as pas). Plus long à valider.

## 5. Corrections suggérées à la fiche Play Store (play-store-fiche.txt)

- La description ne parle pas des nouveautés : ajouter « voix du Prof (voix d'homme), schémas dans les leçons ».
- « Un abonnement illimité est prévu, payable via Orange Money, Wave ou Moov Money » : correct tant que le paiement se fait
  manuellement par WhatsApp ; ne pas écrire « paiement automatique ».
- Ne pas promettre de « cours pour toutes les matières » : les leçons existent surtout pour Maths, Physique-Chimie, SVT,
  Histoire-Géo et un peu de Philosophie.
