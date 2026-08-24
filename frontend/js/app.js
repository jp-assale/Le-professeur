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
  const deviceCodeBtn = document.getElementById("device-code-btn");
  const reportBtn = document.getElementById("report-btn");
  const upgradeLink = document.getElementById("upgrade-link");
  const quizBtn = document.getElementById("quiz-btn");
  const diagnosticBtn = document.getElementById("diagnostic-btn");
  const correctionBtn = document.getElementById("correction-btn");
  const correctionPanel = document.getElementById("correction-panel");
  const corrEnonce = document.getElementById("corr-enonce");
  const corrReponse = document.getElementById("corr-reponse");
  const corrPhoto = document.getElementById("corr-photo");
  const corrBareme = document.getElementById("corr-bareme");
  const corrSubmit = document.getElementById("corr-submit");
  const progressBtn = document.getElementById("progress-btn");
  const progressOverlay = document.getElementById("progress-overlay");
  const progressClose = document.getElementById("progress-close");
  const progressContent = document.getElementById("progress-content");

  let lastBotMessage = "";
  let isPremium = false;

  const DEVICE_ID = getOrCreateDeviceId();
  const WELCOME_TEXT = "Salut ! Je suis Le Professeur, ton assistant pour les devoirs. " +
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

  function addMessage(text, cls) {
    const div = document.createElement("div");
    div.className = "msg " + cls;
    const p = document.createElement("p");
    p.textContent = text;
    div.appendChild(p);
    chatEl.appendChild(div);
    chatEl.scrollTop = chatEl.scrollHeight;
    if (cls === "msg-bot") lastBotMessage = text;
    return div;
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
      const [pdfSujets, exercices] = await Promise.all([
        fetchWithRetry(apiUrl("/api/pdf-sujets?" + params.toString())).then((r) => r.json()),
        fetchWithRetry(apiUrl("/api/epreuves?" + params.toString())).then((r) => r.json()),
      ]);
      epreuvesList.innerHTML = "";

      if (pdfSujets.length) {
        epreuvesList.appendChild(sectionHeader("📄 Sujets officiels (PDF)"));
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
          workBtn.textContent = "💬 Corriger avec Le Professeur";
          workBtn.addEventListener("click", () => workOnPdfSujet(s.id, s.titre));

          li.appendChild(viewLink);
          li.appendChild(workBtn);
          epreuvesList.appendChild(li);
        });
      }

      if (exercices.length) {
        epreuvesList.appendChild(sectionHeader("📝 Exercices type (originaux)"));
        exercices.forEach((ep) => {
          const li = document.createElement("li");
          const btn = document.createElement("button");
          btn.type = "button";
          btn.textContent = ep.titre + " (" + ep.annee + ")";
          btn.addEventListener("click", () => startEpreuve(ep.id));
          li.appendChild(btn);
          epreuvesList.appendChild(li);
        });
      }

      if (!pdfSujets.length && !exercices.length) {
        epreuvesList.innerHTML =
          '<li class="epreuves-empty">Aucun sujet pour cette combinaison pays / niveau / matière pour l\'instant.</li>';
      }
    } catch (e) {
      epreuvesList.innerHTML = '<li class="epreuves-empty">Erreur de chargement.</li>';
    }
  }

  function sectionHeader(text) {
    const li = document.createElement("li");
    li.className = "epreuves-section-header";
    li.textContent = text;
    return li;
  }

  async function startEpreuve(id) {
    try {
      const res = await fetch(apiUrl("/api/epreuves/" + encodeURIComponent(id)));
      if (!res.ok) return;
      const ep = await res.json();

      currentEpreuveId = ep.id;
      history = [];
      clearChat();
      addMessage("📄 " + ep.titre + " (" + ep.annee + ")\n\n" + ep.enonce, "msg-bot");

      epreuveActive.hidden = false;
      epreuveActive.textContent = "Sujet : " + ep.titre;
      quitEpreuveBtn.hidden = false;
      epreuvesPanel.hidden = true;
    } catch (e) {
      // silencieux: l'utilisateur peut réessayer
    }
  }

  function quitEpreuve() {
    currentEpreuveId = null;
    history = [];
    clearChat();
    addMessage(WELCOME_TEXT, "msg-bot");
    epreuveActive.hidden = true;
    quitEpreuveBtn.hidden = true;
  }

  toggleEpreuvesBtn.addEventListener("click", () => {
    correctionPanel.hidden = true;
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

    const loadingEl = addMessage("Le Professeur réfléchit…", "msg-loading");

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
          epreuve_id: currentEpreuveId,
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
      history.push({ role: "user", content: question });
      history.push({ role: "assistant", content: data.answer });
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
    clearChat();
    addMessage("📎 " + (displayLabel || file.name), "msg-user");
    const loadingEl = addMessage("Le Professeur regarde ton sujet…", "msg-loading");
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
      history = [
        { role: "user", content: "[L'élève a envoyé une photo/PDF de son sujet]" },
        { role: "assistant", content: data.answer },
      ];
      epreuveActive.hidden = false;
      epreuveActive.textContent = "Sujet envoyé : " + (displayLabel || file.name);
      quitEpreuveBtn.hidden = false;
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
    try {
      const res = await fetch(apiUrl("/api/pdf-sujets/" + encodeURIComponent(sujetId) + "/fichier"));
      if (!res.ok) {
        addMessage("Impossible de récupérer ce PDF.", "msg-error");
        return;
      }
      const blob = await res.blob();
      const file = new File([blob], titre + ".pdf", { type: "application/pdf" });
      processFileForCorrection(file, titre);
    } catch (e) {
      addMessage("Connexion impossible. Réessaie plus tard.", "msg-error");
    }
  }

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
      "Qu'est-ce qui semble faux ou pose problème dans la dernière réponse du Professeur ? " +
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
      p.textContent = (qi + 1) + ". " + q.question;
      qDiv.appendChild(p);

      q.options.forEach((opt, oi) => {
        const optBtn = document.createElement("button");
        optBtn.type = "button";
        optBtn.className = "quiz-option";
        optBtn.textContent = opt;
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
      expl.textContent = q.explication || "";
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

  // --- Correction de copie ----------------------------------------------

  correctionBtn.addEventListener("click", () => {
    epreuvesPanel.hidden = true;
    correctionPanel.hidden = !correctionPanel.hidden;
  });

  corrSubmit.addEventListener("click", async () => {
    const enonce = corrEnonce.value.trim();
    const reponseTexte = corrReponse.value.trim();
    const photoFile = corrPhoto.files[0];
    const bareme = parseInt(corrBareme.value, 10) || 20;

    if (!enonce) {
      window.alert("Indique l'énoncé de la question.");
      return;
    }
    if (!reponseTexte && !photoFile) {
      window.alert("Écris ta réponse ou joins une photo de ta copie.");
      return;
    }

    corrSubmit.disabled = true;
    corrSubmit.textContent = "Correction en cours…";
    correctionPanel.hidden = true;

    addMessage("✍️ Copie envoyée pour correction : " + enonce, "msg-user");
    const loadingEl = addMessage("Le Professeur corrige ta copie…", "msg-loading");

    try {
      const body = {
        device_id: DEVICE_ID,
        pays: selectPays.value,
        niveau: selectNiveau.value,
        matiere: selectMatiere.value,
        enonce: enonce,
        reponse_texte: reponseTexte,
        bareme: bareme,
      };
      if (photoFile) {
        body.mime_type = photoFile.type;
        body.data = await fileToBase64(photoFile);
      }
      const res = await fetch(apiUrl("/api/correction-copie"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      loadingEl.remove();

      if (!res.ok) {
        addMessage(data.message || data.error || "Une erreur est survenue.", "msg-error");
        if (typeof data.remaining === "number") setQuota(data.remaining, undefined);
        return;
      }
      addMessage(data.answer, "msg-bot");
      isPremium = !!data.premium;
      setQuota(data.remaining, undefined);
      corrEnonce.value = "";
      corrReponse.value = "";
      corrPhoto.value = "";
    } catch (e) {
      loadingEl.remove();
      addMessage("Connexion impossible. Réessaie plus tard.", "msg-error");
    } finally {
      corrSubmit.disabled = false;
      corrSubmit.textContent = "Faire corriger";
    }
  });

  // --- Suivi de progression ----------------------------------------------

  progressBtn.addEventListener("click", async () => {
    progressOverlay.hidden = false;
    progressContent.innerHTML = '<p class="epreuves-empty">Chargement… (nouvelle tentative automatique si ça ne répond pas)</p>';
    try {
      const res = await fetchWithRetry(
        apiUrl("/api/progress?device_id=" + encodeURIComponent(DEVICE_ID)),
        undefined, 2, 15000
      );
      if (!res.ok) {
        progressContent.innerHTML = '<p class="epreuves-empty">Erreur serveur (' + res.status + '). Réessaie plus tard.</p>';
        return;
      }
      const data = await res.json();
      if (!data.matieres || !data.matieres.length) {
        progressContent.innerHTML = '<p class="epreuves-empty">Pas encore d\'activité enregistrée — pose des questions, fais un quiz !</p>';
        return;
      }
      progressContent.innerHTML = "";
      data.matieres.forEach((m) => {
        const row = document.createElement("div");
        row.className = "progress-row";
        const pct = m.avg_score_pct;
        row.innerHTML =
          '<div class="matiere-name">' + m.matiere + "</div>" +
          '<div class="progress-stats">' + m.questions + " question(s) posée(s)" +
          (m.quiz_count ? " · " + m.quiz_count + " quiz/test(s), score moyen " + pct + "%" : "") +
          "</div>" +
          (pct !== null && pct !== undefined
            ? '<div class="progress-bar-track"><div class="progress-bar-fill" style="width:' + pct + '%"></div></div>'
            : "");
        progressContent.appendChild(row);
      });
    } catch (e) {
      clearTimeout(timeoutId);
      console.error("Erreur /api/progress:", e);
      const msg = e.name === "AbortError"
        ? "Le serveur met trop de temps à répondre (plus de 60s). Vérifie ta connexion et réessaie."
        : "Connexion impossible (" + (e.message || e) + "). Vérifie ta connexion et réessaie.";
      progressContent.innerHTML = '<p class="epreuves-empty">' + msg + '</p>';
    }
  });

  progressClose.addEventListener("click", () => { progressOverlay.hidden = true; });
  progressOverlay.addEventListener("click", (e) => {
    if (e.target === progressOverlay) progressOverlay.hidden = true;
  });

  loadCurriculum();
  loadQuota();

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("service-worker.js").catch(() => {});
    });
  }
})();
