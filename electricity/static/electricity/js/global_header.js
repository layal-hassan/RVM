(() => {
  const header = document.querySelector(".rwm-electricity-global-header[data-rwmh]");
  if (!header) return;

  const toggle = header.querySelector("[data-rwmh-toggle]");
  const menu = header.querySelector("[data-rwmh-menu]");
  if (!toggle || !menu) return;

  toggle.addEventListener("click", () => {
    const isOpen = header.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
  });
})();
