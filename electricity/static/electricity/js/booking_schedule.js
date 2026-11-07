(() => {
    const input = document.querySelector('input[name="preferred_time"]');
    if (!input || input.closest('.booking-time-shell')) return;
    const lang = document.documentElement.lang || 'en';
    const labels = lang.startsWith('ar')
        ? { time: 'اختيار الوقت', hour: 'الساعة', minute: 'الدقيقة', apply: 'تأكيد', clear: 'مسح' }
        : lang.startsWith('sv')
            ? { time: 'Välj tid', hour: 'Timme', minute: 'Minut', apply: 'Välj', clear: 'Rensa' }
            : { time: 'Choose time', hour: 'Hour', minute: 'Minute', apply: 'Apply', clear: 'Clear' };
    const shell = document.createElement('div');
    shell.className = 'booking-time-shell';
    input.before(shell);
    shell.append(input);
    input.type = 'text';
    input.readOnly = true;
    input.placeholder = 'HH:MM';
    input.setAttribute('aria-haspopup', 'dialog');
    input.setAttribute('aria-expanded', 'false');
    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'site-date-trigger';
    trigger.setAttribute('aria-label', labels.time);
    trigger.innerHTML = '<svg class="site-date-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/></svg>';
    shell.append(trigger);
    const picker = document.createElement('div');
    picker.className = 'booking-time-picker';
    picker.hidden = true;
    picker.setAttribute('role', 'dialog');
    picker.setAttribute('aria-label', labels.time);
    picker.innerHTML = `<strong>${labels.time}</strong><div class="booking-time-columns"></div><div class="booking-time-actions"><button type="button" data-clear>${labels.clear}</button><button type="button" data-apply>${labels.apply}</button></div>`;
    shell.append(picker);
    let hour = '09', minute = '00';
    const columns = picker.querySelector('.booking-time-columns');
    for (const [kind, count] of [['hour', 24], ['minute', 60]]) {
        const column = document.createElement('div');
        const heading = document.createElement('div');
        heading.textContent = labels[kind];
        column.append(heading);
        const list = document.createElement('div');
        list.className = 'booking-time-list';
        list.setAttribute('role', 'group');
        list.setAttribute('aria-label', labels[kind]);
        for (let i = 0; i < count; i++) {
            const value = String(i).padStart(2, '0');
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = value;
            button.dataset.kind = kind;
            button.dataset.value = value;
            button.addEventListener('click', () => {
                if (kind === 'hour') hour = value;
                else minute = value;
                sync();
            });
            list.append(button);
        }
        column.append(list);
        columns.append(column);
    }
    function sync() {
        picker.querySelectorAll('[data-kind]').forEach(button => {
            const selected = button.dataset.value === (button.dataset.kind === 'hour' ? hour : minute);
            button.classList.toggle('is-selected', selected);
            button.setAttribute('aria-pressed', String(selected));
        });
    }
    const close = (restoreFocus = false) => {
        picker.hidden = true;
        shell.classList.remove('is-open');
        input.setAttribute('aria-expanded', 'false');
        if (restoreFocus) trigger.focus();
    };
    const open = () => {
        document.dispatchEvent(new Event('click'));
        [hour, minute] = /^\d{2}:\d{2}$/.test(input.value) ? input.value.split(':') : ['09', '00'];
        sync();
        picker.hidden = false;
        shell.classList.add('is-open');
        input.setAttribute('aria-expanded', 'true');
        picker.querySelectorAll('.is-selected').forEach(button => button.parentElement.scrollTop = button.offsetTop - button.parentElement.offsetTop - 60);
        picker.querySelector('.is-selected').focus({ preventScroll: true });
    };
    input.addEventListener('click', open);
    trigger.addEventListener('click', () => picker.hidden ? open() : close());
    input.addEventListener('keydown', event => {
        if (['Enter', ' ', 'ArrowDown'].includes(event.key)) { event.preventDefault(); open(); }
    });
    const commit = value => {
        input.value = value;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        close(true);
    };
    picker.querySelector('[data-apply]').addEventListener('click', () => commit(`${hour}:${minute}`));
    picker.querySelector('[data-clear]').addEventListener('click', () => commit(''));
    document.addEventListener('click', event => { if (!shell.contains(event.target)) close(); });
    document.addEventListener('pointerdown', event => { if (!shell.contains(event.target)) close(); }, true);
    shell.addEventListener('keydown', event => { if (event.key === 'Escape') { event.stopPropagation(); close(true); } });
    shell.addEventListener('focusout', event => { if (!shell.contains(event.relatedTarget)) close(); });
})();
