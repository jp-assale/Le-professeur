(function () {
  "use strict";

  const API_BASE = (window.AIDA_API_BASE_URL || "").replace(/\/$/, "");
  function apiUrl(path) {
    return API_BASE + path;
  }

  // Connexion instable frequente sur le terrain (Afrique de l'Ouest) : les
  // lectures simples (GET) reessaient automatiquement avant d'abandonner,
  // avec un delai maximum par tentative pour ne jamais rester bloque sans
  // retour visuel a l'ecran.
  async function fetchWithRetry(url, options, retries, timeoutMs) {
    retries = retries === undefined ? 2 : retries;
    timeoutMs = timeoutMs === undefined ? 15000 : timeoutMs;
    let lastError;
    for (let attempt = 0; attempt <= retries; attempt++) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const res = await fetch(url, Object.assign({}, options, { signal: controller.signal }));
        clearTimeout(timeoutId);
        // 429/503 = surcharge temporaire cote serveur (pic de connexions) -
        // le quota n'est jamais consomme sur un appel IA en echec, donc
        // reessayer automatiquement ici est sans risque de double-decompte.
        if ((res.status === 429 || res.status === 503) && attempt < retries) {
          await new Promise((r) => setTimeout(r, 1200 * (attempt + 1)));
          continue;
        }
        return res;
      } catch (e) {
        clearTimeout(timeoutId);
        lastError = e;
        if (attempt < retries) {
          await new Promise((r) => setTimeout(r, 500 * (attempt + 1)));
        }
      }
    }
    throw lastError;
  }

  const chatEl = document.getElementById("chat");
  const form = document.getElementById("composer");
  const input = document.getElementById("question-input");
  const sendBtn = document.getElementById("send-btn");
  const quotaBadge = document.getElementById("quota-badge");
  const streakBadge = document.getElementById("streak-badge");
  const selectPays = document.getElementById("select-pays");
  const selectNiveau = document.getElementById("select-niveau");
  const selectMatiere = document.getElementById("select-matiere");
  const toggleEpreuvesBtn = document.getElementById("toggle-epreuves-btn");
  const epreuvesPanel = document.getElementById("epreuves-panel");
  const epreuvesList = document.getElementById("epreuves-list");
  const toggleCoursBtn = document.getElementById("toggle-cours-btn");
  const coursPanel = document.getElementById("cours-panel");
  const coursList = document.getElementById("cours-list");
  const toggleDevoirsBtn = document.getElementById("toggle-devoirs-btn");
  const devoirsPanel = document.getElementById("devoirs-panel");
  const devoirsList = document.getElementById("devoirs-list");
  const saveDevoirBtn = document.getElementById("save-devoir-btn");
  const epreuveActive = document.getElementById("epreuve-active");
  const quitEpreuveBtn = document.getElementById("quit-epreuve-btn");
  const attachBtn = document.getElementById("attach-btn");
  const attachInput = document.getElementById("attach-input");
  const cameraBtn = document.getElementById("camera-btn");
  const cameraInput = document.getElementById("camera-input");
  const micBtn = document.getElementById("mic-btn");
  const newSessionBtn = document.getElementById("new-session-btn");
  const shareBtn = document.getElementById("share-btn");
  const deviceCodeBtn = document.getElementById("device-code-btn");
  const reportBtn = document.getElementById("report-btn");
  const upgradeLink = document.getElementById("upgrade-link");
  const quizBtn = document.getElementById("quiz-btn");
  const diagnosticBtn = document.getElementById("diagnostic-btn");

  let lastBotMessage = "";
  let isPremium = false;

  const DEVICE_ID = getOrCreateDeviceId();
  const SHARE_URL = "https://le-professeur.onrender.com";

  function shareToWhatsApp(text) {
    const url = "https://wa.me/?text=" + encodeURIComponent(text + "\n\n" + SHARE_URL);
    window.open(url, "_blank", "noopener");
  }

  const WELCOME_TEXT = "Salut ! Je suis Le Prof JPA, ton assistant pour les devoirs. " +
    "Touche la puce « Pays · Niveau · Matière » en haut pour choisir ton " +
    "programme, puis pose-moi ta question de cours ou d'exercice. Je " +
    "t'explique étape par étape, je ne donne pas juste la réponse toute " +
    "cuite 😉 Tu peux aussi piocher un sujet type examen dans « 📄 Sujets » " +
    "juste au-dessus.";

  // Prenom de l'eleve (retour testeur : "le prof doit m'appeler par mon
  // nom") - demande une fois via une fenetre, stocke sur l'appareil, et
  // envoye avec chaque question pour que le Prof JPA l'utilise dans ses
  // reponses (pas stocke cote serveur).
  const PRENOM_KEY = "aida_prenom";
  const PRENOM_ASKED_KEY = "aida_prenom_asked";

  function getStoredPrenom() {
    try { return (localStorage.getItem(PRENOM_KEY) || "").trim(); } catch (e) { return ""; }
  }

  function getWelcomeText() {
    const prenom = getStoredPrenom();
    return prenom ? WELCOME_TEXT.replace("Salut !", "Salut " + prenom + " !") : WELCOME_TEXT;
  }

  function openPrenomModal() {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
      <div class="modal-box">
        <div class="modal-header">
          <span>👋 Comment t'appelles-tu ?</span>
          <button type="button" id="prenom-close" style="background:none;border:none;font-size:1.1rem;cursor:pointer;color:var(--text-muted);">✕</button>
        </div>
        <p style="font-size:0.88rem;color:var(--text-muted);margin:0 0 10px;">
          Le Prof JPA t'appellera par ton prénom dans ses explications.
          Il reste sur ton téléphone, jamais publié.
        </p>
        <div style="display:flex;gap:8px;">
          <input type="text" id="prenom-input" maxlength="30" placeholder="Ton prénom"
            style="flex:1;min-width:0;padding:10px 12px;border-radius:8px;border:1px solid var(--border);font-size:0.95rem;">
          <button type="button" id="prenom-save"
            style="flex-shrink:0;padding:10px 16px;border-radius:8px;border:none;background:var(--green);color:#fff;font-size:0.9rem;cursor:pointer;">Valider</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const field = overlay.querySelector("#prenom-input");
    field.value = getStoredPrenom();
    setTimeout(() => field.focus(), 50);

    function close() {
      try { localStorage.setItem(PRENOM_ASKED_KEY, "1"); } catch (e) {}
      overlay.remove();
    }
    function save() {
      const name = field.value.trim().slice(0, 30);
      if (name) {
        try { localStorage.setItem(PRENOM_KEY, name); } catch (e) {}
        const welcomePrenomEl = document.getElementById("welcome-prenom");
        if (welcomePrenomEl) welcomePrenomEl.textContent = "Salut " + name + " !";
      }
      close();
    }
    overlay.querySelector("#prenom-save").addEventListener("click", save);
    field.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); save(); } });
    overlay.querySelector("#prenom-close").addEventListener("click", close);
    overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  }

  function askPrenomIfNeeded() {
    let asked = false;
    try { asked = !!localStorage.getItem(PRENOM_ASKED_KEY); } catch (e) {}
    if (getStoredPrenom() || asked) return;
    openPrenomModal();
  }

  let currentEpreuveId = null;
  let history = [];

  function getOrCreateDeviceId() {
    const KEY = "aida_device_id";
    let id = localStorage.getItem(KEY);
    if (!id) {
      id = "dev-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem(KEY, id);
    }
    return id;
  }

  // Formules entre $...$ / $$...$$ / \(...\) / \[...\] - protegees avant le
  // passage par le parseur Markdown (des soulignes/asterisques a l'interieur
  // d'une formule, ex $P_{n+1}$, seraient sinon mal interpretes comme de la
  // mise en forme), puis restaurees et rendues par KaTeX une fois le HTML en
  // place.
  const MATH_REGEX = /\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\$[^\n$]+?\$|\\\([^\n]+?\\\)/g;
  const MATH_DELIMITERS = [
    { left: "$$", right: "$$", display: true },
    { left: "\\[", right: "\\]", display: true },
    { left: "$", right: "$", display: false },
    { left: "\\(", right: "\\)", display: false },
  ];

  // Lecture a voix haute des reponses (retour testeur) - repose sur la
  // synthese vocale du navigateur (gratuite, aucun service externe),
  // disponible sur Chrome/Android WebView. Le texte brut (markdown + LaTeX)
  // est nettoye pour etre comprehensible a l'oral plutot que lu tel quel
  // ("dollar x chapeau 2 dollar").
  function spokenMath(expr) {
    return expr
      .replace(/\\times/g, " fois ")
      .replace(/\\div/g, " divisé par ")
      .replace(/\\pm/g, " plus ou moins ")
      .replace(/\\sqrt\{([^}]+)\}/g, " racine carrée de $1 ")
      .replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, " $1 sur $2 ")
      .replace(/\^\{([^}]+)\}/g, " puissance $1 ")
      .replace(/\^(\w)/g, " puissance $1 ")
      .replace(/_\{([^}]+)\}/g, " indice $1 ")
      .replace(/_(\w)/g, " indice $1 ")
      .replace(/[\\{}]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function cleanTextForSpeech(text) {
    return text
      // Blocs de code (graphique ```plot, schema ```diagram / ```schema) : ce
      // sont des instructions pour l'appli, pas du texte a lire a voix haute.
      .replace(/```[\s\S]*?```/g, " ")
      .replace(/\$\$([\s\S]+?)\$\$/g, (_, inner) => " " + spokenMath(inner) + " ")
      .replace(/\\\[([\s\S]+?)\\\]/g, (_, inner) => " " + spokenMath(inner) + " ")
      .replace(/\$([^\n$]+?)\$/g, (_, inner) => " " + spokenMath(inner) + " ")
      .replace(/\\\(([^\n]+?)\\\)/g, (_, inner) => " " + spokenMath(inner) + " ")
      .replace(/^#{1,6}\s+/gm, "")
      .replace(/\*\*(.+?)\*\*/g, "$1")
      .replace(/\*(.+?)\*/g, "$1")
      .replace(/`([^`]+)`/g, "$1")
      // Puce de liste ("- " ou "* " en debut de ligne) : marque une pause
      // (comme un point) plutot que de l'effacer silencieusement, sinon les
      // elements d'une liste s'enchainent a l'oral sans aucune coupure
      // (retour testeur).
      .replace(/^[-*]\s+/gm, ". ")
      // Tiret moyen/cadratin utilise en milieu de phrase comme une pause a
      // l'ecrit ("... d'exercice — je t'explique ...") : marque la meme
      // pause a l'oral plutot que de laisser les deux bouts de phrase se
      // recoller sans coupure (retour testeur).
      .replace(/\s+[-—–]\s+/g, ". ")
      // Emojis/pictogrammes - certains moteurs de synthese vocale les
      // decrivent a voix haute ("signe de pouce vers le haut"), ce qui n'a
      // rien de naturel a l'oral (retour testeur). ‍ et ️ sont les
      // caracteres d'assemblage invisibles laisses par certains emojis. Ici
      // aussi, une pause (comme un point) plutot qu'une simple suppression -
      // un emoji marque souvent la fin d'une idee dans le texte de l'IA.
      .replace(/[\p{Extended_Pictographic}‍️]/gu, ". ")
      .replace(/\n{2,}/g, ". ")
      .replace(/\n/g, " ")
      // Plusieurs points d'affilee (ex: deux emojis cote a cote, ou un point
      // de phrase juste avant une puce) se recollent en un seul.
      .replace(/\.(\s*\.)+/g, ".")
      .replace(/\s+/g, " ")
      .trim();
  }

  // Le Prof JPA est un personnage masculin - on cherche une voix francaise
  // masculine parmi celles installees sur l'appareil. L'API Web Speech ne
  // donne pas le genre explicitement, donc on devine via le nom (ca depend
  // des voix presentes sur le telephone - a defaut, la premiere voix
  // francaise disponible est utilisee). Ne s'applique qu'au web : dans l'app
  // Android, c'est le plugin natif (voir isNativeApp) qui parle, sans
  // controle fin sur la voix.
  let cachedFrenchVoice = null;
  function getFrenchMaleVoice() {
    if (!window.speechSynthesis) return null;
    if (cachedFrenchVoice) return cachedFrenchVoice;
    const voices = speechSynthesis.getVoices();
    if (!voices.length) return null;
    const french = voices.filter((v) => v.lang && v.lang.toLowerCase().startsWith("fr"));
    // Voix imposee par le proprietaire : « Microsoft Paul - French » (voix
    // masculine disponible sur Windows/Edge/Chrome PC). A defaut, repli sur
    // une autre voix francaise masculine probable.
    const paul = french.find((v) => /microsoft paul/i.test(v.name)) || french.find((v) => /paul/i.test(v.name));
    if (paul) { cachedFrenchVoice = paul; return paul; }
    const male = french.find((v) => /male|homme|thomas|paul|nicolas|guillaume|daniel|henri|louis/i.test(v.name) && !/female|femme/i.test(v.name));
    cachedFrenchVoice = male || french[0] || voices[0] || null;
    return cachedFrenchVoice;
  }
  if (window.speechSynthesis) {
    speechSynthesis.addEventListener("voiceschanged", () => { cachedFrenchVoice = null; });
  }

  // La WebView Android n'implemente PAS window.speechSynthesis (contrairement
  // a Chrome desktop/mobile) - sans ce plugin natif, le bouton "Ecouter"
  // resterait invisible dans l'appli installee alors qu'il fonctionne sur le
  // web (retour testeur). Le plugin est expose automatiquement sur
  // Capacitor.Plugins une fois synchronise, pas besoin d'import ES ici.
  function isNativeApp() {
    return !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());
  }
  function getNativeTTS() {
    return (window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.TextToSpeech) || null;
  }
  function speechAvailable() {
    return isNativeApp() ? !!getNativeTTS() : !!window.speechSynthesis;
  }

  // Sur Android, le moteur systeme n'indique pas le genre des voix et la
  // voix "Microsoft Paul" n'existe pas (elle est propre a Windows/Edge/
  // Chrome sur PC) : on privilegie les variantes « frb »/« frd » du moteur
  // Google (generalement masculines, non garanti) et on baisse le pitch.
  async function getNativeFrenchVoices() {
    const tts = getNativeTTS();
    if (!tts || !tts.getSupportedVoices) return [];
    try {
      const res = await tts.getSupportedVoices();
      return (res.voices || [])
        .map((v, index) => ({ index, uri: v.voiceURI || "", lang: v.lang || "" }))
        .filter((v) => /^fr/i.test(v.lang));
    } catch (e) {
      return [];
    }
  }

  async function pickNativeVoiceIndex() {
    const voices = await getNativeFrenchVoices();
    const chosen = voices.find((v) => /fr-fr-x-(frb|frd)/i.test(v.uri));
    return chosen ? chosen.index : undefined;
  }

  async function speakNative(text) {
    const voice = await pickNativeVoiceIndex();
    const opts = { text, lang: "fr-FR", rate: 0.95, pitch: 0.8 };
    if (voice !== undefined) opts.voice = voice;
    return getNativeTTS().speak(opts);
  }

  let currentUtteranceBtn = null;
  let speechToken = 0;

  function stopSpeaking() {
    speechToken++; // invalide tout callback de fin en attente pour l'ancienne lecture
    if (isNativeApp()) {
      const tts = getNativeTTS();
      if (tts) tts.stop();
    } else if (window.speechSynthesis) {
      speechSynthesis.cancel();
    }
    if (currentUtteranceBtn) {
      currentUtteranceBtn.classList.remove("speaking");
      currentUtteranceBtn.textContent = "🔊 Écouter";
    }
    currentUtteranceBtn = null;
  }

  function addSpeakButton(container, rawText) {
    if (!speechAvailable()) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "msg-speak-btn";
    btn.textContent = "🔊 Écouter";
    btn.addEventListener("click", () => {
      const wasSpeaking = currentUtteranceBtn === btn;
      stopSpeaking();
      if (wasSpeaking) return; // un second clic sur le meme bouton = juste arreter
      const text = cleanTextForSpeech(rawText);
      const myToken = speechToken;
      currentUtteranceBtn = btn;
      btn.classList.add("speaking");
      btn.textContent = "⏸ Arrêter";

      if (isNativeApp()) {
        speakNative(text).catch(() => {}).then(() => {
          if (speechToken === myToken) stopSpeaking();
        });
      } else {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "fr-FR";
        const voice = getFrenchMaleVoice();
        if (voice) utterance.voice = voice;
        utterance.rate = 0.95;
        utterance.onend = () => { if (speechToken === myToken) stopSpeaking(); };
        utterance.onerror = () => { if (speechToken === myToken) stopSpeaking(); };
        speechSynthesis.speak(utterance);
      }
    });
    container.appendChild(btn);
  }

  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // Version allegee pour les contextes ou le Markdown bloc (listes, titres)
  // ne convient pas structurellement - texte de question/option de quiz,
  // qui peut neanmoins contenir des formules a rendre.
  function renderMathOnly(container, text) {
    container.textContent = text;
    if (window.renderMathInElement) {
      renderMathInElement(container, { delimiters: MATH_DELIMITERS, throwOnError: false });
    }
  }

  function renderBotContent(container, text) {
    const mathBlocks = [];
    const protectedText = text.replace(MATH_REGEX, (m) => {
      mathBlocks.push(m);
      return "@@MATH" + (mathBlocks.length - 1) + "@@";
    });

    let html = window.marked
      ? marked.parse(protectedText, { breaks: true })
      : escapeHtml(protectedText).replace(/\n/g, "<br>");

    html = html.replace(/@@MATH(\d+)@@/g, (_, i) => escapeHtml(mathBlocks[Number(i)]));

    container.innerHTML = window.DOMPurify ? DOMPurify.sanitize(html) : html;

    // Les blocs ```plot sont remplaces par un graphique SVG genere par du
    // code de confiance (pas par le HTML de l'IA), donc apres la
    // sanitisation ci-dessus - inutile d'elargir l'autorisation DOMPurify.
    if (window.renderPlotBlocks) {
      renderPlotBlocks(container);
    }
    if (window.renderDiagramBlocks) {
      renderDiagramBlocks(container);
    }
    if (window.renderSchemaBlocks) {
      renderSchemaBlocks(container);
    }

    if (window.renderMathInElement) {
      renderMathInElement(container, { delimiters: MATH_DELIMITERS, throwOnError: false });
    }
  }

  // Une equation longue (chimie, biologie...) peut deborder la largeur de la
  // bulle sur un petit ecran - reduit sa taille pour qu'elle reste entiere-
  // ment visible sans que l'eleve ait besoin de deviner qu'il faut la faire
  // defiler horizontalement. Ne peut mesurer la largeur reelle qu'une fois
  // l'element attache au DOM visible, donc appele apres chatEl.appendChild.
  function shrinkOverflowingMath(container) {
    container.querySelectorAll(".katex-display").forEach((displayEl) => {
      const katexEl = displayEl.querySelector(".katex");
      if (!katexEl || displayEl.scrollWidth <= displayEl.clientWidth + 1) return;
      const ratio = displayEl.clientWidth / displayEl.scrollWidth;
      const currentSize = parseFloat(getComputedStyle(katexEl).fontSize) || 16;
      katexEl.style.fontSize = Math.max(currentSize * ratio * 0.95, 10) + "px";
    });
  }

  // Petite animation (en boucle) qui montre comment choisir son programme :
  // toucher la puce, remplir pays / niveau / matiere, valider. Affichee sous
  // le message d'accueil du Prof (voir addMessage et l'initialisation).
  function buildProgrammeDemo() {
    const d = document.createElement("div");
    d.className = "prog-demo";
    d.setAttribute("aria-hidden", "true");
    d.innerHTML =
      '<div class="pd-title">🎬 Comment choisir ton programme</div>' +
      '<div class="pd-stage">' +
        '<div class="pd-head"></div>' +
        '<div class="pd-chip"><span>📍</span><span class="pd-chip-text">' +
          '<span class="pd-t1">Pays · Niveau · Matière</span><span class="pd-t2">Mali · Lycée · Maths</span>' +
        '</span><span>▾</span></div>' +
        '<div class="pd-sheet">' +
          '<div class="pd-row pd-r1"><span>Pays</span><span class="pd-cell"><span class="pd-ph">Choisir ▾</span><span class="pd-val">Mali</span></span></div>' +
          '<div class="pd-row pd-r2"><span>Niveau</span><span class="pd-cell"><span class="pd-ph">Choisir ▾</span><span class="pd-val">Lycée</span></span></div>' +
          '<div class="pd-row pd-r3"><span>Matière</span><span class="pd-cell"><span class="pd-ph">Choisir ▾</span><span class="pd-val">Mathématiques</span></span></div>' +
          '<div class="pd-btn">Valider</div>' +
        '</div>' +
        '<div class="pd-finger">👆</div>' +
      '</div>' +
      '<div class="pd-caption">① Touche la puce verte en haut · ② Choisis pays, niveau, matière · ③ Valide</div>';
    return d;
  }

  function isWelcomeMessage(text) {
    return typeof text === "string" && text.indexOf("Je suis Le Prof JPA, ton assistant pour les devoirs") !== -1;
  }

  function addMessage(text, cls) {
    const div = document.createElement("div");
    div.className = "msg " + cls;
    let content = null;
    if (cls === "msg-bot") {
      content = document.createElement("div");
      content.className = "msg-content";
      renderBotContent(content, text);
      if (isWelcomeMessage(text)) content.appendChild(buildProgrammeDemo());
      div.appendChild(content);
      addSpeakButton(div, text);
    } else {
      const p = document.createElement("p");
      p.textContent = text;
      div.appendChild(p);
    }
    chatEl.appendChild(div);
    if (content) shrinkOverflowingMath(content);
    // Une explication longue commence en haut : si on defile jusqu'en bas,
    // l'eleve voit la fin en premier et doit remonter pour lire le debut
    // (retour testeur). On aligne plutot le HAUT du nouveau message avec le
    // haut de la zone visible, sauf pour son propre message ou un message
    // court (chargement/erreur) ou defiler jusqu'en bas reste plus naturel.
    if (cls === "msg-bot") {
      // div.offsetTop se calcule par rapport a offsetParent (ici <body>,
      // car .chat n'est pas "position" en CSS) et PAS par rapport a .chat -
      // l'ancien calcul (offsetTop - 8) etait donc structurellement faux,
      // pas juste une question de timing (bug trouve en comparant offsetTop
      // aux positions ecran reelles via getBoundingClientRect). On calcule
      // plutot l'ecart visuel actuel entre le haut du message et le haut de
      // la zone de chat, et on ajuste scrollTop de cet ecart exact.
      const scrollToTop = () => {
        const chatRect = chatEl.getBoundingClientRect();
        const divRect = div.getBoundingClientRect();
        chatEl.scrollTop += (divRect.top - chatRect.top) - 8;
      };
      scrollToTop();
      // Sur certains telephones, une police (KaTeX) qui finit de se charger
      // ou une image dans la reponse peut decaler la mise en page juste
      // apres ce premier defilement - on reajuste sur deux frames de plus
      // pour rattraper ce genre de decalage tardif.
      requestAnimationFrame(() => requestAnimationFrame(scrollToTop));
      setTimeout(scrollToTop, 300);
    } else {
      chatEl.scrollTop = chatEl.scrollHeight;
    }
    if (cls === "msg-bot") lastBotMessage = text;
    if (!restoringChat && (cls === "msg-user" || cls === "msg-bot")) {
      chatLog.push({ text, cls });
      persistChatState();
    }
    return div;
  }

  // Fin des questions gratuites du jour : message clair avec le bouton pour
  // passer en illimite ou la possibilite d'attendre demain (au lieu d'un
  // simple message d'erreur). Non conserve dans l'historique de conversation.
  function showQuotaExhausted(scrollToIt) {
    const existing = chatEl.querySelector(".msg-quota");
    if (existing) {
      if (scrollToIt) chatEl.scrollTop = chatEl.scrollHeight;
      return;
    }
    const div = document.createElement("div");
    div.className = "msg msg-quota";
    div.innerHTML =
      "<p><b>Tu as utilisé tes questions gratuites du jour 🎓</b></p>" +
      "<p>Pour continuer à poser des questions sans limite, passe en illimité. " +
      "Sinon, reviens demain : tu retrouveras de nouvelles questions gratuites.</p>" +
      '<div class="quota-actions">' +
      '<button type="button" class="quota-upgrade">✨ Passer en illimité</button>' +
      '<button type="button" class="quota-wait">⏰ Revenir demain</button>' +
      "</div>";
    div.querySelector(".quota-upgrade").addEventListener("click", openSubscribeWhatsAppModal);
    div.querySelector(".quota-wait").addEventListener("click", () => {
      div.querySelector(".quota-actions").outerHTML = "<p>À demain ! 👋 Tes questions gratuites reviennent chaque jour.</p>";
    });
    chatEl.appendChild(div);
    if (scrollToIt) chatEl.scrollTop = chatEl.scrollHeight;
  }

  // Affiche une erreur renvoyee par le serveur - ou, si c'est la fin des
  // questions gratuites, le message dedie avec le bouton d'abonnement.
  function addErrorMessage(data, fallback) {
    if (data && data.error === "quota_depasse") {
      showQuotaExhausted(true);
      return;
    }
    addMessage((data && (data.message || data.error)) || fallback, "msg-error");
  }

  // Conserve la conversation en cours (localStorage) pour que revenir dans
  // l'appli apres etre passe en arriere-plan ne remette pas a zero - sur
  // Android, le systeme tue souvent le processus en arriere-plan sur les
  // telephones d'entree de gamme (peu de RAM), ce qui recharge la page a
  // vide et effacait toute la discussion (retour direct de plusieurs
  // testeurs du test ferme).
  const CHAT_STATE_KEY = "aida_chat_state";
  let chatLog = [];
  let restoringChat = false;

  function persistChatState() {
    try {
      localStorage.setItem(CHAT_STATE_KEY, JSON.stringify({
        chatLog: chatLog,
        history: history,
        lastBotMessage: lastBotMessage,
        epreuveActiveText: epreuveActive.hidden ? null : epreuveActive.textContent,
      }));
    } catch (e) {
      // stockage plein ou indisponible (navigation privee) - tant pis, pas bloquant
    }
  }

  function clearPersistedChatState() {
    try {
      localStorage.removeItem(CHAT_STATE_KEY);
    } catch (e) {}
  }

  function restoreChatState() {
    let raw;
    try {
      raw = localStorage.getItem(CHAT_STATE_KEY);
    } catch (e) {
      return false;
    }
    if (!raw) return false;
    let saved;
    try {
      saved = JSON.parse(raw);
    } catch (e) {
      return false;
    }
    if (!saved || !Array.isArray(saved.chatLog) || !saved.chatLog.length) return false;

    restoringChat = true;
    clearChat();
    saved.chatLog.forEach((m) => addMessage(m.text, m.cls));
    restoringChat = false;

    chatLog = saved.chatLog;
    history = Array.isArray(saved.history) ? saved.history : [];
    lastBotMessage = saved.lastBotMessage || lastBotMessage;
    if (saved.epreuveActiveText) {
      epreuveActive.hidden = false;
      epreuveActive.textContent = saved.epreuveActiveText;
      quitEpreuveBtn.hidden = false;
    }
    return true;
  }

  // Serie de jours consecutifs d'utilisation - purement locale (localStorage),
  // pas d'appel serveur, pour eviter le probleme rencontre avec l'ancien
  // tableau de progression (lenteur due au reveil du serveur Render gratuit).
  const STREAK_DATE_KEY = "aida_streak_date";
  const STREAK_COUNT_KEY = "aida_streak_count";

  function todayISO() {
    return new Date().toISOString().slice(0, 10);
  }

  function renderStreak(count) {
    if (!count || count < 2) {
      streakBadge.hidden = true;
      return;
    }
    streakBadge.hidden = false;
    streakBadge.textContent = "🔥 " + count + "j";
  }

  function showStoredStreak() {
    renderStreak(parseInt(localStorage.getItem(STREAK_COUNT_KEY) || "0", 10));
  }

  // Appele apres une vraie interaction (question envoyee, sujet ouvert, quiz
  // genere) - pas juste a l'ouverture de l'appli, pour que la serie reflete
  // un usage reel plutot qu'un onglet laisse ouvert en arriere-plan.
  function recordActivity() {
    const today = todayISO();
    const lastDate = localStorage.getItem(STREAK_DATE_KEY);
    if (lastDate === today) return;

    let count = parseInt(localStorage.getItem(STREAK_COUNT_KEY) || "0", 10);
    const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
    count = lastDate === yesterday ? count + 1 : 1;

    localStorage.setItem(STREAK_DATE_KEY, today);
    localStorage.setItem(STREAK_COUNT_KEY, String(count));
    renderStreak(count);
  }

  let lastQuotaLimit = null;

  function setQuota(remaining, limit) {
    // Le bouton "Passer en illimite" (sous le compteur, en haut a droite)
    // disparait pour un abonne - voir .app.is-premium dans styles.css.
    const appEl = document.querySelector(".app");
    if (appEl) appEl.classList.toggle("is-premium", !!isPremium);
    if (isPremium) {
      quotaBadge.textContent = "✨ Illimité";
      return;
    }
    if (remaining === null || remaining === undefined) {
      quotaBadge.textContent = "…";
      return;
    }
    if (limit !== null && limit !== undefined) lastQuotaLimit = limit;
    quotaBadge.textContent = remaining + "/" + (lastQuotaLimit ?? "?") + " questions";
  }

  async function loadCurriculum() {
    // Un seul essai rapide (pas les 2 tentatives + attente en cas de 429/503
    // par defaut) : ces donnees ne sont pas critiques a la seconde pres, on
    // ne veut pas bloquer l'affichage au demarrage si le serveur se reveille
    // (retour testeur : demarrage devenu lent).
    const res = await fetchWithRetry(apiUrl("/api/curriculum"), undefined, 1, 6000);
    const data = await res.json();

    data.pays.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.code;
      opt.textContent = p.label;
      selectPays.appendChild(opt);
    });
    const savedPays = localStorage.getItem("aida_pays");
    if (savedPays) selectPays.value = savedPays;

    data.niveaux.forEach((n) => {
      const opt = document.createElement("option");
      opt.value = n.code;
      opt.textContent = n.label;
      selectNiveau.appendChild(opt);
    });
    const savedNiveau = localStorage.getItem("aida_niveau");
    if (savedNiveau) selectNiveau.value = savedNiveau;

    data.matieres.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = m;
      selectMatiere.appendChild(opt);
    });
    const savedMatiere = localStorage.getItem("aida_matiere");
    if (savedMatiere) selectMatiere.value = savedMatiere;
    updateContextLabel();
  }

  // Puce "Pays · Niveau · Matiere" de l'en-tete (ouvre la feuille de choix).
  function updateContextLabel() {
    const txt = (sel) => {
      const opt = sel.selectedOptions && sel.selectedOptions[0];
      return opt ? opt.textContent.replace(/\s*\(.*\)\s*$/, "").trim() : "";
    };
    const parts = [txt(selectPays), txt(selectNiveau), txt(selectMatiere)].filter(Boolean);
    document.getElementById("context-label").textContent = parts.length ? parts.join(" · ") : "Pays · Niveau · Matière";
  }

  [selectPays, selectNiveau, selectMatiere].forEach((sel) => {
    sel.addEventListener("change", () => {
      updateContextLabel();
      localStorage.setItem("aida_pays", selectPays.value);
      localStorage.setItem("aida_niveau", selectNiveau.value);
      localStorage.setItem("aida_matiere", selectMatiere.value);
      if (!epreuvesPanel.hidden) loadEpreuvesList();
      if (!coursPanel.hidden) loadCoursList();
    });
  });

  function clearChat() {
    chatEl.innerHTML = "";
  }

  async function loadEpreuvesList() {
    epreuvesList.innerHTML = '<li class="epreuves-empty">Chargement…</li>';
    const params = new URLSearchParams({
      pays: selectPays.value,
      niveau: selectNiveau.value,
      matiere: selectMatiere.value,
    });
    try {
      const pdfSujets = await fetchWithRetry(apiUrl("/api/pdf-sujets?" + params.toString())).then((r) => r.json());
      epreuvesList.innerHTML = "";

      if (pdfSujets.length) {
        pdfSujets.forEach((s) => {
          const li = document.createElement("li");
          li.className = "pdf-sujet-item";

          const viewLink = document.createElement("a");
          viewLink.href = apiUrl("/api/pdf-sujets/" + s.id + "/fichier");
          viewLink.target = "_blank";
          viewLink.rel = "noopener";
          viewLink.className = "pdf-sujet-view";
          viewLink.textContent = "📄 " + s.titre + " (" + s.annee + ")";

          const workBtn = document.createElement("button");
          workBtn.type = "button";
          workBtn.textContent = "💬 Corriger avec Le Prof JPA";
          workBtn.addEventListener("click", () => workOnPdfSujet(s.id, s.titre));

          li.appendChild(viewLink);
          li.appendChild(workBtn);
          epreuvesList.appendChild(li);
        });
      } else {
        epreuvesList.innerHTML =
          '<li class="epreuves-empty">Aucun sujet pour cette combinaison pays / niveau / matière pour l\'instant.</li>';
      }
    } catch (e) {
      epreuvesList.innerHTML = '<li class="epreuves-empty">Erreur de chargement.</li>';
    }
  }

  function quitEpreuve() {
    stopSpeaking();
    currentEpreuveId = null;
    history = [];
    chatLog = [];
    clearPersistedChatState();
    clearChat();
    addMessage(getWelcomeText(), "msg-bot");
    epreuveActive.hidden = true;
    quitEpreuveBtn.hidden = true;
  }

  toggleEpreuvesBtn.addEventListener("click", () => {
    coursPanel.hidden = true;
    devoirsPanel.hidden = true;
    epreuvesPanel.hidden = !epreuvesPanel.hidden;
    if (!epreuvesPanel.hidden) loadEpreuvesList();
  });

  async function loadCoursList() {
    coursList.innerHTML = '<li class="epreuves-empty">Chargement…</li>';
    const params = new URLSearchParams({
      pays: selectPays.value,
      niveau: selectNiveau.value,
      matiere: selectMatiere.value,
    });
    try {
      const lecons = await fetchWithRetry(apiUrl("/api/cours?" + params.toString())).then((r) => r.json());
      coursList.innerHTML = "";

      if (lecons.length) {
        if (lecons[0].fallback_for) {
          const note = document.createElement("li");
          note.className = "epreuves-empty";
          note.textContent =
            "Programme pas encore confirmé pour ce pays — voici le programme régional de référence, à titre indicatif.";
          coursList.appendChild(note);
        }
        lecons.forEach((c) => {
          const li = document.createElement("li");
          li.className = "pdf-sujet-item";

          const link = document.createElement("a");
          let href = "cours.html?slug=" + encodeURIComponent(c.slug);
          if (c.fallback_for) href += "&fallback_for=" + encodeURIComponent(c.fallback_for);
          link.href = href;
          link.className = "pdf-sujet-view";
          link.textContent = (c.fallback_for ? "📚🌍 " : "📚 ") + (c.title || c.chapitre);

          li.appendChild(link);
          coursList.appendChild(li);
        });
      } else {
        coursList.innerHTML =
          '<li class="epreuves-empty">Aucun cours pour cette combinaison pays / niveau / matière pour l\'instant.</li>';
      }
    } catch (e) {
      coursList.innerHTML = '<li class="epreuves-empty">Erreur de chargement.</li>';
    }
  }

  // Sauvegarde locale de devoirs precis (retour eleve : retrouver un devoir
  // traite plusieurs jours plus tot, apres avoir enchaine d'autres sujets
  // entre-temps - la conversation continue existe deja, mais sans repere
  // pour y revenir precisement, et la memoire active du Prof JPA ne garde de
  // toute facon que les 12 derniers echanges). Stockage 100% local
  // (localStorage), comme le reste de l'etat de la conversation.
  const SAVED_DEVOIRS_KEY = "aida_saved_devoirs";

  function getSavedDevoirs() {
    try {
      return JSON.parse(localStorage.getItem(SAVED_DEVOIRS_KEY) || "[]");
    } catch (e) {
      return [];
    }
  }

  function setSavedDevoirs(list) {
    try {
      localStorage.setItem(SAVED_DEVOIRS_KEY, JSON.stringify(list));
    } catch (e) {
      // stockage plein ou indisponible - tant pis, pas bloquant
    }
  }

  function renderDevoirsList() {
    const devoirs = getSavedDevoirs();
    devoirsList.innerHTML = "";
    if (!devoirs.length) {
      devoirsList.innerHTML =
        '<li class="epreuves-empty">Aucun devoir sauvegardé pour l\'instant.</li>';
      return;
    }
    devoirs.forEach((d) => {
      const li = document.createElement("li");
      li.className = "pdf-sujet-item";

      const info = document.createElement("span");
      info.className = "pdf-sujet-view";
      const dateTxt = new Date(d.savedAt).toLocaleDateString("fr-FR");
      info.textContent = "📌 " + d.title + " · " + d.matiere + " · " + dateTxt;

      const openBtn = document.createElement("button");
      openBtn.type = "button";
      openBtn.textContent = "📂 Ouvrir";
      openBtn.addEventListener("click", () => openSavedDevoir(d.id));

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.textContent = "🗑️";
      delBtn.style.background = "#fdeceb";
      delBtn.style.color = "#9b2c2c";
      delBtn.addEventListener("click", () => deleteSavedDevoir(d.id));

      li.appendChild(info);
      li.appendChild(openBtn);
      li.appendChild(delBtn);
      devoirsList.appendChild(li);
    });
  }

  function saveCurrentDevoir() {
    if (!chatLog.length) {
      window.alert("Rien à sauvegarder pour l'instant - pose d'abord une question.");
      return;
    }
    const defaultTitle = selectMatiere.value + " – " + new Date().toLocaleDateString("fr-FR");
    const title = window.prompt("Nom de ce devoir (pour le retrouver plus tard) :", defaultTitle);
    if (!title || !title.trim()) return;

    const devoirs = getSavedDevoirs();
    devoirs.unshift({
      id: "sd-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2),
      title: title.trim().slice(0, 80),
      pays: selectPays.value,
      niveau: selectNiveau.value,
      matiere: selectMatiere.value,
      savedAt: new Date().toISOString(),
      chatLog: chatLog.slice(),
      history: history.slice(),
      lastBotMessage: lastBotMessage,
      epreuveActiveText: epreuveActive.hidden ? null : epreuveActive.textContent,
    });
    setSavedDevoirs(devoirs);
    renderDevoirsList();
    window.alert("✅ Devoir sauvegardé ! Retrouve-le dans « 📌 Mes devoirs ».");
  }

  function openSavedDevoir(id) {
    const d = getSavedDevoirs().find((x) => x.id === id);
    if (!d) return;
    if (chatLog.length && !window.confirm(
      "Charger ce devoir va remplacer la conversation actuelle à l'écran " +
      "(pense à la sauvegarder avant si besoin). Continuer ?"
    )) return;

    stopSpeaking();
    selectPays.value = d.pays;
    selectNiveau.value = d.niveau;
    selectMatiere.value = d.matiere;
    localStorage.setItem("aida_pays", selectPays.value);
    localStorage.setItem("aida_niveau", selectNiveau.value);
    localStorage.setItem("aida_matiere", selectMatiere.value);
    updateContextLabel();

    currentEpreuveId = null;
    history = Array.isArray(d.history) ? d.history.slice() : [];
    clearPersistedChatState();
    clearChat();
    restoringChat = true;
    d.chatLog.forEach((m) => addMessage(m.text, m.cls));
    restoringChat = false;
    chatLog = d.chatLog.slice();
    lastBotMessage = d.lastBotMessage || "";

    if (d.epreuveActiveText) {
      epreuveActive.hidden = false;
      epreuveActive.textContent = d.epreuveActiveText;
      quitEpreuveBtn.hidden = false;
    } else {
      epreuveActive.hidden = true;
      quitEpreuveBtn.hidden = true;
    }
    persistChatState();
    devoirsPanel.hidden = true;
  }

  function deleteSavedDevoir(id) {
    if (!window.confirm("Supprimer ce devoir sauvegardé ? Cette action est irréversible.")) return;
    setSavedDevoirs(getSavedDevoirs().filter((d) => d.id !== id));
    renderDevoirsList();
  }

  saveDevoirBtn.addEventListener("click", saveCurrentDevoir);

  toggleDevoirsBtn.addEventListener("click", () => {
    epreuvesPanel.hidden = true;
    coursPanel.hidden = true;
    devoirsPanel.hidden = !devoirsPanel.hidden;
    if (!devoirsPanel.hidden) renderDevoirsList();
  });

  toggleCoursBtn.addEventListener("click", () => {
    epreuvesPanel.hidden = true;
    devoirsPanel.hidden = true;
    coursPanel.hidden = !coursPanel.hidden;
    if (!coursPanel.hidden) loadCoursList();
  });

  quitEpreuveBtn.addEventListener("click", quitEpreuve);

  newSessionBtn.addEventListener("click", () => {
    if (!chatLog.length) return; // rien a effacer, evite une confirmation inutile
    if (window.confirm("Effacer la discussion en cours et repartir à zéro ?")) {
      quitEpreuve();
    }
  });

  async function loadQuota() {
    try {
      const res = await fetchWithRetry(apiUrl("/api/quota?device_id=" + encodeURIComponent(DEVICE_ID)), undefined, 1, 6000);
      const data = await res.json();
      isPremium = !!data.premium;
      setQuota(data.remaining, data.limit);
    } catch (e) {
      quotaBadge.textContent = "";
    }
  }

  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 120) + "px";
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const question = input.value.trim();
    if (!question) return;

    stopSpeaking();
    addMessage(question, "msg-user");
    input.value = "";
    input.style.height = "auto";
    sendBtn.disabled = true;

    const loadingEl = addMessage("Le Prof JPA réfléchit…", "msg-loading");

    try {
      const res = await fetchWithRetry(apiUrl("/api/ask"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_id: DEVICE_ID,
          pays: selectPays.value,
          niveau: selectNiveau.value,
          matiere: selectMatiere.value,
          question: question,
          history: history,
          prenom: getStoredPrenom(),
        }),
      }, 2, 45000);
      const data = await res.json();
      loadingEl.remove();

      if (!res.ok) {
        addErrorMessage(data, "Une erreur est survenue.");
        if (typeof data.remaining === "number") setQuota(data.remaining, undefined);
        return;
      }

      addMessage(data.answer, "msg-bot");
      recordActivity();
      history.push({ role: "user", content: question });
      history.push({ role: "assistant", content: data.answer });
      persistChatState();
      isPremium = !!data.premium;
      setQuota(data.remaining, undefined);
      if (!isPremium && data.remaining === 0) showQuotaExhausted();
    } catch (err) {
      loadingEl.remove();
      addMessage("Connexion impossible. Vérifie ta connexion et réessaie.", "msg-error");
    } finally {
      sendBtn.disabled = false;
    }
  });

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  async function processFileForCorrection(file, displayLabel) {
    const MAX_BYTES = 9 * 1024 * 1024;
    const ALLOWED = ["image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"];

    if (!ALLOWED.includes(file.type)) {
      addMessage("Format non supporté. Envoie une photo (jpg/png) ou un PDF.", "msg-error");
      return;
    }
    if (file.size > MAX_BYTES) {
      addMessage("Ce fichier est trop volumineux (max ~9 Mo). Essaie une photo plus légère ou recadrée.", "msg-error");
      return;
    }

    currentEpreuveId = null;
    history = [];
    chatLog = [];
    clearPersistedChatState();
    clearChat();
    addMessage("📎 " + (displayLabel || file.name), "msg-user");
    const loadingEl = addMessage("Le Prof JPA regarde ton sujet…", "msg-loading");
    sendBtn.disabled = true;
    attachBtn.disabled = true;
    epreuvesPanel.hidden = true;

    try {
      const base64 = await fileToBase64(file);
      const res = await fetch(apiUrl("/api/upload-exercice"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_id: DEVICE_ID,
          pays: selectPays.value,
          niveau: selectNiveau.value,
          matiere: selectMatiere.value,
          mime_type: file.type,
          data: base64,
          prenom: getStoredPrenom(),
        }),
      });
      const data = await res.json();
      loadingEl.remove();

      if (!res.ok) {
        addErrorMessage(data, "Une erreur est survenue.");
        if (typeof data.remaining === "number") setQuota(data.remaining, undefined);
        return;
      }

      addMessage(data.answer, "msg-bot");
      recordActivity();
      history = [
        { role: "user", content: "[L'élève a envoyé une photo/PDF de son sujet]" },
        { role: "assistant", content: data.answer },
      ];
      epreuveActive.hidden = false;
      epreuveActive.textContent = "Sujet envoyé : " + (displayLabel || file.name);
      quitEpreuveBtn.hidden = false;
      persistChatState();
      isPremium = !!data.premium;
      setQuota(data.remaining, undefined);
    } catch (err) {
      loadingEl.remove();
      addMessage("Connexion impossible. Vérifie ta connexion et réessaie.", "msg-error");
    } finally {
      sendBtn.disabled = false;
      attachBtn.disabled = false;
    }
  }

  attachBtn.addEventListener("click", () => attachInput.click());
  cameraBtn.addEventListener("click", () => cameraInput.click());

  cameraInput.addEventListener("change", () => {
    const file = cameraInput.files[0];
    cameraInput.value = "";
    if (file) processFileForCorrection(file, "Photo de mon sujet");
  });

  attachInput.addEventListener("change", () => {
    const file = attachInput.files[0];
    attachInput.value = "";
    if (file) processFileForCorrection(file);
  });

  // Dictee vocale de la question - repose sur la reconnaissance vocale du
  // navigateur (gratuite, aucun service externe), disponible sur
  // Chrome/Android WebView mais pas partout (ex: Firefox) - le bouton reste
  // cache si l'API n'existe pas plutot que d'afficher un controle casse.
  const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognitionCtor) {
    micBtn.hidden = false;
    const recognition = new SpeechRecognitionCtor();
    recognition.lang = "fr-FR";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    let listening = false;

    recognition.addEventListener("start", () => {
      listening = true;
      micBtn.classList.add("mic-listening");
      micBtn.title = "Enregistrement en cours… parle maintenant";
    });

    recognition.addEventListener("result", (e) => {
      const transcript = e.results[0][0].transcript.trim();
      if (!transcript) return;
      input.value = input.value ? input.value + " " + transcript : transcript;
      input.dispatchEvent(new Event("input"));
      input.focus();
    });

    recognition.addEventListener("error", (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        window.alert("Le micro n'est pas autorisé. Vérifie les permissions de l'application/du navigateur.");
      }
    });

    recognition.addEventListener("end", () => {
      listening = false;
      micBtn.classList.remove("mic-listening");
      micBtn.title = "Poser ta question à la voix";
    });

    micBtn.addEventListener("click", () => {
      if (listening) {
        recognition.stop();
      } else {
        try {
          recognition.start();
        } catch (e) {
          // start() jette une erreur si deja demarree - sans consequence.
        }
      }
    });
  }

  async function workOnPdfSujet(sujetId, titre) {
    currentEpreuveId = null;
    history = [];
    chatLog = [];
    clearPersistedChatState();
    clearChat();
    addMessage("📄 " + titre, "msg-user");
    const loadingEl = addMessage("Le Prof JPA regarde ton sujet…", "msg-loading");
    epreuvesPanel.hidden = true;

    try {
      const res = await fetch(apiUrl("/api/pdf-sujets/" + encodeURIComponent(sujetId) + "/corriger"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_id: DEVICE_ID,
          pays: selectPays.value,
          niveau: selectNiveau.value,
          matiere: selectMatiere.value,
        }),
      });
      const data = await res.json();
      loadingEl.remove();

      if (!res.ok) {
        addErrorMessage(data, "Une erreur est survenue.");
        if (typeof data.remaining === "number") setQuota(data.remaining, undefined);
        return;
      }

      addMessage(data.answer, "msg-bot");
      recordActivity();
      history = [
        { role: "user", content: "[L'élève travaille sur : " + titre + "]" },
        { role: "assistant", content: data.answer },
      ];
      epreuveActive.hidden = false;
      epreuveActive.textContent = "Sujet : " + titre;
      quitEpreuveBtn.hidden = false;
      persistChatState();
      isPremium = !!data.premium;
      setQuota(data.remaining, undefined);
    } catch (e) {
      loadingEl.remove();
      addMessage("Connexion impossible. Réessaie plus tard.", "msg-error");
    }
  }

  shareBtn.addEventListener("click", () => {
    if (!lastBotMessage) {
      window.alert("Pose d'abord une question, puis partage l'explication sur WhatsApp.");
      return;
    }
    const excerpt = lastBotMessage.length > 200 ? lastBotMessage.slice(0, 200) + "…" : lastBotMessage;
    shareToWhatsApp(
      "🎓 Le Prof JPA vient de m'expliquer ça :\n\n« " + excerpt + " »\n\n" +
      "Essaie toi aussi, c'est gratuit :"
    );
  });

  let deviceCodeModal = null;

  function buildDeviceCodeModal() {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
      <div class="modal-box">
        <div class="modal-header">
          <span>🔑 Ton code appareil</span>
          <button type="button" id="device-modal-close" style="background:none;border:none;font-size:1.1rem;cursor:pointer;color:var(--text-muted);">✕</button>
        </div>
        <p style="font-size:0.85rem;color:var(--text-muted);margin:0 0 10px;">
          Note-le pour retrouver tes questions restantes sur un autre téléphone.
        </p>
        <div style="display:flex;gap:8px;">
          <input type="text" id="device-code-display" readonly
            style="flex:1;min-width:0;padding:8px 10px;border-radius:8px;border:1px solid var(--border);font-family:monospace;font-size:0.8rem;background:var(--bg);">
          <button type="button" id="device-copy-btn"
            style="flex-shrink:0;padding:8px 14px;border-radius:8px;border:none;background:var(--green);color:#fff;font-size:0.85rem;cursor:pointer;">📋 Copier</button>
        </div>
        <p id="device-copy-msg" style="font-size:0.8rem;color:var(--green-dark);min-height:1.2em;margin:6px 0 0;"></p>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:4px;">
          <button type="button" id="device-prenom-btn"
            style="padding:8px 12px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text);font-size:0.82rem;cursor:pointer;">✏️ Changer mon prénom</button>
        </div>
        <hr style="margin:14px 0;border:none;border-top:1px solid var(--border);">
        <p style="font-size:0.85rem;color:var(--text-muted);margin:0 0 8px;">
          Tu as déjà un code (utilisé sur un autre téléphone) ? Colle-le ici :
        </p>
        <div style="display:flex;gap:8px;">
          <input type="text" id="device-code-input" placeholder="dev-..."
            style="flex:1;min-width:0;padding:8px 10px;border-radius:8px;border:1px solid var(--border);font-size:0.82rem;">
          <button type="button" id="device-restore-btn"
            style="flex-shrink:0;padding:8px 14px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text);font-size:0.85rem;cursor:pointer;">Utiliser</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);

    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) overlay.remove();
    });
    overlay.querySelector("#device-modal-close").addEventListener("click", () => overlay.remove());

    const copyBtn = overlay.querySelector("#device-copy-btn");
    const copyMsg = overlay.querySelector("#device-copy-msg");
    const displayInput = overlay.querySelector("#device-code-display");
    copyBtn.addEventListener("click", async () => {
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(DEVICE_ID);
        } else {
          displayInput.select();
          document.execCommand("copy");
        }
        copyMsg.textContent = "✅ Copié !";
      } catch (e) {
        displayInput.select();
        copyMsg.textContent = "Sélectionne le texte ci-dessus et copie-le manuellement.";
      }
      setTimeout(() => { copyMsg.textContent = ""; }, 2500);
    });

    overlay.querySelector("#device-prenom-btn").addEventListener("click", () => {
      overlay.remove();
      openPrenomModal();
    });
    overlay.querySelector("#device-restore-btn").addEventListener("click", () => {
      const val = overlay.querySelector("#device-code-input").value.trim();
      if (val && val !== DEVICE_ID) {
        localStorage.setItem("aida_device_id", val);
        window.location.reload();
      }
    });

    return overlay;
  }

  deviceCodeBtn.addEventListener("click", () => {
    if (!deviceCodeModal || !document.body.contains(deviceCodeModal)) {
      deviceCodeModal = buildDeviceCodeModal();
    }
    deviceCodeModal.querySelector("#device-code-display").value = DEVICE_ID;
    deviceCodeModal.querySelector("#device-code-input").value = "";
    deviceCodeModal.querySelector("#device-copy-msg").textContent = "";
  });

  reportBtn.addEventListener("click", async () => {
    if (!lastBotMessage) {
      window.alert("Pose d'abord une question ou ouvre un sujet, puis signale si besoin.");
      return;
    }
    const comment = window.prompt(
      "Qu'est-ce qui semble faux ou pose problème dans la dernière réponse ? " +
      "(optionnel, tu peux laisser vide)",
      ""
    );
    if (comment === null) return; // annulé
    try {
      await fetch(apiUrl("/api/report"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_id: DEVICE_ID,
          context: currentEpreuveId || "chat-libre",
          excerpt: lastBotMessage,
          comment: comment,
        }),
      });
      window.alert("Merci, c'est signalé — on va vérifier.");
    } catch (e) {
      window.alert("Signalement non envoyé (pas de connexion). Réessaie plus tard.");
    }
  });

  // Numero WhatsApp Business pour l'abonnement manuel (en attendant que
  // CinetPay/PayDunya/FedaPay active un compte marchand - tous bloques sur
  // leur verification a ce jour). Format wa.me : chiffres uniquement, sans
  // le "00" ni le "+".
  const SUBSCRIBE_WHATSAPP_NUMBER = "22371698694";

  // Un seul forfait a la fois a du sens (pas un choix multiple) - boutons
  // radio plutot que des cases a cocher independantes, meme principe visuel.
  const SUBSCRIBE_PLANS = [
    { id: "1-mois", label: "1 mois", price: 2500, days: 30 },
    { id: "2-mois", label: "2 mois", price: 4500, days: 60 },
  ];

  function openSubscribeWhatsAppModal() {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    const plansHtml = SUBSCRIBE_PLANS.map((p, i) => `
      <label style="display:flex;align-items:center;justify-content:space-between;padding:10px 12px;${i < SUBSCRIBE_PLANS.length - 1 ? "border-bottom:1px solid var(--border);" : ""}cursor:pointer;font-size:0.9rem;">
        <span><input type="radio" name="sub-plan" value="${p.id}" data-price="${p.price}" data-days="${p.days}" data-label="${p.label}"${i === 0 ? " checked" : ""}> ${p.label}</span>
        <span style="font-weight:600;">${p.price.toLocaleString("fr-FR")} FCFA</span>
      </label>`).join("");
    overlay.innerHTML = `
      <div class="modal-box">
        <div class="modal-header">
          <span>✨ Passer en illimité</span>
          <button type="button" id="subscribe-modal-close" style="background:none;border:none;font-size:1.1rem;cursor:pointer;color:var(--text-muted);">✕</button>
        </div>
        <p style="font-size:0.9rem;color:var(--text);margin:0 0 14px;line-height:1.5;">
          Le paiement en ligne automatique arrive bientôt ! En attendant, tu
          peux t'abonner directement par WhatsApp : choisis ta formule
          ci-dessous, dis-nous que tu veux passer en illimité, on t'indique
          comment payer (Mobile Money) et on active ton compte en quelques
          minutes.
        </p>
        <div style="border:1px solid var(--border);border-radius:10px;overflow:hidden;margin-bottom:14px;">
          ${plansHtml}
        </div>
        <a id="subscribe-whatsapp-link" href="#" target="_blank" rel="noopener"
          style="display:block;text-align:center;padding:12px;border-radius:10px;background:#25d366;color:#fff;font-weight:600;text-decoration:none;font-size:0.95rem;">
          💬 Contacter sur WhatsApp
        </a>
      </div>`;
    document.body.appendChild(overlay);
    overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector("#subscribe-modal-close").addEventListener("click", () => overlay.remove());

    const waLink = overlay.querySelector("#subscribe-whatsapp-link");
    function updateWaLink() {
      const checked = overlay.querySelector('input[name="sub-plan"]:checked');
      const label = checked ? checked.dataset.label : SUBSCRIBE_PLANS[0].label;
      const price = checked ? checked.dataset.price : SUBSCRIBE_PLANS[0].price;
      const days = checked ? checked.dataset.days : SUBSCRIBE_PLANS[0].days;
      const prenom = getStoredPrenom();
      // Lien qui ouvre la page admin avec le code et la duree deja remplis
      // (l'admin n'a plus qu'a verifier le paiement et cliquer Activer).
      const adminUrl = SHARE_URL + "/admin.html?device=" + encodeURIComponent(DEVICE_ID) +
        "&days=" + days + (prenom ? "&nom=" + encodeURIComponent(prenom) : "");
      const message =
        "Bonjour ! Je voudrais m'abonner à l'illimité sur JPA Assistant Scolaire.\n" +
        (prenom ? "Je m'appelle " + prenom + ".\n" : "") +
        "Formule choisie : " + label + " (" + Number(price).toLocaleString("fr-FR") + " FCFA)\n" +
        "Mon code appareil : " + DEVICE_ID + "\n" +
        "(Je t'envoie la capture de mon paiement juste après.)\n\n" +
        "Lien d'activation (réservé à l'admin) : " + adminUrl;
      waLink.href = "https://wa.me/" + SUBSCRIBE_WHATSAPP_NUMBER + "?text=" + encodeURIComponent(message);
    }
    overlay.querySelectorAll('input[name="sub-plan"]').forEach((input) => {
      input.addEventListener("change", updateWaLink);
    });
    updateWaLink();
  }

  upgradeLink.addEventListener("click", async () => {
    if (isPremium) {
      window.alert("Tu es déjà en illimité ✨");
      return;
    }
    upgradeLink.disabled = true;
    try {
      const res = await fetch(apiUrl("/api/subscribe"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_id: DEVICE_ID }),
      });
      const data = await res.json();
      if (!res.ok || !data.payment_url) {
        openSubscribeWhatsAppModal();
        return;
      }
      window.location.href = data.payment_url;
    } catch (e) {
      openSubscribeWhatsAppModal();
    } finally {
      upgradeLink.disabled = false;
    }
  });

  // --- Quiz interactif (topic ou diagnostic) ---------------------------

  function renderQuizInChat(questions, mode) {
    const box = document.createElement("div");
    box.className = "quiz-box";

    const answers = new Array(questions.length).fill(null);

    questions.forEach((q, qi) => {
      const qDiv = document.createElement("div");
      qDiv.className = "quiz-question";
      const p = document.createElement("p");
      const numSpan = document.createElement("span");
      numSpan.textContent = (qi + 1) + ". ";
      p.appendChild(numSpan);
      const qContent = document.createElement("span");
      renderMathOnly(qContent, q.question);
      p.appendChild(qContent);
      qDiv.appendChild(p);

      q.options.forEach((opt, oi) => {
        const optBtn = document.createElement("button");
        optBtn.type = "button";
        optBtn.className = "quiz-option";
        renderMathOnly(optBtn, opt);
        optBtn.addEventListener("click", () => {
          if (optBtn.disabled) return;
          qDiv.querySelectorAll(".quiz-option").forEach((b) => b.classList.remove("selected"));
          optBtn.classList.add("selected");
          answers[qi] = oi;
        });
        qDiv.appendChild(optBtn);
      });

      const expl = document.createElement("div");
      expl.className = "quiz-explication";
      expl.hidden = true;
      renderMathOnly(expl, q.explication || "");
      qDiv.appendChild(expl);

      box.appendChild(qDiv);
    });

    const submitBtn = document.createElement("button");
    submitBtn.type = "button";
    submitBtn.className = "quiz-submit";
    submitBtn.textContent = "Valider mes réponses";
    box.appendChild(submitBtn);

    const scoreEl = document.createElement("div");
    scoreEl.className = "quiz-score";
    scoreEl.hidden = true;
    box.appendChild(scoreEl);

    submitBtn.addEventListener("click", async () => {
      let score = 0;
      const results = [];
      box.querySelectorAll(".quiz-question").forEach((qDiv, qi) => {
        const q = questions[qi];
        const opts = qDiv.querySelectorAll(".quiz-option");
        opts.forEach((b, oi) => {
          b.disabled = true;
          if (oi === q.correct_index) b.classList.add("correct");
          else if (oi === answers[qi]) b.classList.add("incorrect");
        });
        qDiv.querySelector(".quiz-explication").hidden = false;
        const correct = answers[qi] === q.correct_index;
        if (correct) score++;
        results.push({
          question: q.question,
          user_answer: answers[qi] !== null ? q.options[answers[qi]] : "(sans réponse)",
          correct_answer: q.options[q.correct_index],
          correct: correct,
        });
      });

      submitBtn.hidden = true;
      scoreEl.hidden = false;
      scoreEl.textContent = "Score : " + score + "/" + questions.length;
      chatEl.scrollTop = chatEl.scrollHeight;

      const pays = selectPays.value, niveau = selectNiveau.value, matiere = selectMatiere.value;

      if (mode !== "diagnostic") {
        const shareScoreBtn = document.createElement("button");
        shareScoreBtn.type = "button";
        shareScoreBtn.className = "quiz-note";
        shareScoreBtn.textContent = "📤 Partager mon score";
        shareScoreBtn.addEventListener("click", () => {
          shareToWhatsApp(
            "🎯 J'ai eu " + score + "/" + questions.length + " à un quiz de " + matiere +
            " sur JPA Assistant Scolaire (assistant IA gratuit pour les devoirs) !\n\nEssaie toi aussi :"
          );
        });
        box.appendChild(shareScoreBtn);
      }

      if (mode === "diagnostic") {
        const noteBtn = document.createElement("button");
        noteBtn.type = "button";
        noteBtn.className = "quiz-note";
        noteBtn.textContent = "Voir mon bilan personnalisé";
        box.appendChild(noteBtn);
        noteBtn.addEventListener("click", async () => {
          noteBtn.disabled = true;
          noteBtn.textContent = "Analyse en cours…";
          try {
            const res = await fetch(apiUrl("/api/diagnostic/complete"), {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ device_id: DEVICE_ID, pays, niveau, matiere, score, total: questions.length, results }),
            });
            const data = await res.json();
            noteBtn.remove();
            if (!res.ok) {
              addErrorMessage(data, "Erreur lors de l'analyse.");
              return;
            }
            addMessage("🎯 " + data.note, "msg-bot");
          } catch (e) {
            addMessage("Connexion impossible pour générer le bilan.", "msg-error");
          }
        });
      } else {
        try {
          await fetch(apiUrl("/api/progress/log-quiz"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ device_id: DEVICE_ID, pays, niveau, matiere, score, total: questions.length }),
          });
        } catch (e) {
          // silencieux
        }
      }
    });

    chatEl.appendChild(box);
    chatEl.scrollTop = chatEl.scrollHeight;
  }

  async function startQuiz(diagnostic) {
    if (!diagnostic && !lastBotMessage) {
      window.alert("Pose d'abord une question, puis lance un quiz sur cette explication.");
      return;
    }
    if (diagnostic && !window.confirm(
      "Le diagnostic te pose 6 questions de base sur la matière choisie pour repérer " +
      "tes points forts et tes lacunes. Ça compte pour 1 question de ton quota. Continuer ?"
    )) return;

    const btn = diagnostic ? diagnosticBtn : quizBtn;
    btn.disabled = true;
    const loadingEl = addMessage(diagnostic ? "Préparation du diagnostic…" : "Préparation du quiz…", "msg-loading");

    try {
      const res = await fetch(apiUrl("/api/quiz"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_id: DEVICE_ID,
          pays: selectPays.value,
          niveau: selectNiveau.value,
          matiere: selectMatiere.value,
          sujet: diagnostic ? "" : lastBotMessage.slice(0, 1500),
          diagnostic: diagnostic,
        }),
      });
      const data = await res.json();
      loadingEl.remove();

      if (!res.ok) {
        addErrorMessage(data, "Une erreur est survenue.");
        if (typeof data.remaining === "number") setQuota(data.remaining, undefined);
        return;
      }
      if (!data.questions || !data.questions.length) {
        addMessage("Le quiz n'a pas pu être généré, réessaie.", "msg-error");
        return;
      }
      renderQuizInChat(data.questions, diagnostic ? "diagnostic" : "topic");
      recordActivity();
      isPremium = !!data.premium;
      setQuota(data.remaining, undefined);
    } catch (e) {
      loadingEl.remove();
      addMessage("Connexion impossible. Réessaie plus tard.", "msg-error");
    } finally {
      btn.disabled = false;
    }
  }

  quizBtn.addEventListener("click", () => startQuiz(false));
  diagnosticBtn.addEventListener("click", () => startQuiz(true));


  loadCurriculum();
  loadQuota();
  showStoredStreak();
  if (!restoreChatState()) {
    const staticWelcome = document.getElementById("welcome-msg");
    if (staticWelcome && staticWelcome.parentElement && !staticWelcome.parentElement.querySelector(".prog-demo")) {
      staticWelcome.parentElement.appendChild(buildProgrammeDemo());
    }
    const prenom = getStoredPrenom();
    if (prenom) {
      const welcomePrenomEl = document.getElementById("welcome-prenom");
      if (welcomePrenomEl) welcomePrenomEl.textContent = "Salut " + prenom + " !";
    }
  }
  askPrenomIfNeeded();

  // --- Navigation V2 : feuilles coulissantes, onglets du bas, mode sombre ---
  const scrimEl = document.getElementById("scrim");

  function closeSheets() {
    scrimEl.classList.remove("show");
    document.querySelectorAll(".sheet").forEach((s) => s.classList.remove("show"));
  }
  function openSheet(id) {
    closeSheets();
    scrimEl.classList.add("show");
    document.getElementById(id).classList.add("show");
  }
  document.getElementById("context-chip").addEventListener("click", () => openSheet("sheet-context"));
  document.getElementById("open-more-btn").addEventListener("click", () => openSheet("sheet-more"));
  scrimEl.addEventListener("click", closeSheets);
  document.querySelectorAll("[data-close-sheet]").forEach((b) => b.addEventListener("click", closeSheets));
  document.querySelectorAll("#sheet-more .menu-item").forEach((b) => b.addEventListener("click", closeSheets));

  // Onglet actif = panneau ouvert (Sujets / Cours / Devoirs), sinon "Prof".
  const panelTabs = [
    ["toggle-epreuves-btn", epreuvesPanel],
    ["toggle-cours-btn", coursPanel],
    ["toggle-devoirs-btn", devoirsPanel],
  ];
  const profTab = document.getElementById("tab-prof");
  function refreshTabs() {
    let anyOpen = false;
    panelTabs.forEach(([id, panel]) => {
      const open = !panel.hidden;
      if (open) anyOpen = true;
      document.getElementById(id).classList.toggle("active", open);
    });
    profTab.classList.toggle("active", !anyOpen);
  }
  const tabsObserver = new MutationObserver(refreshTabs);
  panelTabs.forEach(([, panel]) => tabsObserver.observe(panel, { attributes: true, attributeFilter: ["hidden"] }));
  profTab.addEventListener("click", () => {
    panelTabs.forEach(([, panel]) => { panel.hidden = true; });
    refreshTabs();
  });

  const themeToggleBtn = document.getElementById("theme-toggle-btn");
  const themeToggleLabel = document.getElementById("theme-toggle-label");
  function applyTheme(dark) {
    if (dark) document.documentElement.setAttribute("data-theme", "dark");
    else document.documentElement.removeAttribute("data-theme");
    themeToggleLabel.textContent = dark ? "Mode clair" : "Mode sombre";
  }
  applyTheme(document.documentElement.getAttribute("data-theme") === "dark");
  themeToggleBtn.addEventListener("click", () => {
    const dark = document.documentElement.getAttribute("data-theme") !== "dark";
    applyTheme(dark);
    try { localStorage.setItem("aida_theme", dark ? "dark" : "light"); } catch (e) {}
  });

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("service-worker.js").catch(() => {});
    });
  }
})();
