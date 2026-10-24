(() => {
  const dialog = document.querySelector("#request-flow");
  const form = document.querySelector("#request-flow-form");
  const drawer = document.querySelector("[data-cart-drawer]");
  const drawerBackdrop = document.querySelector("[data-cart-backdrop]");
  const cartFab = document.querySelector("[data-cart-fab]");
  if (!dialog || !form || !drawer || typeof dialog.showModal !== "function") return;

  let step = 2;
  let cart = [];
  let parkedCart = null;
  let files = [];
  let lastAdded = null;
  const fileUrls = new WeakMap();
  const esc = value => { const node = document.createElement("span"); node.textContent = value || ""; return node.innerHTML; };
  const money = value => new Intl.NumberFormat(document.documentElement.lang || "en", { maximumFractionDigits: 0 }).format(value);
  const numericPrice = text => {
    const match = String(text || "").match(/\d[\d\s.,]*/);
    if (!match) return 0;
    let value = match[0].replace(/\s/g, "");
    if (/^\d{1,3}(,\d{3})+$/.test(value)) value = value.replace(/,/g, "");
    else if (/^\d{1,3}(\.\d{3})+$/.test(value)) value = value.replace(/\./g, "");
    else if (value.includes(",") && !value.includes(".")) value = value.replace(",", ".");
    else value = value.replace(/,/g, "");
    return Number(value) || 0;
  };
  const total = () => cart.reduce((sum, item) => sum + (item.mode === "fixed" ? item.unitPrice * item.quantity : 0), 0);
  const hasQuote = () => cart.some(item => item.mode === "quote");
  const totalLabel = () => `${total() ? `From SEK ${money(total())}` : "Quote required"}${hasQuote() && total() ? " + quote services" : ""}`;
  const fileUrl = file => { if (!fileUrls.has(file)) fileUrls.set(file, URL.createObjectURL(file)); return fileUrls.get(file); };
  const fileSize = file => file.size < 1024 * 1024 ? `${Math.max(1, Math.round(file.size / 1024))} KB` : `${(file.size / 1024 / 1024).toFixed(1)} MB`;
  const fileThumb = file => { const url = fileUrl(file); if (file.type.startsWith("image/")) return `<img src="${url}" alt="">`; if (file.type.startsWith("video/")) return `<span class="request-file-thumb is-video">▶</span>`; if (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) return '<span class="request-file-thumb is-pdf">PDF</span>'; return '<span class="request-file-thumb">DOC</span>'; };
  const serviceRow = (item, controls = false) => `<article class="request-flow-cart-item" data-cart-id="${esc(item.key)}">${item.image ? `<img src="${esc(item.image)}" alt="">` : '<span class="request-flow-placeholder">⚡</span>'}<div><strong>${esc(item.title)}</strong><small>${esc(item.description)}</small><em>${item.mode === "quote" ? "Quote required" : `${esc(item.price)} per item`}</em>${controls ? `<span class="request-flow-inline-quantity"><button type="button" data-cart-minus>−</button><output>${item.quantity}</output><button type="button" data-cart-plus>+</button></span>` : `<small>Quantity: ${item.quantity}</small>`}</div>${controls ? '<button type="button" class="request-flow-remove" data-cart-remove aria-label="Remove">×</button>' : `<b>${item.mode === "quote" ? "Quote required" : `SEK ${money(item.unitPrice * item.quantity)}`}</b>`}</article>`;

  function updateProgress() {
    dialog.querySelectorAll("[data-progress]").forEach(node => { const number = Number(node.dataset.progress); node.classList.toggle("is-active", number === step); node.classList.toggle("is-done", number < step); });
  }
  function show(next) {
    step = next;
    dialog.classList.toggle("is-added-step", next === 2);
    dialog.querySelectorAll("[data-step]").forEach(node => node.classList.toggle("is-active", Number(node.dataset.step) === step));
    updateProgress(); clearErrors(); dialog.scrollTop = 0;
  }
  function clearErrors() { dialog.querySelectorAll("[data-error]").forEach(node => node.textContent = ""); }
  function setError(message) { dialog.querySelectorAll("[data-error]").forEach(node => node.textContent = message || ""); }
  function syncHidden() { form.elements.services_json.value = JSON.stringify(cart.map(({ id, source, quantity }) => ({ id, source, quantity }))); }
  function renderCart() {
    syncHidden();
    document.querySelectorAll("[data-cart-count]").forEach(node => node.textContent = cart.reduce((sum, item) => sum + item.quantity, 0));
    document.querySelectorAll("[data-total]").forEach(node => node.textContent = totalLabel());
    const cartNode = dialog.querySelector("[data-cart]");
    const cartMarkup = cart.length ? cart.map(item => serviceRow(item, true)).join("") : '<p class="request-flow-empty">Your request is empty. Add a service to continue.</p>';
    cartNode.innerHTML = cartMarkup;
    drawer.querySelector("[data-drawer-cart]").innerHTML = cartMarkup;
    drawer.querySelector("[data-cart-continue]").disabled = !cart.length;
    if (cartFab) cartFab.hidden = !cart.some(item => item.cartEligible);
    dialog.querySelectorAll("[data-summary-services], [data-review-services]").forEach(node => node.innerHTML = cart.map(item => serviceRow(item)).join(""));
  }
  function openDrawer() { drawer.classList.add("is-open"); drawerBackdrop.classList.add("is-open"); drawer.setAttribute("aria-hidden", "false"); }
  function closeDrawer() { drawer.classList.remove("is-open"); drawerBackdrop.classList.remove("is-open"); drawer.setAttribute("aria-hidden", "true"); }
  function restoreParkedCart() {
    if (parkedCart === null) return;
    cart = parkedCart;
    parkedCart = null;
    renderCart();
  }
  function handleCartControls(event) {
    const row = event.target.closest("[data-cart-id]");
    if (!row) return false;
    const item = cart.find(entry => entry.key === row.dataset.cartId); if (!item) return true;
    if (event.target.closest("[data-cart-plus]")) item.quantity = Math.min(99, item.quantity + 1);
    if (event.target.closest("[data-cart-minus]")) item.quantity = Math.max(1, item.quantity - 1);
    if (event.target.closest("[data-cart-remove]")) cart = cart.filter(entry => entry.key !== item.key);
    renderCart(); return true;
  }
  function updateFiles() {
    const transfer = new DataTransfer(); files.forEach(file => transfer.items.add(file)); form.elements.attachments.files = transfer.files;
    const empty = '<p>No attachments added.</p>';
    dialog.querySelector("[data-files]").innerHTML = files.length ? files.map((file, index) => `<div><span>▤ <b>${esc(file.name)}</b><small>${(file.size / 1024 / 1024).toFixed(1)} MB</small></span><button type="button" data-file-remove="${index}" aria-label="Remove">×</button></div>`).join("") : empty;
    dialog.querySelector("[data-review-files]").innerHTML = files.length ? files.map((file, index) => `<article class="request-review-file">${fileThumb(file)}<span class="request-review-file-copy"><b>${esc(file.name)}</b><small>${fileSize(file)}</small></span><span class="request-flow-file-actions"><button type="button" data-file-preview="${index}" aria-label="Preview">◉</button><button type="button" data-file-download="${index}" aria-label="Download">⇩</button></span></article>`).join("") : empty;
  }
  function validateDetails() {
    const invalid = [...form.querySelectorAll("[data-step='4'] [required]")].find(field => !field.checkValidity());
    const timeframeError = dialog.querySelector("[data-timeframe-error]");
    timeframeError.textContent = "";
    if (invalid) {
      if (invalid.name === "preferred_timeframe") timeframeError.textContent = "Please choose your preferred timeframe.";
      setError("Please complete all required fields before continuing.");
      invalid.scrollIntoView({ behavior: "smooth", block: "center" });
      invalid.focus();
      invalid.reportValidity();
      return false;
    }
    return true;
  }
  function renderReview() {
    const data = new FormData(form); const type = ({ private: "Private", business: "Business", brf: "BRF" })[data.get("customer_type")] || "Private";
    dialog.querySelector("[data-review-details]").innerHTML = `<dt>Customer type</dt><dd>${type}</dd><dt>Full name</dt><dd>${esc(data.get("full_name"))}</dd><dt>Email address</dt><dd>${esc(data.get("email"))}</dd><dt>Phone number</dt><dd>${esc(data.get("phone"))}</dd><dt>Installation address</dt><dd>${esc(data.get("street_address"))}, ${esc(data.get("postcode"))} ${esc(data.get("city"))}</dd><dt>Preferred timeframe</dt><dd>${esc(data.get("preferred_timeframe"))}</dd><dt>Additional information</dt><dd>${esc(data.get("additional_information")) || "N/A"}</dd>`;
    renderCart(); updateFiles();
  }

  document.querySelectorAll(".js-request-flow").forEach(button => button.addEventListener("click", event => {
    event.preventDefault();
    const card = button.closest("[data-project-config]");
    const quantity = Number(card?.querySelector("[data-quantity]")?.textContent || 1);
    const key = `${button.dataset.source}:${button.dataset.itemId}`;
    const cartEligible = button.dataset.cartTrigger === "true";
    if (!cartEligible) {
      parkedCart = cart;
      cart = [{ key, id: button.dataset.itemId, source: button.dataset.source, title: button.dataset.title, description: button.dataset.description, price: button.dataset.price, unitPrice: numericPrice(button.dataset.price), mode: button.dataset.mode || "quote", image: button.dataset.image || "", quantity, cartEligible: false }];
      lastAdded = cart[0];
      dialog.querySelector("[data-added-service]").innerHTML = serviceRow(lastAdded);
      renderCart();
      show(4);
      dialog.showModal();
      return;
    }
    const existing = cart.find(item => item.key === key);
    if (existing) { existing.quantity = Math.min(99, existing.quantity + quantity); existing.cartEligible ||= cartEligible; }
    else cart.push({ key, id: button.dataset.itemId, source: button.dataset.source, title: button.dataset.title, description: button.dataset.description, price: button.dataset.price, unitPrice: numericPrice(button.dataset.price), mode: button.dataset.mode || "fixed", image: button.dataset.image || "", quantity, cartEligible });
    lastAdded = cart.find(item => item.key === key);
    dialog.querySelector("[data-added-service]").innerHTML = serviceRow(lastAdded);
    renderCart();
    show(2);
    dialog.showModal();
  }));
  dialog.addEventListener("click", event => {
    const go = event.target.closest("[data-go]");
    if (go) { const next = Number(go.dataset.go); if (next === 4 && !cart.length) return setError("Please add at least one service."); if (next === 5) { if (!validateDetails()) return; renderReview(); } show(next); return; }
    const close = event.target.closest("[data-close]"); if (close) { dialog.close(); return; }
    if (handleCartControls(event)) return;
    const removeFile = event.target.closest("[data-file-remove]"); if (removeFile) { files.splice(Number(removeFile.dataset.fileRemove), 1); updateFiles(); }
    const previewFile = event.target.closest("[data-file-preview]"); if (previewFile) { const url = URL.createObjectURL(files[Number(previewFile.dataset.filePreview)]); window.open(url, "_blank", "noopener"); setTimeout(() => URL.revokeObjectURL(url), 60000); }
    const downloadFile = event.target.closest("[data-file-download]"); if (downloadFile) { const file = files[Number(downloadFile.dataset.fileDownload)]; const link = document.createElement("a"); link.href = URL.createObjectURL(file); link.download = file.name; link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 1000); }
  });
  drawer.addEventListener("click", event => { if (handleCartControls(event)) return; if (event.target.closest("[data-cart-close]")) closeDrawer(); if (event.target.closest("[data-cart-continue]") && cart.length) { closeDrawer(); renderCart(); show(3); dialog.showModal(); } });
  if (cartFab) cartFab.addEventListener("click", openDrawer);
  drawerBackdrop.addEventListener("click", closeDrawer);
  dialog.addEventListener("close", restoreParkedCart);
  dialog.querySelector(".request-flow-close").addEventListener("click", () => dialog.close());
  form.elements.attachments.addEventListener("change", event => { files = [...files, ...event.target.files].slice(0, 10); updateFiles(); });
  form.elements.preferred_timeframe.addEventListener("change", () => { dialog.querySelector("[data-timeframe-error]").textContent = ""; clearErrors(); });
  const dropzone = dialog.querySelector(".request-flow-upload");
  ["dragenter", "dragover"].forEach(type => dropzone.addEventListener(type, event => { event.preventDefault(); dropzone.classList.add("is-dragging"); }));
  ["dragleave", "drop"].forEach(type => dropzone.addEventListener(type, event => { event.preventDefault(); dropzone.classList.remove("is-dragging"); }));
  dropzone.addEventListener("drop", event => { files = [...files, ...event.dataTransfer.files].slice(0, 10); updateFiles(); });
  form.addEventListener("submit", async event => {
    event.preventDefault(); clearErrors();
    if (!dialog.querySelector("[data-confirm]").checked) return setError("Please confirm that the information is correct.");
    syncHidden(); const submit = dialog.querySelector("[data-submit]"); submit.disabled = true; const original = submit.textContent; submit.textContent = "Sending…";
    try { const response = await fetch(form.dataset.submitUrl, { method: "POST", body: new FormData(form), headers: { "X-Requested-With": "XMLHttpRequest" } }); const result = await response.json(); if (!response.ok) throw new Error(result.error || "Could not send your request."); dialog.querySelector("[data-reference]").textContent = result.reference; cart = []; files = []; renderCart(); show(6); }
    catch (error) { setError(error.message); } finally { submit.disabled = false; submit.textContent = original; }
  });
  dialog.querySelector("[data-finish]").addEventListener("click", () => { restoreParkedCart(); dialog.close(); form.reset(); renderCart(); updateFiles(); window.scrollTo({ top: 0, behavior: "smooth" }); });
})();
