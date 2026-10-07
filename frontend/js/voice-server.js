/* Lecture vocale via le serveur (voix masculine fr-FR-HenriNeural) pour
   l'appli Android : la voix du systeme ne permet pas de garantir un genre.
   Utilise par app.js (chat) et cours-render.js (cours).
   speakServer(text) -> Promise : resolue a la fin de la lecture ou apres
   stopServerSpeech(); rejetee si le serveur n'a rien pu fournir au debut
   (l'appelant retombe alors sur la voix native du telephone). */
(function () {
  const CHUNK_MAX = 1800;
  let session = 0;
  let audio = null;

  function splitText(text) {
    const parts = [];
    let rest = text.trim();
    while (rest.length > CHUNK_MAX) {
      let cut = Math.max(
        rest.lastIndexOf(". ", CHUNK_MAX),
        rest.lastIndexOf("? ", CHUNK_MAX),
        rest.lastIndexOf("! ", CHUNK_MAX),
        rest.lastIndexOf("\n", CHUNK_MAX)
      );
      if (cut < CHUNK_MAX / 2) cut = rest.lastIndexOf(" ", CHUNK_MAX);
      if (cut < 1) cut = CHUNK_MAX;
      parts.push(rest.slice(0, cut + 1).trim());
      rest = rest.slice(cut + 1).trim();
    }
    if (rest) parts.push(rest);
    return parts;
  }

  async function fetchChunk(text, rate) {
    const base = window.AIDA_API_BASE_URL || "";
    const res = await fetch(base + "/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, rate }),
    });
    if (!res.ok) throw new Error("tts " + res.status);
    return URL.createObjectURL(await res.blob());
  }

  function playUrl(url, mySession) {
    return new Promise((resolve) => {
      if (mySession !== session) { URL.revokeObjectURL(url); resolve(); return; }
      audio = new Audio(url);
      const done = () => { URL.revokeObjectURL(url); resolve(); };
      audio.onended = done;
      audio.onerror = done;
      audio.play().catch(done);
    });
  }

  window.stopServerSpeech = function () {
    session++;
    if (audio) {
      try { audio.pause(); } catch (e) {}
      audio = null;
    }
  };

  window.speakServer = async function (text, rate) {
    window.stopServerSpeech();
    const mySession = session;
    const parts = splitText(text);
    if (!parts.length) return;
    let next = fetchChunk(parts[0], rate);
    for (let i = 0; i < parts.length; i++) {
      let url;
      try {
        url = await next;
      } catch (e) {
        if (i === 0) throw e; // rien lu : l'appelant bascule sur la voix native
        return;
      }
      if (mySession !== session) { URL.revokeObjectURL(url); return; }
      next = i + 1 < parts.length ? fetchChunk(parts[i + 1], rate) : null;
      if (next) next.catch(() => {});
      await playUrl(url, mySession);
      if (mySession !== session) return;
    }
  };
})();
