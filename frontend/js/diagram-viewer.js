/* Bibliotheque de schemas annotes (SVT/sciences) - detecte les blocs
   ```diagram dans les reponses de Le Prof JPA et les remplace par un schema
   dessine a l'avance (pas de generation d'image a la volee : un schema
   anatomique ne se "calcule" pas comme une courbe, et sa justesse compte
   trop pour etre improvisee). L'IA ne fait que CHOISIR un identifiant dans
   une liste connue - jamais en inventer un nouveau. */

function labelLine(x1, y1, x2, y2) {
  return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#6b7570" stroke-width="1"/>`;
}
function labelText(x, y, text, anchor) {
  return `<text x="${x}" y="${y}" font-size="11" fill="#1c2321" text-anchor="${anchor || 'start'}">${text}</text>`;
}

const DIAGRAM_LIBRARY = {
  appareil_reproducteur_feminin: {
    title: "Appareil reproducteur féminin (schéma simplifié, vue de face)",
    svg: `
      <svg viewBox="0 0 320 300" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;background:#fff;border:1px solid #e1e6e3;border-radius:10px;">
        <ellipse cx="95" cy="95" rx="20" ry="14" fill="#f3c9d6" stroke="#c98aa3" stroke-width="1.5"/>
        <ellipse cx="225" cy="95" rx="20" ry="14" fill="#f3c9d6" stroke="#c98aa3" stroke-width="1.5"/>
        <path d="M 105 92 Q 140 70 155 105" fill="none" stroke="#e0a8bb" stroke-width="6" stroke-linecap="round"/>
        <path d="M 215 92 Q 180 70 165 105" fill="none" stroke="#e0a8bb" stroke-width="6" stroke-linecap="round"/>
        <path d="M 130 100 Q 160 90 190 100 L 185 175 Q 160 195 135 175 Z" fill="#f7d7c4" stroke="#d9a479" stroke-width="1.5"/>
        <rect x="148" y="175" width="24" height="35" fill="#f0c39e" stroke="#d9a479" stroke-width="1.5"/>
        <path d="M 148 210 L 172 210 L 178 265 L 142 265 Z" fill="#f3ddc9" stroke="#d9a479" stroke-width="1.5"/>
        ${labelLine(95, 81, 60, 60)}${labelText(58, 56, "Ovaire", "end")}
        ${labelLine(140, 85, 100, 45)}${labelText(98, 41, "Trompe de Fallope", "end")}
        ${labelLine(160, 130, 245, 130)}${labelText(248, 133, "Utérus", "start")}
        ${labelLine(160, 190, 245, 200)}${labelText(248, 203, "Col de l'utérus", "start")}
        ${labelLine(160, 235, 245, 250)}${labelText(248, 253, "Vagin", "start")}
      </svg>`,
  },

  appareil_reproducteur_masculin: {
    title: "Appareil reproducteur masculin (schéma simplifié, vue de profil)",
    svg: `
      <svg viewBox="0 0 320 260" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;background:#fff;border:1px solid #e1e6e3;border-radius:10px;">
        <path d="M 60 60 Q 100 40 150 55 L 155 90 Q 100 100 60 85 Z" fill="#f7d7c4" stroke="#d9a479" stroke-width="1.5"/>
        <path d="M 150 62 Q 200 55 230 75" fill="none" stroke="#e0a8bb" stroke-width="4" stroke-linecap="round"/>
        <ellipse cx="245" cy="80" rx="20" ry="14" fill="#f0c39e" stroke="#d9a479" stroke-width="1.5" transform="rotate(20 245 80)"/>
        <path d="M 235 90 Q 220 130 200 150" fill="none" stroke="#d9a479" stroke-width="5" stroke-linecap="round"/>
        <ellipse cx="180" cy="170" rx="26" ry="34" fill="#f3ddc9" stroke="#d9a479" stroke-width="1.5"/>
        <path d="M 178 200 Q 172 220 168 240" fill="none" stroke="#d9a479" stroke-width="6" stroke-linecap="round"/>
        ${labelLine(100, 60, 90, 30)}${labelText(88, 26, "Vessie", "end")}
        ${labelLine(200, 78, 250, 55)}${labelText(253, 52, "Vésicule séminale", "start")}
        ${labelLine(245, 92, 270, 110)}${labelText(273, 113, "Prostate", "start")}
        ${labelLine(215, 130, 260, 140)}${labelText(263, 143, "Canal déférent", "start")}
        ${labelLine(200, 172, 250, 180)}${labelText(253, 183, "Testicule", "start")}
        ${labelLine(170, 220, 130, 235)}${labelText(128, 238, "Urètre / Pénis", "end")}
      </svg>`,
  },

  appareil_digestif: {
    title: "Appareil digestif (schéma simplifié)",
    svg: `
      <svg viewBox="0 0 320 320" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;background:#fff;border:1px solid #e1e6e3;border-radius:10px;">
        <ellipse cx="150" cy="25" rx="28" ry="12" fill="#f3ddc9" stroke="#d9a479" stroke-width="1.5"/>
        <rect x="142" y="35" width="16" height="55" fill="#f0c39e" stroke="#d9a479" stroke-width="1.5"/>
        <path d="M 140 90 Q 100 100 100 140 Q 100 175 150 175 Q 190 175 185 135 Q 182 100 158 90 Z" fill="#f7c8a3" stroke="#d9a479" stroke-width="1.5"/>
        <path d="M 175 100 Q 220 95 235 120 Q 240 140 210 145" fill="#f3ddc9" stroke="#d9a479" stroke-width="1.5"/>
        <ellipse cx="150" cy="150" rx="18" ry="10" fill="#e8b98f" stroke="#d9a479" stroke-width="1.5"/>
        <path d="M 150 175 Q 130 200 140 230 Q 150 260 180 250 Q 210 240 195 210 Q 185 190 150 175 Z" fill="#f0c39e" stroke="#d9a479" stroke-width="1.5"/>
        <path d="M 90 190 L 90 270 Q 90 290 130 290 L 220 290 Q 250 290 250 260 L 250 200" fill="none" stroke="#d9a479" stroke-width="10" stroke-linecap="round"/>
        ${labelLine(150, 20, 100, 15)}${labelText(98, 12, "Bouche", "end")}
        ${labelLine(150, 55, 100, 55)}${labelText(98, 58, "Œsophage", "end")}
        ${labelLine(115, 130, 70, 130)}${labelText(68, 133, "Estomac", "end")}
        ${labelLine(220, 110, 260, 100)}${labelText(263, 103, "Foie", "start")}
        ${labelLine(150, 152, 200, 155)}${labelText(203, 158, "Pancréas", "start")}
        ${labelLine(175, 215, 225, 220)}${labelText(228, 223, "Intestin grêle", "start")}
        ${labelLine(90, 250, 55, 250)}${labelText(53, 253, "Gros intestin (côlon)", "end")}
      </svg>`,
  },

  systeme_circulatoire_coeur: {
    title: "Le cœur et la circulation sanguine (schéma simplifié)",
    svg: `
      <svg viewBox="0 0 320 280" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;background:#fff;border:1px solid #e1e6e3;border-radius:10px;">
        <path d="M 160 60 Q 100 30 80 90 Q 70 140 160 220 Q 250 140 240 90 Q 220 30 160 60 Z" fill="#f3c9c9" stroke="#c96f6f" stroke-width="1.5"/>
        <line x1="160" y1="65" x2="160" y2="200" stroke="#c96f6f" stroke-width="2"/>
        <line x1="105" y1="85" x2="130" y2="150" stroke="#c96f6f" stroke-width="1.5"/>
        <line x1="215" y1="85" x2="190" y2="150" stroke="#c96f6f" stroke-width="1.5"/>
        <path d="M 130 60 L 130 20" fill="none" stroke="#7fa8d9" stroke-width="8" stroke-linecap="round"/>
        <path d="M 190 60 L 190 15" fill="none" stroke="#d97f7f" stroke-width="8" stroke-linecap="round"/>
        ${labelLine(120, 40, 70, 30)}${labelText(68, 27, "Veine cave (sang pauvre en O₂)", "end")}
        ${labelLine(195, 35, 250, 25)}${labelText(253, 22, "Aorte (sang riche en O₂)", "start")}
        ${labelLine(105, 100, 55, 110)}${labelText(53, 113, "Oreillette droite", "end")}
        ${labelLine(215, 100, 265, 110)}${labelText(268, 113, "Oreillette gauche", "start")}
        ${labelLine(120, 165, 60, 190)}${labelText(58, 193, "Ventricule droit", "end")}
        ${labelLine(200, 165, 260, 190)}${labelText(263, 193, "Ventricule gauche", "start")}
      </svg>`,
  },
  courbe_chauffage_eau: {
    title: "Courbe de chauffage et changement d'état de l'eau (température en fonction de l'énergie apportée)",
    svg: `
      <svg viewBox="0 0 380 320" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;background:#fff;border:1px solid #e1e6e3;border-radius:10px;">
        <line x1="45" y1="231" x2="355" y2="231" stroke="#c7d0cb" stroke-width="1" stroke-dasharray="4,3"/>
        <line x1="45" y1="88" x2="355" y2="88" stroke="#c7d0cb" stroke-width="1" stroke-dasharray="4,3"/>
        <line x1="45" y1="260" x2="365" y2="260" stroke="#1c2321" stroke-width="1.5"/>
        <polygon points="365,260 357,256 357,264" fill="#1c2321"/>
        <line x1="45" y1="260" x2="45" y2="20" stroke="#1c2321" stroke-width="1.5"/>
        <polygon points="45,20 41,28 49,28" fill="#1c2321"/>
        <line x1="110" y1="257" x2="110" y2="263" stroke="#1c2321" stroke-width="1"/>
        <line x1="170" y1="257" x2="170" y2="263" stroke="#1c2321" stroke-width="1"/>
        <line x1="230" y1="257" x2="230" y2="263" stroke="#1c2321" stroke-width="1"/>
        <line x1="290" y1="257" x2="290" y2="263" stroke="#1c2321" stroke-width="1"/>
        <path d="M 50 260 L 110 231 L 170 231 L 230 88 L 290 88 L 350 30" fill="none" stroke="#c9612f" stroke-width="2.5"/>
        <circle cx="50" cy="260" r="3" fill="#c9612f"/>
        <circle cx="110" cy="231" r="3" fill="#c9612f"/>
        <circle cx="170" cy="231" r="3" fill="#c9612f"/>
        <circle cx="230" cy="88" r="3" fill="#c9612f"/>
        <circle cx="290" cy="88" r="3" fill="#c9612f"/>
        <circle cx="350" cy="30" r="3" fill="#c9612f"/>
        ${labelText(10, 15, "T (°C)", "start")}
        ${labelText(40, 264, "-20", "end")}
        ${labelText(40, 235, "0", "end")}
        ${labelText(40, 92, "100", "end")}
        ${labelText(40, 26, "140", "end")}
        ${labelText(80, 275, "Glace", "middle")}
        ${labelText(140, 275, "Fusion", "middle")}
        ${labelText(200, 275, "Eau liquide", "middle")}
        ${labelText(260, 275, "Vaporisation", "middle")}
        ${labelText(320, 275, "Vapeur", "middle")}
        ${labelText(200, 300, "Énergie apportée (chauffage) →", "middle")}
      </svg>`,
  },
  appareil_urinaire_masculin: {
    title: "Appareil urinaire masculin (schéma simplifié, vue de face)",
    svg: `
      <svg viewBox="0 0 320 350" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;background:#fff;border:1px solid #e1e6e3;border-radius:10px;">
        <ellipse cx="105" cy="80" rx="18" ry="30" transform="rotate(-10 105 80)" fill="#e3b0a0" stroke="#b9776a" stroke-width="1.5"/>
        <ellipse cx="215" cy="80" rx="18" ry="30" transform="rotate(10 215 80)" fill="#e3b0a0" stroke="#b9776a" stroke-width="1.5"/>
        <path d="M 118 90 Q 135 145 152 205" fill="none" stroke="#d9a479" stroke-width="3.5" stroke-linecap="round"/>
        <path d="M 202 90 Q 185 145 168 205" fill="none" stroke="#d9a479" stroke-width="3.5" stroke-linecap="round"/>
        <path d="M 130 205 Q 160 188 190 205 Q 196 242 160 246 Q 124 242 130 205 Z" fill="#f3d9a8" stroke="#d9a479" stroke-width="1.5"/>
        <ellipse cx="160" cy="260" rx="17" ry="12" fill="#e8b98f" stroke="#d9a479" stroke-width="1.5"/>
        <rect x="148" y="270" width="24" height="62" rx="12" fill="#f7d7c4" stroke="#d9a479" stroke-width="1.5"/>
        <line x1="160" y1="246" x2="160" y2="326" stroke="#c98a5a" stroke-width="3" stroke-linecap="round"/>
        ${labelLine(95, 60, 55, 40)}${labelText(53, 36, "Rein", "end")}
        ${labelLine(139, 150, 95, 150)}${labelText(93, 153, "Uretère", "end")}
        ${labelLine(190, 222, 245, 222)}${labelText(248, 225, "Vessie", "start")}
        ${labelLine(177, 260, 245, 260)}${labelText(248, 263, "Prostate", "start")}
        ${labelLine(148, 300, 95, 300)}${labelText(93, 303, "Urètre", "end")}
        ${labelLine(222, 60, 262, 40)}${labelText(265, 36, "Rein", "start")}
      </svg>`,
  },

  appareil_urinaire_feminin: {
    title: "Appareil urinaire féminin (schéma simplifié, vue de face)",
    svg: `
      <svg viewBox="0 0 320 320" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;background:#fff;border:1px solid #e1e6e3;border-radius:10px;">
        <ellipse cx="105" cy="80" rx="18" ry="30" transform="rotate(-10 105 80)" fill="#e3b0a0" stroke="#b9776a" stroke-width="1.5"/>
        <ellipse cx="215" cy="80" rx="18" ry="30" transform="rotate(10 215 80)" fill="#e3b0a0" stroke="#b9776a" stroke-width="1.5"/>
        <path d="M 118 90 Q 135 145 152 205" fill="none" stroke="#d9a479" stroke-width="3.5" stroke-linecap="round"/>
        <path d="M 202 90 Q 185 145 168 205" fill="none" stroke="#d9a479" stroke-width="3.5" stroke-linecap="round"/>
        <path d="M 130 205 Q 160 188 190 205 Q 196 242 160 246 Q 124 242 130 205 Z" fill="#f3d9a8" stroke="#d9a479" stroke-width="1.5"/>
        <path d="M 160 246 L 160 282" fill="none" stroke="#c98a5a" stroke-width="5" stroke-linecap="round"/>
        <circle cx="160" cy="286" r="5" fill="#f3c9d6" stroke="#c98aa3" stroke-width="1.5"/>
        ${labelLine(95, 60, 55, 40)}${labelText(53, 36, "Rein", "end")}
        ${labelLine(139, 150, 95, 150)}${labelText(93, 153, "Uretère", "end")}
        ${labelLine(190, 222, 245, 222)}${labelText(248, 225, "Vessie", "start")}
        ${labelLine(162, 264, 245, 264)}${labelText(248, 267, "Urètre", "start")}
        ${labelLine(166, 288, 245, 292)}${labelText(248, 295, "Méat urinaire", "start")}
        ${labelLine(222, 60, 262, 40)}${labelText(265, 36, "Rein", "start")}
      </svg>`,
  },
};

