/* Rendu generique d'une lecon "Cours" a partir du JSON renvoye par /api/cours/<slug>.
   Les 3 simulations interactives (geometry_ratio, physics_vector, function_affine)
   sont du code fixe et deja valide - le contenu genere par l'IA ne fournit que le
   texte (mise en situation, enonce, exemple, quiz), jamais de HTML/JS. */

function el(tag, opts) {
  const node = document.createElement(tag);
  if (opts) {
    if (opts.className) node.className = opts.className;
    if (opts.text !== undefined) node.textContent = opts.text;
    if (opts.html !== undefined) node.innerHTML = opts.html;
  }
  return node;
}

function buildSlideShell(kicker, heading) {
  const section = el("section", { className: "slide" });
  section.appendChild(el("div", { className: "slide-kicker", text: kicker }));
  if (heading) section.appendChild(el("h2", { text: heading }));
  return section;
}

/* Lecture a voix haute : texte converti en francais parle par speech-text.js
   (formules, unites, pauses), vitesse reduite s'il y a des calculs. */
function cleanCoursTextForSpeech(text) {
  return window.speakableFrench ? window.speakableFrench(text) : String(text || "").replace(/[$\{}]/g, " ");
}
function coursSpeechRate(rawText) {
  return window.speechRateFor ? window.speechRateFor(rawText) : 0.9;
}

let coursCachedFrenchVoice = null;
function getCoursFrenchMaleVoice() {
  if (!window.speechSynthesis) return null;
  if (coursCachedFrenchVoice) return coursCachedFrenchVoice;
  const voices = speechSynthesis.getVoices();
  if (!voices.length) return null;
  const french = voices.filter((v) => v.lang && v.lang.toLowerCase().startsWith("fr"));
  // Voix imposee : « Microsoft Paul - French » (Windows/Edge/Chrome PC).
  const paul = french.find((v) => /microsoft paul/i.test(v.name)) || french.find((v) => /paul/i.test(v.name));
  if (paul) { coursCachedFrenchVoice = paul; return paul; }
  const male = french.find((v) => /male|homme|thomas|paul|nicolas|guillaume|daniel|henri|louis/i.test(v.name) && !/female|femme/i.test(v.name));
  coursCachedFrenchVoice = male || french[0] || voices[0] || null;
  return coursCachedFrenchVoice;
}
if (window.speechSynthesis) {
  speechSynthesis.addEventListener("voiceschanged", () => { coursCachedFrenchVoice = null; });
}

// La WebView Android n'implemente pas window.speechSynthesis - sans ce
// plugin natif, le bouton "Ecouter" resterait invisible dans l'appli
// installee alors qu'il fonctionne sur le web (voir app.js pour le meme
// correctif, duplique ici car cours.html est un contexte JS separe).
function coursIsNativeApp() {
  return !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());
}
function coursGetNativeTTS() {
  return (window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.TextToSpeech) || null;
}
function coursSpeechAvailable() {
  return coursIsNativeApp() ? !!coursGetNativeTTS() : !!window.speechSynthesis;
}

async function coursSpeakNative(text, rate) {
  rate = rate || 0.9;
  if (window.speakServer) {
    try { return await window.speakServer(text, rate); } catch (e) {}
  }
  const tts = coursGetNativeTTS();
  let voiceIndex;
  try {
    const res = await tts.getSupportedVoices();
    const fr = (res.voices || [])
      .map((v, index) => ({ index, uri: v.voiceURI || "", lang: v.lang || "" }))
      .filter((v) => /^fr/i.test(v.lang));
    const chosen = fr.find((v) => /fr-fr-x-(frb|frd)/i.test(v.uri));
    if (chosen) voiceIndex = chosen.index;
  } catch (e) {}
  const opts = { text, lang: "fr-FR", rate, pitch: 0.8 };
  if (voiceIndex !== undefined) opts.voice = voiceIndex;
  return tts.speak(opts);
}

let coursCurrentSpeakBtn = null;
let coursSpeechToken = 0;

function stopCoursSpeaking() {
  coursSpeechToken++;
  if (coursIsNativeApp()) {
    if (window.stopServerSpeech) window.stopServerSpeech();
    const tts = coursGetNativeTTS();
    if (tts) tts.stop();
  } else if (window.speechSynthesis) {
    speechSynthesis.cancel();
  }
  if (coursCurrentSpeakBtn) {
    coursCurrentSpeakBtn.classList.remove("speaking");
    coursCurrentSpeakBtn.textContent = "🔊 Écouter";
  }
  coursCurrentSpeakBtn = null;
}

