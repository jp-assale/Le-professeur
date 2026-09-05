/* Moteur de cours - navigation du diaporama, réutilisé par toutes les leçons */
function initCoursEngine(totalSlides) {
  let current = 0;

  const progressEl = document.getElementById("progress");
  for (let i = 0; i < totalSlides; i++) {
    const d = document.createElement("div");
    d.className = "dot";
    progressEl.appendChild(d);
  }

  const slides = document.querySelectorAll(".slide");
  const btnPrev = document.getElementById("btn-prev");
  const btnNext = document.getElementById("btn-next");

  function render() {
    slides.forEach((s, i) => s.classList.toggle("active", i === current));
    progressEl.querySelectorAll(".dot").forEach((d, i) => {
      d.classList.toggle("done", i < current);
      d.classList.toggle("current", i === current);
    });
    btnPrev.disabled = current === 0;
    btnNext.textContent = current === totalSlides - 1 ? "Terminer ✓" : "Suivant →";
    document.querySelector(".lesson-body").scrollTop = 0;
  }

  btnPrev.addEventListener("click", () => { if (current > 0) { current--; render(); } });
  btnNext.addEventListener("click", () => {
    if (current < totalSlides - 1) { current++; render(); }
    else { history.back(); }
  });

  render();
}
