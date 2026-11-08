(() => {
  const widgets = [...document.querySelectorAll("[data-turnstile]")];
  if (!widgets.length) return;
  const ids = new Map();
  const error = node => node.closest(".submission-verification").querySelector("[data-turnstile-error]");
  const reset = form => widgets.filter(node => node.closest("form") === form).forEach(node => {
    if (ids.has(node) && window.turnstile) window.turnstile.reset(ids.get(node));
  });
  window.resetSubmissionVerification = reset;
  // Capture before existing AJAX handlers so unverified forms never start sending.
  document.addEventListener("submit", event => {
    const node = widgets.find(widget => widget.closest("form") === event.target);
    if (!node) return;
    if (!window.turnstile || !ids.has(node) || !window.turnstile.getResponse(ids.get(node))) {
      event.preventDefault();
      event.stopImmediatePropagation();
      error(node).hidden = false;
      node.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }, true);
  const renderVisible = () => {
    if (!window.turnstile) return;
    widgets.forEach(node => {
      // Dialogs and review steps must be visible before rendering the challenge.
      if (ids.has(node) || !node.getClientRects().length) return;
      ids.set(node, window.turnstile.render(node, {
        sitekey: node.dataset.sitekey,
        size: "flexible",
        callback: () => { error(node).hidden = true; },
        "error-callback": () => { error(node).hidden = false; },
        "expired-callback": () => { error(node).hidden = false; },
      }));
    });
  };
  window.onSubmissionTurnstileLoad = renderVisible;
  const script = document.createElement("script");
  script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?onload=onSubmissionTurnstileLoad&render=explicit";
  script.async = true;
  script.onerror = () => widgets.forEach(node => { error(node).hidden = false; });
  document.head.append(script);
  new MutationObserver(renderVisible).observe(document.body, {
    subtree: true, attributes: true, attributeFilter: ["class", "style", "hidden", "open"],
  });
  window.addEventListener("pageshow", event => {
    if (event.persisted) widgets.forEach(node => reset(node.closest("form")));
  });
})();