function addCoursSpeakButton(section, text) {
  if (!coursSpeechAvailable()) return;
  const btn = el("button", { className: "msg-speak-btn", text: "🔊 Écouter" });
  btn.addEventListener("click", () => {
    const wasSpeaking = coursCurrentSpeakBtn === btn;
    stopCoursSpeaking();
    if (wasSpeaking) return;
    const cleanText = cleanCoursTextForSpeech(text);
    const rate = coursSpeechRate(text);
    const myToken = coursSpeechToken;
    coursCurrentSpeakBtn = btn;
    btn.classList.add("speaking");
    btn.textContent = "⏸ Arrêter";

    if (coursIsNativeApp()) {
      // Voir app.js pour le detail : voix choisie par l'eleve (menu
      // « Choisir la voix », partagee via localStorage), a defaut variantes
      // « frb »/« frd » du moteur Google + pitch abaisse.
      coursSpeakNative(cleanText, rate).catch(() => {}).then(() => {
        if (coursSpeechToken === myToken) stopCoursSpeaking();
      });
    } else {
      const utterance = new SpeechSynthesisUtterance(cleanText);
      utterance.lang = "fr-FR";
      const voice = getCoursFrenchMaleVoice();
      if (voice) utterance.voice = voice;
      utterance.rate = rate;
      utterance.onend = () => { if (coursSpeechToken === myToken) stopCoursSpeaking(); };
      utterance.onerror = () => { if (coursSpeechToken === myToken) stopCoursSpeaking(); };
      speechSynthesis.speak(utterance);
    }
  });
  section.appendChild(btn);
}

/* Court rappel visuel (3 points + icone) affiche sous la mise en situation,
   qui apparait progressivement (comme un "build" PowerPoint) - genere par
   l'IA en meme temps que le reste de la lecon (champ "resume" optionnel,
   absent sur les lecons plus anciennes pas encore mises a jour). */
function renderResumeSection(data) {
  const points = data.resume && data.resume.points;
  if (!Array.isArray(points) || !points.length) return null;

  const wrap = el("div", { className: "resume-section" });
  wrap.appendChild(el("div", { className: "resume-title", text: "✨ Résumé en un coup d'œil" }));
  const card = el("div", { className: "resume-card" });
  const list = el("ul", { className: "resume-points" });
  points.forEach((pt, i) => {
    const li = el("li", {});
    li.style.animationDelay = (0.3 + i * 0.45) + "s";
    li.appendChild(el("span", { className: "icon", text: pt.icon || "" }));
    li.appendChild(el("span", { text: pt.text || "" }));
    list.appendChild(li);
  });
  card.appendChild(list);
  wrap.appendChild(card);
  return wrap;
}

/* Petite liste titree (objectifs, prerequis...) - champs optionnels apportes
   par les complements pedagogiques (cours_seed/enrichments/). */
function renderMiniList(className, title, items) {
  if (!Array.isArray(items) || !items.length) return null;
  const box = el("div", { className: "mini-list " + className });
  box.appendChild(el("div", { className: "mini-list-title", text: title }));
  const ul = el("ul");
  items.forEach((t) => ul.appendChild(el("li", { text: t })));
  box.appendChild(ul);
  return box;
}

function renderIntroSlide(data) {
  const section = buildSlideShell("Mise en situation", data.intro.heading);
  const card = el("div", { className: "card" });
  card.appendChild(el("p", { text: data.intro.body }));
  section.appendChild(card);
  addCoursSpeakButton(section, data.intro.heading + ". " + data.intro.body);
  // La situation accroche d'abord l'eleve ; objectifs et prerequis viennent
  // ensuite, avant le resume anime.
  const objectifs = renderMiniList("objectifs", "🎯 À la fin de ce cours, tu sauras :", data.objectifs);
  if (objectifs) section.appendChild(objectifs);
  const prerequis = renderMiniList("prerequis", "🧱 Ce que tu dois déjà savoir :", data.prerequis);
  if (prerequis) section.appendChild(prerequis);
  const resume = renderResumeSection(data);
  if (resume) section.appendChild(resume);
  return section;
}

const PAYS_LABELS = {
  cote_ivoire: "Côte d'Ivoire", mali: "Mali", senegal: "Sénégal",
  burkina_faso: "Burkina Faso", benin: "Bénin", guinee: "Guinée",
};

/* Schema simplifie de la lecon (SVT / physique-chimie) : structure generee
   puis VERIFIEE par un second modele (voir backend/generate_cours_schemas.py),
   dessinee ici par du code fixe - jamais de SVG ecrit par l'IA. Absent pour
   les lecons sans schema valide. */
function renderLessonSchema(data) {
  const schema = data.schema;
  if (!schema || !window.buildSchemaSvg) return null;
  if (data.schema_status !== "ok" && data.schema_status !== "corrige") return null;
  let svg;
  try {
    svg = buildSchemaSvg(schema);
  } catch (e) {
    return null;
  }
  const wrap = el("div", { className: "schema-block" });
  if (schema.titre) {
    const title = el("p", { text: "🔬 " + schema.titre });
    title.style.cssText = "margin:0 0 6px;font-weight:700;";
    wrap.appendChild(title);
  }
  wrap.appendChild(svg);
  wrap.appendChild(el("p", {
    className: "schema-note",
    text: "Schéma simplifié généré par l'IA et vérifié. Compare-le avec ton cours.",
  }));
  return wrap;
}

