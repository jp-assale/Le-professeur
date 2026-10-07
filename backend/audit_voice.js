const fs = require("fs"), path = require("path");
const { speakableFrench: sp } = require("../frontend/js/speech-text.js");
const dir = path.join(__dirname, "cours_seed", "lessons");
const strings = [];
function walk(v, file, key) {
  if (typeof v === "string") { if (v.length > 3) strings.push({ file, key, v }); }
  else if (Array.isArray(v)) v.forEach((x) => walk(x, file, key));
  else if (v && typeof v === "object") for (const k of Object.keys(v)) { if (k === "schema" || k === "schema_status") continue; walk(v[k], file, k); }
}
for (const f of fs.readdirSync(dir)) walk(JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")), f, "");
console.log("textes:", strings.length);
const ok = /[A-Za-zÀ-ÿŒœ0-9\s.,;:!?'’"()\-«»%]/;
const stat = {}; const ctx = {};
let leftoverMath = 0;
for (const s of strings) {
  const out = sp(s.v);
  for (const ch of out) if (!ok.test(ch)) { stat[ch] = (stat[ch] || 0) + 1; if (!ctx[ch]) ctx[ch] = { file: s.file.slice(0, 40), key: s.key, out: out.slice(Math.max(0, out.indexOf(ch) - 40), out.indexOf(ch) + 40) }; }
  if (/\[a-zA-Z]|[$^_{}]/.test(out)) leftoverMath++;
}
console.log("caractères résiduels après conversion:");
for (const [ch, n] of Object.entries(stat).sort((a, b) => b[1] - a[1])) console.log(JSON.stringify(ch), "U+" + ch.codePointAt(0).toString(16), n, "|", JSON.stringify(ctx[ch].out));
console.log("textes avec reste de LaTeX:", leftoverMath);
