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
  const epreuveActive = document.getElementById("epreuve-active");
  const quitEpreuveBtn = document.getElementById("quit-epreuve-btn");
  const attachBtn = document.getElementById("attach-btn");
  const attachInput = document.getElementById("attach-input");
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
    "Choisis ton pays, ton niveau et ta matière ci-dessus, puis pose-moi ta " +
    "question de cours ou d'exercice — je t'explique étape par étape, je ne " +
    "donne pas juste la réponse toute cuite 😉 Tu peux aussi piocher un sujet " +
    "type examen dans « 📄 Sujets d'examen ».";

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

  function addMessage(text, cls) {
    const div = document.createElement("div");
    div.className = "msg " + cls;
    let content = null;
    if (cls === "msg-bot") {
      content = document.createElement("div");
      content.className = "msg-content";
      renderBotContent(content, text);
      div.appendChild(content);
    } else {
      const p = document.createElement("p");
      p.textContent = text;
      div.appendChild(p);
    }
    chatEl.appendChild(div);
    if (content) shrinkOverflowingMath(content);
    chatEl.scrollTop = chatEl.scrollHeight;
    if (cls === "msg-bot") lastBotMessage = text;
    if (!restoringChat && (cls === "msg-user" || cls === "msg-bot")) {
      chatLog.push({ text, cls });
      persistChatState();
    }
    return div;
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

  function setQuota(remaining, limit) {
    if (isPremium) {
      quotaBadge.textContent = "✨ Illimité";
      return;
    }
    if (remaining === null || remaining === undefined) {
      quotaBadge.textContent = "…";
      return;
    }
    quotaBadge.textContent = remaining + "/" + (limit ?? "?") + " questions";
  }

  async function loadCurriculum() {
    const res = await fetchWithRetry(apiUrl("/api/curriculum"));
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
  }

  [selectPays, selectNiveau, selectMatiere].forEach((sel) => {
    sel.addEventListener("change", () => {
      localStorage.setItem("aida_pays", selectPays.value);
      localStorage.setItem("aida_niveau", selectNiveau.value);
      localStorage.setItem("aida_matiere", selectMatiere.value);
      if (!epreuvesPanel.hidden) loadEpreuvesList();
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
    currentEpreuveId = null;
    history = [];
    chatLog = [];
    clearPersistedChatState();
    clearChat();
    addMessage(WELCOME_TEXT, "msg-bot");
    epreuveActive.hidden = true;
    quitEpreuveBtn.hidden = true;
  }

  toggleEpreuvesBtn.addEventListener("click", () => {
    epreuvesPanel.hidden = !epreuvesPanel.hidden;
    if (!epreuvesPanel.hidden) loadEpreuvesList();
  });

  quitEpreuveBtn.addEventListener("click", quitEpreuve);

  async function loadQuota() {
    try {
      const res = await fetchWithRetry(apiUrl("/api/quota?device_id=" + encodeURIComponent(DEVICE_ID)));
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

    addMessage(question, "msg-user");
    input.value = "";
    input.style.height = "auto";
    sendBtn.disabled = true;

    const loadingEl = addMessage("Le Prof JPA réfléchit…", "msg-loading");

    try {
      const res = await fetch(apiUrl("/api/ask"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_id: DEVICE_ID,
          pays: selectPays.value,
          niveau: selectNiveau.value,
          matiere: selectMatiere.value,
          question: question,
          history: history,
        }),
      });
      const data = await res.json();
      loadingEl.remove();

      if (!res.ok) {
        addMessage(data.message || data.error || "Une erreur est survenue.", "msg-error");
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
        }),
      });
      const data = await res.json();
      loadingEl.remove();

      if (!res.ok) {
        addMessage(data.message || data.error || "Une erreur est survenue.", "msg-error");
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

  attachInput.addEventListener("change", () => {
    const file = attachInput.files[0];
    attachInput.value = "";
    if (file) processFileForCorrection(file);
  });

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
        addMessage(data.message || data.error || "Une erreur est survenue.", "msg-error");
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

  deviceCodeBtn.addEventListener("click", () => {
    const input = window.prompt(
      "Ton code appareil (note-le pour retrouver tes questions restantes sur un " +
      "autre téléphone) :\n\n" + DEVICE_ID +
      "\n\nPour utiliser un code que tu as déjà, colle-le ci-dessous puis valide. " +
      "Sinon laisse tel quel et annule.",
      DEVICE_ID
    );
    if (input && input.trim() && input.trim() !== DEVICE_ID) {
      localStorage.setItem("aida_device_id", input.trim());
      window.location.reload();
    }
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
        window.alert(
          data.message || data.error ||
          "Abonnement pas encore disponible, réessaie plus tard."
        );
        return;
      }
      window.location.href = data.payment_url;
    } catch (e) {
      window.alert("Connexion impossible. Réessaie plus tard.");
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
              addMessage(data.message || data.error || "Erreur lors de l'analyse.", "msg-error");
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
        addMessage(data.message || data.error || "Une erreur est survenue.", "msg-error");
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
  restoreChatState();

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("service-worker.js").catch(() => {});
    });
  }
})();