function renderConceptSlide(data) {
  const section = buildSlideShell("Le concept", data.concept.heading);
  section.appendChild(el("p", { text: data.concept.explanation }));
  const schemaBlock = renderLessonSchema(data);
  if (schemaBlock) section.appendChild(schemaBlock);
  if (data.concept.highlight) {
    const box = el("div", { className: "theorem-box" });
    box.appendChild(el("b", { text: data.concept.highlight }));
    section.appendChild(box);
  }
  // Seconde partie du concept (presente sur quelques lecons, jusqu'ici
  // generee mais jamais affichee).
  const c2 = data.concept_2;
  if (c2 && c2.explanation) {
    if (c2.heading) section.appendChild(el("h3", { className: "sub-heading", text: c2.heading }));
    section.appendChild(el("p", { text: c2.explanation }));
    if (c2.highlight) {
      const box2 = el("div", { className: "theorem-box" });
      box2.appendChild(el("b", { text: c2.highlight }));
      section.appendChild(box2);
    }
  }
  const ext = data.concept_extension;
  if (ext && Array.isArray(ext.types) && ext.types.length) {
    if (ext.heading) section.appendChild(el("h3", { className: "sub-heading", text: ext.heading }));
    ext.types.forEach((t) => {
      const card = el("div", { className: "card type-card" });
      card.appendChild(el("b", { text: t.name || "" }));
      if (t.description) card.appendChild(el("p", { text: t.description }));
      if (t.signal) card.appendChild(el("p", { className: "muted", text: "🔎 " + t.signal }));
      section.appendChild(card);
    });
  }
  if (data.fallback_for) {
    const note = el("div", { className: "theorem-box warn-box" });
    note.textContent =
      "🌍 Programme non confirmé pour " + (PAYS_LABELS[data.fallback_for] || data.fallback_for) +
      " — ce cours suit le programme confirmé de " + (PAYS_LABELS[data.pays] || data.pays) +
      ", pris comme référence régionale (tronc commun francophone).";
    section.appendChild(note);
  }
  const src = el("span", { className: "badge-source", text: "Source du programme : " + data.source });
  section.appendChild(src);
  addCoursSpeakButton(section, data.concept.heading + ". " + data.concept.explanation + (data.concept.highlight ? ". " + data.concept.highlight : ""));
  return section;
}

function appendExampleSteps(card, steps) {
  (steps || []).forEach((txt, i) => {
    const row = el("div", { className: "example-step" });
    row.style.animationDelay = (i * 0.2) + "s";
    row.appendChild(el("div", { className: "num", text: String(i + 1) }));
    row.appendChild(el("div", { text: txt }));
    card.appendChild(row);
  });
}

function renderExampleSlide(data) {
  const section = buildSlideShell("Exemple résolu", "Applique ce que tu viens de voir");
  section.appendChild(el("p", { text: data.example.problem }));
  const card = el("div", { className: "card" });
  appendExampleSteps(card, data.example.steps);
  section.appendChild(card);
  let spoken = data.example.problem + ". " + data.example.steps.join(". ");
  const ex2 = data.example_2;
  if (ex2 && ex2.problem) {
    section.appendChild(el("h3", { className: "sub-heading", text: "Deuxième exemple" }));
    section.appendChild(el("p", { text: ex2.problem }));
    const card2 = el("div", { className: "card" });
    appendExampleSteps(card2, ex2.steps);
    section.appendChild(card2);
    spoken += ". Deuxième exemple. " + ex2.problem + ". " + (ex2.steps || []).join(". ");
  }
  addCoursSpeakButton(section, spoken);
  return section;
}

/* Melange de Fisher-Yates : dans les lecons generees, la bonne reponse est
   tres souvent le 2e choix (86 % des cas) - sans melange, l'eleve apprend a
   cocher « B » au lieu de reflechir. */
