/* Moteur de cours - navigation du diaporama, réutilisé par toutes les leçons.

   initCoursEngine(totalSlides)            -> comportement d'origine (pages pilotes)
   initCoursEngine(totalSlides, options)   -> options facultatives :
     onSlide(index)  appelé à chaque changement de diapositive
     onFinish()      appelé sur « Terminer ✓ » (défaut : history.back())

   Navigation aussi au clavier (← →) et par glissement du doigt (swipe),
   naturel sur téléphone. */
function initCoursEngine(totalSlides, options) {
  const opts = options || {};
  let current = 0;

  const progressEl = document.getElementById("progress");
  progressEl.innerHTML = "";
  progressEl.setAttribute("role", "progressbar");
  progressEl.setAttribute("aria-valuemin", "1");
  progressEl.setAttribute("aria-valuemax", String(totalSlides));
  for (let i = 0; i < totalSlides; i++) {
    const d = document.createElement("div");
    d.className = "dot";
    progressEl.appendChild(d);
  }

  const slides = document.querySelectorAll(".slide");
  const btnPrev = document.getElementById("btn-prev");
  const btnNext = document.getElementById("btn-next");
  const bodyEl = document.querySelector(".lesson-body");

  function render() {
    slides.forEach((s, i) => s.classList.toggle("active", i === current));
    progressEl.querySelectorAll(".dot").forEach((d, i) => {
      d.classList.toggle("done", i < current);
      d.classList.toggle("current", i === current);
    });
    progressEl.setAttribute("aria-valuenow", String(current + 1));
    btnPrev.disabled = current === 0;
    btnNext.textContent = current === totalSlides - 1 ? "Terminer ✓" : "Suivant →";
    bodyEl.scrollTop = 0;
    if (opts.onSlide) opts.onSlide(current);
  }

  function stopSpeakingIfAny() {
    if (window.stopCoursSpeaking) stopCoursSpeaking();
  }

  function goPrev() {
    stopSpeakingIfAny();
    if (current > 0) { current--; render(); }
  }
  function goNext() {
    stopSpeakingIfAny();
    if (current < totalSlides - 1) { current++; render(); }
    else if (opts.onFinish) { opts.onFinish(); }
    else { history.back(); }
  }

  btnPrev.addEventListener("click", goPrev);
  btnNext.addEventListener("click", goNext);

  document.addEventListener("keydown", (e) => {
    const tag = (e.target && e.target.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA") return;
    if (e.key === "ArrowRight") goNext();
    else if (e.key === "ArrowLeft") goPrev();
  });

  // Glissement horizontal net (pas un simple defilement vertical, ni un
  // curseur de simulation qu'on fait glisser).
  let startX = null, startY = null;
  bodyEl.addEventListener("touchstart", (e) => {
    if (e.target.closest && e.target.closest("input, svg, .scene")) { startX = null; return; }
    startX = e.touches[0].clientX; startY = e.touches[0].clientY;
  }, { passive: true });
  bodyEl.addEventListener("touchend", (e) => {
    if (startX === null) return;
    const dx = e.changedTouches[0].clientX - startX;
    const dy = e.changedTouches[0].clientY - startY;
    startX = null;
    if (Math.abs(dx) < 70 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
    if (dx < 0) { if (current < totalSlides - 1) goNext(); }
    else goPrev();
  }, { passive: true });

  render();
  return {
    goTo(i) { if (i >= 0 && i < totalSlides) { stopSpeakingIfAny(); current = i; render(); } },
  };
}
