(function () {
  "use strict";

  const API_BASE = (window.AIDA_API_BASE_URL || "").replace(/\/$/, "");
  function apiUrl(path) {
    return API_BASE + path;
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
    const res = await fetch(apiUrl("/api/curriculum"));
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
        fetch(apiUrl("/api/pdf-sujets?" + params.toString())).then((r) => r.json()),
        fetch(apiUrl("/api/epreuves?" + params.toString())).then((r) => r.json()),
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
    epreuvesPanel.hidden = !epreuvesPanel.hidden;
    if (!epreuvesPanel.hidden) loadEpreuvesList();
  });

  quitEpreuveBtn.addEventListener("click", quitEpreuve);

  async function loadQuota() {
    try {
      const res = await fetch(apiUrl("/api/quota?device_id=" + encodeURIComponent(DEVICE_ID)));
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

  loadCurriculum();
  loadQuota();

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("service-worker.js").catch(() => {});
    });
  }
})();
