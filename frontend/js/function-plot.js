/* Traceur de courbes pour le chat - detecte les blocs ```plot dans les
   reponses de Le Prof JPA et les remplace par un graphique SVG, au lieu
   de renvoyer l'eleve vers un outil externe (GeoGebra/Desmos). Aucune
   dependance : petit evaluateur d'expression maison (pas d'eval()). */

function compilePlotExpression(expr) {
  const src = expr.replace(/\s+/g, "");
  const tokens = [];
  let i = 0;
  const isDigit = (c) => c >= "0" && c <= "9";
  const isAlpha = (c) => /[a-zA-Z]/.test(c);

  while (i < src.length) {
    const c = src[i];
    if (isDigit(c) || c === ".") {
      let j = i;
      while (j < src.length && (isDigit(src[j]) || src[j] === ".")) j++;
      tokens.push({ type: "num", value: parseFloat(src.slice(i, j)) });
      i = j;
    } else if (isAlpha(c)) {
      let j = i;
      while (j < src.length && isAlpha(src[j])) j++;
      tokens.push({ type: "ident", value: src.slice(i, j) });
      i = j;
    } else if ("+-*/^(),".includes(c)) {
      tokens.push({ type: c });
      i++;
    } else {
      throw new Error("Caractère invalide dans l'expression: " + c);
    }
  }

  let pos = 0;
  const peekTok = () => tokens[pos];
  const next = () => tokens[pos++];

  const FUNCS = {
    sin: Math.sin, cos: Math.cos, tan: Math.tan,
    sqrt: Math.sqrt, abs: Math.abs, exp: Math.exp,
    ln: Math.log, log: Math.log10,
  };

  function parseExpr() { return parseAddSub(); }

  function parseAddSub() {
    let node = parseMulDiv();
    while (peekTok() && (peekTok().type === "+" || peekTok().type === "-")) {
      const op = next().type;
      const right = parseMulDiv();
      const left = node;
      node = op === "+" ? (x) => left(x) + right(x) : (x) => left(x) - right(x);
    }
    return node;
  }

  function parseMulDiv() {
    let node = parseUnary();
    while (peekTok() && (peekTok().type === "*" || peekTok().type === "/")) {
      const op = next().type;
      const right = parseUnary();
      const left = node;
      node = op === "*" ? (x) => left(x) * right(x) : (x) => left(x) / right(x);
    }
    return node;
  }

  function parseUnary() {
    if (peekTok() && peekTok().type === "-") { next(); const n = parseUnary(); return (x) => -n(x); }
    if (peekTok() && peekTok().type === "+") { next(); return parseUnary(); }
    return parsePow();
  }

  function parsePow() {
    const base = parseAtom();
    if (peekTok() && peekTok().type === "^") {
      next();
      const exp = parseUnary();
      return (x) => Math.pow(base(x), exp(x));
    }
    return base;
  }

  function parseAtom() {
    const t = peekTok();
    if (!t) throw new Error("Expression incomplète");
    if (t.type === "num") { next(); return () => t.value; }
    if (t.type === "(") {
      next();
      const node = parseExpr();
      if (!peekTok() || peekTok().type !== ")") throw new Error("Parenthèse manquante");
      next();
      return node;
    }
    if (t.type === "ident") {
      next();
      if (t.value === "x") return (x) => x;
      if (t.value === "pi") return () => Math.PI;
      if (t.value === "e") return () => Math.E;
      if (FUNCS[t.value]) {
        if (!peekTok() || peekTok().type !== "(") throw new Error("Parenthèse attendue après " + t.value);
        next();
        const arg = parseExpr();
        if (!peekTok() || peekTok().type !== ")") throw new Error("Parenthèse manquante");
        next();
        const fn = FUNCS[t.value];
        return (x) => fn(arg(x));
      }
      throw new Error("Fonction/variable inconnue: " + t.value);
    }
    throw new Error("Expression mal formée");
  }

  const fn = parseExpr();
  if (pos !== tokens.length) throw new Error("Expression mal formée");
  return fn;
}

function percentile(sortedArr, p) {
  const idx = (sortedArr.length - 1) * p;
  const lo = Math.floor(idx), hi = Math.ceil(idx);
  if (lo === hi) return sortedArr[lo];
  return sortedArr[lo] + (sortedArr[hi] - sortedArr[lo]) * (idx - lo);
}

/* Parse le texte d'un bloc ```plot : une ligne "f(x) = ..." (ou "y = ...")
   et une ligne optionnelle "domaine: [min, max]". */