function shuffled(list) {
  const a = list.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function renderQuizSlide(data) {
  const section = buildSlideShell("Question flash", "Vérifie que tu as compris");
  section.appendChild(el("p", { text: data.quiz.question }));
  const choicesBox = el("div", { className: "quiz-choices" });
  const feedback = el("div", { className: "quiz-feedback" });
  feedback.setAttribute("aria-live", "polite");
  let answered = false;
  const buttons = [];
  shuffled(data.quiz.choices).forEach(c => {
    const btn = el("button", { className: "quiz-choice", text: c.label });
    buttons.push({ btn, c });
    btn.addEventListener("click", () => {
      if (answered) return;
      answered = true;
      btn.classList.add(c.correct ? "correct" : "wrong");
      // Montre toujours la bonne reponse apres une erreur.
      if (!c.correct) buttons.forEach((b) => { if (b.c.correct) b.btn.classList.add("correct"); });
      buttons.forEach((b) => { b.btn.disabled = true; });
      feedback.classList.add(c.correct ? "ok" : "ko");
      feedback.textContent = c.correct ? data.quiz.feedback_correct : data.quiz.feedback_wrong;
    });
    choicesBox.appendChild(btn);
  });
  section.appendChild(choicesBox);
  section.appendChild(feedback);
  return section;
}

/* --- Fiche « À retenir » : l'essentiel a reviser la veille de l'examen,
   les erreurs classiques et la methode attendue a l'examen. --- */
function renderRetenirSlide(data) {
  const ar = data.a_retenir || {};
  const points = Array.isArray(ar.points) ? ar.points : [];
  const formules = Array.isArray(ar.formules) ? ar.formules : [];
  const erreurs = Array.isArray(data.erreurs_frequentes) ? data.erreurs_frequentes : [];
  const methode = data.methode_examen;
  if (!points.length && !formules.length && !erreurs.length && !methode) return null;

  const section = buildSlideShell("À retenir", "Ta fiche de révision");
  let spoken = "";
  if (points.length) {
    const card = el("div", { className: "card retenir-card" });
    const ul = el("ul", { className: "retenir-list" });
    points.forEach((p) => ul.appendChild(el("li", { text: p })));
    card.appendChild(ul);
    section.appendChild(card);
    spoken += points.join(". ") + ". ";
  }
  if (formules.length) {
    const box = el("div", { className: "theorem-box formules-box" });
    box.appendChild(el("div", { className: "mini-list-title", text: "📐 Formules et règles clés" }));
    formules.forEach((f) => box.appendChild(el("div", { className: "formule", text: f })));
    section.appendChild(box);
  }
  if (erreurs.length) {
    section.appendChild(el("h3", { className: "sub-heading", text: "⚠️ Erreurs fréquentes à éviter" }));
    erreurs.forEach((e) => {
      const card = el("div", { className: "card erreur-card" });
      card.appendChild(el("p", { className: "erreur", text: "✗ " + (e.erreur || "") }));
      card.appendChild(el("p", { className: "correction", text: "✓ " + (e.correction || "") }));
      section.appendChild(card);
      spoken += "Erreur fréquente : " + (e.erreur || "") + ". " + (e.correction || "") + ". ";
    });
  }
  if (methode && Array.isArray(methode.etapes) && methode.etapes.length) {
    const box = el("div", { className: "card methode-card" });
    box.appendChild(el("div", { className: "mini-list-title", text: "🧭 " + (methode.titre || "Méthode à l'examen") }));
    const ol = el("ol");
    methode.etapes.forEach((t) => ol.appendChild(el("li", { text: t })));
    box.appendChild(ol);
    section.appendChild(box);
  }
  if (spoken) addCoursSpeakButton(section, spoken);
  return section;
}

/* --- Exercices d'entrainement corriges (facile → type examen), avec indice
   et corrige caches : l'eleve cherche d'abord, puis s'auto-evalue. Le
   meilleur score est garde localement (CoursProgress). --- */
const NIVEAU_EXO = { facile: "Facile", moyen: "Moyen", examen: "Type examen" };

function renderExercicesSlide(data) {
  const exos = Array.isArray(data.exercices) ? data.exercices.filter((x) => x && x.enonce) : [];
  if (!exos.length) return null;
  const section = buildSlideShell("Entraîne-toi", "Exercices corrigés");
  section.appendChild(el("p", {
    className: "muted",
    text: "Cherche d'abord sur ton cahier. Ouvre l'indice si tu bloques, puis compare avec le corrigé et dis honnêtement si tu as réussi.",
  }));
  const results = new Array(exos.length).fill(null);
  const score = el("div", { className: "exo-score" });
  score.setAttribute("aria-live", "polite");

  function refreshScore() {
    const answered = results.filter((r) => r !== null).length;
    const ok = results.filter((r) => r === true).length;
    if (!answered) { score.textContent = ""; return; }
    score.textContent = `Score : ${ok} / ${exos.length}` + (answered < exos.length ? " (continue !)" : ok === exos.length ? " — excellent 🎉" : " — revois la fiche « À retenir » et réessaie.");
    if (answered === exos.length && window.CoursProgress) CoursProgress.saveScore(data.slug, ok, exos.length);
  }

  exos.forEach((x, i) => {
    const card = el("div", { className: "card exo-card" });
    const head = el("div", { className: "exo-head" });
    head.appendChild(el("b", { text: "Exercice " + (i + 1) }));
    if (x.niveau) head.appendChild(el("span", { className: "exo-niveau " + x.niveau, text: NIVEAU_EXO[x.niveau] || x.niveau }));
    card.appendChild(head);
    // Une sous-question par ligne : « … 1) … 2) … » -> retours a la ligne.
    card.appendChild(el("p", { className: "exo-enonce", text: String(x.enonce).replace(/\s(?=\d\)\s)/g, "\n") }));

    const actions = el("div", { className: "exo-actions" });
    if (x.indice) {
      const hintBtn = el("button", { className: "exo-btn", text: "💡 Indice" });
      const hint = el("p", { className: "exo-indice", text: x.indice });
      hint.hidden = true;
      hintBtn.addEventListener("click", () => { hint.hidden = !hint.hidden; });
      actions.appendChild(hintBtn);
      card.appendChild(actions);
      card.appendChild(hint);
    } else {
      card.appendChild(actions);
    }
    const corrBtn = el("button", { className: "exo-btn primary", text: "📖 Voir le corrigé" });
    actions.appendChild(corrBtn);
    const corr = el("div", { className: "exo-corrige" });
    corr.hidden = true;
    const steps = Array.isArray(x.corrige) ? x.corrige : [x.corrige || ""];
    appendExampleSteps(corr, steps);
    const self = el("div", { className: "exo-self" });
    self.appendChild(el("span", { text: "As-tu trouvé ?" }));
    const yes = el("button", { className: "exo-btn ok", text: "✓ Oui" });
    const no = el("button", { className: "exo-btn ko", text: "✗ Pas encore" });
    yes.addEventListener("click", () => { results[i] = true; yes.classList.add("chosen"); no.classList.remove("chosen"); refreshScore(); });
    no.addEventListener("click", () => { results[i] = false; no.classList.add("chosen"); yes.classList.remove("chosen"); refreshScore(); });
    self.appendChild(yes);
    self.appendChild(no);
    corr.appendChild(self);
    corrBtn.addEventListener("click", () => {
      corr.hidden = !corr.hidden;
      corrBtn.textContent = corr.hidden ? "📖 Voir le corrigé" : "Masquer le corrigé";
    });
    card.appendChild(corr);
    section.appendChild(card);
  });
  section.appendChild(score);
  return section;
}