/* ---------------------------------------------------------------------
   Schemas generes a la demande (bloc ```schema) - l'IA decrit seulement la
   STRUCTURE en texte (type, titre, elements) ; c'est ce code, fiable, qui
   dessine. Jamais de SVG ecrit par l'IA (pas de risque d'injection, rendu
   toujours propre). Quatre mises en page :
     flux       : etapes enchainees (processus, reactions, digestion...)
     cycle      : etapes en boucle (cycle de l'eau, du carbone, cardiaque...)
     hierarchie : une racine et ses branches (classification, organisation)
     parties    : un element central et ses parties legendees (schema de
                  principe d'un organe, d'une cellule, d'un appareil...)
   Ce sont des schemas SIMPLIFIES de principe, pas des dessins anatomiques
   exacts : la mention est affichee sous chaque schema.
   --------------------------------------------------------------------- */

const SCHEMA_NS = "http://www.w3.org/2000/svg";
const SCHEMA_MAX_ITEMS = 8;

function schemaEl(tag, attrs, text) {
  const e = document.createElementNS(SCHEMA_NS, tag);
  Object.keys(attrs || {}).forEach((k) => e.setAttribute(k, attrs[k]));
  if (text !== undefined) e.textContent = text;
  return e;
}

function schemaNormKey(s) {
  return s.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z]/g, "");
}

