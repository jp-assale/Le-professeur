const fs = require("fs");
const { speakableFrench: sp, speechRateFor: rate } = require("../frontend/js/speech-text.js");
const answers = JSON.parse(fs.readFileSync(__dirname + "/audit_answers.json", "utf8"));
const ok = /[A-Za-zÀ-ÿŒœ0-9\s.,;:!?'’"()\-«»%]/;
for (const a of answers) {
  const out = sp(a.answer);
  const bad = [...out].filter((c) => !ok.test(c));
  console.log("== " + a.tag + " | vitesse " + rate(a.answer) + " | symboles résiduels: " + (bad.length ? JSON.stringify([...new Set(bad)]) : "aucun"));
  if (/Physique|Mathematiques|SVT/.test(a.tag)) console.log("   " + out.slice(0, 420).replace(/\n/g, " ") + "\n");
}