/* --- Simulation : rapports de Thalès (geometry_ratio) --- */
function renderGeometryRatioSim() {
  const section = buildSlideShell("À toi de manipuler", "Fais glisser le point M et observe");
  const card = el("div", { className: "card" });
  card.innerHTML = `
    <svg class="scene" viewBox="0 0 320 220" xmlns="http://www.w3.org/2000/svg">
      <polygon points="160,20 40,190 280,190" fill="none" stroke="currentColor" stroke-width="2"/>
      <line id="sim-mn" x1="100" y1="105" x2="220" y2="105" stroke="#0d7a5f" stroke-width="3"/>
      <circle cx="160" cy="20" r="4" fill="currentColor"/>
      <circle cx="40" cy="190" r="4" fill="currentColor"/>
      <circle cx="280" cy="190" r="4" fill="currentColor"/>
      <circle id="sim-m" cx="100" cy="105" r="5" fill="#0d7a5f"/>
      <circle id="sim-n" cx="220" cy="105" r="5" fill="#0d7a5f"/>
      <text x="160" y="12" font-size="13" text-anchor="middle" font-weight="700">A</text>
      <text x="26" y="198" font-size="13" font-weight="700">B</text>
      <text x="288" y="198" font-size="13" font-weight="700">C</text>
    </svg>
    <div class="sim-controls">
      <label>Position de M sur [AB] <input type="range" id="sim-slider" min="5" max="95" value="50"></label>
    </div>
    <div class="sim-controls">
      <label><input type="checkbox" id="sim-parallel" checked> (MN) parallèle à (BC)</label>
    </div>
    <div class="sim-values" id="sim-values"></div>
    <div class="sim-verdict" id="sim-verdict"></div>
  `;
  section.appendChild(card);
  section.appendChild(el("p", {
    className: "muted",
    text: "Décoche la case pour casser le parallélisme : les rapports cessent d'être égaux."
  }));

  section._wire = function () {
    const A = { x: 160, y: 20 }, B = { x: 40, y: 190 }, C = { x: 280, y: 190 };
    const slider = section.querySelector("#sim-slider");
    const parallelBox = section.querySelector("#sim-parallel");
    const mDot = section.querySelector("#sim-m");
    const nDot = section.querySelector("#sim-n");
    const mnLine = section.querySelector("#sim-mn");
    const valuesBox = section.querySelector("#sim-values");
    const verdictBox = section.querySelector("#sim-verdict");
    let frozenN = null;

    function lerp(P, Q, t) { return { x: P.x + (Q.x - P.x) * t, y: P.y + (Q.y - P.y) * t }; }
    function dist(P, Q) { return Math.hypot(Q.x - P.x, Q.y - P.y); }

    function update() {
      const t = slider.value / 100;
      const M = lerp(A, B, t);
      let N;
      if (parallelBox.checked) { N = lerp(A, C, t); frozenN = null; }
      else { if (!frozenN) frozenN = lerp(A, C, 0.75); N = frozenN; }

      mDot.setAttribute("cx", M.x); mDot.setAttribute("cy", M.y);
      nDot.setAttribute("cx", N.x); nDot.setAttribute("cy", N.y);
      mnLine.setAttribute("x1", M.x); mnLine.setAttribute("y1", M.y);
      mnLine.setAttribute("x2", N.x); mnLine.setAttribute("y2", N.y);

      const rAM = dist(A, M) / dist(A, B), rAN = dist(A, N) / dist(A, C), rMN = dist(M, N) / dist(B, C);
      const same = Math.abs(rAM - rAN) < 0.01 && Math.abs(rAM - rMN) < 0.01;
      valuesBox.innerHTML = `
        <span class="chip ${same ? 'ok' : 'warn'}">AM/AB = ${rAM.toFixed(2)}</span>
        <span class="chip ${same ? 'ok' : 'warn'}">AN/AC = ${rAN.toFixed(2)}</span>
        <span class="chip ${same ? 'ok' : 'warn'}">MN/BC = ${rMN.toFixed(2)}</span>`;
      verdictBox.textContent = same
        ? "✅ Les trois rapports sont égaux : Thalès s'applique."
        : "❌ (MN) n'est pas parallèle à (BC) → les rapports ne sont plus égaux.";
      verdictBox.className = "sim-verdict " + (same ? "ok" : "ko");
    }
    slider.addEventListener("input", update);
    parallelBox.addEventListener("change", update);
    update();
  };
  return section;
}