function parseSchemaSpec(text) {
  const spec = { type: "", titre: "", racine: "", centre: "", items: [] };
  let inList = false;
  text.split(/\r?\n/).forEach((raw) => {
    const line = raw.trim();
    if (!line) return;
    const bullet = line.match(/^[-*•]\s+(.*)$/);
    if (bullet && inList) {
      spec.items.push(bullet[1].trim());
      return;
    }
    const kv = line.match(/^([A-Za-zÀ-ÿ_]+)\s*:\s*(.*)$/);
    if (!kv) return;
    const key = schemaNormKey(kv[1]);
    const val = kv[2].trim();
    if (key === "type") spec.type = schemaNormKey(val);
    else if (key === "titre" || key === "title") spec.titre = val;
    else if (key === "racine") spec.racine = val;
    else if (key === "centre") spec.centre = val;
    else if (key === "etapes" || key === "branches" || key === "parties" || key === "elements") {
      inList = true;
      if (val) spec.items.push(val);
    }
  });
  spec.items = spec.items.slice(0, SCHEMA_MAX_ITEMS).map((it) => {
    const i = it.indexOf(":");
    const label = (i > 0 ? it.slice(0, i) : it).trim().slice(0, 40);
    const detail = i > 0 ? it.slice(i + 1).trim().slice(0, 90) : "";
    return { label, detail };
  }).filter((it) => it.label);
  if (!spec.type) spec.type = spec.racine ? "hierarchie" : spec.centre ? "parties" : "flux";
  return spec;
}

