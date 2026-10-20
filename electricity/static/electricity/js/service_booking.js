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

(() => {
  const shells = document.querySelectorAll(".date-input-shell");
  if (!shells.length) return;

  const locale = document.documentElement.lang || "en";
  const isArabic = locale.startsWith("ar");
  const labels = isArabic
    ? { today: "اليوم", clear: "مسح", previous: "الشهر السابق", next: "الشهر التالي" }
    : { today: "Today", clear: "Clear", previous: "Previous month", next: "Next month" };
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  let activePicker = null;

  const parseDate = (value) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return null;
    const [year, month, day] = value.split("-").map(Number);
    const date = new Date(year, month - 1, day);
    return Number.isNaN(date.getTime()) ? null : date;
  };

  const toISO = (date) => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  };

  const closePicker = () => {
    if (!activePicker) return;
    activePicker.picker.hidden = true;
    activePicker.shell.classList.remove("is-calendar-open");
    activePicker.trigger.setAttribute("aria-expanded", "false");
    activePicker = null;
  };

  shells.forEach((shell) => {
    const input = shell.querySelector('input[type="date"]');
    const trigger = shell.querySelector("[data-date-trigger]");
    if (!input || !trigger) return;

    input.type = "text";
    input.readOnly = true;
    input.setAttribute("inputmode", "none");
    input.setAttribute("autocomplete", "off");
    input.setAttribute("aria-haspopup", "dialog");
    trigger.setAttribute("aria-haspopup", "dialog");
    trigger.setAttribute("aria-expanded", "false");

    const picker = document.createElement("div");
    picker.className = "rwm-calendar";
    picker.hidden = true;
    picker.setAttribute("role", "dialog");
    picker.setAttribute("aria-label", "Calendar");
    picker.innerHTML = `
      <div class="rwm-calendar-head">
        <button type="button" class="rwm-calendar-nav" data-calendar-prev aria-label="${labels.previous}">‹</button>
        <strong class="rwm-calendar-month"></strong>
        <button type="button" class="rwm-calendar-nav" data-calendar-next aria-label="${labels.next}">›</button>
      </div>
      <div class="rwm-calendar-weekdays"></div>
      <div class="rwm-calendar-days"></div>
      <div class="rwm-calendar-footer">
        <button type="button" data-calendar-clear>${labels.clear}</button>
        <button type="button" data-calendar-today>${labels.today}</button>
      </div>`;
    shell.appendChild(picker);

    const selected = parseDate(input.value);
    let viewDate = selected ? new Date(selected) : new Date(today);
    viewDate.setDate(1);
    const monthLabel = picker.querySelector(".rwm-calendar-month");
    const weekdays = picker.querySelector(".rwm-calendar-weekdays");
    const days = picker.querySelector(".rwm-calendar-days");

    const weekdayFormat = new Intl.DateTimeFormat(locale, { weekday: "short" });
    const sunday = new Date(2024, 0, 7);
    weekdays.innerHTML = Array.from({ length: 7 }, (_, index) => {
      const day = new Date(sunday);
      day.setDate(sunday.getDate() + index);
      return `<span>${weekdayFormat.format(day).replace(".", "")}</span>`;
    }).join("");

    const render = () => {
      monthLabel.textContent = new Intl.DateTimeFormat(locale, { month: "long", year: "numeric" }).format(viewDate);
      days.innerHTML = "";
      const year = viewDate.getFullYear();
      const month = viewDate.getMonth();
      const firstWeekday = new Date(year, month, 1).getDay();
      const monthLength = new Date(year, month + 1, 0).getDate();
      const previousLength = new Date(year, month, 0).getDate();

      for (let cell = 0; cell < 42; cell += 1) {
        const dayOffset = cell - firstWeekday + 1;
        let date;
        let outside = false;
        if (dayOffset < 1) {
          date = new Date(year, month - 1, previousLength + dayOffset);
          outside = true;
        } else if (dayOffset > monthLength) {
          date = new Date(year, month + 1, dayOffset - monthLength);
          outside = true;
        } else {
          date = new Date(year, month, dayOffset);
        }
        date.setHours(0, 0, 0, 0);
        const button = document.createElement("button");
        button.type = "button";
        button.className = "rwm-calendar-day";
        button.textContent = date.getDate();
        button.dataset.value = toISO(date);
        if (outside) button.classList.add("is-outside");
        if (date < today) {
          button.disabled = true;
          button.classList.add("is-disabled");
        }
        if (toISO(date) === toISO(today)) button.classList.add("is-today");
        if (button.dataset.value === input.value) button.classList.add("is-selected");
        button.addEventListener("click", () => {
          input.value = button.dataset.value;
          input.dispatchEvent(new Event("change", { bubbles: true }));
          closePicker();
        });
        days.appendChild(button);
      }
    };

    const openPicker = () => {
      if (activePicker && activePicker.picker !== picker) closePicker();
      const current = parseDate(input.value);
      viewDate = current ? new Date(current.getFullYear(), current.getMonth(), 1) : new Date(today.getFullYear(), today.getMonth(), 1);
      render();
      picker.hidden = false;
      shell.classList.add("is-calendar-open");
      trigger.setAttribute("aria-expanded", "true");
      activePicker = { picker, shell, trigger };
    };

    trigger.addEventListener("click", (event) => {
      event.stopPropagation();
      if (!picker.hidden) closePicker(); else openPicker();
    });
    input.addEventListener("click", (event) => {
      event.stopPropagation();
      openPicker();
    });
    picker.addEventListener("click", (event) => event.stopPropagation());
    picker.querySelector("[data-calendar-prev]").addEventListener("click", () => { viewDate.setMonth(viewDate.getMonth() - 1); render(); });
    picker.querySelector("[data-calendar-next]").addEventListener("click", () => { viewDate.setMonth(viewDate.getMonth() + 1); render(); });
    picker.querySelector("[data-calendar-today]").addEventListener("click", () => {
      input.value = toISO(today);
      input.dispatchEvent(new Event("change", { bubbles: true }));
      closePicker();
    });
    picker.querySelector("[data-calendar-clear]").addEventListener("click", () => {
      input.value = "";
      input.dispatchEvent(new Event("change", { bubbles: true }));
      closePicker();
    });
  });

  document.addEventListener("click", closePicker);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closePicker();
  });
})();