/* --- Simulation : équilibre de deux forces (physics_vector) --- */
function renderPhysicsVectorSim() {
  const section = buildSlideShell("À toi de manipuler", "Règle F2 pour équilibrer le solide");
  const card = el("div", { className: "card" });
  card.innerHTML = `
    <svg class="scene" viewBox="0 0 320 220" xmlns="http://www.w3.org/2000/svg">
      <circle cx="160" cy="110" r="9" fill="currentColor"/>
      <line id="f1-line" x1="160" y1="110" x2="160" y2="170" stroke="#8a3ffc" stroke-width="3" marker-end="url(#mkP2)"/>
      <line id="f2-line" x1="160" y1="110" x2="160" y2="50" stroke="#0d7a5f" stroke-width="3" marker-end="url(#mkG2)"/>
      <line id="result-line" x1="160" y1="110" x2="160" y2="110" stroke="#b3261e" stroke-width="3" marker-end="url(#mkR2)" opacity="0"/>
      <text x="140" y="30" font-size="12" fill="#6b7570" text-anchor="middle">résultante en rouge si non nulle</text>
      <defs>
        <marker id="mkP2" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#8a3ffc"/></marker>
        <marker id="mkG2" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#0d7a5f"/></marker>
        <marker id="mkR2" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#b3261e"/></marker>
      </defs>
    </svg>
    <p class="muted">F1 (violet) = poids du solide, fixe, 6 N vers le bas.</p>
    <div class="sim-controls">
      <label>Intensité de F2 (N) <input type="range" id="mag-slider" min="0" max="120" value="60"></label>
    </div>
    <div class="sim-controls">
      <label>Direction de F2 (°) <input type="range" id="angle-slider" min="0" max="360" value="270"></label>
    </div>
    <div class="sim-values" id="sim-values"></div>
    <div class="sim-verdict" id="sim-verdict"></div>
  `;
  section.appendChild(card);
  section.appendChild(el("p", {
    className: "muted",
    text: "Pour équilibrer le solide : même intensité que F1, direction opposée (270°)."
  }));

  section._wire = function () {
    const O = { x: 160, y: 110 }, F1_MAG = 60, F1_ANGLE = 90;
    const magSlider = section.querySelector("#mag-slider");
    const angleSlider = section.querySelector("#angle-slider");
    const f1Line = section.querySelector("#f1-line");
    const f2Line = section.querySelector("#f2-line");
    const resultLine = section.querySelector("#result-line");
    const valuesBox = section.querySelector("#sim-values");
    const verdictBox = section.querySelector("#sim-verdict");

    function vecEnd(origin, mag, angleDeg) {
      const rad = angleDeg * Math.PI / 180;
      return { x: origin.x + mag * Math.cos(rad), y: origin.y + mag * Math.sin(rad) };
    }
    function update() {
      const mag2px = Number(magSlider.value), angle2 = Number(angleSlider.value);
      const f1End = vecEnd(O, F1_MAG, F1_ANGLE);
      f1Line.setAttribute("x2", f1End.x); f1Line.setAttribute("y2", f1End.y);
      const f2End = vecEnd(O, mag2px, angle2);
      f2Line.setAttribute("x2", f2End.x); f2Line.setAttribute("y2", f2End.y);

      const f1x = F1_MAG * Math.cos(F1_ANGLE * Math.PI / 180), f1y = F1_MAG * Math.sin(F1_ANGLE * Math.PI / 180);
      const f2x = mag2px * Math.cos(angle2 * Math.PI / 180), f2y = mag2px * Math.sin(angle2 * Math.PI / 180);
      const rx = f1x + f2x, ry = f1y + f2y, rMag = Math.hypot(rx, ry);

      if (rMag > 3) { resultLine.setAttribute("opacity", "1"); resultLine.setAttribute("x2", O.x + rx); resultLine.setAttribute("y2", O.y + ry); }
      else resultLine.setAttribute("opacity", "0");

      const equilibrium = rMag < 3;
      valuesBox.innerHTML = `
        <span class="chip">F1 = ${(F1_MAG / 10).toFixed(1)} N</span>
        <span class="chip ${equilibrium ? 'ok' : 'warn'}">F2 = ${(mag2px / 10).toFixed(1)} N</span>
        <span class="chip ${equilibrium ? 'ok' : 'warn'}">Résultante = ${(rMag / 10).toFixed(1)} N</span>`;
      verdictBox.textContent = equilibrium
        ? "✅ Solide en équilibre : F1 et F2 sont alignées, opposées et de même intensité."
        : "❌ Pas en équilibre : le solide accélère dans le sens de la résultante (en rouge).";
      verdictBox.className = "sim-verdict " + (equilibrium ? "ok" : "ko");
    }
    magSlider.addEventListener("input", update);
    angleSlider.addEventListener("input", update);
    update();
  };
  return section;
}