function schemaWrap(str, maxChars) {
  const words = str.split(/\s+/);
  const lines = [];
  let cur = "";
  words.forEach((w) => {
    if ((cur + " " + w).trim().length > maxChars && cur) {
      lines.push(cur);
      cur = w;
    } else {
      cur = (cur + " " + w).trim();
    }
  });
  if (cur) lines.push(cur);
  return lines;
}

function schemaMeasure(w, label, detail) {
  const labelLines = schemaWrap(label, Math.max(8, Math.floor(w / 7.4))).slice(0, 3);
  const detailLines = detail ? schemaWrap(detail, Math.max(10, Math.floor(w / 5.6))).slice(0, 3) : [];
  const h = 16 + labelLines.length * 16 + (detailLines.length ? 4 + detailLines.length * 13 : 0);
  return { h, labelLines, detailLines };
}

function schemaDrawBox(svg, x, y, w, m, fill, stroke) {
  svg.appendChild(schemaEl("rect", { x, y, width: w, height: m.h, rx: 12, fill, stroke, "stroke-width": 1.6 }));
  let ty = y + 12 + 8;
  m.labelLines.forEach((l) => {
    svg.appendChild(schemaEl("text", { x: x + w / 2, y: ty, "text-anchor": "middle", "font-size": 13, "font-weight": 700, fill: "#1c2321" }, l));
    ty += 16;
  });
  if (m.detailLines.length) {
    ty -= 2;
    m.detailLines.forEach((l) => {
      svg.appendChild(schemaEl("text", { x: x + w / 2, y: ty, "text-anchor": "middle", "font-size": 10.5, fill: "#4a5550" }, l));
      ty += 13;
    });
  }
}

