(() => {
  const header = document.querySelector(".rwm-electricity-global-header[data-rwmh]");
  if (!header) return;

  const toggle = header.querySelector("[data-rwmh-toggle]");
  const menu = header.querySelector("[data-rwmh-menu]");
  if (!toggle || !menu) return;

  const dropdowns = Array.from(header.querySelectorAll("[data-rwmh-dropdown]"));
  dropdowns.forEach((dropdown) => {
    const trigger = dropdown.querySelector("[data-rwmh-dropdown-trigger]");
    if (!trigger) return;

    trigger.addEventListener("click", (event) => {
      if (window.innerWidth > 980) return;
      event.preventDefault();
      const willOpen = !dropdown.classList.contains("is-open");
      dropdowns.forEach((item) => {
        item.classList.remove("is-open");
        const itemTrigger = item.querySelector("[data-rwmh-dropdown-trigger]");
        if (itemTrigger) itemTrigger.setAttribute("aria-expanded", "false");
      });
      dropdown.classList.toggle("is-open", willOpen);
      trigger.setAttribute("aria-expanded", willOpen ? "true" : "false");
    });
  });

  toggle.addEventListener("click", () => {
    const isOpen = header.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
  });

  document.addEventListener("click", (event) => {
    if (header.contains(event.target)) return;
    dropdowns.forEach((dropdown) => {
      dropdown.classList.remove("is-open");
      const trigger = dropdown.querySelector("[data-rwmh-dropdown-trigger]");
      if (trigger) trigger.setAttribute("aria-expanded", "false");
    });
  });
})();
