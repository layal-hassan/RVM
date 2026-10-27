(() => {
  const header = document.querySelector(".rwm-electricity-global-header[data-rwmh]");
  if (!header) return;

  const toggle = header.querySelector("[data-rwmh-toggle]");
  const menu = header.querySelector("[data-rwmh-menu]");
  if (!toggle || !menu) return;

  const dropdowns = Array.from(header.querySelectorAll("[data-rwmh-dropdown]"));
  const onCallLinks = Array.from(header.querySelectorAll("[data-rwmh-on-call]"));

  const closeMenu = () => {
    header.classList.remove("is-open");
    document.body.classList.remove("rwm-mobile-menu-open");
    toggle.setAttribute("aria-expanded", "false");
  };

  const updateOnCallActiveLink = () => {
    if (!onCallLinks.length) return;
    const jourLink = onCallLinks.find((link) => link.dataset.rwmhOnCall === "jour");
    if (!jourLink) return;
    const onCallPath = new URL(jourLink.href, window.location.href).pathname;
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
    const linkButton = dropdown.querySelector(".rwm-egh-link-button");
    let hoverCloseTimer = null;

    const toggleDropdown = (event) => {
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
    };

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

    trigger.addEventListener("click", toggleDropdown);
    linkButton?.addEventListener("click", toggleDropdown);
  });

  toggle.addEventListener("click", () => {
    const isOpen = header.classList.toggle("is-open");
    document.body.classList.toggle("rwm-mobile-menu-open", isOpen);
    toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
  });

  menu.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", closeMenu);
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
    closeMenu();
    dropdowns.forEach((dropdown) => {
      dropdown.classList.remove("is-open");
      dropdown.classList.remove("is-hover-open");
      const trigger = dropdown.querySelector("[data-rwmh-dropdown-trigger]");
      if (trigger) trigger.setAttribute("aria-expanded", "false");
    });
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > 980) closeMenu();
  });
})();