/* --- Simulation : fonction affine (function_affine) --- */
function renderFunctionAffineSim() {
  const section = buildSlideShell("À toi de manipuler", "Fais varier a et b et observe la droite");
  const card = el("div", { className: "card" });
  card.innerHTML = `
    <svg class="scene" viewBox="0 0 320 220" xmlns="http://www.w3.org/2000/svg">
      <g stroke="#e1e6e3" stroke-width="1">
        <line x1="40" y1="20" x2="40" y2="212"/>
        <line x1="40" y1="180" x2="300" y2="180"/>
      </g>
      <line id="fn-line" x1="40" y1="180" x2="300" y2="180" stroke="#0d7a5f" stroke-width="3"/>
      <circle id="fn-origin" cx="40" cy="180" r="5" fill="#8a3ffc"/>
      <text x="46" y="14" font-size="11" fill="#6b7570">y</text>
      <text x="304" y="184" font-size="11" fill="#6b7570">x</text>
    </svg>
    <div class="sim-controls">
      <label>a — coefficient directeur <input type="range" id="a-slider" min="-3" max="3" step="0.5" value="1"></label>
    </div>
    <div class="sim-controls">
      <label>b — ordonnée à l'origine <input type="range" id="b-slider" min="-2" max="8" step="1" value="2"></label>
    </div>
    <div class="sim-values" id="sim-values"></div>
    <div class="sim-verdict" id="sim-verdict"></div>
  `;
  section.appendChild(card);
  section.appendChild(el("p", {
    className: "muted",
    text: "Le point violet est (0, b). Regarde la droite pivoter autour de lui quand tu changes a."
  }));

  section._wire = function () {
    const X0_PX = 40, X_SCALE = 32.5, Y0_PX = 180, Y_SCALE = 16, X_MAX = 8;
    function xPx(x) { return X0_PX + x * X_SCALE; }
    function yPx(y) { return Y0_PX - y * Y_SCALE; }
    const aSlider = section.querySelector("#a-slider");
    const bSlider = section.querySelector("#b-slider");
    const fnLine = section.querySelector("#fn-line");
    const originDot = section.querySelector("#fn-origin");
    const valuesBox = section.querySelector("#sim-values");
    const verdictBox = section.querySelector("#sim-verdict");

    function update() {
      const a = Number(aSlider.value), b = Number(bSlider.value);
      const y0 = b, y1 = a * X_MAX + b;
      fnLine.setAttribute("x1", xPx(0)); fnLine.setAttribute("y1", yPx(y0));
      fnLine.setAttribute("x2", xPx(X_MAX)); fnLine.setAttribute("y2", yPx(y1));
      originDot.setAttribute("cx", xPx(0)); originDot.setAttribute("cy", yPx(b));

      const f1 = a * 1 + b;
      let sens = "constante";
      if (a > 0) sens = "croissante"; else if (a < 0) sens = "décroissante";
      valuesBox.innerHTML = `<span class="chip">a = ${a}</span><span class="chip">b = ${b}</span><span class="chip ok">f(1) = ${f1}</span>`;
      verdictBox.textContent = `f(x) = ${a}x + ${b} → fonction ${sens}`;
      verdictBox.className = "sim-verdict ok";
    }
    aSlider.addEventListener("input", update);
    bSlider.addEventListener("input", update);
    update();
  };
  return section;
}

function getCoursDeviceId() {
  const KEY = "aida_device_id";
  try {
    let id = localStorage.getItem(KEY);
    if (!id) {
      id = "dev-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem(KEY, id);
    }
    return id;
  } catch (e) {
    return "dev-" + Math.random().toString(36).slice(2);
  }
}

const QUIZ_MATH_DELIMITERS = [
  { left: "$$", right: "$$", display: true },
  { left: "\\[", right: "\\]", display: true },
  { left: "$", right: "$", display: false },
  { left: "\\(", right: "\\)", display: false },
];

function renderFullQuizQuestions(container, questions) {
  questions.forEach((q, qi) => {
    const qCard = el("div", { className: "card" });
    qCard.appendChild(el("p", { text: (qi + 1) + ". " + q.question }));
    let answered = false;
    (q.options || []).forEach((opt, oi) => {
      const optBtn = el("button", { className: "quiz-choice", text: opt });
      optBtn.addEventListener("click", () => {
        if (answered) return;
        answered = true;
        const correct = oi === q.correct_index;
        optBtn.classList.add(correct ? "correct" : "wrong");
        const fb = el("div", { className: "quiz-feedback", text: q.explication || "" });
        fb.classList.add(correct ? "ok" : "ko");
        qCard.appendChild(fb);
        if (window.renderMathInElement) renderMathInElement(fb, { delimiters: QUIZ_MATH_DELIMITERS, throwOnError: false });
      });
      qCard.appendChild(optBtn);
    });
    container.appendChild(qCard);
  });
  if (window.renderMathInElement) renderMathInElement(container, { delimiters: QUIZ_MATH_DELIMITERS, throwOnError: false });
}

