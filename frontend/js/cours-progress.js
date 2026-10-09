/* Progression de l'eleve dans les cours - purement locale (localStorage),
   comme la serie de jours 🔥 : aucun appel serveur, fonctionne hors-ligne.
   Partage entre index.html (liste des cours) et cours.html (lecon). */
(function () {
  const KEY = "aida_cours_progress";

  function read() {
    try {
      const data = JSON.parse(localStorage.getItem(KEY) || "{}");
      return data && typeof data === "object" ? data : {};
    } catch (e) {
      return {};
    }
  }

  function write(data) {
    try { localStorage.setItem(KEY, JSON.stringify(data)); } catch (e) {}
  }

  function update(slug, patch) {
    if (!slug) return;
    const data = read();
    data[slug] = Object.assign({}, data[slug], patch, { last: Date.now() });
    write(data);
  }

  // Meme logique que recordActivity() d'app.js (cles partagees) : terminer
  // une lecon compte comme une vraie journee de travail pour la serie 🔥.
  function recordStreakActivity() {
    try {
      const today = new Date().toISOString().slice(0, 10);
      const lastDate = localStorage.getItem("aida_streak_date");
      if (lastDate === today) return;
      let count = parseInt(localStorage.getItem("aida_streak_count") || "0", 10);
      const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
      count = lastDate === yesterday ? count + 1 : 1;
      localStorage.setItem("aida_streak_date", today);
      localStorage.setItem("aida_streak_count", String(count));
    } catch (e) {}
  }

  window.CoursProgress = {
    get(slug) { return read()[slug] || null; },
    all: read,
    markOpened(slug) { update(slug, { opened: true }); },
    markDone(slug) { update(slug, { done: true }); recordStreakActivity(); },
    // Meilleur score obtenu aux exercices auto-evalues de la lecon.
    saveScore(slug, ok, total) {
      const prev = read()[slug];
      const best = prev && typeof prev.best === "number" ? prev.best : -1;
      if (ok >= best) update(slug, { best: ok, total: total });
    },
    isDone(slug) { const p = read()[slug]; return !!(p && p.done); },
  };
})();