// Fleche entre deux boites (rectangles centres), raccourcie a leurs bords.
function schemaArrow(svg, c1, s1, c2, s2, withHead) {
  const dx = c2.x - c1.x;
  const dy = c2.y - c1.y;
  const len = Math.hypot(dx, dy) || 1;
  const clip = (s) => Math.min(
    dx === 0 ? Infinity : (s.w / 2 + 3) / Math.abs(dx),
    dy === 0 ? Infinity : (s.h / 2 + 3) / Math.abs(dy)
  );
  const t1 = clip(s1);
  const t2 = clip(s2);
  if (t1 + t2 >= 0.98) return;
  const x1 = c1.x + dx * t1, y1 = c1.y + dy * t1;
  const x2 = c2.x - dx * t2, y2 = c2.y - dy * t2;
  svg.appendChild(schemaEl("line", { x1, y1, x2, y2, stroke: "#0d7a5f", "stroke-width": 2 }));
  if (withHead) {
    const ux = dx / len, uy = dy / len;
    const p = (a, b) => (x2 - ux * a - uy * b) + "," + (y2 - uy * a + ux * b);
    svg.appendChild(schemaEl("polygon", { points: [x2 + "," + y2, p(9, 5), p(9, -5)].join(" "), fill: "#0d7a5f" }));
  }
}

