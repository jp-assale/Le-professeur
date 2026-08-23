"""Catalogue d'exercices type examen (DEF/BEPC/Bac) pour le mode "Sujets d'examen".

IMPORTANT: ce sont des exercices originaux, ecrits dans le style des epreuves
nationales (memes themes, meme niveau de difficulte) - PAS des sujets officiels
scannes ou copies. Pour de vrais sujets officiels, il faudra soit les saisir a
la main a partir d'archives ministerielles/associations d'enseignants, soit
nouer un partenariat avec un site qui en detient deja (ex. epreuvesetcorriges.com),
soit obtenir une autorisation de reproduction. Ne pas presenter ce contenu comme
"officiel" tant que la source n'est pas verifiee.

Chaque entree:
- id: identifiant stable utilise par le frontend et dans /api/ask
- pays / niveau / matiere: memes codes que curriculum.py
- annee: annee de reference (indicative, pas une vraie session d'examen)
- titre: theme court affiche dans la liste
- enonce: texte complet de l'exercice
"""

EPREUVES = [
    {
        "id": "ml-college-maths-eq1",
        "pays": "mali",
        "niveau": "college",
        "matiere": "Mathematiques",
        "annee": 2024,
        "titre": "Equations du premier degre",
        "enonce": (
            "Exercice (6 points)\n"
            "1) Resoudre dans R l'equation : 3x - 7 = 2x + 5\n"
            "2) Un vendeur de Bamako achete des mangues a 150 FCFA le kilo. Il les "
            "revend avec un benefice de 50 FCFA par kilo. Sachant qu'il a gagne au "
            "total 4500 FCFA sur cette vente, combien de kilos de mangues a-t-il "
            "vendus ? Poser une equation puis la resoudre."
        ),
    },
    {
        "id": "ml-college-francais-comprehension1",
        "pays": "mali",
        "niveau": "college",
        "matiere": "Francais",
        "annee": 2024,
        "titre": "Comprehension de texte et expression ecrite",
        "enonce": (
            "Texte : 'Depuis quelques annees, de plus en plus de jeunes maliens "
            "quittent leur village pour tenter leur chance en ville. Cet exode "
            "rural transforme profondement la vie des campagnes comme celle des "
            "villes.'\n\n"
            "1) Quel est le theme principal de ce texte ? (2 points)\n"
            "2) Releve un mot de la meme famille que 'rural'. (2 points)\n"
            "3) Expression ecrite (10 lignes) : D'apres toi, quelles sont les "
            "consequences de l'exode rural sur la vie des villages ? (10 points)"
        ),
    },
    {
        "id": "ml-lycee-maths-fonctions1",
        "pays": "mali",
        "niveau": "lycee",
        "matiere": "Mathematiques",
        "annee": 2024,
        "titre": "Etude d'une fonction du second degre",
        "enonce": (
            "On considere la fonction f definie sur R par f(x) = x^2 - 4x + 3.\n"
            "1) Calculer f(0), f(1) et f(3).\n"
            "2) Determiner la forme canonique de f(x).\n"
            "3) Etudier les variations de f et dresser son tableau de variation.\n"
            "4) Resoudre l'equation f(x) = 0."
        ),
    },
    {
        "id": "sn-college-maths-stats1",
        "pays": "senegal",
        "niveau": "college",
        "matiere": "Mathematiques",
        "annee": 2024,
        "titre": "Statistiques : moyenne et effectifs",
        "enonce": (
            "Un professeur releve les notes sur 20 de sa classe de 3eme lors d'un "
            "devoir de mathematiques :\n"
            "8, 12, 15, 9, 14, 17, 11, 13, 10, 16\n"
            "1) Calculer la moyenne de la classe.\n"
            "2) Determiner la note minimale et la note maximale.\n"
            "3) Combien d'eleves ont une note superieure ou egale a 12 ?"
        ),
    },
    {
        "id": "ci-college-maths-geo1",
        "pays": "cote_ivoire",
        "niveau": "college",
        "matiere": "Mathematiques",
        "annee": 2024,
        "titre": "Geometrie : theoreme de Pythagore",
        "enonce": (
            "ABC est un triangle rectangle en A tel que AB = 6 cm et AC = 8 cm.\n"
            "1) Calculer la longueur BC.\n"
            "2) Calculer l'aire du triangle ABC.\n"
            "3) Un eleve affirme que le perimetre du triangle est superieur a "
            "25 cm. A-t-il raison ? Justifier."
        ),
    },
    {
        "id": "ml-college-pc-circuit1",
        "pays": "mali",
        "niveau": "college",
        "matiere": "Physique-Chimie",
        "annee": 2024,
        "titre": "Circuit electrique simple",
        "enonce": (
            "Exercice (5 points)\n"
            "1) Un circuit electrique est compose d'une pile de 4,5V, d'une lampe "
            "et d'un interrupteur relies en serie. Schematiser ce circuit en "
            "utilisant les symboles normalises.\n"
            "2) L'interrupteur est ouvert. La lampe brille-t-elle ? Justifier.\n"
            "3) On mesure l'intensite du courant dans le circuit ferme : I = 0,3 A. "
            "Calculer la resistance de la lampe sachant que U = 4,5 V "
            "(loi d'Ohm : U = R x I)."
        ),
    },
    {
        "id": "ml-college-svt-digestion1",
        "pays": "mali",
        "niveau": "college",
        "matiere": "SVT",
        "annee": 2024,
        "titre": "La digestion des aliments",
        "enonce": (
            "Exercice (5 points)\n"
            "1) Cite dans l'ordre les organes traverses par les aliments depuis "
            "la bouche jusqu'a l'anus.\n"
            "2) Quel est le role du suc gastrique dans l'estomac ?\n"
            "3) Explique en quelques lignes pourquoi il est important de bien "
            "macher les aliments avant de les avaler."
        ),
    },
    {
        "id": "ml-lycee-philo-liberte1",
        "pays": "mali",
        "niveau": "lycee",
        "matiere": "Philosophie",
        "annee": 2024,
        "titre": "Dissertation : la liberte",
        "enonce": (
            "Sujet de dissertation :\n"
            "« Peut-on etre libre sans respecter aucune loi ? »\n"
            "Vous redigerez une dissertation structuree (introduction avec "
            "problematique, developpement en deux ou trois parties argumentees "
            "avec exemples, conclusion) repondant a cette question."
        ),
    },
    {
        "id": "sn-college-francais-conjugaison1",
        "pays": "senegal",
        "niveau": "college",
        "matiere": "Francais",
        "annee": 2024,
        "titre": "Conjugaison et expression ecrite",
        "enonce": (
            "Exercice (10 points)\n"
            "1) Conjugue le verbe 'partir' au present, au passe compose et au "
            "futur simple, a la troisieme personne du singulier. (6 points)\n"
            "2) Redige un paragraphe de 8 a 10 lignes racontant un souvenir de "
            "marche au grand marche de Dakar, en utilisant au moins trois verbes "
            "au passe compose. (4 points)"
        ),
    },
    {
        "id": "sn-lycee-maths-suites1",
        "pays": "senegal",
        "niveau": "lycee",
        "matiere": "Mathematiques",
        "annee": 2024,
        "titre": "Suites numeriques",
        "enonce": (
            "Exercice (7 points)\n"
            "On considere la suite (Un) definie par U0 = 3 et, pour tout entier "
            "naturel n, U(n+1) = 2Un - 1.\n"
            "1) Calculer U1, U2 et U3.\n"
            "2) On pose Vn = Un - 1. Montrer que (Vn) est une suite geometrique "
            "dont on precisera la raison.\n"
            "3) En deduire l'expression de Un en fonction de n."
        ),
    },
    {
        "id": "sn-college-histgeo-fleuve1",
        "pays": "senegal",
        "niveau": "college",
        "matiere": "Histoire-Geographie",
        "annee": 2024,
        "titre": "Le fleuve Senegal et son bassin",
        "enonce": (
            "Exercice (6 points)\n"
            "1) Cite trois pays traverses par le fleuve Senegal.\n"
            "2) Quel est le role economique de ce fleuve pour les populations "
            "riveraines (agriculture, peche, transport) ?\n"
            "3) Nomme un grand barrage construit sur le fleuve Senegal et "
            "explique son interet."
        ),
    },
    {
        "id": "ci-college-francais-resume1",
        "pays": "cote_ivoire",
        "niveau": "college",
        "matiere": "Francais",
        "annee": 2024,
        "titre": "Resume de texte",
        "enonce": (
            "Texte (a resumer au quart de sa longueur) :\n"
            "« La culture du cacao occupe une place centrale dans l'economie "
            "ivoirienne depuis plus d'un siecle. Des milliers de familles vivent "
            "de cette production, mais les cacaoculteurs font face a de nombreux "
            "defis : prix instables, vieillissement des plantations, et effets "
            "du changement climatique sur les recoltes. »\n\n"
            "1) Resume ce texte en respectant la consigne de longueur. (8 points)\n"
            "2) Quelle est l'idee principale du texte ? (2 points)"
        ),
    },
    {
        "id": "ci-college-pc-etatsmatiere1",
        "pays": "cote_ivoire",
        "niveau": "college",
        "matiere": "Physique-Chimie",
        "annee": 2024,
        "titre": "Les changements d'etat de l'eau",
        "enonce": (
            "Exercice (5 points)\n"
            "1) Nomme les trois etats physiques de l'eau.\n"
            "2) Comment s'appelle le changement d'etat de l'eau liquide vers "
            "l'etat gazeux ? Et de l'etat liquide vers l'etat solide ?\n"
            "3) A quelle temperature l'eau pure bout-elle au niveau de la mer ? "
            "Et a quelle temperature gele-t-elle ?"
        ),
    },
    {
        "id": "ci-lycee-maths-probabilites1",
        "pays": "cote_ivoire",
        "niveau": "lycee",
        "matiere": "Mathematiques",
        "annee": 2024,
        "titre": "Probabilites",
        "enonce": (
            "Exercice (6 points)\n"
            "Un sac contient 5 boules rouges, 3 boules vertes et 2 boules "
            "jaunes, indiscernables au toucher. On tire une boule au hasard.\n"
            "1) Quelle est la probabilite de tirer une boule rouge ?\n"
            "2) Quelle est la probabilite de tirer une boule verte ou jaune ?\n"
            "3) On tire une boule, on note sa couleur, puis on la remet dans le "
            "sac avant un second tirage. Quelle est la probabilite d'obtenir "
            "deux boules rouges de suite ?"
        ),
    },
    {
        "id": "bf-college-maths-pourcentage1",
        "pays": "burkina_faso",
        "niveau": "college",
        "matiere": "Mathematiques",
        "annee": 2024,
        "titre": "Pourcentages et proportionnalite",
        "enonce": (
            "Exercice (6 points)\n"
            "Un commercant de Ouagadougou achete un sac de coton a 15000 FCFA. "
            "Il le revend avec une augmentation de 20%.\n"
            "1) Calculer le prix de vente du sac de coton.\n"
            "2) S'il vend 12 sacs dans les memes conditions, quel est son "
            "benefice total ?\n"
            "3) Quel pourcentage represente ce benefice total par rapport au "
            "prix d'achat total des 12 sacs ?"
        ),
    },
    {
        "id": "bf-college-francais-grammaire1",
        "pays": "burkina_faso",
        "niveau": "college",
        "matiere": "Francais",
        "annee": 2024,
        "titre": "Nature et fonction des mots",
        "enonce": (
            "Exercice (8 points)\n"
            "Phrase a analyser : « Les eleves studieux de Ouagadougou "
            "reussissent brillamment leurs examens chaque annee. »\n"
            "1) Identifie la nature grammaticale des mots : 'studieux', "
            "'brillamment', 'chaque'.\n"
            "2) Quelle est la fonction du groupe nominal 'leurs examens' dans "
            "la phrase ?\n"
            "3) Recris la phrase en remplacant 'les eleves' par 'l'eleve' et "
            "fais tous les accords necessaires."
        ),
    },
    {
        "id": "bf-lycee-maths-derivees1",
        "pays": "burkina_faso",
        "niveau": "lycee",
        "matiere": "Mathematiques",
        "annee": 2024,
        "titre": "Derivation de fonctions",
        "enonce": (
            "Exercice (7 points)\n"
            "On considere la fonction f definie sur R par "
            "f(x) = 2x^3 - 3x^2 + 1.\n"
            "1) Calculer la derivee f'(x).\n"
            "2) Etudier le signe de f'(x) et en deduire les variations de f.\n"
            "3) Determiner les coordonnees des points ou la tangente a la "
            "courbe de f est horizontale."
        ),
    },
    {
        "id": "bj-college-maths-fractions1",
        "pays": "benin",
        "niveau": "college",
        "matiere": "Mathematiques",
        "annee": 2024,
        "titre": "Operations sur les fractions",
        "enonce": (
            "Exercice (6 points)\n"
            "1) Calculer et donner le resultat sous forme de fraction "
            "irreductible : 2/3 + 5/6\n"
            "2) Calculer : (3/4) x (8/9)\n"
            "3) Un champ de palmiers a huile a Porto-Novo est partage entre "
            "trois freres. Le premier recoit 1/2 du champ, le deuxieme 1/3, et "
            "le troisieme le reste. Quelle fraction du champ revient au "
            "troisieme frere ?"
        ),
    },
    {
        "id": "bj-college-francais-dictee1",
        "pays": "benin",
        "niveau": "college",
        "matiere": "Francais",
        "annee": 2024,
        "titre": "Dictee et questions de comprehension",
        "enonce": (
            "Texte : « Le marche de Cotonou s'anime des le lever du jour. "
            "Les vendeuses installent leurs etals colores, remplis de fruits, "
            "de legumes et de tissus aux motifs vifs. »\n\n"
            "1) Combien de phrases compte ce texte ?\n"
            "2) Releve tous les adjectifs qualificatifs du texte.\n"
            "3) Conjugue le verbe 's'animer' a l'imparfait, a la meme personne "
            "que dans le texte."
        ),
    },
    {
        "id": "bj-college-svt-respiration1",
        "pays": "benin",
        "niveau": "college",
        "matiere": "SVT",
        "annee": 2024,
        "titre": "La respiration chez l'Homme",
        "enonce": (
            "Exercice (5 points)\n"
            "1) Nomme les principaux organes de l'appareil respiratoire, dans "
            "l'ordre du passage de l'air.\n"
            "2) Quel gaz l'organisme absorbe-t-il lors de la respiration, et "
            "quel gaz rejette-t-il ?\n"
            "3) Explique pourquoi il est dangereux de respirer dans un local "
            "ferme sans aeration."
        ),
    },
    {
        "id": "tg-college-maths-geometrie1",
        "pays": "togo",
        "niveau": "college",
        "matiere": "Mathematiques",
        "annee": 2024,
        "titre": "Perimetre et aire d'un rectangle",
        "enonce": (
            "Exercice (5 points)\n"
            "Un terrain rectangulaire situe pres de Lome mesure 45 m de "
            "longueur et 30 m de largeur.\n"
            "1) Calculer le perimetre de ce terrain.\n"
            "2) Calculer son aire en metres carres.\n"
            "3) Le proprietaire veut cloturer le terrain avec un grillage qui "
            "coute 2500 FCFA le metre. Quel sera le cout total de la cloture ?"
        ),
    },
    {
        "id": "tg-college-francais-vocabulaire1",
        "pays": "togo",
        "niveau": "college",
        "matiere": "Francais",
        "annee": 2024,
        "titre": "Vocabulaire et figures de style",
        "enonce": (
            "Exercice (7 points)\n"
            "1) Donne un synonyme et un antonyme du mot 'genereux'.\n"
            "2) Identifie la figure de style dans la phrase : « Le soleil "
            "de Lome brulait comme un four. »\n"
            "3) Redige une phrase contenant une comparaison de ton choix."
        ),
    },
    {
        "id": "tg-lycee-maths-vecteurs1",
        "pays": "togo",
        "niveau": "lycee",
        "matiere": "Mathematiques",
        "annee": 2024,
        "titre": "Vecteurs et geometrie analytique",
        "enonce": (
            "Exercice (6 points)\n"
            "Dans un repere orthonorme, on donne les points A(1;2), B(4;6) et "
            "C(-2;3).\n"
            "1) Calculer les coordonnees du vecteur AB.\n"
            "2) Calculer la distance AB.\n"
            "3) Determiner les coordonnees du milieu du segment [AC]."
        ),
    },
    {
        "id": "ne-college-maths-proportionnalite1",
        "pays": "niger",
        "niveau": "college",
        "matiere": "Mathematiques",
        "annee": 2024,
        "titre": "Proportionnalite",
        "enonce": (
            "Exercice (6 points)\n"
            "A Niamey, 8 kg de mil coutent 4000 FCFA.\n"
            "1) Quel est le prix de 1 kg de mil ?\n"
            "2) Quel serait le prix de 15 kg de mil, au meme tarif ?\n"
            "3) Une famille dispose de 6000 FCFA. Combien de kilos de mil "
            "peut-elle acheter au maximum ?"
        ),
    },
    {
        "id": "ne-college-francais-texte1",
        "pays": "niger",
        "niveau": "college",
        "matiere": "Francais",
        "annee": 2024,
        "titre": "Comprehension et expression ecrite",
        "enonce": (
            "Texte : « Le fleuve Niger traverse la ville de Niamey et "
            "constitue une source de vie pour de nombreuses familles qui y "
            "pechent et y cultivent des terres fertiles. »\n\n"
            "1) De quel fleuve parle ce texte ?\n"
            "2) Releve les deux activites economiques mentionnees dans le "
            "texte.\n"
            "3) Expression ecrite (8 lignes) : decris un lieu de ta ville que "
            "tu apprecies particulierement."
        ),
    },
    {
        "id": "ne-lycee-maths-logarithme1",
        "pays": "niger",
        "niveau": "lycee",
        "matiere": "Mathematiques",
        "annee": 2024,
        "titre": "Fonction logarithme",
        "enonce": (
            "Exercice (6 points)\n"
            "1) Resoudre dans R l'equation : ln(x) = 2 (valeur exacte puis "
            "valeur approchee a 0,01 pres).\n"
            "2) Resoudre l'inequation : ln(x) < 0.\n"
            "3) Calculer la derivee de la fonction g definie par "
            "g(x) = ln(2x + 1) sur son domaine de definition."
        ),
    },
    {
        "id": "gn-college-maths-equations1",
        "pays": "guinee",
        "niveau": "college",
        "matiere": "Mathematiques",
        "annee": 2024,
        "titre": "Equations et mise en equation",
        "enonce": (
            "Exercice (6 points)\n"
            "A Conakry, un mineur transporte des sacs de bauxite. Chaque sac "
            "pese 25 kg de plus que le precedent, et le premier sac pese x kg.\n"
            "1) Exprime en fonction de x le poids du troisieme sac.\n"
            "2) Sachant que le troisieme sac pese 90 kg, calcule x.\n"
            "3) Quel est alors le poids total des trois sacs ?"
        ),
    },
    {
        "id": "gn-college-francais-narration1",
        "pays": "guinee",
        "niveau": "college",
        "matiere": "Francais",
        "annee": 2024,
        "titre": "Recit et temps du passe",
        "enonce": (
            "Exercice (8 points)\n"
            "1) Conjugue le verbe 'aller' a l'imparfait et au passe simple, a "
            "la premiere personne du singulier.\n"
            "2) Redige un court recit (10 lignes) racontant un voyage en "
            "pirogue sur le fleuve, en utilisant le passe simple pour les "
            "actions principales et l'imparfait pour les descriptions."
        ),
    },
    {
        "id": "gn-college-svt-ecosysteme1",
        "pays": "guinee",
        "niveau": "college",
        "matiere": "SVT",
        "annee": 2024,
        "titre": "Ecosystemes et biodiversite",
        "enonce": (
            "Exercice (5 points)\n"
            "1) Definis ce qu'est un ecosysteme.\n"
            "2) Cite trois elements (vivants ou non vivants) presents dans un "
            "ecosysteme de foret guineenne.\n"
            "3) Explique en quelques lignes pourquoi la deforestation menace "
            "la biodiversite."
        ),
    },
]


def list_epreuves(pays: str | None = None, niveau: str | None = None, matiere: str | None = None):
    result = EPREUVES
    if pays:
        result = [e for e in result if e["pays"] == pays]
    if niveau:
        result = [e for e in result if e["niveau"] == niveau]
    if matiere:
        result = [e for e in result if e["matiere"] == matiere]
    return [{"id": e["id"], "titre": e["titre"], "annee": e["annee"]} for e in result]


def get_epreuve(epreuve_id: str):
    for e in EPREUVES:
        if e["id"] == epreuve_id:
            return e
    return None
