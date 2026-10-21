(() => {
  const inputs = [...document.querySelectorAll('input[type="date"]')]
    .filter((input) => !input.closest('.date-input-shell') && !input.dataset.nativeDate);
  if (!inputs.length) return;

  const locale = document.documentElement.lang || 'en';
  const labels = locale.startsWith('ar')
    ? { today: 'اليوم', clear: 'مسح', previous: 'الشهر السابق', next: 'الشهر التالي' }
    : locale.startsWith('sv')
      ? { today: 'Idag', clear: 'Rensa', previous: 'Föregående månad', next: 'Nästa månad' }
      : { today: 'Today', clear: 'Clear', previous: 'Previous month', next: 'Next month' };
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  let active = null;

  const iso = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  const parse = (value) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return null;
    const [year, month, day] = value.split('-').map(Number);
    const date = new Date(year, month - 1, day);
    return Number.isNaN(date.getTime()) ? null : date;
  };
  const close = () => {
    if (!active) return;
    active.picker.hidden = true;
    active.shell.classList.remove('is-calendar-open');
    active = null;
  };

  inputs.forEach((input) => {
    const shell = document.createElement('div');
    shell.className = 'site-date-shell';
    input.parentNode.insertBefore(shell, input);
    shell.appendChild(input);
    input.type = 'text';
    input.readOnly = true;
    input.inputMode = 'none';
    input.autocomplete = 'off';
    input.setAttribute('aria-haspopup', 'dialog');

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'site-date-trigger';
    trigger.setAttribute('aria-label', labels.today);
    trigger.innerHTML = '<svg class="site-date-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M7 3v3M17 3v3M4.5 9h15M6 5h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z"/><path d="M8 13h2M14 13h2M8 17h2M14 17h2"/></svg>';
    shell.appendChild(trigger);

    const picker = document.createElement('div');
    picker.className = 'rwm-calendar';
    picker.hidden = true;
    picker.setAttribute('role', 'dialog');
    picker.innerHTML = `<div class="rwm-calendar-head"><button type="button" class="rwm-calendar-nav" data-prev aria-label="${labels.previous}">‹</button><strong class="rwm-calendar-month"></strong><button type="button" class="rwm-calendar-nav" data-next aria-label="${labels.next}">›</button></div><div class="rwm-calendar-weekdays"></div><div class="rwm-calendar-days"></div><div class="rwm-calendar-footer"><button type="button" data-clear>${labels.clear}</button><button type="button" data-today>${labels.today}</button></div>`;
    shell.appendChild(picker);

    const monthLabel = picker.querySelector('.rwm-calendar-month');
    const weekdays = picker.querySelector('.rwm-calendar-weekdays');
    const days = picker.querySelector('.rwm-calendar-days');
    let view = parse(input.value) || new Date(today);
    view = new Date(view.getFullYear(), view.getMonth(), 1);
    const sunday = new Date(2024, 0, 7);
    const weekdayFormat = new Intl.DateTimeFormat(locale, { weekday: 'short' });
    weekdays.innerHTML = Array.from({ length: 7 }, (_, index) => {
      const day = new Date(sunday);
      day.setDate(sunday.getDate() + index);
      return `<span>${weekdayFormat.format(day).replace('.', '')}</span>`;
    }).join('');

    const render = () => {
      monthLabel.textContent = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(view);
      days.innerHTML = '';
      const year = view.getFullYear();
      const month = view.getMonth();
      const first = new Date(year, month, 1).getDay();
      const length = new Date(year, month + 1, 0).getDate();
      const previousLength = new Date(year, month, 0).getDate();
      for (let cell = 0; cell < 42; cell += 1) {
        const offset = cell - first + 1;
        const outside = offset < 1 || offset > length;
        const date = offset < 1
          ? new Date(year, month - 1, previousLength + offset)
          : offset > length ? new Date(year, month + 1, offset - length) : new Date(year, month, offset);
        date.setHours(0, 0, 0, 0);
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'rwm-calendar-day';
        button.textContent = date.getDate();
        if (outside) button.classList.add('is-outside');
        if (iso(date) === iso(today)) button.classList.add('is-today');
        if (iso(date) === input.value) button.classList.add('is-selected');
        button.addEventListener('click', () => {
          input.value = iso(date);
          input.dispatchEvent(new Event('change', { bubbles: true }));
          close();
        });
        days.appendChild(button);
      }
    };
    const open = () => {
      if (active && active.picker !== picker) close();
      const selected = parse(input.value);
      view = selected ? new Date(selected.getFullYear(), selected.getMonth(), 1) : new Date(today.getFullYear(), today.getMonth(), 1);
      render();
      picker.hidden = false;
      shell.classList.add('is-calendar-open');
      active = { picker, shell };
    };

    input.addEventListener('click', (event) => { event.stopPropagation(); open(); });
    trigger.addEventListener('click', (event) => { event.stopPropagation(); picker.hidden ? open() : close(); });
    picker.addEventListener('click', (event) => event.stopPropagation());
    picker.querySelector('[data-prev]').addEventListener('click', () => { view.setMonth(view.getMonth() - 1); render(); });
    picker.querySelector('[data-next]').addEventListener('click', () => { view.setMonth(view.getMonth() + 1); render(); });
    picker.querySelector('[data-today]').addEventListener('click', () => { input.value = iso(today); input.dispatchEvent(new Event('change', { bubbles: true })); close(); });
    picker.querySelector('[data-clear]').addEventListener('click', () => { input.value = ''; input.dispatchEvent(new Event('change', { bubbles: true })); close(); });
  });

  document.addEventListener('click', close);
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') close(); });
})();