function buildSchemaSvg(spec) {
  const W = 340;
  const items = spec.items;
  const svg = schemaEl("svg", { viewBox: "0 0 " + W + " 100", xmlns: SCHEMA_NS });
  svg.style.cssText = "width:100%;height:auto;background:#fff;border:1px solid #e1e6e3;border-radius:10px;";
  const FILL = "#e6f4ef", STROKE = "#0d7a5f";
  let H = 100;

  if (spec.type === "cycle" && items.length >= 3 && items.length <= 6) {
    const n = items.length;
    const R = n <= 5 ? 108 : 118;
    const bw = 96;
    const cx = W / 2;
    const metrics = items.map((it) => schemaMeasure(bw, it.label, ""));
    const maxH = Math.max(...metrics.map((m) => m.h));
    const cy = R + maxH / 2 + 12;
    H = cy + R + maxH / 2 + 12;
    const centers = items.map((_, i) => {
      const a = -Math.PI / 2 + (i * 2 * Math.PI) / n;
      return { x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) };
    });
    items.forEach((_, i) => {
      const j = (i + 1) % n;
      schemaArrow(svg, centers[i], { w: bw, h: metrics[i].h }, centers[j], { w: bw, h: metrics[j].h }, true);
    });
    items.forEach((it, i) => {
      schemaDrawBox(svg, centers[i].x - bw / 2, centers[i].y - metrics[i].h / 2, bw, metrics[i], FILL, STROKE);
    });
  } else if (spec.type === "hierarchie" && spec.racine) {
    const rootW = 240;
    const rootM = schemaMeasure(rootW, spec.racine, "");
    let y = 10;
    schemaDrawBox(svg, (W - rootW) / 2, y, rootW, rootM, "#fff1de", "#d98f2b");
    const trunkX = 52;
    const bx = 70, bw = W - bx - 10;
    let cy = y + rootM.h + 14;
    const rootBottom = y + rootM.h;
    let lastCenter = rootBottom;
    items.forEach((it) => {
      const m = schemaMeasure(bw, it.label, it.detail);
      schemaDrawBox(svg, bx, cy, bw, m, FILL, STROKE);
      const mid = cy + m.h / 2;
      svg.appendChild(schemaEl("line", { x1: trunkX, y1: mid, x2: bx, y2: mid, stroke: STROKE, "stroke-width": 2 }));
      lastCenter = mid;
      cy += m.h + 12;
    });
    svg.appendChild(schemaEl("line", { x1: trunkX, y1: rootBottom, x2: trunkX, y2: lastCenter, stroke: STROKE, "stroke-width": 2 }));
    H = cy + 4;
  } else if (spec.type === "parties" && spec.centre) {
    const bw = 124;
    const left = [], right = [];
    items.forEach((it, i) => (i % 2 === 0 ? left : right).push(it));
    const measure = (col) => col.map((it) => schemaMeasure(bw, it.label, it.detail));
    const lm = measure(left), rm = measure(right);
    const colH = (ms) => ms.reduce((s, m) => s + m.h, 0) + Math.max(0, ms.length - 1) * 12;
    H = Math.max(colH(lm), colH(rm), 90) + 20;
    const cx = W / 2, cy = H / 2, rx = 46, ry = 32;
    const place = (col, ms, x, isLeft) => {
      const total = colH(ms);
      let y = (H - total) / 2;
      col.forEach((it, i) => {
        schemaDrawBox(svg, x, y, bw, ms[i], FILL, STROKE);
        const px = isLeft ? x + bw : x;
        const py = y + ms[i].h / 2;
        const dx = px - cx, dy = py - cy;
        const k = 1 / Math.sqrt((dx / rx) ** 2 + (dy / ry) ** 2);
        svg.appendChild(schemaEl("line", { x1: px, y1: py, x2: cx + dx * k, y2: cy + dy * k, stroke: STROKE, "stroke-width": 1.6 }));
        y += ms[i].h + 12;
      });
    };
    place(left, lm, 6, true);
    place(right, rm, W - bw - 6, false);
    svg.appendChild(schemaEl("ellipse", { cx, cy, rx, ry, fill: "#fff1de", stroke: "#d98f2b", "stroke-width": 2 }));
    const cl = schemaWrap(spec.centre, 11).slice(0, 3);
    let ty = cy - ((cl.length - 1) * 14) / 2 + 4;
    cl.forEach((l) => {
      svg.appendChild(schemaEl("text", { x: cx, y: ty, "text-anchor": "middle", "font-size": 12, "font-weight": 700, fill: "#1c2321" }, l));
      ty += 14;
    });
  } else {
    // flux (par defaut, et repli si un autre type est mal renseigne)
    const bw = 260;
    let y = 10;
    items.forEach((it, i) => {
      const m = schemaMeasure(bw, it.label, it.detail);
      schemaDrawBox(svg, (W - bw) / 2, y, bw, m, FILL, STROKE);
      y += m.h;
      if (i < items.length - 1) {
        svg.appendChild(schemaEl("line", { x1: W / 2, y1: y + 2, x2: W / 2, y2: y + 22, stroke: STROKE, "stroke-width": 2 }));
        svg.appendChild(schemaEl("polygon", { points: (W / 2) + "," + (y + 26) + " " + (W / 2 - 6) + "," + (y + 17) + " " + (W / 2 + 6) + "," + (y + 17), fill: STROKE }));
        y += 28;
      }
    });
    H = y + 12;
  }
  svg.setAttribute("viewBox", "0 0 " + W + " " + Math.ceil(H));
  return svg;
}