function renderFullQuizSlide(lesson) {
  const section = buildSlideShell("Quiz complet", "Vérifie à fond ta compréhension");
  section.appendChild(el("p", {
    className: "muted",
    text: "10 questions pour vérifier que tu maîtrises bien ce chapitre.",
  }));
  const container = el("div");
  const btn = el("button", { className: "nav-btn next", text: "Générer le quiz (10 questions)" });
  btn.style.width = "100%";
  container.appendChild(btn);
  section.appendChild(container);

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    btn.textContent = "Génération en cours…";
    try {
      const base = window.AIDA_API_BASE_URL || "";
      const sujet = [lesson.concept.explanation, lesson.example.problem].filter(Boolean).join("\n\n");
      const res = await fetch(`${base}/api/quiz`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_id: getCoursDeviceId(),
          pays: lesson.pays,
          niveau: lesson.niveau,
          matiere: lesson.matiere,
          sujet: sujet.slice(0, 4000),
          n_questions: 10,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || data.error || "Erreur de génération");
      container.innerHTML = "";
      renderFullQuizQuestions(container, data.questions || []);
    } catch (e) {
      container.innerHTML = "";
      container.appendChild(el("p", { className: "muted", text: "Erreur : " + e.message + " Réessaie dans quelques instants." }));
    }
  });

  return section;
}

const SIM_RENDERERS = {
  geometry_ratio: renderGeometryRatioSim,
  physics_vector: renderPhysicsVectorSim,
  function_affine: renderFunctionAffineSim,
};

const MATIERE_LABELS = {
  Mathematiques: "Mathématiques", Francais: "Français", "Physique-Chimie": "Physique-Chimie",
  SVT: "SVT", "Histoire-Geographie": "Histoire-Géographie", Anglais: "Anglais",
  Philosophie: "Philosophie", Economie: "Économie", Allemand: "Allemand", Espagnol: "Espagnol",
};
const EXAMEN_LABELS = { Baccalaureat: "BAC" };

function lessonHref(meta) {
  let href = "cours.html?slug=" + encodeURIComponent(meta.slug);
  if (meta.fallback_for) href += "&fallback_for=" + encodeURIComponent(meta.fallback_for);
  return href;
}

/* Derniere diapositive : felicitations, chapitre marque comme termine,
   lien direct vers le chapitre suivant du programme (meme serie). */
function renderBilanSlide(lesson) {
  const section = buildSlideShell("Bilan", "Chapitre terminé 🎉");
  section.appendChild(el("p", {
    text: "Bravo ! Ce chapitre est marqué comme terminé dans ta progression. " +
      "Pour bien le retenir, relis la fiche « À retenir » demain, puis refais un exercice sans regarder le corrigé.",
  }));
  const next = el("div", { className: "bilan-next" });
  section.appendChild(next);
  section._setNext = function (meta) {
    next.innerHTML = "";
    if (!meta) return;
    const a = el("a", { className: "nav-btn next bilan-link", text: "Chapitre suivant : " + (meta.title || meta.chapitre) + " →" });
    a.href = lessonHref(meta);
    next.appendChild(a);
  };
  return section;
}

/* Chapitre suivant dans la liste du programme (meme pays/niveau/matiere/serie). */
function findNextLesson(lesson, siblings) {
  if (!Array.isArray(siblings) || !siblings.length) return null;
  const same = siblings.filter((m) => (m.serie || null) === (lesson.serie || null));
  const i = same.findIndex((m) => m.slug === lesson.slug);
  return i >= 0 && i < same.length - 1 ? same[i + 1] : null;
}

function renderLesson(lesson, rootIds, ctx) {
  const displayPays = PAYS_LABELS[lesson.fallback_for || lesson.pays] || (lesson.fallback_for || lesson.pays).replace("_", " ");
  const matiere = MATIERE_LABELS[lesson.matiere] || lesson.matiere.replace("-", " ");
  const examen = EXAMEN_LABELS[lesson.examen] || lesson.examen;
  document.getElementById(rootIds.eyebrow).textContent =
    `${matiere} · ${examen}${lesson.serie ? " · série " + lesson.serie : ""} · ${displayPays}`;
  document.getElementById(rootIds.name).textContent = lesson.title || lesson.chapitre;
  document.title = (lesson.title || lesson.chapitre) + " · Cours";

  const body = document.getElementById(rootIds.body);
  body.innerHTML = "";

  const slides = [renderIntroSlide(lesson), renderConceptSlide(lesson)];
  const simRenderer = SIM_RENDERERS[lesson.template];
  if (simRenderer) slides.push(simRenderer());
  slides.push(renderExampleSlide(lesson), renderQuizSlide(lesson));
  // Complements pedagogiques : seulement s'ils existent pour cette lecon.
  const retenir = renderRetenirSlide(lesson);
  if (retenir) slides.push(retenir);
  const exos = renderExercicesSlide(lesson);
  if (exos) slides.push(exos);
  slides.push(renderFullQuizSlide(lesson));
  const bilan = renderBilanSlide(lesson);
  slides.push(bilan);

  slides.forEach((s, i) => {
    s.setAttribute("data-slide", i);
    body.appendChild(s);
  });

  if (window.CoursProgress) CoursProgress.markOpened(lesson.slug);
  bilan._setNext(findNextLesson(lesson, ctx && ctx.siblings));

  initCoursEngine(slides.length, {
    onSlide(i) {
      if (i === slides.length - 1 && window.CoursProgress) CoursProgress.markDone(lesson.slug);
    },
  });
  slides.forEach(s => { if (s._wire) s._wire(); });
  // La liste du programme arrive parfois apres la lecon (reseau lent) :
  // cours.html complete alors le lien « chapitre suivant » apres coup.
  return { setSiblings(list) { bilan._setNext(findNextLesson(lesson, list)); } };
}
