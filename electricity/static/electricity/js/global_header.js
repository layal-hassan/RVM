(() => {
  const header = document.querySelector(".rwm-electricity-global-header[data-rwmh]");
  if (!header) return;

  const toggle = header.querySelector("[data-rwmh-toggle]");
  const menu = header.querySelector("[data-rwmh-menu]");
  if (!toggle || !menu) return;

  const dropdowns = Array.from(header.querySelectorAll("[data-rwmh-dropdown]"));
  const onCallLinks = Array.from(header.querySelectorAll("[data-rwmh-on-call]"));

  const updateOnCallActiveLink = () => {
    if (!onCallLinks.length) return;
    const onCallPath = new URL(onCallLinks[0].href, window.location.href).pathname;
    if (window.location.pathname !== onCallPath) return;
    const activeSection = window.location.hash === "#pricing" ? "pricing" : "jour";
    onCallLinks.forEach((link) => {
      const isActive = link.dataset.rwmhOnCall === activeSection;
      link.classList.toggle("is-active", isActive);
      if (isActive) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  };

  updateOnCallActiveLink();
  window.addEventListener("hashchange", updateOnCallActiveLink);

  dropdowns.forEach((dropdown) => {
    const trigger = dropdown.querySelector("[data-rwmh-dropdown-trigger]");
    if (!trigger) return;
    let hoverCloseTimer = null;

    const keepDropdownOpen = () => {
      if (window.innerWidth <= 980) return;
      if (hoverCloseTimer) window.clearTimeout(hoverCloseTimer);
      dropdown.classList.add("is-hover-open");
    };

    const scheduleDropdownClose = () => {
      if (window.innerWidth <= 980) return;
      if (hoverCloseTimer) window.clearTimeout(hoverCloseTimer);
      hoverCloseTimer = window.setTimeout(() => {
        dropdown.classList.remove("is-hover-open");
      }, 450);
    };

    dropdown.addEventListener("mouseenter", keepDropdownOpen);
    dropdown.addEventListener("mouseleave", scheduleDropdownClose);

    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      const willOpen = !dropdown.classList.contains("is-open");
      dropdowns.forEach((item) => {
        item.classList.remove("is-open");
        item.classList.remove("is-hover-open");
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
      dropdown.classList.remove("is-hover-open");
      const trigger = dropdown.querySelector("[data-rwmh-dropdown-trigger]");
      if (trigger) trigger.setAttribute("aria-expanded", "false");
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    dropdowns.forEach((dropdown) => {
      dropdown.classList.remove("is-open");
      dropdown.classList.remove("is-hover-open");
      const trigger = dropdown.querySelector("[data-rwmh-dropdown-trigger]");
      if (trigger) trigger.setAttribute("aria-expanded", "false");
    });
  });
})();
