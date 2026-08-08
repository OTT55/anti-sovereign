/* Distribution Strategy structured form: builds a natural-language question
   from genre/tier/awards selections and submits it through the exact same
   ask() path chat.js uses for free-form questions. There is no separate
   analysis engine here — this is a question-template builder only. */
(() => {
  const analyzeBtn = document.getElementById("dist-analyze");
  if (!analyzeBtn) return; // not a distribution-intelligence collection page

  const tierTabs = document.querySelectorAll(".tier-tab");
  let selectedTier = null;

  const GENRE_LABELS = {
    horror: "Horror",
    family: "Animated / Family",
    "awards-drama": "Awards Drama / Prestige",
    action: "Action / Tentpole",
    romance: "Romance / Rom-Com",
    indie: "Low-Budget / Indie",
  };
  const TIER_LABELS = {
    micro: "micro-budget (< $5M)",
    mid: "mid-budget ($5M–$40M)",
    tentpole: "tentpole ($40M+)",
  };

  tierTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tierTabs.forEach((t) => t.classList.remove("is-selected"));
      tab.classList.add("is-selected");
      selectedTier = tab.dataset.tier;
    });
  });

  function buildQuestion() {
    const genres = Array.from(document.querySelectorAll(".dist-genre:checked")).map(
      (el) => GENRE_LABELS[el.value]
    );
    const awards = document.getElementById("dist-awards").checked;

    if (genres.length === 0 || !selectedTier) return null;

    const tierLabel = TIER_LABELS[selectedTier];
    const genrePhrase = genres.join(" / ");
    let q = `What is the best release window and distribution platform strategy for a ${tierLabel} ${genrePhrase} film`;
    if (awards) q += ", being positioned for awards consideration";
    q += "? Cite specific real comparable film releases with their dates and outcomes.";
    return q;
  }

  analyzeBtn.addEventListener("click", () => {
    const question = buildQuestion();
    const err = document.getElementById("err");
    if (!question) {
      err.textContent = "Choose at least one genre and a budget tier.";
      err.classList.remove("hidden");
      return;
    }
    err.classList.add("hidden");
    window.__contextcoreAsk(question);
  });
})();
