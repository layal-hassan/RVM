(() => {
  const uploads = document.querySelector('input[type="file"][name="uploads"]');
  if (!uploads) return;
  const list = document.querySelector("[data-upload-list]");

  const formatSize = (bytes) => {
    if (!bytes && bytes !== 0) return "";
    const kb = bytes / 1024;
    if (kb < 1024) return `${Math.round(kb)} KB`;
    return `${(kb / 1024).toFixed(1)} MB`;
  };

  uploads.addEventListener("change", () => {
    if (!list) return;
    list.innerHTML = "";
    Array.from(uploads.files || []).forEach((file) => {
      const item = document.createElement("div");
      item.className = "upload-item";
      item.innerHTML = `
        <span class="file-icon">📎</span>
        <span>${file.name}</span>
        <span class="file-meta">${formatSize(file.size)}</span>
      `;
      list.appendChild(item);
    });
  });
})();

(() => {
  const billingRadios = document.querySelectorAll('input[name="billing_type"]');
  if (!billingRadios.length) return;

  const updateBillingVisibility = () => {
    const selected = document.querySelector('input[name="billing_type"]:checked');
    const value = selected ? selected.value : null;
    document.querySelectorAll('[data-billing]').forEach((el) => {
      el.classList.toggle('is-visible', value && el.dataset.billing === value);
    });
    document.querySelectorAll("[data-billing-field]").forEach((field) => {
      const group = field.getAttribute("data-billing-field");
      field.disabled = value && group !== value;
    });
  };

  billingRadios.forEach((radio) => {
    radio.addEventListener('change', updateBillingVisibility);
  });

  updateBillingVisibility();
})();

(() => {
  const form = document.querySelector(".booking-form");
  const dateInput = document.querySelector('input[name="preferred_date"]');
  const altDateInput = document.querySelector('input[name="alt_date"]');
  const slotSelect = document.querySelector('select[name="preferred_time_slot"]');
  const altSlotSelect = document.querySelector('select[name="alt_time_slot"]');
  const slotNote = document.querySelector('[data-slot-note="preferred"]');
  const altSlotNote = document.querySelector('[data-slot-note="alt"]');
  const hoursSelect = document.getElementById("hourly-hours");

  if (!form || !dateInput || !slotSelect) return;

  const slotsUrl = form.dataset.slotsUrl || "/service-booking/slots/";

  const initPlaceholder = (select) => {
    if (!select) return;
    if (!select.dataset.placeholder) {
      const option = select.querySelector("option");
      select.dataset.placeholder = option ? option.textContent : "Select time slot";
    }
  };

  initPlaceholder(slotSelect);
  initPlaceholder(altSlotSelect);

  const buildUrl = (dateValue) => {
    const url = new URL(slotsUrl, window.location.origin);
    url.searchParams.set("date", dateValue);
    if (hoursSelect && hoursSelect.value) {
      url.searchParams.set("hours", hoursSelect.value);
    }
    return url.toString();
  };

  const updateSelect = (select, slots, selectedValue, noteEl, emptyMessage) => {
    if (!select) return;
    const placeholderText = select.dataset.placeholder || "Select time slot";
    const safeSlots = slots || [];
    const tom = select.tomselect || null;
    if (tom) {
      tom.clearOptions();
      tom.addOption({ value: "", text: placeholderText });
      safeSlots.forEach((slot) => {
        tom.addOption({ value: slot.start, text: slot.label });
      });
      tom.refreshOptions(false);
      if (selectedValue) {
        tom.setValue(selectedValue, true);
      } else {
        tom.setValue("", true);
      }
    } else {
      select.innerHTML = "";
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = placeholderText;
      select.appendChild(placeholder);
      safeSlots.forEach((slot) => {
        const option = document.createElement("option");
        option.value = slot.start;
        option.textContent = slot.label;
        select.appendChild(option);
      });
      if (selectedValue) {
        const match = Array.from(select.options).find((opt) => opt.value === selectedValue);
        if (match) match.selected = true;
      }
    }
    if (noteEl) {
      if (!safeSlots.length) {
        noteEl.textContent = emptyMessage || "No availability for the selected date.";
        noteEl.classList.add("is-empty");
        if (tom) {
          tom.disable();
        } else {
          select.disabled = true;
        }
      } else {
        noteEl.textContent = "";
        noteEl.classList.remove("is-empty");
        if (tom) {
          tom.enable();
        } else {
          select.disabled = false;
        }
      }
    }
  };

  const loadSlots = (dateInputEl, selectEl, noteEl) => {
    if (!dateInputEl || !selectEl) return;
    const dateValue = dateInputEl.value;
    const selectedValue = selectEl.value;
    if (!dateValue) {
      updateSelect(selectEl, [], "", noteEl, "");
      return;
    }
    fetch(buildUrl(dateValue))
      .then((res) => (res.ok ? res.json() : { slots: [] }))
      .then((data) => updateSelect(selectEl, data.slots || [], selectedValue, noteEl))
      .catch(() => updateSelect(selectEl, [], selectedValue, noteEl));
  };

  dateInput.addEventListener("change", () => loadSlots(dateInput, slotSelect, slotNote));
  dateInput.addEventListener("input", () => loadSlots(dateInput, slotSelect, slotNote));
  if (altDateInput && altSlotSelect) {
    altDateInput.addEventListener("change", () => loadSlots(altDateInput, altSlotSelect, altSlotNote));
    altDateInput.addEventListener("input", () => loadSlots(altDateInput, altSlotSelect, altSlotNote));
  }
  if (hoursSelect) {
    hoursSelect.addEventListener("change", () => {
      loadSlots(dateInput, slotSelect, slotNote);
      if (altDateInput && altSlotSelect) {
        loadSlots(altDateInput, altSlotSelect, altSlotNote);
      }
    });
  }

  if (dateInput.value) {
    loadSlots(dateInput, slotSelect, slotNote);
  }
  if (altDateInput && altDateInput.value) {
    loadSlots(altDateInput, altSlotSelect, altSlotNote);
  }
})();