function renderSchemaBlocks(container) {
  container.querySelectorAll("code.language-schema").forEach((codeEl) => {
    const pre = codeEl.closest("pre") || codeEl;
    const spec = parseSchemaSpec(codeEl.textContent || "");
    const needsRoot = spec.type === "hierarchie" && !spec.racine;
    const needsCenter = spec.type === "parties" && !spec.centre;
    if (!spec.items.length || needsRoot || needsCenter) {
      pre.remove();
      return;
    }
    const wrapper = document.createElement("div");
    wrapper.className = "plot-block schema-block";
    if (spec.titre) {
      const title = document.createElement("p");
      title.style.cssText = "margin:0 0 6px;font-weight:700;";
      title.textContent = spec.titre;
      wrapper.appendChild(title);
    }
    wrapper.appendChild(buildSchemaSvg(spec));
    const note = document.createElement("p");
    note.className = "schema-note";
    note.textContent = "Schéma simplifié généré par l'IA : compare-le toujours avec ton cours.";
    wrapper.appendChild(note);
    pre.replaceWith(wrapper);
  });
}

function parseDiagramSpec(text) {
  const match = text.match(/id\s*:\s*([a-z_]+)/i);
  return match ? match[1].trim() : null;
}

function renderDiagramBlocks(container) {
  container.querySelectorAll("code.language-diagram").forEach((codeEl) => {
    const pre = codeEl.closest("pre") || codeEl;
    const id = parseDiagramSpec(codeEl.textContent || "");
    const entry = id && DIAGRAM_LIBRARY[id];
    if (!entry) {
      pre.remove();
      return;
    }
    const wrapper = document.createElement("div");
    wrapper.className = "plot-block";
    const caption = document.createElement("p");
    caption.className = "muted";
    caption.style.marginTop = "6px";
    caption.textContent = entry.title;
    wrapper.innerHTML = entry.svg;
    wrapper.appendChild(caption);
    pre.replaceWith(wrapper);
  });
}