function parsePlotSpec(text) {
  const exprMatch = text.match(/(?:f\(x\)|y)\s*=\s*(.+)/i);
  if (!exprMatch) return null;
  const expr = exprMatch[1].trim();

  let domain = [-5, 5];
  const domainMatch = text.match(/domaine\s*:\s*\[\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\]/i);
  if (domainMatch) {
    domain = [parseFloat(domainMatch[1]), parseFloat(domainMatch[2])];
  }
  return { expr, domain };
}

function buildPlotSvg(expr, domain) {
  const fn = compilePlotExpression(expr);
  const [xmin, xmax] = domain;
  const N = 240;
  const points = [];
  for (let i = 0; i <= N; i++) {
    const x = xmin + ((xmax - xmin) * i) / N;
    let y;
    try { y = fn(x); } catch (e) { y = NaN; }
    if (typeof y !== "number" || !isFinite(y)) y = NaN;
    points.push([x, y]);
  }

  const finiteYs = points.map((p) => p[1]).filter((y) => !isNaN(y)).sort((a, b) => a - b);
  if (!finiteYs.length) throw new Error("Fonction non definie sur cet intervalle");

  let ymin = percentile(finiteYs, 0.02);
  let ymax = percentile(finiteYs, 0.98);
  if (ymin === ymax) { ymin -= 1; ymax += 1; }
  const pad = (ymax - ymin) * 0.1;
  ymin -= pad;
  ymax += pad;

  const W = 320, H = 220, M = 28;
  const xPx = (x) => M + ((x - xmin) / (xmax - xmin)) * (W - 2 * M);
  const yPx = (y) => H - M - ((y - ymin) / (ymax - ymin)) * (H - 2 * M);
  const bigJump = (H - 2 * M) * 0.65;

  let d = "";
  let drawing = false;
  let prevPy = null;
  points.forEach(([x, y]) => {
    if (isNaN(y) || y < ymin - (ymax - ymin) || y > ymax + (ymax - ymin)) {
      drawing = false;
      prevPy = null;
      return;
    }
    const px = xPx(x), py = yPx(y);
    if (drawing && prevPy !== null && Math.abs(py - prevPy) > bigJump) {
      drawing = false;
    }
    d += (drawing ? " L " : " M ") + px.toFixed(1) + " " + py.toFixed(1);
    drawing = true;
    prevPy = py;
  });

  const axesSvg = [];
  if (0 >= ymin && 0 <= ymax) {
    axesSvg.push(`<line x1="${M}" y1="${yPx(0).toFixed(1)}" x2="${W - M}" y2="${yPx(0).toFixed(1)}" stroke="#c9d2cd" stroke-width="1"/>`);
  }
  if (0 >= xmin && 0 <= xmax) {
    axesSvg.push(`<line x1="${xPx(0).toFixed(1)}" y1="${M}" x2="${xPx(0).toFixed(1)}" y2="${H - M}" stroke="#c9d2cd" stroke-width="1"/>`);
  }

  return (
    `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;background:#fff;border:1px solid #e1e6e3;border-radius:10px;">` +
    axesSvg.join("") +
    `<path d="${d.trim()}" fill="none" stroke="#0d7a5f" stroke-width="2.5"/>` +
    `<text x="${W - M + 4}" y="${(0 >= ymin && 0 <= ymax ? yPx(0) : H - M) - 4}" font-size="11" fill="#6b7570">x</text>` +
    `<text x="${(0 >= xmin && 0 <= xmax ? xPx(0) : M) + 4}" y="${M - 6}" font-size="11" fill="#6b7570">y</text>` +
    `</svg>`
  );
}

/* Cherche les blocs de code ```plot deja rendus en <pre><code class="language-plot">
   par marked a l'interieur de container, et les remplace par le graphique. */
function renderPlotBlocks(container) {
  container.querySelectorAll("code.language-plot").forEach((codeEl) => {
    const pre = codeEl.closest("pre") || codeEl;
    const spec = parsePlotSpec(codeEl.textContent || "");
    const wrapper = document.createElement("div");
    wrapper.className = "plot-block";
    try {
      if (!spec) throw new Error("Format de bloc plot invalide");
      wrapper.innerHTML = buildPlotSvg(spec.expr, spec.domain);
    } catch (e) {
      // Si la fonction generee par l'IA est mal formee, on efface juste le
      // bloc technique plutot que d'afficher du code brut ou une erreur a
      // l'eleve - l'explication textuelle autour reste intacte.
      wrapper.remove();
      pre.remove();
      return;
    }
    pre.replaceWith(wrapper);
  });
}
