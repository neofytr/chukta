// Applies the saved theme before first paint, so the page never flashes the wrong colors.
(() => {
  const root = document.documentElement;
  let seed = null, mode = null;
  try {
    seed = localStorage.getItem("chukta-seed");
    mode = localStorage.getItem("chukta-mode");
  } catch { /* Storage can be blocked. The defaults still work. */ }
  root.dataset.seed = ["forest", "bay", "peony", "marigold"].includes(seed) ? seed : "forest";
  root.dataset.mode = mode === "dark" || mode === "light" ? mode : matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
})();
