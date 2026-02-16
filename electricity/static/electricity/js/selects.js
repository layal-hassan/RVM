(() => {
  const DEFAULT_SELECTOR = "select";
  const IGNORE_SELECTOR = "[data-tomselect='false'], [data-native-select='true']";

  const getPlaceholder = (el) =>
    el.getAttribute("data-placeholder") ||
    el.getAttribute("placeholder") ||
    (el.multiple ? "Select options" : "Select option");

  window.refreshTomSelect = (select) => {
    if (!select || !select.tomselect) return;
    select.tomselect.sync();
    select.tomselect.refreshOptions(false);
  };

  const initTomSelect = (root = document) => {
    if (!window.TomSelect) return;

    const selects = root.querySelectorAll(DEFAULT_SELECTOR);
    selects.forEach((select) => {
      if (select.matches(IGNORE_SELECTOR)) return;
      if (select.dataset.tomselectInitialized === "true") return;
      if (select.tomselect) return;
      if (select.classList.contains("ts-hidden-accessible")) return;

      const plugins = [];
      if (select.multiple) {
        plugins.push("remove_button");
      }

      select.dataset.tomselectInitialized = "true";
      const tom = new TomSelect(select, {
        plugins,
        create: false,
        allowEmptyOption: true,
        placeholder: getPlaceholder(select),
        closeAfterSelect: !select.multiple,
        dropdownParent: "body",
      });

    });
  };

  const initOnLoad = () => initTomSelect(document);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initOnLoad, { once: true });
  } else {
    initOnLoad();
  }

  document.addEventListener("htmx:afterSwap", (event) => {
    initTomSelect(event.target);
  });

  document.addEventListener("htmx:afterSettle", (event) => {
    initTomSelect(event.target);
  });
})();
