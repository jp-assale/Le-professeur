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
};

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
