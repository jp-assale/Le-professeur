/* Transforme un texte de cours/reponse (Markdown + LaTeX) en texte FRANCAIS
   lisible a voix haute : formules, unites, operateurs, puissances, fractions,
   pauses entre les etapes. Utilise par app.js (chat) et cours-render.js (cours),
   et testable sous Node (module.exports).

   window.speakableFrench(texte) -> texte a lire
   window.speechRateFor(texte)   -> vitesse (1 = normale) : plus lente quand le
                                    texte contient des calculs, pour pouvoir suivre. */
(function (root) {
  "use strict";

  const GREEK = {
    alpha: "alpha", beta: "bêta", gamma: "gamma", Gamma: "gamma", delta: "delta", Delta: "delta",
    epsilon: "epsilon", varepsilon: "epsilon", theta: "thêta", Theta: "thêta", lambda: "lambda",
    Lambda: "lambda", mu: "mu", nu: "nu", pi: "pi", Pi: "pi", rho: "rhô", sigma: "sigma",
    Sigma: "sigma", tau: "tau", phi: "phi", varphi: "phi", Phi: "phi", omega: "oméga",
    Omega: "oméga", eta: "êta", zeta: "dzêta", psi: "psi", Psi: "psi", chi: "khi",
  };

  const SYMBOLS = {
    times: " fois ", cdot: " fois ", div: " divisé par ", pm: " plus ou moins ", mp: " moins ou plus ",
    neq: " différent de ", ne: " différent de ", leq: " inférieur ou égal à ", le: " inférieur ou égal à ",
    geq: " supérieur ou égal à ", ge: " supérieur ou égal à ", approx: " environ égal à ",
    equiv: " équivaut à ", Rightarrow: " donc ", implies: " donc ", Leftrightarrow: " équivaut à ",
    iff: " équivaut à ", to: " tend vers ", rightarrow: " donne ", longrightarrow: " donne ",
    in: " appartient à ", notin: " n'appartient pas à ", subset: " inclus dans ", cup: " union ",
    cap: " inter ", infty: " l'infini ", circ: " degrés ", ldots: " etc. ", cdots: " etc. ",
    dots: " etc. ", sin: " sinus ", cos: " cosinus ", tan: " tangente ", ln: " logarithme népérien de ",
    log: " logarithme de ", exp: " exponentielle de ", angle: " angle ", parallel: " parallèle à ",
    perp: " perpendiculaire à ", prime: " prime ", int: " intégrale ", sum: " somme ", prod: " produit ",
    lim: " limite ", forall: " pour tout ", exists: " il existe ", degree: " degrés ",
  };

  // symbole -> [singulier, pluriel, genre]
  const UNITS = {
    km: ["kilomètre", "kilomètres", "m"], hm: ["hectomètre", "hectomètres", "m"],
    dam: ["décamètre", "décamètres", "m"], dm: ["décimètre", "décimètres", "m"],
    cm: ["centimètre", "centimètres", "m"], mm: ["millimètre", "millimètres", "m"],
    "µm": ["micromètre", "micromètres", "m"], "μm": ["micromètre", "micromètres", "m"],
    nm: ["nanomètre", "nanomètres", "m"], m: ["mètre", "mètres", "m"],
    kg: ["kilogramme", "kilogrammes", "m"], mg: ["milligramme", "milligrammes", "m"],
    g: ["gramme", "grammes", "m"], t: ["tonne", "tonnes", "f"],
    ms: ["milliseconde", "millisecondes", "f"], s: ["seconde", "secondes", "f"],
    min: ["minute", "minutes", "f"], h: ["heure", "heures", "f"],
    mL: ["millilitre", "millilitres", "m"], ml: ["millilitre", "millilitres", "m"],
    cL: ["centilitre", "centilitres", "m"], cl: ["centilitre", "centilitres", "m"],
    dL: ["décilitre", "décilitres", "m"], dl: ["décilitre", "décilitres", "m"],
    L: ["litre", "litres", "m"], l: ["litre", "litres", "m"],
    mmol: ["millimole", "millimoles", "f"], mol: ["mole", "moles", "f"],
    kN: ["kilonewton", "kilonewtons", "m"], N: ["newton", "newtons", "m"],
    MJ: ["mégajoule", "mégajoules", "m"], kJ: ["kilojoule", "kilojoules", "m"], J: ["joule", "joules", "m"],
    kcal: ["kilocalorie", "kilocalories", "f"], cal: ["calorie", "calories", "f"],
    MW: ["mégawatt", "mégawatts", "m"], kW: ["kilowatt", "kilowatts", "m"], W: ["watt", "watts", "m"],
    kWh: ["kilowattheure", "kilowattheures", "m"], Wh: ["wattheure", "wattheures", "m"],
    kV: ["kilovolt", "kilovolts", "m"], mV: ["millivolt", "millivolts", "m"], V: ["volt", "volts", "m"],
    mA: ["milliampère", "milliampères", "m"], A: ["ampère", "ampères", "m"],
    MΩ: ["mégohm", "mégohms", "m"], kΩ: ["kilo-ohm", "kilo-ohms", "m"], "Ω": ["ohm", "ohms", "m"],
    MHz: ["mégahertz", "mégahertz", "m"], kHz: ["kilohertz", "kilohertz", "m"], Hz: ["hertz", "hertz", "m"],
    hPa: ["hectopascal", "hectopascals", "m"], kPa: ["kilopascal", "kilopascals", "m"],
    Pa: ["pascal", "pascals", "m"], bar: ["bar", "bars", "m"], K: ["kelvin", "kelvins", "m"],
    eV: ["électronvolt", "électronvolts", "m"], FCFA: ["franc CFA", "francs CFA", "m"],
  };

  // Symboles d'une seule lettre : ambigus avec des variables (m, t, s, A, V...).
  const AMBIGUOUS = new Set(["m", "g", "s", "h", "t", "l", "L", "N", "J", "W", "V", "A", "K"]);
  // Parmi eux, ceux qu'on accepte collés au nombre dans un texte (pas une formule) : "5m".
  const GLUED_OK = new Set(["m", "g", "s", "h", "l", "L"]);

  const UNIT_ALT = Object.keys(UNITS)
    .sort((a, b) => b.length - a.length)
    .map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|");
  const UNIT_TOKEN = "(" + UNIT_ALT + ")(?:\\^\\{?([23])\\}?|([²³]))?";
  const LETTER = "A-Za-zÀ-ÿ";
  const RE_NUM_UNIT = new RegExp(
    "(-?\\d+(?:[.,]\\d+)?)(\\s*)" + UNIT_TOKEN + "(?:\\/" + UNIT_TOKEN + ")?(?![" + LETTER + "0-9_])", "g");
  const RE_BARE_UNIT = new RegExp(
    "(?<![" + LETTER + "0-9_\\/])" + UNIT_TOKEN + "(?:\\/" + UNIT_TOKEN + ")?(?![" + LETTER + "0-9_])", "g");

  function expOf(a, b) {
    const e = a || (b === "²" ? "2" : b === "³" ? "3" : "");
    return e;
  }

  function unitWords(sym, exp, plural, denominator) {
    const u = UNITS[sym];
    let name = plural && !denominator ? u[1] : u[0];
    if (exp === "2") name = (plural && !denominator ? u[1] : u[0]) + (plural && !denominator ? (u[2] === "f" ? " carrées" : " carrés") : (u[2] === "f" ? " carrée" : " carré"));
    if (exp === "3") name = (plural && !denominator ? u[1] : u[0]) + (plural && !denominator ? " cubes" : " cube");
    return name;
  }

  function composeUnit(u1, e1, u2, e2, plural) {
    let out = unitWords(u1, e1, plural, false);
    if (u2) out += " par " + unitWords(u2, e2, false, true);
    return out;
  }

  function convertUnits(text, inMath) {
    // °C, °F, ° et % collés ou non à un nombre.
    text = text
      .replace(/(-?\d+(?:[.,]\d+)?)\s*°\s*C\b/g, (m, n) => n + (Math.abs(parseFloat(n.replace(",", "."))) >= 2 ? " degrés Celsius" : " degré Celsius"))
      .replace(/(-?\d+(?:[.,]\d+)?)\s*°(?!\s*C)/g, (m, n) => n + (Math.abs(parseFloat(n.replace(",", "."))) >= 2 ? " degrés" : " degré"))
      .replace(/°\s*C\b/g, " degrés Celsius")
      .replace(/\s*(?:\\%|%)/g, " pour cent");
    // nombre + unite
    text = text.replace(RE_NUM_UNIT, (m, num, space, u1, e1a, e1b, u2, e2a, e2b, offset, whole) => {
      const e1 = expOf(e1a, e1b);
      const e2 = expOf(e2a, e2b);
      const plain = !e1 && !u2;
      if (AMBIGUOUS.has(u1) && plain) {
        const next = whole.slice(offset + m.length).match(/^\s*(.)?/)[1] || "";
        // « 2 m v² », « 3m(x) » : une variable suit, ce n'est pas une unite.
        if (/[A-Za-z0-9(]/.test(next)) return m;
        // "2A", "3m + 2" : variable probable. "5m" seul reste une longueur.
        if (space === "" && (inMath || !GLUED_OK.has(u1) || /[+\-−=*\/×÷^<>]/.test(next))) return m;
      }
      const value = parseFloat(num.replace(",", "."));
      return num + " " + composeUnit(u1, e1, u2, e2, Math.abs(value) >= 2);
    });
    // unites composees ou avec exposant sans nombre (m/s, km/h, cm³, kg/m³...)
    text = text.replace(RE_BARE_UNIT, (m, u1, e1a, e1b, u2, e2a, e2b) => {
      const e1 = expOf(e1a, e1b);
      const e2 = expOf(e2a, e2b);
      if (!e1 && !u2) return m;
      if (inMath && (u1.length === 1 || (u2 && u2.length === 1 && !e2))) return m;
      if (!inMath && u1.length === 1 && !u2 && AMBIGUOUS.has(u1) && /^[stmhg]$/.test(u1) && e1) return m;
      return composeUnit(u1, e1, u2, e2, true);
    });
    return text;
  }

  function dropBraces(s, re, fn) {
    let prev;
    do { prev = s; s = s.replace(re, fn); } while (s !== prev);
    return s;
  }

  function spokenMath(expr, opts) {
    const inMath = !(opts && opts.prose);
    let s = " " + expr + " ";

    // Mise en forme sans effet a l'oral.
    s = s.replace(/\\(?:left|right|displaystyle|textstyle|big|Big|bigg|Bigg|limits|nolimits)(?![A-Za-z])/g, " ")
      .replace(/\\[,;:! ]/g, " ").replace(/~/g, " ").replace(/\\(?:quad|qquad)(?![A-Za-z])/g, " ")
      .replace(/−/g, "-");

    // Texte dans la formule (unites ecrites \text{m}, \mathrm{kg}).
    s = dropBraces(s, /\\(?:text|mathrm|textbf|mathbf|mbox|operatorname|textit)\s*\{([^{}]*)\}/g, " $1 ");
    s = s.replace(/\\mathbb\{([^{}]*)\}/g, " $1 ");

    // Fractions et racines (de l'interieur vers l'exterieur).
    s = dropBraces(s, /\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, (m, a, b) => {
      const simple = (x) => !/[\s+\-*/=]/.test(x.trim());
      return simple(a) && simple(b) ? " " + a + " sur " + b + " " : " , " + a + " , sur , " + b + " , ";
    });
    s = dropBraces(s, /\\sqrt\s*\[([^\]]*)\]\s*\{([^{}]*)\}/g, " racine d'ordre $1 de , $2 , ");
    s = dropBraces(s, /\\sqrt\s*\{([^{}]*)\}/g, " racine carrée de , $1 , ");
    s = s.replace(/\\sqrt\s*([A-Za-z0-9])/g, " racine carrée de $1 ").replace(/√\s*\(?([A-Za-z0-9]+)\)?/g, " racine carrée de $1 ");
    s = dropBraces(s, /\\(?:vec|overrightarrow)\s*\{([^{}]*)\}/g, " vecteur $1 ");
    s = dropBraces(s, /\\(?:widehat)\s*\{([^{}]*)\}/g, " angle $1 ");
    s = dropBraces(s, /\\(?:overline|bar|hat|tilde|dot)\s*\{([^{}]*)\}/g, " $1 ");
    s = s.replace(/\\lim\s*_\s*\{([^{}]*)\}/g, " limite quand $1 , ");

    s = s.replace(/(\d)\s*(k|M)?\\Omega(?![A-Za-z])/g, "$1 $2Ω");

    // Unites (avant les operateurs, pour ne pas casser « m/s » et « kg/m³ »).
    s = convertUnits(s, inMath);

    // Commandes \nom : lettres grecques, symboles, fonctions ; inconnues : ignorees.
    s = s.replace(/\\([A-Za-z]+)/g, (m, name) => {
      if (GREEK[name]) return " " + GREEK[name] + " ";
      if (SYMBOLS[name]) return SYMBOLS[name];
      return " ";
    });
    s = s.replace(/\\\\/g, " , ").replace(/&/g, " ");

    // Puissances.
    s = s.replace(/\^\s*\{\s*2\s*\}|\^\s*2(?![0-9])|²/g, " au carré ")
      .replace(/\^\s*\{\s*3\s*\}|\^\s*3(?![0-9])|³/g, " au cube ")
      .replace(/\^\s*\{([^{}]+)\}/g, (m, e) => (/[\s+\-*/]/.test(e.trim()) ? " puissance , " + e + " , " : " puissance " + e + " "))
      .replace(/\^\s*(-?[A-Za-z0-9])/g, " puissance $1 ");

    // Indices : chimie (H_2O, CO_2) = chiffres seuls ; maths (u_n, x_1) = « indice ».
    s = s.replace(/(?<=[A-Z)])_\s*\{?(\d+)\}?/g, " $1 ")
      .replace(/_\s*\{([^{}]+)\}/g, " indice $1 , ")
      .replace(/_\s*([A-Za-z0-9])/g, " indice $1 ");

    s = s.replace(/[{}]/g, " ");

    // Fonctions f(x), g(x), h(x).
    s = s.replace(/(?<![A-Za-z])([fgh])\(([^()]*)\)/g, " $1 de $2 , ");

    // Operateurs.
    s = s.replace(/≠/g, " différent de ").replace(/≤/g, " inférieur ou égal à ").replace(/≥/g, " supérieur ou égal à ")
      .replace(/≈/g, " environ égal à ").replace(/×/g, " fois ").replace(/÷/g, " divisé par ")
      .replace(/±/g, " plus ou moins ").replace(/π/g, " pi ").replace(/∞/g, " l'infini ")
      .replace(/→/g, " donne ").replace(/⇒/g, " donc ")
      .replace(/=/g, " égale ").replace(/\+/g, " plus ").replace(/\*/g, " fois ")
      .replace(/</g, " inférieur à ").replace(/>/g, " supérieur à ")
      .replace(/(?<=[0-9A-Za-z)\s])\/(?=[0-9A-Za-z(\s])/g, " sur ")
      .replace(/-/g, " moins ");

    // Parentheses.
    s = s.replace(/\(/g, " , parenthèse ouverte , ").replace(/\)/g, " , parenthèse fermée , ")
      .replace(/\[/g, " , crochet ouvert , ").replace(/\]/g, " , crochet fermé , ");

    s = s.replace(/(\d)\.(\d)/g, "$1 virgule $2");
    return s.replace(/\s+/g, " ").replace(/\s*,(\s*,)+/g, ",").replace(/\s+,/g, ",").replace(/^[\s.,]+/, "").trim();
  }

  // Equations ecrites sans $ dans le texte courant (« 2x + 5 = 13 »).
  function proseMath(text) {
    const L = "(?<![A-Za-zÀ-ÿ])[a-z](?![A-Za-zÀ-ÿ])";
    // Unites d'abord : « m/s² » ne doit pas devenir « m/s au carré ».
    text = convertUnits(text, false);
    text = text
      .replace(new RegExp("(\\d|\\)|" + L + ")\\s[-−]\\s(?=\\d|\\(|" + L + ")", "g"), "$1 moins ")
      .replace(/(^|[\s(=+×,])−(?=\d)/g, "$1moins ")
      .replace(/(^|[\s(=+×,])-(?=\d)(?<=\s-|^-|\(-|=-|\+-)/g, "$1moins ")
      .replace(/(\d|\)|[A-Za-z])\s*=\s*(?=[\dA-Za-z(-−])/g, "$1 égale ")
      .replace(/(\d|\)|[A-Za-z])\s+\+\s+(?=[\dA-Za-z(])/g, "$1 plus ")
      .replace(/\s×\s/g, " fois ").replace(/\s÷\s/g, " divisé par ")
      .replace(/≠/g, " différent de ").replace(/≤/g, " inférieur ou égal à ").replace(/≥/g, " supérieur ou égal à ")
      .replace(/≈/g, " environ égal à ").replace(/→/g, " donne ").replace(/⇒/g, " donc ")
      .replace(/√\s*\(?([A-Za-z0-9]+)\)?/g, " racine carrée de $1 ")
      .replace(/(\d|[a-z])²/g, "$1 au carré ").replace(/(\d|[a-z])³/g, "$1 au cube ")
      .replace(/\b(\d{1,4})\/(\d{1,4})\b(?!\/)(?<!\/\d{1,4}\/\d{1,4})/g, "$1 sur $2")
      .replace(/(\d)\.(\d)/g, "$1 virgule $2")
      .replace(/(?<![A-Za-zÀ-ÿ])([fgh])\(([^()\n]{1,12})\)/g, " $1 de $2 ");
    return text;
  }

  function speakableFrench(text) {
    let t = String(text || "");
    t = t
      // Blocs de code (graphique, schema) : instructions pour l'appli, pas du texte a lire.
      .replace(/```[\s\S]*?```/g, " ")
      .replace(/\$\$([\s\S]+?)\$\$/g, (_, e) => ". " + spokenMath(e) + ". ")
      .replace(/\\\[([\s\S]+?)\\\]/g, (_, e) => ". " + spokenMath(e) + ". ")
      .replace(/\$([^\n$]+?)\$/g, (_, e) => " " + spokenMath(e) + " ")
      .replace(/\\\(([^\n]+?)\\\)/g, (_, e) => " " + spokenMath(e) + " ")
      .replace(/^#{1,6}\s+/gm, "")
      .replace(/\*\*(.+?)\*\*/g, "$1")
      .replace(/\*(.+?)\*/g, "$1")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/^[-*]\s+/gm, ". ");
    t = proseMath(t);
    t = t
      // Tiret moyen/cadratin en milieu de phrase = pause.
      .replace(/\s+[-—–]\s+/g, ". ")
      // Emojis : une pause plutot qu'une description a voix haute.
      .replace(/[\p{Extended_Pictographic}‍️]/gu, ". ")
      .replace(/\n{2,}/g, ". ")
      // Retour a la ligne simple = pause (une etape de calcul par ligne).
      .replace(/([^.!?:;,\n])\n/g, "$1. ")
      .replace(/\n/g, " ")
      .replace(/\.(\s*\.)+/g, ".")
      .replace(/\s+([.,])/g, "$1")
      .replace(/\s+/g, " ")
      .trim();
    return t;
  }

  // 1 = normale. Texte avec calculs : nettement plus lent pour pouvoir suivre.
  function speechRateFor(text) {
    const raw = String(text || "");
    const spans = (raw.match(/\$\$|\\\[|\\\(|\$[^$\n]+\$/g) || []).length;
    const equals = (raw.match(/=/g) || []).length;
    const heavy = spans >= 2 || equals >= 2 || /\\frac|\\sqrt|\d\s*[+×*\/÷]\s*\d/.test(raw);
    return heavy ? 0.72 : 0.9;
  }

  const api = { speakableFrench, speechRateFor, spokenMath };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else { root.speakableFrench = speakableFrench; root.speechRateFor = speechRateFor; }
})(typeof window !== "undefined" ? window : globalThis);
