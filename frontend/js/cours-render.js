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

function renderIntroSlide(data) {
  const section = buildSlideShell("Mise en situation", data.intro.heading);
  const card = el("div", { className: "card" });
  card.appendChild(el("p", { text: data.intro.body }));
  section.appendChild(card);
  return section;
}

const PAYS_LABELS = {
  cote_ivoire: "Côte d'Ivoire", mali: "Mali", senegal: "Sénégal",
  burkina_faso: "Burkina Faso", benin: "Bénin", guinee: "Guinée",
};

function renderConceptSlide(data) {
  const section = buildSlideShell("Le concept", data.concept.heading);
  section.appendChild(el("p", { text: data.concept.explanation }));
  if (data.concept.highlight) {
    const box = el("div", { className: "theorem-box" });
    box.appendChild(el("b", { text: data.concept.highlight }));
    section.appendChild(box);
  }
  if (data.fallback_for) {
    const note = el("div", { className: "theorem-box" });
    note.style.background = "#fff4e0";
    note.style.borderLeftColor = "#ffb347";
    note.textContent =
      "🌍 Programme non confirmé pour " + (PAYS_LABELS[data.fallback_for] || data.fallback_for) +
      " — ce cours suit le programme confirmé de " + (PAYS_LABELS[data.pays] || data.pays) +
      ", pris comme référence régionale (tronc commun francophone).";
    section.appendChild(note);
  }
  const src = el("span", { className: "badge-source", text: "Source du programme : " + data.source });
  section.appendChild(src);
  return section;
}

function renderExampleSlide(data) {
  const section = buildSlideShell("Exemple résolu", "Applique ce que tu viens de voir");
  section.appendChild(el("p", { text: data.example.problem }));
  const card = el("div", { className: "card" });
  data.example.steps.forEach((txt, i) => {
    const row = el("div", { className: "example-step" });
    row.style.animationDelay = (i * 0.2) + "s";
    row.appendChild(el("div", { className: "num", text: String(i + 1) }));
    row.appendChild(el("div", { text: txt }));
    card.appendChild(row);
  });
  section.appendChild(card);
  return section;
}

function renderQuizSlide(data) {
  const section = buildSlideShell("Question flash", "Vérifie que tu as compris");
  section.appendChild(el("p", { text: data.quiz.question }));
  const choicesBox = el("div");
  const feedback = el("div", { className: "quiz-feedback" });
  let answered = false;
  data.quiz.choices.forEach(c => {
    const btn = el("button", { className: "quiz-choice", text: c.label });
    btn.addEventListener("click", () => {
      if (answered) return;
      answered = true;
      btn.classList.add(c.correct ? "correct" : "wrong");
      feedback.style.color = c.correct ? "#1a7a3a" : "#b3261e";
      feedback.textContent = c.correct ? data.quiz.feedback_correct : data.quiz.feedback_wrong;
    });
    choicesBox.appendChild(btn);
  });
  section.appendChild(choicesBox);
  section.appendChild(feedback);
  return section;
}

/* --- Simulation : rapports de Thalès (geometry_ratio) --- */
function renderGeometryRatioSim() {
  const section = buildSlideShell("À toi de manipuler", "Fais glisser le point M et observe");
  const card = el("div", { className: "card" });
  card.innerHTML = `
    <svg class="scene" viewBox="0 0 320 220" xmlns="http://www.w3.org/2000/svg">
      <polygon points="160,20 40,190 280,190" fill="none" stroke="#1c2321" stroke-width="2"/>
      <line id="sim-mn" x1="100" y1="105" x2="220" y2="105" stroke="#0d7a5f" stroke-width="3"/>
      <circle cx="160" cy="20" r="4" fill="#1c2321"/>
      <circle cx="40" cy="190" r="4" fill="#1c2321"/>
      <circle cx="280" cy="190" r="4" fill="#1c2321"/>
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
      verdictBox.style.color = same ? "#1a7a3a" : "#b3261e";
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
      <circle cx="160" cy="110" r="9" fill="#1c2321"/>
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
      verdictBox.style.color = equilibrium ? "#1a7a3a" : "#b3261e";
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
      verdictBox.style.color = "#1a7a3a";
    }
    aSlider.addEventListener("input", update);
    bSlider.addEventListener("input", update);
    update();
  };
  return section;
}

const SIM_RENDERERS = {
  geometry_ratio: renderGeometryRatioSim,
  physics_vector: renderPhysicsVectorSim,
  function_affine: renderFunctionAffineSim,
};

function renderLesson(lesson, rootIds) {
  const displayPays = (lesson.fallback_for || lesson.pays).replace("_", " ");
  document.getElementById(rootIds.eyebrow).textContent =
    `${lesson.matiere.replace("-", " ")} · ${lesson.examen}${lesson.serie ? " · série " + lesson.serie : ""} · ${displayPays}`;
  document.getElementById(rootIds.name).textContent = lesson.title || lesson.chapitre;

  const body = document.getElementById(rootIds.body);
  body.innerHTML = "";

  const slides = [renderIntroSlide(lesson), renderConceptSlide(lesson)];
  const simRenderer = SIM_RENDERERS[lesson.template];
  if (simRenderer) slides.push(simRenderer());
  slides.push(renderExampleSlide(lesson), renderQuizSlide(lesson));

  slides.forEach((s, i) => {
    s.setAttribute("data-slide", i);
    body.appendChild(s);
  });

  initCoursEngine(slides.length);
  slides.forEach(s => { if (s._wire) s._wire(); });
}
